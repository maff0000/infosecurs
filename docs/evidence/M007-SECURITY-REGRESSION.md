# M007 — Security Regression (Index)

**Authorising commit:** `fb5be593131fde51d4fc2aafce268f64a5816850`.

This is a short index, not a duplicate write-up. M007's security
regression evidence was produced across several WI6 dispatches, each
already landed as its own durable, detailed evidence file. Rather than
copy their content here (risking drift between two descriptions of the
same proof), this file records **which document proves which security
property**, so every gate is recoverable from a single starting point.

| Security property | Proven in | Method |
|---|---|---|
| Full tier matrix (PAUSED/FOUNDATION/MONTHLY/PRO), direct/copied URL probes, POST-only/nested-object routes | `docs/evidence/M007-SESSION-ENTITLEMENTS.md` (Part A.1) | Real Django `Client` requests, fresh Engineer dispatch + PL independent reproduction |
| Client-side spoofing (forged header/query/cookie/POST-body) has zero effect, including a structural (`inspect.getsource`) proof that the entitlement decision functions never reference client-supplied request data at all | `docs/evidence/M007-SESSION-ENTITLEMENTS.md` (Part A.2) | Real requests + source inspection |
| Tenant/object isolation across every organisation-scoped app, including a genuinely non-member-of-either-organisation PRO-tier client | `docs/evidence/M007-SESSION-ENTITLEMENTS.md` (Part A.3) | Real `org_a`/`org_b`/`org_c` fixtures, real cross-tenant requests |
| Active-organisation alignment (session realignment + key rotation + tier/code preservation, both directions) | `docs/evidence/M007-SESSION-ENTITLEMENTS.md` (Part A.4) | Real dual-membership client, real session inspection |
| Logout destroys access; replayed old session cookie denied across 9 real routes; fresh login issues a genuinely different session key reflecting only the real default tier | `docs/evidence/M007-SESSION-ENTITLEMENTS.md` (Part A.5) | Real POST logout, real session-store row-deletion check, real cookie replay |
| Invalid session matrix (every required field missing individually, bool-tier type confusion) at the route level | `docs/evidence/M007-SESSION-ENTITLEMENTS.md` (Part A.6) | Real requests with tampered session contexts |
| Real-browser XSS execution challenge on the one new M007 customer-controlled surface (`organisation.name` in the new Home/Foundations page-header subtitle), with explicit reasoning for why every pre-existing surface is confirmed-unchanged rather than re-executed | `docs/evidence/M007-BROWSER-ACCEPTANCE.md` (Part 5) | Real Chromium, execution-sentinel + DOM inspection, per the established M006 methodology |
| Sidebar/hamburger drawer: same server-rendered, entitlement-filtered markup at desktop and narrow widths; no unauthorised item reachable via DOM manipulation of presentation state | `docs/evidence/M007-BROWSER-ACCEPTANCE.md` (Part 3) | Real Chromium, DOM comparison |
| CSRF: real logout is a POST with a valid CSRF token; every state-changing form in the shell/Home/Foundations uses the existing, unmodified CSRF machinery — no new form/endpoint introduced by M007 bypasses it | `docs/evidence/M007-SESSION-ENTITLEMENTS.md` (Part A.5's real logout POST) and by construction (no new state-changing endpoint exists in M007 beyond the ones already covered by WI3's route-guard proof) | Real POST requests |
| Safe errors: no stack trace/secret/internal path in a 403 response | `entitlements/decorators.py`'s own `PermissionDenied` → Django's existing, independently-tested branded `templates/403.html` (`core/tests/test_error_pages.py`, pre-existing, unmodified, still green throughout M007) | Existing, still-passing test suite |
| Release-image security scan | `docs/evidence/M007-RELEASE.md` (§9) | Trivy 0.70.0, CRITICAL+HIGH, 0 findings |
| Secret never baked into the release image | `docs/evidence/M007-RELEASE.md` (§7) | Direct byte-level grep of the exported image tar |

## What genuinely changed vs. what was re-proven

M007 did not touch CSRF handling, session-cookie security flags,
password/authentication validators, or the existing branded error-page
templates at all — those remain exactly as M006 hardened them, still
covered by their own pre-existing, still-green test suites throughout
every WI1-WI6 full-suite run (`1806` → `1852` → final counts, all
independently reproduced by the PL, zero regressions in any pre-existing
security-relevant test). What M007 genuinely added to the security
surface — the entitlement decorator, the session realignment/rotation
step, the new Home/Foundations routes and their one new customer-
controlled rendering location — is exactly what the table above
independently re-proves, fresh, against the final merged source.

See `docs/evidence/M007-AUDIT-0001.md` for the fresh, zero-context
Auditor's own independent security testing and verdict — that document,
not this index, is the final word on whether anything here was missed.
