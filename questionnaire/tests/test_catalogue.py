"""
Shape/sanity tests for `questionnaire.catalogue` (M005 PID §10 -
m005-1-foundation dispatch).
"""
from ai_platform.policy_contracts import ALLOWED_SECTION_KEYS
from questionnaire.catalogue import CATALOGUE, CATALOGUE_BY_KEY, CATALOGUE_KEYS, CATALOGUE_VERSION
from security_baseline.catalogue import CATALOGUE as BASELINE_CATALOGUE


def test_catalogue_version_is_set():
    assert CATALOGUE_VERSION == "questionnaire-catalogue-v1"


def test_catalogue_has_twenty_nine_entries():
    assert len(CATALOGUE) == 29
    assert len(CATALOGUE_KEYS) == 29


def test_every_entry_has_key_and_description():
    for entry in CATALOGUE:
        assert entry["key"]
        assert entry["description"]
        assert isinstance(entry["key"], str)
        assert isinstance(entry["description"], str)


def test_keys_are_unique():
    assert len(set(CATALOGUE_KEYS)) == len(CATALOGUE_KEYS)


def test_every_baseline_control_key_is_present_as_control_prefixed():
    for item in BASELINE_CATALOGUE:
        key = f"control:{item['key']}"
        assert key in CATALOGUE_BY_KEY
        assert CATALOGUE_BY_KEY[key]["description"] == item["question"]


def test_every_allowed_policy_section_key_is_present_as_policy_section_prefixed():
    for section_key in ALLOWED_SECTION_KEYS:
        assert f"policy_section:{section_key}" in CATALOGUE_BY_KEY


def test_organisation_fact_keys_present():
    expected = {
        "org:certification_cyber_essentials",
        "org:certification_iso27001",
        "org:working_model",
        "org:handles_personal_data",
        "org:handles_confidential_business_data",
        "org:handles_payment_card_data",
        "org:handles_special_category_data",
        "org:receives_security_questionnaires",
        "org:develops_hosts_own_software",
    }
    assert expected.issubset(set(CATALOGUE_KEYS))


def test_every_key_uses_a_recognised_prefix():
    for key in CATALOGUE_KEYS:
        assert key.startswith("control:") or key.startswith("policy_section:") or key.startswith("org:")
