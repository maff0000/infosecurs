"""
Common-security methodology catalogue
(docs/pids/M002-SECURITY-BASELINE-AND-INITIAL-RISK.md §0.4/§0.4a).

This is the "versioned common-security methodology catalogue" the §0
amendment requires: a small, Git-controlled table linking

    asset category -> exposure -> relevant control check(s) -> threat event
                   -> consequence -> suggested treatment

for common SME assets, reusing `key_assets`' own category constants and
`security_baseline`'s own stable control `key` values - never inventing a
parallel taxonomy for either. It is versioned product methodology, not
tenant data, so like `security_baseline/catalogue.py` it lives in Git as
plain Python rather than editable database rows.

This module is deliberately inert: it contains no organisation ID, asset
UUID, control-answer row, or any other tenant-specific value, and it makes
no database query. A later, separate Engineer dispatch builds the
deterministic scenario-instantiation engine that reads a tenant's actual
assets/control-state together with this catalogue to produce tenant-
specific candidate risks (§0.6) - this module only supplies the
methodology that engine reads.

Terminology (PID §0.2, worked laptop/encryption example - the calibration
for depth/tone used throughout this catalogue):

    Asset:                 employee laptop
    Exposure:               portable / leaves controlled premises
    Threat event:            loss or theft
    Control check:            full-disk encryption
    Control state:             no / unknown
    Vulnerability/control gap:  data on a lost device may be readable
    Consequence:                  confidential information disclosure

An EXPOSURE is an asset's inherent characteristic (e.g. "portable, leaves
controlled premises") - it is true regardless of any control answer. A
VULNERABILITY/CONTROL GAP is what turns an exposure into something
exploitable, and only exists once a relevant control is missing/uncertain
(e.g. the *absence* of full-disk encryption on that portable laptop). This
module keeps the two fields separate for that reason - never collapsed
into one.

`scenario_id` values are stable identifiers, same discipline as
`security_baseline.catalogue`'s `key` values: once published, a
`scenario_id` is never renamed or repurposed - retire it (leave it out of
CATALOGUE, but never reuse the string for something else) and add a new
one instead if a scenario's meaning changes materially.

§0.4a - the critical `unknown` != `no` invariant: a control answer of
`unknown` must never deterministically produce a statement that the
control is absent. Each scenario below carries its control-gap wording as
two explicit, separate variants (`ControlGapWording.no` /
`ControlGapWording.unknown`) rather than one template string a caller
might reuse for both - so a caller cannot accidentally apply the
assertive `no` wording to an `unknown` answer. `MethodologyScenario.
trigger_states` then maps every `security_baseline` answer state that
instantiates a given scenario to exactly one of those two variants, and
`MethodologyScenario.wording_for()` is the single supported way to resolve
that pairing - a caller never has to remember the `unknown != no` rule
itself, only call `wording_for(answer_state)`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Tuple

from key_assets.models import (
    CATEGORY_BUSINESS_APPLICATION,
    CATEGORY_CLOUD_SERVICE,
    CATEGORY_ENDPOINT,
    CATEGORY_IDENTITY_OR_PRODUCTIVITY,
    CATEGORY_INFORMATION,
    CATEGORY_NETWORK_OR_LOCATION,
    CATEGORY_PEOPLE,
)
from key_assets.models import CATEGORY_CHOICES as _ASSET_CATEGORY_CHOICES
from security_baseline.catalogue import CATALOGUE_KEYS as _BASELINE_KEYS
from security_baseline.models import (
    ANSWER_NO,
    ANSWER_NOT_APPLICABLE,
    ANSWER_PARTIAL,
    ANSWER_UNKNOWN,
    ANSWER_YES,
)

CATALOGUE_VERSION = "2026-09-methodology-v1"

# The only two control-gap wording variants a scenario may ever produce
# (PID §0.4a). Every `trigger_states` value must be one of these.
VARIANT_NO = "no"
VARIANT_UNKNOWN = "unknown"
_VALID_VARIANTS = frozenset({VARIANT_NO, VARIANT_UNKNOWN})

_VALID_ASSET_CATEGORIES = frozenset(key for key, _label in _ASSET_CATEGORY_CHOICES)
_VALID_BASELINE_KEYS = frozenset(_BASELINE_KEYS)
_VALID_ANSWER_STATES = frozenset(
    {ANSWER_YES, ANSWER_PARTIAL, ANSWER_NO, ANSWER_UNKNOWN, ANSWER_NOT_APPLICABLE}
)


@dataclass(frozen=True)
class ControlGapWording:
    """The `no`-state and `unknown`-state phrasing for one scenario's
    vulnerability/control-gap wording (PID §0.4a).

    `no` may state the control gap definitively (e.g. "full-disk
    encryption is not enabled"). `unknown` must be hedged/clarification-
    oriented (e.g. "full-disk encryption status is not confirmed") and
    must NEVER assert the control is absent. Kept as two separate, named
    fields - never one template string a caller could misapply to both.
    """

    no: str
    unknown: str

    def for_variant(self, variant: str) -> str:
        if variant not in _VALID_VARIANTS:
            raise ValueError(f"Unsupported wording variant: {variant!r}")
        return self.no if variant == VARIANT_NO else self.unknown


@dataclass(frozen=True)
class InstantiatedWording:
    """The resolved (single-variant) wording for one scenario at one
    specific answer state - what `MethodologyScenario.wording_for()`
    returns, so a caller never touches `ControlGapWording` directly."""

    variant: str
    vulnerability: str
    consequence: str


@dataclass(frozen=True)
class MethodologyScenario:
    """One row of the methodology catalogue (PID §0.4's exact field list)."""

    scenario_id: str
    asset_category: str
    exposure: str
    control_keys: Tuple[str, ...]
    threat_event: str
    vulnerability: ControlGapWording
    consequence: ControlGapWording
    suggested_treatment: str
    # Maps every `security_baseline` answer state that instantiates this
    # scenario to which wording variant applies (PID §0.4/§0.4a's
    # "answer-state/applicability rule"). A state absent from this mapping
    # never triggers the scenario - `yes`/`not_applicable` are never
    # present here (asserted below): they normally mean no risk. `partial`
    # is a deliberate per-scenario judgement call (see individual
    # scenarios) and, where included, always resolves to the hedged
    # `unknown` variant - a partially-implemented control is not a
    # confirmed absence either.
    trigger_states: Mapping[str, str]

    def applies_to(self, answer_state: str) -> bool:
        """Whether this scenario is instantiated at all for `answer_state`."""
        return answer_state in self.trigger_states

    def wording_for(self, answer_state: str) -> InstantiatedWording:
        """The single correct wording for `answer_state` - the only
        supported way to resolve the `unknown` != `no` pairing (§0.4a).
        Raises if the scenario does not apply to this answer state at all
        (i.e. `answer_state` was never a trigger, e.g. `yes`).
        """
        if not self.applies_to(answer_state):
            raise ValueError(
                f"Scenario {self.scenario_id!r} does not apply to answer "
                f"state {answer_state!r}"
            )
        variant = self.trigger_states[answer_state]
        return InstantiatedWording(
            variant=variant,
            vulnerability=self.vulnerability.for_variant(variant),
            consequence=self.consequence.for_variant(variant),
        )


# A `no`/`unknown` pair used by several scenarios below for `partial`: a
# partially-implemented control is genuinely between "confirmed gap" and
# "confirmed fine" - it always resolves to the hedged `unknown` variant,
# never the assertive `no` one.
_NO_AND_UNKNOWN = {ANSWER_NO: VARIANT_NO, ANSWER_UNKNOWN: VARIANT_UNKNOWN}
_NO_UNKNOWN_AND_PARTIAL = {
    ANSWER_NO: VARIANT_NO,
    ANSWER_UNKNOWN: VARIANT_UNKNOWN,
    ANSWER_PARTIAL: VARIANT_UNKNOWN,
}


CATALOGUE = [
    # --- Endpoint --------------------------------------------------------
    MethodologyScenario(
        scenario_id="endpoint_device_encryption_loss_theft",
        asset_category=CATEGORY_ENDPOINT,
        exposure="The device is portable and may leave controlled business premises.",
        control_keys=("device_encryption",),
        threat_event="Loss or theft of the device.",
        vulnerability=ControlGapWording(
            no=(
                "Full-disk encryption is not enabled on this device, so data on a "
                "lost or stolen device would be readable."
            ),
            unknown=(
                "It is not confirmed whether full-disk encryption is enabled on "
                "this device; if it is not, data on a lost or stolen device could "
                "be readable."
            ),
        ),
        consequence=ControlGapWording(
            no="Confidential business or customer information disclosure.",
            unknown="Possible confidential business or customer information disclosure.",
        ),
        suggested_treatment=(
            "Enable full-disk encryption (e.g. BitLocker/FileVault) on the device "
            "and put appropriate recovery-key management in place."
        ),
        trigger_states=_NO_AND_UNKNOWN,
    ),
    MethodologyScenario(
        scenario_id="endpoint_anti_malware_compromise",
        asset_category=CATEGORY_ENDPOINT,
        exposure="The device runs everyday business software and reaches email and the web.",
        control_keys=("endpoint_protection",),
        threat_event="Malware or ransomware execution on the device.",
        vulnerability=ControlGapWording(
            no=(
                "This device has no anti-malware/EDR or equivalent endpoint "
                "protection, so malicious software could run undetected."
            ),
            unknown=(
                "It is not confirmed whether this device has anti-malware/EDR or "
                "equivalent endpoint protection; malicious software could run "
                "undetected if it does not."
            ),
        ),
        consequence=ControlGapWording(
            no="Business disruption, data loss or unauthorised access via a compromised device.",
            unknown="Possible business disruption, data loss or unauthorised access via a compromised device.",
        ),
        suggested_treatment=(
            "Deploy reputable anti-malware/EDR (or equivalent) on the device and "
            "keep it enabled and updated."
        ),
        trigger_states=_NO_UNKNOWN_AND_PARTIAL,
    ),
    MethodologyScenario(
        scenario_id="endpoint_patching_known_vulnerability",
        asset_category=CATEGORY_ENDPOINT,
        exposure="The device runs an operating system and applications that accumulate known vulnerabilities over time.",
        control_keys=("patching",),
        threat_event="Exploitation of a known, unpatched vulnerability.",
        vulnerability=ControlGapWording(
            no=(
                "Operating system and application security patches are not "
                "applied to this device in a timely way, leaving known "
                "vulnerabilities exploitable."
            ),
            unknown=(
                "It is not confirmed whether operating system and application "
                "security patches are applied to this device in a timely way; "
                "unpatched known vulnerabilities could be exploitable if they "
                "are not."
            ),
        ),
        consequence=ControlGapWording(
            no="Unauthorised access to, or compromise of, the device and the data it holds.",
            unknown="Possible unauthorised access to, or compromise of, the device and the data it holds.",
        ),
        suggested_treatment=(
            "Apply operating system and application security updates promptly, "
            "and set critical updates to install automatically where practical."
        ),
        trigger_states=_NO_UNKNOWN_AND_PARTIAL,
    ),
    # --- Network / location ------------------------------------------------
    MethodologyScenario(
        scenario_id="network_remote_access_uncontrolled_path",
        asset_category=CATEGORY_NETWORK_OR_LOCATION,
        exposure="Business systems are reached remotely over networks the business does not directly control.",
        control_keys=("remote_access_control",),
        threat_event="Interception or unauthorised use of a remote-access path.",
        vulnerability=ControlGapWording(
            no=(
                "There is no basic control (e.g. VPN or conditional access) over "
                "how this remote-access path reaches company systems, so it may "
                "be used without adequate restriction."
            ),
            unknown=(
                "It is not confirmed whether basic control (e.g. VPN or "
                "conditional access) exists over how this remote-access path "
                "reaches company systems; without it the path could be used "
                "without adequate restriction."
            ),
        ),
        consequence=ControlGapWording(
            no="Unauthorised access to business systems or data.",
            unknown="Possible unauthorised access to business systems or data.",
        ),
        suggested_treatment=(
            "Require a VPN, conditional access, or an equivalent control over "
            "how remote/hybrid working reaches business systems."
        ),
        trigger_states=_NO_AND_UNKNOWN,
    ),
    # --- Identity / productivity --------------------------------------------
    MethodologyScenario(
        scenario_id="identity_mfa_user_account_takeover",
        asset_category=CATEGORY_IDENTITY_OR_PRODUCTIVITY,
        exposure="The account signs in with a username/password over the internet (e.g. Microsoft 365, Google Workspace).",
        control_keys=("mfa_user_accounts",),
        threat_event="Credential theft or phishing leading to account takeover.",
        vulnerability=ControlGapWording(
            no=(
                "Multi-factor authentication is not enabled for ordinary staff "
                "accounts, so a stolen or guessed password alone may be enough "
                "to sign in."
            ),
            unknown=(
                "It is not confirmed whether multi-factor authentication is "
                "enabled for ordinary staff accounts; a stolen or guessed "
                "password alone could be enough to sign in if it is not."
            ),
        ),
        consequence=ControlGapWording(
            no="Unauthorised access to business email/productivity data.",
            unknown="Possible unauthorised access to business email/productivity data.",
        ),
        suggested_treatment=(
            "Enable MFA for all ordinary staff productivity/email accounts."
        ),
        trigger_states=_NO_UNKNOWN_AND_PARTIAL,
    ),
    MethodologyScenario(
        scenario_id="identity_mfa_privileged_account_takeover",
        asset_category=CATEGORY_IDENTITY_OR_PRODUCTIVITY,
        exposure="The privileged/admin account can reconfigure or access the wider tenant if compromised.",
        control_keys=("mfa_privileged_accounts",),
        threat_event="Credential theft or phishing leading to privileged account takeover.",
        vulnerability=ControlGapWording(
            no=(
                "MFA is not enabled for this privileged/admin account, so a "
                "stolen or guessed password alone may grant wide-ranging "
                "administrative access."
            ),
            unknown=(
                "It is not confirmed whether MFA is enabled for this "
                "privileged/admin account; a stolen or guessed password alone "
                "could grant wide-ranging administrative access if it is not."
            ),
        ),
        consequence=ControlGapWording(
            no="Organisation-wide unauthorised access or configuration change.",
            unknown="Possible organisation-wide unauthorised access or configuration change.",
        ),
        suggested_treatment=(
            "Enable MFA for every privileged/admin account, with no exceptions."
        ),
        trigger_states=_NO_UNKNOWN_AND_PARTIAL,
    ),
    MethodologyScenario(
        scenario_id="identity_privileged_access_not_separated",
        asset_category=CATEGORY_IDENTITY_OR_PRODUCTIVITY,
        exposure="The same account or session used for everyday tasks (e.g. email, browsing) may also hold administrative privilege.",
        control_keys=("privileged_access_separation",),
        threat_event="Everyday-use compromise (e.g. phishing, malicious link) escalating directly to administrative access.",
        vulnerability=ControlGapWording(
            no=(
                "Privileged/admin access is not kept separate from everyday "
                "user accounts, so compromise of day-to-day use can escalate "
                "directly to administrative access."
            ),
            unknown=(
                "It is not confirmed whether privileged/admin access is kept "
                "separate from everyday user accounts; if it is not, compromise "
                "of day-to-day use could escalate directly to administrative "
                "access."
            ),
        ),
        consequence=ControlGapWording(
            no="Broader unauthorised access than a compromised ordinary account would otherwise allow.",
            unknown="Possible broader unauthorised access than a compromised ordinary account would otherwise allow.",
        ),
        suggested_treatment=(
            "Use a distinct admin account for administrative tasks, separate "
            "from day-to-day user sign-in, and restrict it to those who need it."
        ),
        trigger_states=_NO_AND_UNKNOWN,
    ),
    MethodologyScenario(
        scenario_id="identity_phishing_protection_delivery",
        asset_category=CATEGORY_IDENTITY_OR_PRODUCTIVITY,
        exposure="The mailbox receives external email, including from unknown or untrusted senders.",
        control_keys=("email_phishing_protection",),
        threat_event="A phishing email reaching a user's inbox.",
        vulnerability=ControlGapWording(
            no=(
                "There are no protections in place against common email/"
                "phishing threats, so malicious messages are more likely to "
                "reach staff inboxes unfiltered."
            ),
            unknown=(
                "It is not confirmed whether protections are in place against "
                "common email/phishing threats; without them, malicious "
                "messages could be more likely to reach staff inboxes "
                "unfiltered."
            ),
        ),
        consequence=ControlGapWording(
            no="Credential theft, malware installation or fraudulent payment from a successful phishing message.",
            unknown="Possible credential theft, malware installation or fraudulent payment from a successful phishing message.",
        ),
        suggested_treatment=(
            "Enable spam/phishing filtering and link/attachment scanning "
            "(platform-native protection is often sufficient for an SME)."
        ),
        trigger_states=_NO_AND_UNKNOWN,
    ),
    # --- People --------------------------------------------------------------
    MethodologyScenario(
        scenario_id="people_joiner_mover_leaver_stale_access",
        asset_category=CATEGORY_PEOPLE,
        exposure="A person's access rights persist independently of their current employment or role status.",
        control_keys=("joiner_mover_leaver",),
        threat_event="A former staff member, or someone who has changed role, retains access they should no longer have.",
        vulnerability=ControlGapWording(
            no=(
                "Access is not promptly removed when someone leaves or changes "
                "role, so former staff or role-changers may retain access they "
                "should no longer have."
            ),
            unknown=(
                "It is not confirmed whether access is promptly removed when "
                "someone leaves or changes role; former staff or role-changers "
                "could retain unwarranted access if it is not."
            ),
        ),
        consequence=ControlGapWording(
            no="Unauthorised access to systems or data by someone no longer entitled to it.",
            unknown="Possible unauthorised access to systems or data by someone no longer entitled to it.",
        ),
        suggested_treatment=(
            "Adopt a simple joiner/mover/leaver checklist so access is "
            "reviewed and removed promptly on every role or employment change."
        ),
        trigger_states=_NO_AND_UNKNOWN,
    ),
    MethodologyScenario(
        scenario_id="people_security_awareness_social_engineering",
        asset_category=CATEGORY_PEOPLE,
        exposure="Staff routinely make judgement calls (e.g. clicking links, handling requests) that affect security.",
        control_keys=("security_awareness_training",),
        threat_event="A staff member falls for a social-engineering or phishing attempt through lack of awareness.",
        vulnerability=ControlGapWording(
            no=(
                "Staff do not receive security-awareness/phishing education, so "
                "they are less likely to recognise and resist common "
                "social-engineering attempts."
            ),
            unknown=(
                "It is not confirmed whether staff receive security-awareness/"
                "phishing education; without it, they could be less likely to "
                "recognise common social-engineering attempts."
            ),
        ),
        consequence=ControlGapWording(
            no="A successful compromise that basic awareness could plausibly have prevented.",
            unknown="Possible successful compromise that basic awareness could plausibly have prevented.",
        ),
        suggested_treatment=(
            "Run regular, even informal, security-awareness/phishing education "
            "for all staff."
        ),
        trigger_states=_NO_AND_UNKNOWN,
    ),
    MethodologyScenario(
        scenario_id="people_incident_reporting_delayed_response",
        asset_category=CATEGORY_PEOPLE,
        exposure="Staff are usually the first to notice suspicious activity affecting themselves or their devices.",
        control_keys=("incident_reporting_route",),
        threat_event="A real incident (e.g. a clicked link, a lost device, a suspicious email) goes unreported or is reported too late.",
        vulnerability=ControlGapWording(
            no=(
                "There is no known route for staff to report suspected "
                "security incidents, so a real incident may go unreported or "
                "be reported too late for an effective response."
            ),
            unknown=(
                "It is not confirmed whether there is a known route for staff "
                "to report suspected security incidents; without one, a real "
                "incident could go unreported or be reported too late."
            ),
        ),
        consequence=ControlGapWording(
            no="Delayed containment, allowing an incident's impact to grow before anyone responds.",
            unknown="Possible delayed containment, allowing an incident's impact to grow before anyone responds.",
        ),
        suggested_treatment=(
            "Establish and communicate a simple, known route (e.g. a named "
            "person or shared inbox) for staff to report suspected incidents."
        ),
        trigger_states=_NO_AND_UNKNOWN,
    ),
    # --- Business application ------------------------------------------------
    MethodologyScenario(
        scenario_id="business_application_backups_data_loss",
        asset_category=CATEGORY_BUSINESS_APPLICATION,
        exposure="Business data held in this application exists primarily as one live, operational copy.",
        control_keys=("backups",),
        threat_event="Data loss (e.g. ransomware, accidental deletion, technical failure).",
        vulnerability=ControlGapWording(
            no=(
                "Important business data in this application is not backed up "
                "with a tested ability to restore it, so a loss event could be "
                "permanent."
            ),
            unknown=(
                "It is not confirmed whether important business data in this "
                "application is backed up with a tested ability to restore it; "
                "a loss event could be permanent if it is not."
            ),
        ),
        consequence=ControlGapWording(
            no="Permanent loss of business data and resulting business disruption.",
            unknown="Possible permanent loss of business data and resulting business disruption.",
        ),
        suggested_treatment=(
            "Set up regular backups of this application's data and periodically "
            "test that a restore actually works."
        ),
        trigger_states=_NO_UNKNOWN_AND_PARTIAL,
    ),
    MethodologyScenario(
        scenario_id="business_application_patching_known_vulnerability",
        asset_category=CATEGORY_BUSINESS_APPLICATION,
        exposure="The application runs on software components that accumulate known vulnerabilities over time.",
        control_keys=("patching",),
        threat_event="Exploitation of a known, unpatched vulnerability in the application or its platform.",
        vulnerability=ControlGapWording(
            no=(
                "Security patches are not applied to this application or its "
                "platform in a timely way, leaving known vulnerabilities "
                "exploitable."
            ),
            unknown=(
                "It is not confirmed whether security patches are applied to "
                "this application or its platform in a timely way; unpatched "
                "known vulnerabilities could be exploitable if they are not."
            ),
        ),
        consequence=ControlGapWording(
            no="Unauthorised access to, or compromise of, the application and the data it holds.",
            unknown="Possible unauthorised access to, or compromise of, the application and the data it holds.",
        ),
        suggested_treatment=(
            "Apply security updates to the application and its platform "
            "promptly, or confirm the hosting/SaaS provider does so."
        ),
        trigger_states=_NO_AND_UNKNOWN,
    ),
    # --- Cloud service ---------------------------------------------------
    MethodologyScenario(
        scenario_id="cloud_service_admin_mfa_account_takeover",
        asset_category=CATEGORY_CLOUD_SERVICE,
        exposure="The cloud environment's administrative console is reachable from the internet and controls the underlying business systems.",
        control_keys=("mfa_privileged_accounts", "privileged_access_separation"),
        threat_event="Credential theft or phishing leading to takeover of the cloud administrative account.",
        vulnerability=ControlGapWording(
            no=(
                "This cloud environment's administrative access is not "
                "protected by MFA and separated privileged access, so a "
                "stolen or guessed password alone may grant wide-ranging "
                "control of hosted systems."
            ),
            unknown=(
                "It is not confirmed whether this cloud environment's "
                "administrative access is protected by MFA and separated "
                "privileged access; a stolen or guessed password alone could "
                "grant wide-ranging control of hosted systems if it is not."
            ),
        ),
        consequence=ControlGapWording(
            no="Organisation-wide compromise of hosted systems or data.",
            unknown="Possible organisation-wide compromise of hosted systems or data.",
        ),
        suggested_treatment=(
            "Enable MFA on every cloud administrative account and keep "
            "administrative access separate from everyday use."
        ),
        trigger_states=_NO_UNKNOWN_AND_PARTIAL,
    ),
    # --- Information ----------------------------------------------------
    MethodologyScenario(
        scenario_id="information_backups_loss_or_corruption",
        asset_category=CATEGORY_INFORMATION,
        exposure="This information is business or customer data the organisation depends on and may hold in only one place.",
        control_keys=("backups",),
        threat_event="Loss, corruption or unauthorised deletion of this information.",
        vulnerability=ControlGapWording(
            no=(
                "This information is not backed up with a tested ability to "
                "restore it, so its loss, corruption or deletion could be "
                "permanent."
            ),
            unknown=(
                "It is not confirmed whether this information is backed up "
                "with a tested ability to restore it; its loss, corruption or "
                "deletion could be permanent if it is not."
            ),
        ),
        consequence=ControlGapWording(
            no="Permanent loss of business/customer information and resulting business or compliance impact.",
            unknown="Possible permanent loss of business/customer information and resulting business or compliance impact.",
        ),
        suggested_treatment=(
            "Identify where this information is held and ensure it is backed "
            "up with a periodically tested restore process."
        ),
        trigger_states=_NO_UNKNOWN_AND_PARTIAL,
    ),
]

CATALOGUE_BY_ID = {scenario.scenario_id: scenario for scenario in CATALOGUE}
CATALOGUE_IDS = list(CATALOGUE_BY_ID.keys())

# --- Catalogue-wide invariants (mirrors security_baseline/catalogue.py's
# own assert-at-import-time discipline) -----------------------------------

assert len(CATALOGUE_IDS) == len(CATALOGUE), "Catalogue scenario IDs must be unique."

assert 12 <= len(CATALOGUE) <= 20, (
    "PID §0.4: keep the catalogue to roughly 12-20 high-value scenarios - "
    f"got {len(CATALOGUE)}."
)

for _scenario in CATALOGUE:
    assert _scenario.asset_category in _VALID_ASSET_CATEGORIES, (
        f"{_scenario.scenario_id}: unknown asset category "
        f"{_scenario.asset_category!r} (must be a key_assets category constant)."
    )
    assert _scenario.control_keys, f"{_scenario.scenario_id}: control_keys must not be empty."
    for _control_key in _scenario.control_keys:
        assert _control_key in _VALID_BASELINE_KEYS, (
            f"{_scenario.scenario_id}: unknown control key {_control_key!r} "
            "(must be a security_baseline catalogue key)."
        )
    assert _scenario.trigger_states, f"{_scenario.scenario_id}: trigger_states must not be empty."
    for _state, _variant in _scenario.trigger_states.items():
        assert _state in _VALID_ANSWER_STATES, (
            f"{_scenario.scenario_id}: unknown answer state {_state!r} in trigger_states."
        )
        assert _variant in _VALID_VARIANTS, (
            f"{_scenario.scenario_id}: trigger_states[{_state!r}] must be "
            f"'no' or 'unknown', got {_variant!r}."
        )
    # §0.4a: yes/not_applicable normally mean no risk - a scenario must
    # never be instantiated by either.
    assert ANSWER_YES not in _scenario.trigger_states, (
        f"{_scenario.scenario_id}: 'yes' must never trigger a scenario."
    )
    assert ANSWER_NOT_APPLICABLE not in _scenario.trigger_states, (
        f"{_scenario.scenario_id}: 'not_applicable' must never trigger a scenario."
    )
    # §0.4a: 'partial', where included, must resolve to the hedged variant,
    # never the assertive 'no' one - a partially-implemented control is not
    # a confirmed absence.
    if ANSWER_PARTIAL in _scenario.trigger_states:
        assert _scenario.trigger_states[ANSWER_PARTIAL] == VARIANT_UNKNOWN, (
            f"{_scenario.scenario_id}: 'partial' must resolve to the "
            "'unknown' wording variant, never 'no'."
        )

del _scenario
