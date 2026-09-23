"""
M004 policy-generation golden-corpus AI evaluation command (PID §25 -
m004-3-eval-harness dispatch), mirroring
`risk_register.management.commands.run_ai_eval` exactly.

    python manage.py run_policy_ai_eval --gateway=fake
    python manage.py run_policy_ai_eval --gateway=live

`--gateway=fake` runs the harness against
`ai_platform.testing.FakePolicyGateway` - proves the harness mechanics, the
real grounding -> generation -> persistence pipeline, and the report
format are correct, with no external network call whatsoever. This is what
this dispatch's own test suite exercises (see
`policy/tests/test_eval_command.py`).

`--gateway=live` constructs the real `ai_platform.gateway.LiteLLMGateway`
and runs the corpus against the configured `trinity-core` alias on the
actual Trinity gateway (PID §13 recommended alias, §25 "run a real live
evaluation"). THIS DISPATCH DOES NOT HAVE, AND DOES NOT ATTEMPT TO OBTAIN,
a working credential for that gateway, and does not run this mode itself -
`AI_GATEWAY_BASE_URL`/`AI_GATEWAY_API_KEY_FILE` are left unset throughout
this dispatch's own work. The PL runs `--gateway=live` separately, exactly
mirroring the M002 eval-harness dispatch's own precedent (see
`risk_register/management/commands/run_ai_eval.py`'s identical header
note).
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from policy.eval.harness import run_eval


class Command(BaseCommand):
    help = "Run the M004 policy-generation AI golden corpus (PID §25) against a fake or live AI gateway."

    def add_arguments(self, parser):
        parser.add_argument(
            "--gateway",
            choices=["fake", "live"],
            required=True,
            help="'fake' uses ai_platform.testing.FakePolicyGateway (no "
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
            from ai_platform.testing import FakePolicyGateway

            gateway = FakePolicyGateway(mode="valid")
        else:
            from ai_platform.gateway import LiteLLMGateway

            gateway = LiteLLMGateway()

        try:
            report = run_eval(gateway)
        except Exception as exc:  # pragma: no cover - defensive: surface loudly, never half-print
            raise CommandError(f"Policy AI evaluation run failed to complete: {exc}") from exc

        rendered = json.dumps(report, indent=2, sort_keys=False, default=str)
        self.stdout.write(rendered)

        if options["output"]:
            Path(options["output"]).write_text(rendered, encoding="utf-8")
            self.stderr.write(self.style.SUCCESS(f"Report written to {options['output']}"))

        if report["overall_verdict"] != "green":
            raise CommandError(
                "Policy AI evaluation overall_verdict is not green - see the printed report "
                "for the failing case(s)."
            )
