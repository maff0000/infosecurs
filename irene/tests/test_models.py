import pytest
from django.db import IntegrityError, transaction

from irene.models import AssistantConversation, AssistantMessage, MessageRole

pytestmark = pytest.mark.django_db


class TestAssistantConversation:
    def test_create_and_str(self, org_a, user_a):
        conversation = AssistantConversation.objects.create(organisation=org_a, owner=user_a)
        assert str(conversation.id) in str(conversation)

    def test_two_users_in_same_org_get_independent_conversations(self, org_a, user_a, user_c, member_c):
        conv_a = AssistantConversation.objects.create(organisation=org_a, owner=user_a)
        conv_c = AssistantConversation.objects.create(organisation=org_a, owner=user_c)
        assert conv_a.id != conv_c.id


class TestAssistantMessageSequenceUniqueness:
    def test_duplicate_sequence_in_same_conversation_rejected(self, org_a, user_a):
        conversation = AssistantConversation.objects.create(organisation=org_a, owner=user_a)
        AssistantMessage.objects.create(
            conversation=conversation, sequence=1, role=MessageRole.USER, content="hello"
        )
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                AssistantMessage.objects.create(
                    conversation=conversation, sequence=1, role=MessageRole.ASSISTANT, content="hi"
                )

    def test_same_sequence_number_allowed_across_different_conversations(self, org_a, user_a, user_c, member_c):
        conv_a = AssistantConversation.objects.create(organisation=org_a, owner=user_a)
        conv_c = AssistantConversation.objects.create(organisation=org_a, owner=user_c)
        AssistantMessage.objects.create(conversation=conv_a, sequence=1, role=MessageRole.USER, content="a")
        AssistantMessage.objects.create(conversation=conv_c, sequence=1, role=MessageRole.USER, content="c")
        assert AssistantMessage.objects.filter(sequence=1).count() == 2
