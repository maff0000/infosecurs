"""
Mechanics test for `manage.py run_ai_eval --gateway=fake` (PID §18,
dispatch instructions "you test this command's mechanics with --gateway=fake
only"). Never invokes --gateway=live.
"""
import io
import json

import pytest
from django.core.management import call_command


@pytest.mark.django_db
class TestRunAiEvalCommandFakeGateway:
    def test_runs_successfully_and_prints_a_valid_json_report(self):
        out = io.StringIO()
        call_command("run_ai_eval", "--gateway=fake", stdout=out)
        report = json.loads(out.getvalue())

        assert report["overall_verdict"] == "green"
        assert report["case_count"] == 8
        assert len(report["cases"]) == 8
        assert report["corpus_version"] == "m002-golden-corpus-v1"
        # M002 repair (2026-09-23): risk_register wiring moved to
        # risk_generation_v2 after the live PID §18 eval found the v1
        # prompt's grounding_refs formatting instruction was not reliably
        # followed under real model conditions - see
        # ai_platform/prompts/risk_generation_v2.py's docstring.
        assert report["prompt_version"] == "risk_generation_v2"

    def test_writes_report_to_output_file_when_requested(self, tmp_path):
        out = io.StringIO()
        output_path = tmp_path / "eval-report.json"
        call_command("run_ai_eval", "--gateway=fake", f"--output={output_path}", stdout=out, stderr=io.StringIO())

        assert output_path.exists()
        written = json.loads(output_path.read_text())
        assert written["case_count"] == 8

    def test_requires_gateway_argument(self):
        with pytest.raises(Exception):
            call_command("run_ai_eval", stdout=io.StringIO())

    def test_is_idempotent_across_repeated_runs(self):
        """
        Running the command twice must not fail on duplicate synthetic
        Organisation rows (ensure_eval_organisations() is get_or_create-
        based) and must not accumulate duplicate AIInvocationRecord/Risk
        state that breaks a subsequent run.
        """
        out1 = io.StringIO()
        call_command("run_ai_eval", "--gateway=fake", stdout=out1)
        report1 = json.loads(out1.getvalue())

        out2 = io.StringIO()
        call_command("run_ai_eval", "--gateway=fake", stdout=out2)
        report2 = json.loads(out2.getvalue())

        assert report1["overall_verdict"] == report2["overall_verdict"] == "green"
        assert report1["case_count"] == report2["case_count"] == 8
