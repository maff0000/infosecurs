import pytest

from irene.product_knowledge import (
    PRODUCT_KNOWLEDGE_MAP,
    ProductKnowledgeMapValidationError,
    get_concept,
    validate_product_knowledge_map,
)


class TestBootTimeValidator:
    def test_real_registry_validates_clean(self):
        validate_product_knowledge_map()  # must not raise

    def test_detects_broken_route_name(self, monkeypatch):
        import dataclasses

        broken = dataclasses.replace(
            PRODUCT_KNOWLEDGE_MAP["task_list"], route_name="not_a_real_route:at_all"
        )
        monkeypatch.setitem(PRODUCT_KNOWLEDGE_MAP, "task_list", broken)
        with pytest.raises(ProductKnowledgeMapValidationError) as excinfo:
            validate_product_knowledge_map()
        assert "not_a_real_route:at_all" in str(excinfo.value)

    def test_detects_broken_service_reference(self, monkeypatch):
        import dataclasses

        broken = dataclasses.replace(
            PRODUCT_KNOWLEDGE_MAP["task_list"], service_reference="not.a.real.module:nope"
        )
        monkeypatch.setitem(PRODUCT_KNOWLEDGE_MAP, "task_list", broken)
        with pytest.raises(ProductKnowledgeMapValidationError) as excinfo:
            validate_product_knowledge_map()
        assert "service_reference" in str(excinfo.value)

    def test_detects_unknown_capability_code(self, monkeypatch):
        import dataclasses

        broken = dataclasses.replace(
            PRODUCT_KNOWLEDGE_MAP["task_list"], required_capability="made_up_capability"
        )
        monkeypatch.setitem(PRODUCT_KNOWLEDGE_MAP, "task_list", broken)
        with pytest.raises(ProductKnowledgeMapValidationError) as excinfo:
            validate_product_knowledge_map()
        assert "made_up_capability" in str(excinfo.value)

    def test_collects_every_problem_not_just_the_first(self, monkeypatch):
        import dataclasses

        broken_1 = dataclasses.replace(PRODUCT_KNOWLEDGE_MAP["task_list"], route_name="nope:nope")
        broken_2 = dataclasses.replace(PRODUCT_KNOWLEDGE_MAP["task_detail"], required_capability="nope")
        monkeypatch.setitem(PRODUCT_KNOWLEDGE_MAP, "task_list", broken_1)
        monkeypatch.setitem(PRODUCT_KNOWLEDGE_MAP, "task_detail", broken_2)
        with pytest.raises(ProductKnowledgeMapValidationError) as excinfo:
            validate_product_knowledge_map()
        message = str(excinfo.value)
        assert "task_list" in message
        assert "task_detail" in message


class TestCustomerAssuranceUploadConcept:
    """M010E PID §3 - the one navigation concept this package adds."""

    def test_registered_and_available(self):
        entry = get_concept("customer_assurance_upload")
        assert entry is not None
        assert entry.route_name == "questionnaire:import_upload"
        assert entry.required_capability == "customer_assurance"


class TestGetConcept:
    def test_returns_available_entry(self):
        assert get_concept("task_list") is not None

    def test_returns_none_for_unregistered_concept(self):
        assert get_concept("definitely_not_registered") is None

    def test_returns_none_for_disabled_concept(self, monkeypatch):
        import dataclasses

        disabled = dataclasses.replace(PRODUCT_KNOWLEDGE_MAP["task_list"], availability_flag=False)
        monkeypatch.setitem(PRODUCT_KNOWLEDGE_MAP, "task_list", disabled)
        assert get_concept("task_list") is None
