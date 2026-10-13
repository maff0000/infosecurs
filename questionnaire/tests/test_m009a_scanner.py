"""
M009A malware-scanning abstraction tests
(WO-M009A-SECURE-INGESTION-XLSX.md "Malware scanning - fail-closed",
Final Correction B).

`TestRealClamdBackend` requires a real `clamd` reachable at
`CLAMAV_HOST`/`CLAMAV_PORT` (the `clamav` Compose service - see
docker-compose.yml) and is skipped automatically if unset, so this file
still collects cleanly in an environment with no scanner configured.
"""
import os
import tempfile

import pytest

from questionnaire import scanner as scanner_module
from questionnaire.eval import m009a_ingestion_corpus as corpus

EICAR = (
    b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
)

requires_real_clamav = pytest.mark.skipif(
    not os.environ.get("CLAMAV_HOST"), reason="CLAMAV_HOST not configured - no real clamd reachable"
)


class TestUnavailableScanner:
    def test_always_returns_unavailable_never_clean(self):
        scanner = scanner_module.UnavailableScanner()
        with tempfile.NamedTemporaryFile() as fh:
            fh.write(b"anything")
            fh.flush()
            result = scanner.scan_file(fh.name)
        assert result.state == scanner_module.STATE_UNAVAILABLE

    def test_ping_is_false(self):
        assert scanner_module.UnavailableScanner().ping() is False


class TestGetScannerFailsClosedOnAbsence:
    def test_no_clamav_host_returns_unavailable_stub(self, monkeypatch):
        monkeypatch.delenv("CLAMAV_HOST", raising=False)
        scanner = scanner_module.get_scanner()
        assert isinstance(scanner, scanner_module.UnavailableScanner)


class TestClamdScannerConnectionFailure:
    def test_unreachable_host_returns_unavailable_not_exception(self):
        """A scanner that cannot be reached at all must fail closed as
        UNAVAILABLE, never raise out to the caller and never CLEAN."""
        scanner = scanner_module.ClamdScanner("127.0.0.1", 1, timeout_seconds=1)
        with tempfile.NamedTemporaryFile() as fh:
            fh.write(b"x")
            fh.flush()
            result = scanner.scan_file(fh.name)
        assert result.state == scanner_module.STATE_UNAVAILABLE


@requires_real_clamav
class TestRealClamdBackend:
    """WO-M009A: 'At least one real ClamAV-backed acceptance test must
    demonstrate: a legitimate XLSX receives CLEAN; a standard safe
    anti-malware test specimen (e.g. the EICAR test file) is detected
    rather than allowed through.'"""

    def _scanner(self):
        return scanner_module.ClamdScanner(
            os.environ["CLAMAV_HOST"], int(os.environ.get("CLAMAV_PORT", "3310")), timeout_seconds=30
        )

    def test_ping(self):
        assert self._scanner().ping() is True

    def test_legitimate_xlsx_is_clean(self):
        with tempfile.NamedTemporaryFile(suffix=".xlsx") as fh:
            fh.write(corpus.valid_multi_sheet_workbook())
            fh.flush()
            result = self._scanner().scan_file(fh.name)
        assert result.state == scanner_module.STATE_CLEAN, result.provenance

    def test_eicar_test_file_is_detected(self):
        with tempfile.NamedTemporaryFile() as fh:
            fh.write(EICAR)
            fh.flush()
            result = self._scanner().scan_file(fh.name)
        assert result.state == scanner_module.STATE_INFECTED, result.provenance
        assert result.infected_signature
