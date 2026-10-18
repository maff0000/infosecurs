import pytest

from irene import services
from irene.exceptions import ConversationBoundsExceededError, ForeignConversationError
from irene.models import MAX_MESSAGES_PER_CONVERSATION, MessageRole

pytestmark = pytest.mark.django_db


class TestGetOrCreateActiveConversation:
    def test_creates_once_and_reuses(self, org_a, user_a, member_a):
        first = services.get_or_create_active_conversation(org_a, user_a)
        second = services.get_or_create_active_conversation(org_a, user_a)
        assert first.id == second.id

    def test_separate_owners_get_separate_conversations(self, org_a, user_a, member_a, user_c, member_c):
        conv_a = services.get_or_create_active_conversation(org_a, user_a)
        conv_c = services.get_or_create_active_conversation(org_a, user_c)
        assert conv_a.id != conv_c.id


class TestPrivacy:
    """M010 threat model §4: private to owning user, never org-wide."""

    def test_owner_can_list_own_messages(self, org_a, user_a, member_a):
        conversation = services.get_or_create_active_conversation(org_a, user_a)
        services.append_message(org_a, user_a, conversation.id, role=MessageRole.USER, content="hi")
        page = services.list_messages(org_a, user_a, conversation.id)
        assert len(page.messages) == 1

    def test_other_member_of_same_org_cannot_list_messages(self, org_a, user_a, member_a, user_c, member_c):
        conversation = services.get_or_create_active_conversation(org_a, user_a)
        services.append_message(org_a, user_a, conversation.id, role=MessageRole.USER, content="secret")
        with pytest.raises(ForeignConversationError):
            services.list_messages(org_a, user_c, conversation.id)

    def test_other_organisation_cannot_list_messages(self, org_a, org_b, user_a, member_a, user_b, member_b):
        conversation = services.get_or_create_active_conversation(org_a, user_a)
        services.append_message(org_a, user_a, conversation.id, role=MessageRole.USER, content="secret")
        with pytest.raises(ForeignConversationError):
            services.list_messages(org_b, user_b, conversation.id)

    def test_other_organisation_cannot_append_message(self, org_a, org_b, user_a, member_a, user_b, member_b):
        conversation = services.get_or_create_active_conversation(org_a, user_a)
        with pytest.raises(ForeignConversationError):
            services.append_message(org_b, user_b, conversation.id, role=MessageRole.USER, content="x")


class TestBounds:
    def test_content_is_truncated_not_rejected(self, org_a, user_a, member_a):
        from irene.models import MAX_MESSAGE_CONTENT_LENGTH

        conversation = services.get_or_create_active_conversation(org_a, user_a)
        long_content = "x" * (MAX_MESSAGE_CONTENT_LENGTH + 500)
        message = services.append_message(org_a, user_a, conversation.id, role=MessageRole.USER, content=long_content)
        assert len(message.content) == MAX_MESSAGE_CONTENT_LENGTH

    def test_sequence_increments(self, org_a, user_a, member_a):
        conversation = services.get_or_create_active_conversation(org_a, user_a)
        m1 = services.append_message(org_a, user_a, conversation.id, role=MessageRole.USER, content="1")
        m2 = services.append_message(org_a, user_a, conversation.id, role=MessageRole.ASSISTANT, content="2")
        assert m1.sequence == 1
        assert m2.sequence == 2

    def test_rejects_unregistered_role(self, org_a, user_a, member_a):
        conversation = services.get_or_create_active_conversation(org_a, user_a)
        with pytest.raises(ValueError):
            services.append_message(org_a, user_a, conversation.id, role="hacker", content="x")

    def test_conversation_bounded_length(self, org_a, user_a, member_a, monkeypatch):
        monkeypatch.setattr("irene.services.MAX_MESSAGES_PER_CONVERSATION", 2)
        conversation = services.get_or_create_active_conversation(org_a, user_a)
        services.append_message(org_a, user_a, conversation.id, role=MessageRole.USER, content="1")
        services.append_message(org_a, user_a, conversation.id, role=MessageRole.USER, content="2")
        with pytest.raises(ConversationBoundsExceededError):
            services.append_message(org_a, user_a, conversation.id, role=MessageRole.USER, content="3")
