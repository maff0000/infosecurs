"""
Deliberately no models here (PID §2, §7).

`security_state` is a read-only aggregation/projection layer over
`security_baseline.BaselineAnswer`, `evidence.ControlEvidenceLink`/
`EvidenceItem` and `remediation.RemediationAction` - see
`security_state/services.py`'s `get_security_state`. It must never become
a second editable control-truth store (PID §2 "Do not create a second
editable security-control truth store"), so this app defines no
database table of its own. Nothing in this app calls `.save()`,
`.create()`, `.update()` or `.delete()` against any model.
"""
