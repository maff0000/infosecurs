# M008D — Policy Clause-to-Source Truth Matrix

**Status:** DESIGN ARTEFACT. Shows the source for every clause used in
the three sample policies (`M008D-SAMPLE-POLICIES.md`), with explicit
truth classification. No clause states a target/recommendation as an
existing implementation.

| Policy statement (as rendered) | Source | Classification |
|---|---|---|
| "This policy applies to all staff, contractors and systems..." | Fixed normative template (not fact-dependent) | NORMATIVE_REQUIREMENT |
| "Overall responsibility... sits with the designated Account Holder" | `governance.GovernanceRoleAssignment` (Account Holder role exists) | CURRENT_CONFIRMED_PRACTICE |
| "Multi-factor authentication is required for all staff accounts" | `BaselineAnswer(mfa_user_accounts) == YES` | CURRENT_CONFIRMED_PRACTICE |
| "Multi-factor authentication is currently enabled for some, but not all, staff accounts" | `BaselineAnswer(mfa_user_accounts) == PARTIAL` | CURRENT_CONFIRMED_PRACTICE (the "some" part) |
| "...extending this to every account is an identified action" | Same fact, PARTIAL branch | GAP_OR_FUTURE_ACTION |
| "Administrator access is kept separate from everyday accounts" | `BaselineAnswer(privileged_access_separation) == YES` | CURRENT_CONFIRMED_PRACTICE |
| "All work devices run anti-malware/endpoint protection" | `BaselineAnswer(endpoint_protection) == YES` | CURRENT_CONFIRMED_PRACTICE |
| "...in place for some devices but not consistently across all devices... including personally owned devices" | `BaselineAnswer(endpoint_protection) == PARTIAL` + `OrganisationProfile.endpoint_management` | CURRENT_CONFIRMED_PRACTICE (partial) + context |
| "Important business data is backed up regularly" | `BaselineAnswer(backups) in {YES, PARTIAL}` (backup itself confirmed) | CURRENT_CONFIRMED_PRACTICE |
| "A test restore of these backups has not yet been carried out" | `BaselineAnswer(backups) == PARTIAL` (the untested-restore variant) | GAP_OR_FUTURE_ACTION |
| "Staff work from the organisation's office. No remote-access arrangement currently applies" | `OrganisationProfile.working_model == "office"` + `remote_access_control == NOT_APPLICABLE` | CURRENT_CONFIRMED_PRACTICE |
| "Staff work remotely." | `OrganisationProfile.working_model == "remote"` | CURRENT_CONFIRMED_PRACTICE |
| "Some remote-access paths are not currently managed or governed consistently" | `BaselineAnswer(remote_access_control) == PARTIAL` | GAP_OR_FUTURE_ACTION |
| "A clear route for staff to report suspected security incidents has not yet been established" | `BaselineAnswer(incident_reporting_route) == NO` | GAP_OR_FUTURE_ACTION |
| "A reporting route... exists informally but is not consistently known" | `BaselineAnswer(incident_reporting_route) == PARTIAL` | mixed (practice exists, gap in consistency) |
| "Security-awareness activity for staff is currently informal and occasional" | `BaselineAnswer(security_awareness_training) == PARTIAL` | CURRENT_CONFIRMED_PRACTICE |
| "No structured security-awareness activity is currently provided" | `BaselineAnswer(security_awareness_training) == NO` | GAP_OR_FUTURE_ACTION |
| "This policy is reviewed at least annually..." | Fixed normative template | NORMATIVE_REQUIREMENT |
| "Not enough has been confirmed yet to state this section's content" (Scenario C) | `BaselineAnswer(<control>) == UNKNOWN` for every control feeding that section | GAP_OR_FUTURE_ACTION (explicit absence, never silently omitted) |

## The one hard rule this matrix enforces

Every row with a **PARTIAL** source fact produces **two** separate
sentences in the rendered policy — one CURRENT_CONFIRMED_PRACTICE
sentence for the part that's true, one GAP_OR_FUTURE_ACTION sentence for
the part that isn't — never a single blended sentence that could be read
either way. This is the literal implementation of "a target or
recommendation must never be written as an existing implementation"
(Central Architecture §10) and of M008's own "PARTIAL != YES" invariant,
carried all the way into rendered prose, not just into the stored
`BaselineAnswer.answer` value.
