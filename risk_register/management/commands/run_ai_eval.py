"""
M002 golden-corpus AI evaluation command (PID §18, corrected for the
interpretation task by the M002-3e dispatch).

    python manage.py run_ai_eval --gateway=fake
    python manage.py run_ai_eval --gateway=live

`--gateway=fake` runs the harness against
`ai_platform.testing.FakeInterpretationGateway` - proves the harness
mechanics, the real scenario-instantiation -> interpretation pipeline, and
the report format are correct, with no external network call whatsoever.
This is what this dispatch's own test suite exercises (see
risk_register/tests/test_eval_command.py).

`--gateway=live` constructs the real `ai_platform.gateway.LiteLLMGateway`
- which implements BOTH `RiskGenerationGateway` and
`RiskInterpretationGateway` (see that class's own docstring) - and runs the
corpus against the configured `trinity-core` alias on the actual Trinity
gateway (PID §24 preflight, §9.2 external configuration). This dispatch
does not have a working credential for that gateway and does not run this
mode - the PL runs it separately once PID §24's preflight is satisfied.
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from risk_register.eval.harness import run_eval


class Command(BaseCommand):
    help = "Run the M002 AI risk-interpretation golden corpus (PID §18) against a fake or live AI gateway."

    def add_arguments(self, parser):
        parser.add_argument(
            "--gateway",
            choices=["fake", "live"],
            required=True,
            help="'fake' uses ai_platform.testing.FakeInterpretationGateway (no "
                 "network call). 'live' uses ai_platform.gateway.LiteLLMGateway "
                 "against the configured trinity-core alias.",
        )
        parser.add_argument(
            "--output",
            default=None,
            help="Optional path to also write the JSON report to.",
        )

    def handle(self, *args, **options):
        gateway_choice = options["gateway"]

        if gateway_choice == "fake":
            from ai_platform.testing import FakeInterpretationGateway

            gateway = FakeInterpretationGateway(mode="valid")
        else:
            from ai_platform.gateway import LiteLLMGateway

            gateway = LiteLLMGateway()

        try:
            report = run_eval(gateway)
        except Exception as exc:  # pragma: no cover - defensive: surface loudly, never half-print
            raise CommandError(f"AI evaluation run failed to complete: {exc}") from exc

        rendered = json.dumps(report, indent=2, sort_keys=False, default=str)
        self.stdout.write(rendered)

        if options["output"]:
            Path(options["output"]).write_text(rendered, encoding="utf-8")
            self.stderr.write(self.style.SUCCESS(f"Report written to {options['output']}"))

        if report["overall_verdict"] != "green":
            raise CommandError(
                "AI evaluation overall_verdict is not green - see the printed report for the failing case(s)."
            )
