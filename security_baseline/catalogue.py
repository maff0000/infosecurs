"""
Security baseline catalogue (docs/pids/M002-SECURITY-BASELINE-AND-INITIAL-RISK.md §6.1).

This is versioned product methodology, not user data, so it lives in Git as
plain Python rather than editable database rows. `CATALOGUE_VERSION` is
bumped deliberately whenever the question set/wording changes; every saved
`BaselineAssessment` records the exact version it was answered against
(§6.4), so a historical answer set remains interpretable even after the
catalogue evolves.

This is a pragmatic SME starter baseline, not a claim of conformity with
Cyber Essentials, ISO 27001, NIST, CIS or any other formal framework (§6.1).

`key` values are stable identifiers referenced elsewhere (e.g. a future
module's `grounding_refs` such as `baseline.mfa_user_accounts`, per PID
§10) - once published, a key should not be renamed; retire and add a new
one instead if a question's meaning changes materially.
"""

CATALOGUE_VERSION = "2026-09-baseline-v1"

CATALOGUE = [
    {
        "key": "mfa_user_accounts",
        "area": "Multi-factor authentication (staff)",
        "question": "Is multi-factor authentication (MFA) enabled for ordinary staff productivity/email accounts?",
        "help_text": "Covers everyday user sign-in, e.g. Microsoft 365 or Google Workspace accounts.",
    },
    {
        "key": "mfa_privileged_accounts",
        "area": "Multi-factor authentication (admin)",
        "question": "Is MFA enabled for privileged/admin accounts (e.g. IT admin, cloud admin)?",
        "help_text": "Privileged accounts carry more risk than ordinary user accounts and are asked about separately.",
    },
    {
        "key": "endpoint_protection",
        "area": "Endpoint protection",
        "question": "Do staff devices have anti-malware/EDR or equivalent endpoint protection?",
        "help_text": "Covers laptops/desktops used to do work, whether company-owned or BYOD.",
    },
    {
        "key": "patching",
        "area": "Patching",
        "question": "Are operating systems and applications kept up to date with security patches in a timely way?",
        "help_text": "A general sense of practice is enough - this is not asking for a patch-compliance report.",
    },
    {
        "key": "device_encryption",
        "area": "Device encryption",
        "question": "Is full-disk encryption enabled on devices that hold business data, where applicable?",
        "help_text": "E.g. BitLocker or FileVault on laptops that store or access business data.",
    },
    {
        "key": "backups",
        "area": "Backups",
        "question": "Are important business data backed up, with a tested ability to restore it?",
        "help_text": "A backup nobody has ever tried to restore from is a weaker answer than 'yes'.",
    },
    {
        "key": "joiner_mover_leaver",
        "area": "Access removal",
        "question": "Is access removed promptly when someone leaves or changes role (joiner/mover/leaver)?",
        "help_text": "Covers accounts, shared logins and access to systems/data, not just email.",
    },
    {
        "key": "privileged_access_separation",
        "area": "Privileged access",
        "question": "Is privileged/admin access kept separate from everyday user accounts and restricted to those who need it?",
        "help_text": "E.g. admins use a distinct admin account rather than day-to-day email login for admin tasks.",
    },
    {
        "key": "security_awareness_training",
        "area": "Staff awareness",
        "question": "Do staff receive security-awareness/phishing education?",
        "help_text": "Any regular, even informal, awareness activity counts - this is not asking for a formal LMS.",
    },
    {
        "key": "incident_reporting_route",
        "area": "Incident reporting",
        "question": "Is there a known route for staff to report and handle suspected security incidents?",
        "help_text": "E.g. staff know who to tell if they click a bad link or lose a device.",
    },
    {
        "key": "email_phishing_protection",
        "area": "Email/phishing protection",
        "question": "Are there protections in place against common email/phishing threats?",
        "help_text": "E.g. spam/phishing filtering, link/attachment scanning, or platform-native protections.",
    },
    {
        "key": "remote_access_control",
        "area": "Remote access",
        "question": "Is there basic control over remote access, where remote/hybrid working applies?",
        "help_text": "E.g. VPN, conditional access, or equivalent control over how systems are reached remotely.",
    },
]

CATALOGUE_BY_KEY = {item["key"]: item for item in CATALOGUE}
CATALOGUE_KEYS = list(CATALOGUE_BY_KEY.keys())

assert len(CATALOGUE_KEYS) == len(CATALOGUE), "Catalogue question keys must be unique."
