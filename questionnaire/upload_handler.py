"""
M009A streaming upload-size guard (WO-M009A-SECURE-INGESTION-XLSX.md,
"Upload size limit is streaming, not post-hoc", Final Correction G).

The frozen rule: the 10 MiB upload limit must be enforced WHILE consuming
the uploaded stream, never after the fact - no unbounded `.read()`, no
loading the whole upload into memory first, no copying unlimited bytes
into questionnaire storage and only checking the size afterwards. SHA-256
and the byte count must be computed during the SAME bounded streaming pass
used to persist/quarantine the file.

How Django's own upload/temp-file behaviour interacts with this (recorded
here per the Work Order's own instruction to document this interaction in
the M009A evidence - see also docs/evidence/M009A-SECURE-INGESTION-XLSX.md):

Django's `MultiPartParser` calls `receive_data_chunk(chunk, offset)` on
EVERY handler in `request.upload_handlers`, IN ORDER, for every chunk of
every uploaded file field, as the multipart body streams in off the wire -
this runs BEFORE `request.POST`/`request.FILES` is ever populated, and
therefore before any view code (or `EvidenceFileUploadForm`-style form
validation) has had a chance to inspect anything. A handler that returns
the chunk unchanged is a transparent observer: Django's default handler
chain (`MemoryFileUploadHandler` then `TemporaryFileUploadHandler`,
Django's own documented default `FILE_UPLOAD_HANDLERS`) still receives and
stores the chunk completely normally afterwards - this handler changes
nothing about how the upload is ultimately materialised as an
`UploadedFile`, it only OBSERVES every chunk as it arrives and can abort
the whole upload the moment the running total crosses the limit, via
Django's own `StopUpload` exception (its documented mechanism for exactly
this: "the client will be told the upload was interrupted" -
`connection_reset=True` tells Django to stop reading the request body and
close/reset the connection outright, rather than continuing to read and
discard the remainder - the ONLY way to make this a genuine mid-stream
abort rather than "read everything anyway, then reject").

Because this handler is installed as the FIRST handler and computes the
running SHA-256 and byte count in the very same `receive_data_chunk` call
that performs the size check, "compute the hash/size during the SAME
bounded streaming pass used to persist the file" and "abort mid-stream
once the limit is exceeded" are the same method call, not two separate
passes - there is no window where this handler has already accepted bytes
beyond the limit before the size check runs.

This handler is deliberately a pure OBSERVER, not a storage handler: it
never writes bytes to disk itself (that stays `questionnaire.
import_storage.store_and_hash_uploaded_file`'s job, reusing
`evidence.storage`'s own proven opaque-filename/permissions pattern) - it
only ever (a) raises `StopUpload` early, or (b) exposes the already-
computed sha256/byte-count/zip-signature-sniff to the view once the
default handler chain has finished materialising the real `UploadedFile`.

**Why this is installed by a MIDDLEWARE (`QuestionnaireUploadSizeGuard
Middleware`, below), never by the view itself** - a genuine finding from
this dispatch's own real-browser acceptance testing, not merely reasoned
about: an earlier version of this module installed the guard at the TOP
of the upload view, before constructing the form. That passed every
Django-test-Client-based test (`django.test.Client` does not enforce CSRF
by default), but FAILED a real-Chromium acceptance run - the browser was
bounced to the login page immediately after a genuine multipart POST.
Root cause: `django.middleware.csrf.CsrfViewMiddleware` reads
`request.POST` (to find the `csrfmiddlewaretoken` field) during its own
`process_view` hook, which Django calls BEFORE the view function runs -
and reading `request.POST` triggers Django's lazy multipart-body parse
using WHATEVER `request.upload_handlers` the request already had at that
moment (the project-wide default). By the time the view itself tried to
install this guard, the body had already been fully parsed once, using
the default handlers - installing a new list of handlers at that point
has no effect on bytes already consumed, and Django caches the parsed
`request.POST`/`request.FILES` so a later access never re-parses. The fix
is the well-known Django pattern for this exact situation: a dedicated
middleware, placed BEFORE `CsrfViewMiddleware` in `MIDDLEWARE`
(`config/settings.py`), narrowly scoped to exactly this one upload
endpoint's path - it runs strictly earlier in the request pipeline than
any `process_view` hook, including CSRF's, so the guard handler is
already installed before anything anywhere touches `request.POST`.
"""
from __future__ import annotations

import hashlib

from django.core.exceptions import ImproperlyConfigured
from django.core.files.uploadhandler import FileUploadHandler, StopUpload
from django.shortcuts import render

