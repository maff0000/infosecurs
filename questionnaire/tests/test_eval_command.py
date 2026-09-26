"""
Mechanics test for `manage.py run_questionnaire_ai_eval --gateway=fake`
(PID §28 - m005-3-eval-harness dispatch). Never invokes --gateway=live.
Mirrors `policy/tests/test_eval_command.py`.
"""
import io
import json

import pytest
from django.core.management import call_command


@pytest.mark.django_db
class TestRunQuestionnaireAiEvalCommandFakeGateway:
    def test_runs_successfully_and_prints_a_valid_json_report(self):
        out = io.StringIO()
        call_command("run_questionnaire_ai_eval", "--gateway=fake", stdout=out)
        report = json.loads(out.getvalue())

        assert report["overall_verdict"] == "green"
        assert report["case_count"] == 14
        assert len(report["cases"]) == 14
        assert report["corpus_version"] == "m005-questionnaire-eval-corpus-v3"
        assert report["interpretation_prompt_version"] == "questionnaire_interpretation_v1"
        assert report["drafting_prompt_version"] == "questionnaire_drafting_v2"
        assert report["gateway_mode"] == "fake"

    def test_writes_report_to_output_file_when_requested(self, tmp_path):
        out = io.StringIO()
        output_path = tmp_path / "questionnaire-eval-report.json"
        call_command(
            "run_questionnaire_ai_eval",
            "--gateway=fake",
            f"--output={output_path}",
            stdout=out,
            stderr=io.StringIO(),
        )

        assert output_path.exists()
        written = json.loads(output_path.read_text())
        assert written["case_count"] == 14

    def test_requires_gateway_argument(self):
        with pytest.raises(Exception):
            call_command("run_questionnaire_ai_eval", stdout=io.StringIO())

    def test_rejects_an_invalid_gateway_choice(self):
        with pytest.raises(Exception):
            call_command("run_questionnaire_ai_eval", "--gateway=bogus", stdout=io.StringIO())

    def test_is_idempotent_across_repeated_runs(self):
        out1 = io.StringIO()
        call_command("run_questionnaire_ai_eval", "--gateway=fake", stdout=out1)
        report1 = json.loads(out1.getvalue())

        out2 = io.StringIO()
        call_command("run_questionnaire_ai_eval", "--gateway=fake", stdout=out2)
        report2 = json.loads(out2.getvalue())

        assert report1["overall_verdict"] == report2["overall_verdict"] == "green"
        assert report1["case_count"] == report2["case_count"] == 14
