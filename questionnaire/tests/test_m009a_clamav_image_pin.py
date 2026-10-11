"""
M009A ClamAV image pin drift guard (Central Architecture Blocker 3
correction to PR #102, 2026-10-11).

WO-M009A-SECURE-INGESTION-XLSX.md's "Scanner deployment shape - frozen"
(Final Correction B) requires the SAME frozen scanner topology in both the
normal development Compose architecture (`docker-compose.yml`) and the
standalone release Compose architecture (`docker-compose.release.yml`) -
"a release artifact in which Customer Assurance upload always fails
because no scanner exists is not M009A GREEN." That requirement is only
as good as the two files never silently diverging on WHICH exact image
they each pin. This is a plain regex-based check deliberately - no YAML
parser dependency is added merely for this guard; both files' `clamav`
service blocks are simple, single-line `image:` declarations.
"""
import re

import pytest

from config.settings import BASE_DIR

# Matches e.g. "clamav/clamav:1.4.4@sha256:<64 hex chars>" - the exact,
# immutable, never-a-floating-tag reference this Work Order's own
# "Scanner deployment shape - frozen" section requires.
_CLAMAV_IMAGE_PATTERN = re.compile(r"clamav/clamav:[^\s@]+@sha256:[0-9a-f]{64}")


def _find_pinned_clamav_image(compose_filename):
    path = BASE_DIR / compose_filename
    text = path.read_text()
    matches = _CLAMAV_IMAGE_PATTERN.findall(text)
    assert matches, (
        f"{compose_filename} does not declare a digest-pinned clamav/clamav "
        "image reference (image: clamav/clamav:<tag>@sha256:<digest>) - "
        "WO-M009A Final Correction B requires an exact immutable digest, "
        "never a floating tag."
    )
    assert len(set(matches)) == 1, (
        f"{compose_filename} declares more than one DIFFERING clamav/clamav "
        f"image reference in the same file: {sorted(set(matches))!r}"
    )
    return matches[0]


class TestClamavImagePinDriftGuard:
    """Proves `docker-compose.yml` and `docker-compose.release.yml` can
    never silently diverge on which exact ClamAV image they each pin -
    the two topologies must always agree, byte-for-byte, on the tag AND
    the resolved immutable digest."""

    def test_dev_and_release_compose_pin_the_identical_clamav_image(self):
        dev_image = _find_pinned_clamav_image("docker-compose.yml")
        release_image = _find_pinned_clamav_image("docker-compose.release.yml")
        assert dev_image == release_image, (
            "docker-compose.yml and docker-compose.release.yml have diverged "
            f"on the pinned clamav/clamav image: dev={dev_image!r} vs "
            f"release={release_image!r}. WO-M009A Final Correction B requires "
            "the identical frozen scanner topology in both - this must never "
            "be allowed to drift silently."
        )

    @pytest.mark.parametrize("compose_filename", ["docker-compose.yml", "docker-compose.release.yml"])
    def test_pinned_clamav_image_is_never_a_floating_tag(self, compose_filename):
        image = _find_pinned_clamav_image(compose_filename)
        assert "@sha256:" in image, (
            f"{compose_filename}'s clamav image {image!r} is not pinned by an "
            "immutable digest."
        )
        assert "latest" not in image and "stable" not in image
