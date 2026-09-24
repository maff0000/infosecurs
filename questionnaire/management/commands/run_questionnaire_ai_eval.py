"""
M005 questionnaire-assurance golden-corpus AI evaluation command (PID §28 -
m005-3-eval-harness dispatch), mirroring
`policy.management.commands.run_policy_ai_eval` exactly.

    python manage.py run_questionnaire_ai_eval --gateway=fake
    python manage.py run_questionnaire_ai_eval --gateway=live

`--gateway=fake` runs the harness against a fresh, per-case pair of
`ai_platform.testing.FakeQuestionnaireInterpretationGateway`/
`FakeQuestionnaireDraftingGateway` (see `questionnaire.eval.harness`'s own
module docstring for why per-case, not shared) - proves the harness
mechanics, the real grounding -> outcome-derivation -> drafting ->
persistence pipeline, and the report format are correct, with no external
network call whatsoever. This is what this dispatch's own test suite
exercises (see `questionnaire/tests/test_eval_command.py`).

`--gateway=live` constructs one real `ai_platform.gateway.LiteLLMGateway`
and runs the corpus against the configured `trinity-core` alias on the
actual Trinity gateway (PID §21 recommended alias, §28 "a live trinity-core
evaluation is mandatory before closure"). THIS DISPATCH DOES NOT HAVE, AND
DOES NOT ATTEMPT TO OBTAIN, a working credential for that gateway, and does
not run this mode itself - `AI_GATEWAY_BASE_URL`/`AI_GATEWAY_API_KEY_FILE`
are left unset throughout this dispatch's own work. The PL runs
`--gateway=live` separately, exactly mirroring
`run_policy_ai_eval.py`'s identical header note.
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from questionnaire.eval.harness import run_eval


class Command(BaseCommand):
    help = (
        "Run the M005 questionnaire-assurance AI golden corpus (PID §28) "
        "against a fake or live AI gateway."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--gateway",
            choices=["fake", "live"],
            required=True,
            help="'fake' uses fresh per-case ai_platform.testing fake gateways (no "
                 "network call). 'live' uses one shared ai_platform.gateway.LiteLLMGateway "
                 "against the configured trinity-core alias for both AI tasks.",
        )
        parser.add_argument(
            "--output",
            default=None,
            help="Optional path to also write the JSON report to.",
        )

    def handle(self, *args, **options):
        gateway_mode = options["gateway"]

        try:
            report = run_eval(gateway_mode)
        except Exception as exc:  # pragma: no cover - defensive: surface loudly, never half-print
            raise CommandError(f"Questionnaire AI evaluation run failed to complete: {exc}") from exc

        rendered = json.dumps(report, indent=2, sort_keys=False, default=str)
        self.stdout.write(rendered)

        if options["output"]:
            Path(options["output"]).write_text(rendered, encoding="utf-8")
            self.stderr.write(self.style.SUCCESS(f"Report written to {options['output']}"))

        if report["overall_verdict"] != "green":
            raise CommandError(
                "Questionnaire AI evaluation overall_verdict is not green - see the printed "
                "report for the failing case(s)."
            )