from questionnaire.decorators import REQUIRES_ASSURANCE_READINESS_ATTR
from security_baseline.readiness import evaluate_assurance_readiness

# WO-M009A Correction 8 - frozen for M009A-v1, not an implementation choice.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MiB

# OOXML (and any ZIP) container signatures - a local file header, an empty
# archive, or a spanned archive. Sniffed here (not a parse - just the first
# few raw bytes of the stream) so `questionnaire.import_services` can
# immediately, deterministically reject anything that is not even
# ZIP-shaped (e.g. a JPEG or plain text file renamed with a `.xlsx`
# extension - WO-M009A evaluation corpus) without running the heavier
# OOXML container gate at all.
ZIP_SIGNATURES = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")
_SIGNATURE_SNIFF_LENGTH = 4


class QuestionnaireUploadSizeGuardHandler(FileUploadHandler):
    """First handler in `request.upload_handlers` for the M009A upload
    views. Observes every chunk of the uploaded file field as it streams
    in, aborting the request the instant the running total exceeds
    `MAX_UPLOAD_BYTES`, and incrementally computing SHA-256 + a bounded
    ZIP-signature sniff in that same pass - exposed afterwards via
    `self.total_bytes` / `self.sha256_hex` / `self.is_zip_shaped`.
    """

    def new_file(self, *args, **kwargs):
        super().new_file(*args, **kwargs)
        self.total_bytes = 0
        self._hasher = hashlib.sha256()
        self._head = b""
        self.is_zip_shaped = False

    def receive_data_chunk(self, raw_data, start):
        self.total_bytes += len(raw_data)
        if self.total_bytes > MAX_UPLOAD_BYTES:
            # Genuine mid-stream abort (Final Correction G) - never "keep
            # reading, reject later". connection_reset=True per Django's
            # own documented StopUpload contract: stop reading the request
            # body and reset the connection, rather than draining the rest
            # of an attacker-controlled, possibly much larger body first.
            raise StopUpload(connection_reset=True)

        self._hasher.update(raw_data)
        if len(self._head) < _SIGNATURE_SNIFF_LENGTH:
            self._head += raw_data[: _SIGNATURE_SNIFF_LENGTH - len(self._head)]
            if len(self._head) >= _SIGNATURE_SNIFF_LENGTH:
                self.is_zip_shaped = self._head.startswith(ZIP_SIGNATURES)

        # Pass the chunk through unchanged - this handler never stores
        # anything itself; the next handler in the chain (Django's own
        # default Memory/TemporaryFileUploadHandler) still does the real
        # work of materialising the UploadedFile exactly as it would have
        # without this handler installed.
        return raw_data

    def file_complete(self, file_size):
        # Zero-byte upload never reached the >=4-byte sniff window above.
        self.sha256_hex = self._hasher.hexdigest()
        # Defer to the next handler in the chain for the actual
        # UploadedFile object - this handler is an observer only.
        return None


def install_upload_size_guard(request):
    """
    Installs `QuestionnaireUploadSizeGuardHandler` as the FIRST upload
    handler on `request`. Idempotent - a no-op if already installed (the
    middleware below already calls this for every matching request; this
    remains available/safe to call again, e.g. from a test that bypasses
    the middleware). Returns the handler instance so the caller can read
    back `.total_bytes` / `.sha256_hex` / `.is_zip_shaped` once
    `request.FILES` has been resolved.
    """
    if request.upload_handlers and isinstance(
        request.upload_handlers[0], QuestionnaireUploadSizeGuardHandler
    ):
        return request.upload_handlers[0]
    guard = QuestionnaireUploadSizeGuardHandler(request)
    request.upload_handlers = [guard] + list(request.upload_handlers)
    return guard


# The one real upload endpoint this guard protects (WO-M009A frozen upload
# limit) - matched by path suffix, never by `request.resolver_match`
# (URL resolution has not happened yet at the point this middleware must
# run - see the module docstring's "why middleware" section). A plain
# string suffix match is sufficient and unambiguous: this is the only
# route in this codebase ending in this exact path shape.
GUARDED_UPLOAD_PATH_SUFFIX = "/questionnaire/imports/upload/"


