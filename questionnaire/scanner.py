"""
M009A malware-scanning abstraction (WO-M009A-SECURE-INGESTION-XLSX.md
"Malware scanning - fail-closed" (Correction 6), "Scanner deployment shape
- frozen" (Final Correction B)).

Four explicit result states, never collapsed into a plain boolean:

    CLEAN        - only this result may advance the security gate to `passed`.
    INFECTED     - reject (terminal for these bytes - security_gate_rejected).
    UNAVAILABLE  - fail closed; do not parse/extract (security_gate_failed, retryable).
    ERROR        - fail closed; do not parse/extract (security_gate_failed, retryable).

`ClamdScanner` talks to ClamAV's `clamd` daemon using its documented
`INSTREAM` network protocol directly over a plain TCP socket - no cloud
malware scanning, no questionnaire bytes sent to any external SaaS/
provider (the frozen deployment shape: an internal Docker Compose service,
reachable only on the internal Compose network, never host-published -
see docker-compose.yml/docker-compose.release.yml's own `clamav` service).

Dependency decision (recorded here, and in docs/evidence/
M009A-SECURE-INGESTION-XLSX.md): `INSTREAM` is a small, fully documented,
length-prefixed-chunk protocol (ClamAV's own `clamdoc.pdf`/man page) - this
hand-rolled client implements exactly that documented protocol, bounded at
every step (a hard chunk size, a hard total-bytes cap matching this
Work Order's own 10 MiB upload limit, and a connect/read timeout), the
same "a small, well-understood protocol is exactly as reliable as a third-
party client library, without a new pinned/hash-locked/licence-reviewed
dependency" judgement call `evidence/storage.py`'s own module docstring
already makes for PDF/PNG/JPEG magic-byte sniffing (see that file's
"Dependency decision" paragraph) - not a shortcut to avoid review, a
documented, equally-reviewable alternative to one. WO-M009A explicitly
permits either approach ("If a small, maintained Python client dependency
is required... permitted... Do not write a bespoke UNSAFE network
protocol merely to preserve an artificial dependency rule" - the operative
word is UNSAFE; this client is bounded/timed-out/narrowly-scoped, not an
ad hoc unsafe protocol).
"""
from __future__ import annotations

import dataclasses
import socket
import struct

from config.env import optional_env

STATE_CLEAN = "CLEAN"
STATE_INFECTED = "INFECTED"
STATE_UNAVAILABLE = "UNAVAILABLE"
STATE_ERROR = "ERROR"

_CHUNK_SIZE = 64 * 1024
# Matches questionnaire.upload_handler.MAX_UPLOAD_BYTES / questionnaire.
# import_storage.MAX_UPLOAD_BYTES - the scanner is never asked to stream
# more than this Work Order's own frozen upload limit; a bounded cap here
# too, never trusting the on-disk file's claimed size alone.
_MAX_SCAN_BYTES = 10 * 1024 * 1024


@dataclasses.dataclass(frozen=True)
class ScanResult:
    """`provenance` NEVER contains file content (Correction 6/Final
    Correction B) - only backend name, engine/signature version where
    available, the raw clamd response line, and scan completion time (the
    caller, `questionnaire.import_services`, adds the timestamp)."""

    state: str
    provenance: dict
    infected_signature: str | None = None


