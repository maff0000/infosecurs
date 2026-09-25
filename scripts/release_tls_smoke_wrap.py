#!/usr/bin/env python
"""
Bounded, single-hop TLS test wrapper for the M006 release-image real-browser
smoke (PID §15/§18.35; Central Architecture Round 6 authorisation §F).

WHY THIS EXISTS
----------------
The release-artifact proof genuinely runs with DJANGO_ENV=production, so
config/settings.py's `SECURE_SSL_REDIRECT = True` is genuinely active (PID
§15/§F requires this - "Do not casually remove SECURE_SSL_REDIRECT merely to
simplify testing"). With no `SECURE_PROXY_SSL_HEADER` configured anywhere in
this codebase (a deliberate, documented, still-open production-readiness
gap - see the comment above `SECURE_SSL_REDIRECT` in config/settings.py and
docs/evidence/M006-ROUND4-PRODCONFIG-HEALTH.md §3), a real browser making a
plain-HTTP request straight to the release container's normal port gets one
real 301 redirect to an `https://` URL - and nothing serves HTTPS there, so
the browser simply fails to load the page. A TLS-terminating PROXY placed in
front does not fix this and in fact reproduces the exact infinite-redirect
loop Round 4 already found: the proxy decrypts and forwards PLAIN HTTP to
Django every time, so Django never sees the request as secure and redirects
again, forever.

This script is not that. It is not a proxy and it adds no second network
hop. It runs INSIDE the same running release container, as an *additional*
disposable process (started only for the smoke-test window, alongside the
container's normal `runserver` process - see docker-compose.release.yml's
reserved 8443 port), and terminates a real, self-signed TLS connection
directly against Django's own WSGI application object in the exact same
Python process/interpreter - the same single hop a real
SECURE_PROXY_SSL_HEADER-trusting reverse proxy would eventually replace,
minus the header-trust question that a real deployment topology decision
would still have to answer safely (PID §25 - explicitly not this dispatch's
call to make). Because the TLS handshake is genuinely terminated in-process
here, `environ["wsgi.url_scheme"] = "https"` below is not spoofing anything
un-verified - it is reporting the literal, true state of the actual socket
this same process just accepted, exactly what a native builtin
Django-terminated-TLS server would compute itself if Django's own
`runserver` supported TLS directly (it does not, without pulling in a new
dependency/server this round is not authorised to add - PID §15 "do not
introduce a new production web-server architecture").

No product source file is touched to make this work. `config/settings.py`
is used completely unmodified - SECURE_SSL_REDIRECT, SESSION_COOKIE_SECURE,
CSRF_COOKIE_SECURE etc. all evaluate for real, genuinely, because the
request the app sees genuinely arrived over TLS.

USAGE
-----
Run inside the release container (a real file in the image - it is
committed source, `COPY . .` puts it at /app/scripts/... like everything
else; nothing here depends on a bind mount):

    docker compose -p <project> --env-file .env.release \\
      -f docker-compose.release.yml exec -d \\
      -e SMOKE_TLS_CERTFILE=/tmp/smoke-cert.pem \\
      -e SMOKE_TLS_KEYFILE=/tmp/smoke-key.pem \\
      web python scripts/release_tls_smoke_wrap.py

(`-d` backgrounds it inside the container; `docker cp` the self-signed
cert/key pair in first - see docs/evidence/M006-RELEASE.md for the exact
`openssl req -x509 ...` invocation used, generated and discarded entirely
outside the repository, same pattern Round 4 already established for its
own throwaway TLS reproduction.) Point Playwright/Chromium at
`https://127.0.0.1:<WEB_TLS_HOST_PORT>/...` with `ignore_https_errors=True`
(the cert is self-signed and test-only - never a real certificate, never
presented to a real client).

This process is never started by the image's own CMD/default command, never
referenced by docker-compose.yml (the normal dev stack), and is torn down
with the rest of the disposable release stack (`docker compose ... down -v`)
at the end of the smoke-test window - it is a test-harness tool, not a
shipped runtime component.
"""
import os
import ssl
import sys

sys.path.insert(0, "/app")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from config.wsgi import application as django_application  # noqa: E402
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server  # noqa: E402


def _https_terminated_app(environ, start_response):
    """
    This process only ever receives connections that arrived over the real
    TLS socket wrapped in main() below - there is no second hop and no
    untrusted header being trusted here. Setting wsgi.url_scheme is
    reporting what already, genuinely happened at the socket layer this
    same process just terminated, which is exactly what request.is_secure()
    reads when (as here, unmodified) SECURE_PROXY_SSL_HEADER is unset.
    """
    environ["wsgi.url_scheme"] = "https"
    return django_application(environ, start_response)


class _ReusableWSGIServer(WSGIServer):
    allow_reuse_address = True


def main():
    host = os.environ.get("SMOKE_TLS_HOST", "0.0.0.0")
    port = int(os.environ.get("SMOKE_TLS_PORT", "8443"))
    certfile = os.environ["SMOKE_TLS_CERTFILE"]
    keyfile = os.environ["SMOKE_TLS_KEYFILE"]

    httpd = make_server(
        host,
        port,
        _https_terminated_app,
        server_class=_ReusableWSGIServer,
        handler_class=WSGIRequestHandler,
    )
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    # CodeQL py/insecure-protocol: PROTOCOL_TLS_SERVER alone permits
    # negotiating down to TLSv1/TLSv1.1 (CWE-327). This wrapper exists to
    # prove production-equivalent TLS behaviour for the release-image
    # smoke (see module docstring) - it should refuse anything a real
    # deployment would, not merely "some TLS".
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(certfile=certfile, keyfile=keyfile)
    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)

    print(
        f"release_tls_smoke_wrap: serving https://{host}:{port}/ "
        "(self-signed, single-hop, test-only - see module docstring)",
        flush=True,
    )
    httpd.serve_forever()


if __name__ == "__main__":
    main()
