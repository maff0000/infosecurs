import pytest

from organisations.models import Organisation


@pytest.fixture
def organisation(db):
    return Organisation.objects.create(name="AI Adapter Test Org")


@pytest.fixture
def other_organisation(db):
    return Organisation.objects.create(name="AI Adapter Other Test Org")


@pytest.fixture
def grounding(organisation):
    from ai_platform.contracts import GroundingPayload

    return GroundingPayload(
        organisation_id=str(organisation.pk),
        profile_facts={"endpoint_management": "byod", "working_model": "hybrid"},
        baseline_facts={"mfa_user_accounts": "no", "backups": "unknown"},
        asset_facts=[{"id": "fixture-endpoint", "category": "endpoint"}],
    )