class ClamdScanner:
    """A bounded, timed-out client for ClamAV's `clamd` `INSTREAM`
    protocol over plain TCP."""

    def __init__(self, host: str, port: int, *, timeout_seconds: float = 30.0):
        self.host = host
        self.port = port
        self.timeout_seconds = timeout_seconds

    def _connect(self) -> socket.socket:
        sock = socket.create_connection((self.host, self.port), timeout=self.timeout_seconds)
        sock.settimeout(self.timeout_seconds)
        return sock

    def ping(self) -> bool:
        """Health-check only (never used as part of a scan decision) -
        clamd's own `PING` -> `PONG` command."""
        try:
            with self._connect() as sock:
                sock.sendall(b"zPING\0")
                response = sock.recv(64)
            return response.strip(b"\0") == b"PONG"
        except OSError:
            return False

    def scan_file(self, file_path: str) -> ScanResult:
        """
        Streams `file_path`'s bytes to `clamd` via `INSTREAM`, bounded at
        `_CHUNK_SIZE` per chunk and `_MAX_SCAN_BYTES` total (defence in
        depth - the file was already proven <= the frozen 10 MiB upload
        limit before this is ever called). Never raises for an ordinary
        scanner-unavailable/scanner-error condition - those become
        `STATE_UNAVAILABLE`/`STATE_ERROR` results, per the fail-closed
        contract this whole module exists to implement.
        """
        try:
            with self._connect() as sock:
                sock.sendall(b"zINSTREAM\0")
                total_sent = 0
                with open(file_path, "rb") as fh:
                    while True:
                        chunk = fh.read(_CHUNK_SIZE)
                        if not chunk:
                            break
                        total_sent += len(chunk)
                        if total_sent > _MAX_SCAN_BYTES:
                            return ScanResult(
                                state=STATE_ERROR,
                                provenance={
                                    "backend": "clamd",
                                    "reason": "file exceeded the bounded scan byte cap",
                                },
                            )
                        sock.sendall(struct.pack("!L", len(chunk)))
                        sock.sendall(chunk)
                # Zero-length chunk terminates the stream (clamd protocol).
                sock.sendall(struct.pack("!L", 0))

                response = b""
                while not response.endswith(b"\0") and len(response) < 4096:
                    part = sock.recv(4096)
                    if not part:
                        break
                    response += part
        except (OSError, socket.timeout) as exc:
            return ScanResult(
                state=STATE_UNAVAILABLE,
                provenance={"backend": "clamd", "reason": f"connection/timeout error: {exc}"},
            )

        text = response.decode("utf-8", errors="replace").strip("\0").strip()
        provenance = {"backend": "clamd", "raw_response": text}

        if text.endswith("OK"):
            return ScanResult(state=STATE_CLEAN, provenance=provenance)
        if "FOUND" in text:
            # e.g. "stream: Win.Test.EICAR_HDB-1 FOUND"
            signature = text.split(":", 1)[-1].replace("FOUND", "").strip()
            return ScanResult(
                state=STATE_INFECTED, provenance=provenance, infected_signature=signature
            )
        if "ERROR" in text or not text:
            return ScanResult(state=STATE_ERROR, provenance=provenance)

        # Any other unrecognised response shape - fail closed as ERROR,
        # never guess that an unrecognised response means CLEAN.
        return ScanResult(state=STATE_ERROR, provenance=provenance)

    def version(self) -> str | None:
        try:
            with self._connect() as sock:
                sock.sendall(b"zVERSION\0")
                response = sock.recv(256)
            return response.decode("utf-8", errors="replace").strip("\0").strip() or None
        except OSError:
            return None


class UnavailableScanner:
    """
    An explicit "scanner unavailable" implementation (WO-M009A: "A
    development/runtime 'scanner unavailable' implementation may exist to
    make absence explicit... it must BLOCK upload processing, never allow
    it through"). Every call deterministically returns `STATE_UNAVAILABLE`
    - never `STATE_CLEAN`. Used only when `CLAMAV_HOST` is genuinely unset
    (see `get_scanner` below) - this is the withdrawn "stub that logs and
    passes" replaced with a stub that genuinely fails closed.
    """

    def ping(self) -> bool:
        return False

    def scan_file(self, file_path: str) -> ScanResult:
        return ScanResult(
            state=STATE_UNAVAILABLE,
            provenance={"backend": "unavailable_stub", "reason": "no scanner backend configured"},
        )


def get_scanner():
    """
    Resolved LAZILY, only when a security-gate-accepted artifact actually
    needs scanning - not at Django startup (same `require_env`/
    `optional_env` discipline as `evidence.storage.evidence_storage_root`/
    `questionnaire.import_storage.questionnaire_storage_root`). Returns an
    `UnavailableScanner` (never `None`, never a silent pass) if
    `CLAMAV_HOST` is unset - this is the explicit "absence is UNAVAILABLE,
    never CLEAN" contract, not an accidental crash path.
    """
    host = optional_env("CLAMAV_HOST", "")
    if not host:
        return UnavailableScanner()
    port = int(optional_env("CLAMAV_PORT", "3310"))
    timeout_seconds = float(optional_env("CLAMAV_TIMEOUT_SECONDS", "30"))
    return ClamdScanner(host, port, timeout_seconds=timeout_seconds)
