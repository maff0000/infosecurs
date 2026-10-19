import uuid

import pytest
from django.core.exceptions import PermissionDenied
from django.http import Http404

from irene import tools as irene_tools
from irene.exceptions import ActionProposalExpiredError
from irene.models import ActionDecisionState, AssistantAction
from irene.tests.conftest import request_at_tier
from security_tasks.models import SecurityTask, TaskKind
from security_tasks.models import TaskStatus
from entitlements.tiers import TIER_MONTHLY, TIER_PAUSED

pytestmark = pytest.mark.django_db


def _context_for(user, organisation, tier=TIER_MONTHLY):
    request = request_at_tier(user, tier=tier, organisation_id=organisation.id)
    return irene_tools.build_authorized_context(request, organisation)


class TestForbiddenToolsDoNotExist:
    """M010 threat model §2/§5 'forbidden by construction'."""

    @pytest.mark.parametrize(
        "name",
        [
            "execute_query",
            "get_object",
            "fetch_url",
            "run_sql",
            "read_file",
            "shell_exec",
            "approve_policy",
            "accept_risk",
            "certify_control",
            "change_entitlements",
            "delete_organisation",
        ],
    )
    def test_no_such_attribute_on_tools_module(self, name):
        assert not hasattr(irene_tools, name)

    @pytest.mark.parametrize(
        "name", ["execute_query", "approve_policy", "accept_risk", "certify_control"]
    )
    def test_not_in_registry(self, name):
        assert name not in irene_tools.TOOL_REGISTRY


class TestReadToolsRevalidateLiveMembership:
    def test_get_foundations_summary_denies_non_member(self, org_a, user_b):
        """user_b is not a member of org_a at all."""
        context = _context_for(user_b, org_a)
        with pytest.raises(Http404):
            irene_tools.get_foundations_summary(context)

    def test_get_security_tasks_denies_after_membership_revoked(self, org_a, user_c, member_c):
        context = _context_for(user_c, org_a)
        irene_tools.get_security_tasks(context)  # works while a member

        member_c.delete()  # membership revoked mid-conversation

        with pytest.raises(Http404):
            irene_tools.get_security_tasks(context)

    def test_denies_insufficient_tier(self, org_a, user_a, member_a):
        context = _context_for(user_a, org_a, tier=TIER_PAUSED)
        with pytest.raises(PermissionDenied):
            irene_tools.get_foundations_summary(context)


class TestGetRegisteredRoute:
    def test_resolves_real_concept(self, org_a, user_a, member_a):
        context = _context_for(user_a, org_a)
        url = irene_tools.get_registered_route(context, concept_id="task_list")
        assert url == f"/organisations/{org_a.id}/tasks/"

    def test_unregistered_concept_returns_none(self, org_a, user_a, member_a):
        context = _context_for(user_a, org_a)
        assert irene_tools.get_registered_route(context, concept_id="not_registered") is None

    def test_never_leaks_another_organisations_id(self, org_a, org_b, user_a, member_a):
        """object_locator can never override the organisation_id - the
        route is always built against the live-revalidated organisation."""
        context = _context_for(user_a, org_a)
        url = irene_tools.get_registered_route(
            context, concept_id="task_list", object_locator={"organisation_id": org_b.id}
        )
        assert str(org_a.id) in url
        assert str(org_b.id) not in url


class TestProposeAndConfirmTaskLifecycle:
    def test_propose_writes_only_an_action_never_a_task(self, org_a, user_a, member_a):
        context = _context_for(user_a, org_a)
        preview = irene_tools.propose_task(context, kind=TaskKind.MANUAL_OTHER, title="Check firewall rules")
        assert SecurityTask.objects.filter(organisation=org_a).count() == 0
        action = AssistantAction.objects.get(pk=preview["action_id"])
        assert action.decision_state == ActionDecisionState.PROPOSED
        assert preview["changes_security_truth"] is False

    def test_confirm_creates_the_real_task(self, org_a, user_a, member_a):
        context = _context_for(user_a, org_a)
        preview = irene_tools.propose_task(context, kind=TaskKind.MANUAL_OTHER, title="Check firewall rules")
        result = irene_tools.confirm_task_creation(context, action_id=preview["action_id"])
        task = SecurityTask.objects.get(pk=result["task_id"])
        assert task.title == "Check firewall rules"
        assert task.organisation_id == org_a.id

    def test_confirm_twice_does_not_create_two_tasks(self, org_a, user_a, member_a):
        context = _context_for(user_a, org_a)
        preview = irene_tools.propose_task(context, kind=TaskKind.MANUAL_OTHER, title="Duplicate-proof task")
        irene_tools.confirm_task_creation(context, action_id=preview["action_id"])
        with pytest.raises(ActionProposalExpiredError):
            irene_tools.confirm_task_creation(context, action_id=preview["action_id"])
        assert SecurityTask.objects.filter(organisation=org_a, title="Duplicate-proof task").count() == 1

    def test_cannot_confirm_someone_elses_proposal(self, org_a, user_a, member_a, user_c, member_c):
        context_a = _context_for(user_a, org_a)
        preview = irene_tools.propose_task(context_a, kind=TaskKind.MANUAL_OTHER, title="Mine, not yours")
        context_c = _context_for(user_c, org_a)
        with pytest.raises(ActionProposalExpiredError):
            irene_tools.confirm_task_creation(context_c, action_id=preview["action_id"])

    def test_cannot_confirm_other_organisations_proposal(self, org_a, org_b, user_a, member_a, user_b, member_b):
        context_a = _context_for(user_a, org_a)
        preview = irene_tools.propose_task(context_a, kind=TaskKind.MANUAL_OTHER, title="Org A only")
        context_b = _context_for(user_b, org_b)
        with pytest.raises(ActionProposalExpiredError):
            irene_tools.confirm_task_creation(context_b, action_id=preview["action_id"])

    def test_confirm_nonexistent_action_id_denied(self, org_a, user_a, member_a):
        context = _context_for(user_a, org_a)
        with pytest.raises(ActionProposalExpiredError):
            irene_tools.confirm_task_creation(context, action_id=uuid.uuid4())

    def test_propose_rejects_unregistered_kind(self, org_a, user_a, member_a):
        context = _context_for(user_a, org_a)
        with pytest.raises(ValueError):
            irene_tools.propose_task(context, kind="not_a_real_kind", title="x")

    def test_propose_rejects_empty_title(self, org_a, user_a, member_a):
        context = _context_for(user_a, org_a)
        with pytest.raises(ValueError):
            irene_tools.propose_task(context, kind=TaskKind.MANUAL_OTHER, title="   ")

    def test_feature_flag_off_denies_propose(self, org_a, user_a, member_a, settings):
        settings.IRENE_TASK_TOOLS_ENABLED = False
        context = _context_for(user_a, org_a)
        with pytest.raises(Exception):
            irene_tools.call_tool("propose_task", context, kind=TaskKind.MANUAL_OTHER, title="x")


class TestCallToolDispatch:
    def test_unregistered_tool_name_denied(self, org_a, user_a, member_a):
        context = _context_for(user_a, org_a)
        from irene.exceptions import UnregisteredToolError

        with pytest.raises(UnregisteredToolError):
            irene_tools.call_tool("not_a_real_tool", context)
