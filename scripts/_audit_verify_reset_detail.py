from organisations.models import Organisation, OrganisationMembership, CustomerZeroFixture
from governance.models import OrganisationPerson, GovernanceRoleAssignment

org_a = Organisation.objects.get(name="Infosecurs Limited")
print("Organisation row present:", Organisation.objects.filter(pk=org_a.pk).exists())
print("CustomerZeroFixture present:", CustomerZeroFixture.objects.filter(organisation=org_a).exists())
print("OrganisationMembership count (should be preserved, 2):",
      OrganisationMembership.objects.filter(organisation=org_a).count())
for m in OrganisationMembership.objects.filter(organisation=org_a):
    print("  membership:", m.user, m.role)

people = OrganisationPerson.objects.filter(organisation=org_a)
print("OrganisationPerson count:", people.count())
for p in people:
    print("  person:", p.full_name, "user=", p.user, "active=", p.is_active)

roles = GovernanceRoleAssignment.objects.filter(organisation=org_a)
print("GovernanceRoleAssignment count (should be 3, re-established):", roles.count())
for r in roles:
    print("  role:", r.role, "person=", r.person.full_name)