class QuestionnaireUploadSizeGuardMiddleware:
    """
    Installs `QuestionnaireUploadSizeGuardHandler` on every POST request
    whose path is the M009A questionnaire-import upload endpoint, BEFORE
    calling `get_response` - i.e. before `CsrfViewMiddleware`'s own
    `process_view` hook (and therefore before anything else in the
    pipeline) ever has a chance to trigger the lazy multipart-body parse
    by reading `request.POST`. Must be placed BEFORE
    `django.middleware.csrf.CsrfViewMiddleware` in `MIDDLEWARE` - see
    `config/settings.py` and this module's own docstring for the full
    real-browser-reproduced reasoning.

    Deliberately narrow: only installs anything for this one path and
    only for POST (a GET to the same URL has no body to guard). Every
    other request in this codebase is completely unaffected - this
    middleware is a no-op for them, not merely "harmless", it does not
    even construct a handler instance.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "POST" and request.path.endswith(GUARDED_UPLOAD_PATH_SUFFIX):
            install_upload_size_guard(request)
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        """
        M009B Increment 1 (WO-M009B-FOUNDATIONS-READINESS-CSV-BULK-
        ORCHESTRATION.md §2.2/§2.6) - the Assurance Readiness Gate's
        pipeline-level enforcement point. Added onto this SAME middleware
        (rather than a new one) specifically because this class already
        sits BEFORE `CsrfViewMiddleware` in `MIDDLEWARE` (see this
        module's own docstring above) - `process_view` hooks fire in
        `MIDDLEWARE` list order, so this hook is guaranteed to run before
        `CsrfViewMiddleware.process_view` for exactly the same reason the
        upload-size guard already is.

        A no-op for any view not marked with `questionnaire.decorators.
        requires_assurance_readiness` - returns `None` immediately, so
        every other route in this codebase (including every XLSX-era
        M009A route this Work Order does not touch) is completely
        unaffected.

        Ordering, load-bearing (WO §2.6/§2.9 - a binding STOP condition
        if violated): tenant MEMBERSHIP is checked FIRST, before
        readiness is ever evaluated or any readiness-derived information
        is returned. A non-member must never be able to distinguish
        "exists, not ready" from "I'm not a member" from "doesn't exist"
        by response shape - exactly the enumeration this codebase's
        existing 404-never-403 convention
        (`organisations.views.get_member_organisation_or_404`) exists to
        prevent.

        Unauthenticated requests are deliberately passed through
        untouched (`return None`) - this hook adds nothing for them.
        Every marked view in this codebase is also `@login_required`
        (an ordinary view decorator, so it only runs once the view is
        finally called, AFTER this hook returns). If this hook instead
        evaluated membership for an anonymous caller,
        `get_member_organisation_or_404` would legitimately find no
        membership row for `AnonymousUser` and return a 404 - REGRESSING
        the existing, correct behaviour of redirecting an unauthenticated
        visitor to the login page instead. Returning `None` here defers
        entirely to the existing, unmodified `@login_required`/CSRF
        pipeline for every caller this hook does not yet recognise as
        authenticated.

        The guarantee this hook actually provides, stated precisely (WO
        §2.6's own required documentation correction - also a binding
        global STOP condition if overclaimed): it prevents Django's own
        lazy multipart parsing from ever running (so `request.POST`/
        `request.FILES` are never populated) and prevents any
        application-level write, storage, or scanning from ever happening
        for an unready organisation's request, by returning a complete
        response BEFORE `CsrfViewMiddleware.process_view` (and therefore
        before anything else in the pipeline) ever has a chance to read
        `request.POST`. It does NOT, and cannot, guarantee that the
        underlying WSGI server has not already read/buffered raw request
        bytes off the socket before Django's own middleware chain runs at
        all - that boundary is owned by the web server, never by Django
        middleware, and this hook makes no claim about it.
        """
        if not getattr(view_func, REQUIRES_ASSURANCE_READINESS_ATTR, False):
            return None

        if not request.user.is_authenticated:
            return None

        organisation_id = view_kwargs.get("organisation_id")
        if organisation_id is None:
            raise ImproperlyConfigured(
                f"requires_assurance_readiness was applied to {view_func.__module__}."
                f"{getattr(view_func, '__qualname__', view_func)!r}, whose URL does not "
                "carry an organisation_id - this hook only guards organisation-scoped "
                "routes."
            )

        # Tenant membership FIRST (WO §2.6) - deferred import, the same
        # circular-import avoidance `entitlements.decorators.
        # require_capability` already uses (see that module's own
        # docstring: `organisations.views` imports `entitlements.
        # decorators`, so a top-level import back here would cycle).
        from organisations.views import get_member_organisation_or_404

        organisation = get_member_organisation_or_404(request.user, organisation_id)

        readiness = evaluate_assurance_readiness(organisation)
        if readiness.is_ready:
            return None

        return render(
            request,
            "questionnaire/import_assurance_not_ready.html",
            {
                "organisation": organisation,
                "completion": readiness.completion,
                "blockers": readiness.blockers,
            },
        )
