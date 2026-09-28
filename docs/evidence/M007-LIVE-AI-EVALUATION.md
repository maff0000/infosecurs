# M007 — Final Live AI Evaluation

**Exact candidate SHA:**
`fb5be593131fde51d4fc2aafce268f64a5816850`

**Release image identity:**
`infosecurs-release:fb5be593131fde51d4fc2aafce268f64a5816850`
`sha256:a3a7973767f4916b52e4a4995babca3ad92ce3c7e66bddfea0237d755f1efc43`

**Gateway:**
real Trinity LiteLLM gateway (`http://192.168.246.202:4000`)

**Model alias:**
`trinity-core`

This is the one remaining PID §30 / PRODUCT_GREEN criterion #43 gate: the
three *fake*-gateway eval harnesses already ran GREEN during WI6 (see
`docs/evidence/M007-METRICS.md`/full-suite results throughout WI4-WI6);
this document proves the three *live*-gateway variants — actual
behavioural evaluation against the real gateway, not a mere connectivity
smoke — also run GREEN, against the exact frozen product candidate.

## Environment

- Clean, detached worktree pinned exactly to `fb5be593131fde51d4fc2aafce268f64a5816850`
  (`/srv/infosecurs-worktrees/m007-live-ai-eval`) — `git rev-parse HEAD`
  confirmed to return exactly that SHA before any command ran; working
  tree confirmed clean both before and after.
- Disposable Docker Compose stack, project `m007liveeval`, distinct ports
  (`19906`/`19805`), fresh named volumes, torn down (`down -v`) after use.
- Real gateway configuration confirmed live inside the container:
  `AI_GATEWAY_BASE_URL=http://192.168.246.202:4000`,
  `AI_RISK_MODEL_ALIAS=trinity-core`,
  `AI_GATEWAY_API_KEY_FILE=/run/secrets/litellm_gateway_key`.
- The real credential (`/srv/secrets/infosecurs/litellm_gateway_key`,
  root-only) bind-mounted read-only via a local, uncommitted
  `docker-compose.override.yml` — confirmed 59 bytes inside the
  container; value never printed, never copied into Git, never baked
  into any image.
- Synthetic data only throughout — no real customer data at any point.

## Results

| Evaluation | Gateway | Corpus | Prompt version(s) | Cases | Result |
|---|---|---|---|---:|---|
| Risk | live | `m002-eval-corpus-interpretation-v1` | `risk_interpretation_v3` | 8 | **GREEN** |
| Policy | live | `m004-policy-eval-corpus-v1` | `policy_generation_v2` | 8 | **GREEN** |
| Questionnaire | live | `m005-questionnaire-eval-corpus-v3` | interpretation: `questionnaire_interpretation_v1`; drafting: `questionnaire_drafting_v2` | 14 | **GREEN** |

### Risk live — detail
- Command: `python manage.py run_ai_eval --gateway=live --output=/tmp/risk_live_eval.json`
- Generated: `2026-09-28T20:00:18.294747+00:00`
- `configured_model_alias`: `trinity-core`
- `case_count`: 8, `overall_verdict`: `green`
- Every one of the 8 cases' `objective_checks`
  (`interpretation_succeeded`, `index_matching_held`,
  `impact_likelihood_within_bounds`, `no_identifier_leak_in_output`,
  `cross_tenant_data_possible`) resolved exactly as expected — including
  the `prompt_injection_in_notes` adversarial case, where injected text
  embedded in a customer-supplied note did not override the interpretation
  behaviour.
- Token totals: 16,989 prompt / 6,086 completion.

### Policy live — detail
- Command: `python manage.py run_policy_ai_eval --gateway=live --output=/tmp/policy_live_eval.json`
- Generated: `2026-09-28T20:01:13.518626+00:00`
- `configured_model_alias`: `trinity-core`
- `case_count`: 8, `overall_verdict`: `green`
- Every one of the 8 cases' `objective_checks`
  (`generation_succeeded`, `output_contract_valid`,
  `section_keys_all_recognised`, `no_identifier_leak`,
  `total_content_length_within_bound`, `cross_tenant_data_possible`)
  resolved exactly as expected, including the adversarial
  `adversarial_prompt_injection_in_baseline_note` case, which additionally
  confirmed `prompt_injection_resisted: true`.
- Token totals: 24,845 prompt / 7,438 completion.

### Questionnaire live — detail
- Command: `python manage.py run_questionnaire_ai_eval --gateway=live --output=/tmp/questionnaire_live_eval.json`
- Generated: `2026-09-28T20:01:41.717192+00:00`
- `gateway_mode`: `live`, `configured_model_alias`: `trinity-core`
- `case_count`: 14, `overall_verdict`: `green`
- Every one of the 14 cases' interpretation+drafting objective checks
  (`generation_succeeded`, `output_contract_valid`,
  `interpretation_keys_valid`, `intent_type_correct`,
  `requirement_scope_correct`, `evidence_explicitly_requested_correct`,
  `outcome_exact`, `no_drafting_outcome_upgrade`,
  `confirm_wording_is_application_safe`,
  `supported_wording_is_application_safe`, `no_identifier_leak`,
  `cross_tenant_data_possible`) resolved as expected under the harness's
  own established, unmodified grading — a `null`/`None` value for a
  check on a given case is the harness's own existing "not applicable to
  this case's outcome" semantics (e.g. `confirm_wording_is_application_safe`
  is only meaningful for a case whose outcome is `confirm`), not a
  failure; the harness's own computed `overall_verdict` is authoritative
  and was not reinterpreted here. The adversarial
  `adversarial_prompt_injection_in_question` case additionally confirmed
  `prompt_injection_resisted: true`.
- Token totals: 32,171 interpretation-prompt / 1,615
  interpretation-completion / 23,074 drafting-prompt / 1,204
  drafting-completion.

## Combined PID PRODUCT_GREEN criterion #43 state

```
risk fake                GREEN  (WI6)
risk live                GREEN  (this document)
policy fake               GREEN  (WI6)
policy live               GREEN  (this document)
questionnaire fake         GREEN  (WI6)
questionnaire live         GREEN  (this document)
```

All six required AI evaluations are now GREEN against the exact frozen
M007 candidate.

## What was NOT done (scope discipline)

- No prompt changed.
- No AI gateway code changed.
- No grounding changed.
- No risk/policy/questionnaire logic changed.
- No eval corpus changed.
- No grading threshold or expected-result logic changed.
- No test weakened.
- No product/runtime source of any kind changed — confirmed mechanically
  below.
- No real customer data used anywhere.
- The secret remained external and read-only throughout; never printed,
  never committed, never baked into any image.

## Product-tree identity proof

`git status --short` in the frozen-SHA worktree, both before and after
running all three live evaluations, showed **zero changes** — the
evaluation runs are entirely read-only against the product tree (they
read prompts/corpora/gateway configuration and call the real LLM gateway;
they write only their own JSON report files outside the repository).

The only change this dispatch makes to the repository is the addition of
this one file, `docs/evidence/M007-LIVE-AI-EVALUATION.md`, via its own
evidence-only branch/PR off current `main` — confirmed by `git status
--short` on that branch showing exactly one new file before commit.

## Teardown

Disposable stack (`m007liveeval` — containers, both named volumes,
network) fully torn down (`down -v`). Local, uncommitted
`docker-compose.override.yml` and `.env` removed from the frozen-SHA
worktree. The frozen-SHA worktree itself left clean and unmodified.
