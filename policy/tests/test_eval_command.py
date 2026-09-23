"""
Mechanics test for `manage.py run_policy_ai_eval --gateway=fake` (PID §25 -
m004-3-eval-harness dispatch; dispatch instructions "you test this
command's mechanics with --gateway=fake only"). Never invokes
--gateway=live. Mirrors `risk_register/tests/test_eval_command.py`.
"""
import io
import json

import pytest
from django.core.management import call_command


@pytest.mark.django_db
class TestRunPolicyAiEvalCommandFakeGateway:
    def test_runs_successfully_and_prints_a_valid_json_report(self):
        out = io.StringIO()
        call_command("run_policy_ai_eval", "--gateway=fake", stdout=out)
        report = json.loads(out.getvalue())

        assert report["overall_verdict"] == "green"
        assert report["case_count"] == 8
        assert len(report["cases"]) == 8
        assert report["corpus_version"] == "m004-policy-eval-corpus-v1"
        assert report["prompt_version"] == "policy_generation_v1"

    def test_writes_report_to_output_file_when_requested(self, tmp_path):
        out = io.StringIO()
        output_path = tmp_path / "policy-eval-report.json"
        call_command(
            "run_policy_ai_eval",
            "--gateway=fake",
            f"--output={output_path}",
            stdout=out,
            stderr=io.StringIO(),
        )

        assert output_path.exists()
        written = json.loads(output_path.read_text())
        assert written["case_count"] == 8

    def test_requires_gateway_argument(self):
        with pytest.raises(Exception):
            call_command("run_policy_ai_eval", stdout=io.StringIO())

    def test_is_idempotent_across_repeated_runs(self):
        """Running the command twice must not fail on duplicate synthetic
        tenant state (golden_corpus.ensure_case_organisation is
        update_or_create-based) and must not accumulate state that breaks
        a subsequent run."""
        out1 = io.StringIO()
        call_command("run_policy_ai_eval", "--gateway=fake", stdout=out1)
        report1 = json.loads(out1.getvalue())

        out2 = io.StringIO()
        call_command("run_policy_ai_eval", "--gateway=fake", stdout=out2)
        report2 = json.loads(out2.getvalue())

        assert report1["overall_verdict"] == report2["overall_verdict"] == "green"
        assert report1["case_count"] == report2["case_count"] == 8

    def test_command_errors_when_verdict_is_not_green(self, monkeypatch):
        """A non-green verdict must fail the command (CommandError), so a
        CI/manual run cannot silently report red while exiting 0.

        `run_policy_ai_eval.Command.handle` imports `FakePolicyGateway`
        locally (inside `handle()`, not at module import time), so
        monkeypatching the name on `ai_platform.testing` before the call
        is resolved is enough to force every case's gateway call to fail -
        same technique `risk_register/tests/test_eval_command.py`'s
        equivalent test already uses.
        """
        import ai_platform.testing as testing_module

        original = testing_module.FakePolicyGateway
        monkeypatch.setattr(
            testing_module,
            "FakePolicyGateway",
            lambda mode="valid": original(mode="auth_error"),
        )

        with pytest.raises(Exception):
            call_command("run_policy_ai_eval", "--gateway=fake", stdout=io.StringIO())
