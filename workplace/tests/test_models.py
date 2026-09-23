import pytest
from django.core.exceptions import ValidationError

from workplace.models import Workplace


@pytest.mark.django_db
class TestWorkplaceModel:
    def test_create_minimal_workplace(self, org_a):
        workplace = Workplace.objects.create(
            organisation=org_a,
            name="Home / remote working",
            type=Workplace.TYPE_DISTRIBUTED_HOME,
        )
        assert workplace.id is not None
        assert workplace.location_label == ""
        assert workplace.approx_people_count is None
        assert workplace.is_primary is False
        assert workplace.is_active is True

    def test_organisation_may_have_multiple_workplaces(self, org_a):
        Workplace.objects.create(
            organisation=org_a, name="London HQ", type=Workplace.TYPE_DEDICATED_OFFICE,
            location_label="London", approx_people_count=15,
        )
        Workplace.objects.create(
            organisation=org_a, name="Home / remote working", type=Workplace.TYPE_DISTRIBUTED_HOME,
            approx_people_count=5,
        )
        assert Workplace.objects.filter(organisation=org_a).count() == 2

    def test_negative_approx_people_count_is_rejected(self, org_a):
        workplace = Workplace(
            organisation=org_a,
            name="Office",
            type=Workplace.TYPE_DEDICATED_OFFICE,
            approx_people_count=-1,
        )
        with pytest.raises(ValidationError):
            workplace.full_clean()

    def test_zero_approx_people_count_is_allowed(self, org_a):
        workplace = Workplace(
            organisation=org_a,
            name="Office",
            type=Workplace.TYPE_DEDICATED_OFFICE,
            approx_people_count=0,
        )
        workplace.full_clean()  # should not raise
        workplace.save()
        assert Workplace.objects.get(pk=workplace.pk).approx_people_count == 0

    def test_invalid_type_rejected(self, org_a):
        workplace = Workplace(
            organisation=org_a, name="Somewhere", type="not_a_real_type"
        )
        with pytest.raises(ValidationError):
            workplace.full_clean()

    def test_str_includes_name_and_organisation(self, org_a):
        workplace = Workplace.objects.create(
            organisation=org_a, name="London HQ", type=Workplace.TYPE_DEDICATED_OFFICE
        )
        assert "London HQ" in str(workplace)
