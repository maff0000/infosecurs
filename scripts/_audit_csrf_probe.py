from django.test import Client
from django.contrib.auth import get_user_model
from organisations.models import Organisation

User = get_user_model()
org = Organisation.objects.get(name="Infosecurs Limited")
user = User.objects.get(username="customerzero")

c = Client(enforce_csrf_checks=True, SERVER_NAME="127.0.0.1")
resp_get = c.get(f"/organisations/{org.id}/dev-tools/reset/")
print("anon GET status:", resp_get.status_code)

c.force_login(user)
resp_get2 = c.get(f"/organisations/{org.id}/dev-tools/reset/")
print("auth GET status:", resp_get2.status_code)
csrftoken = c.cookies.get("csrftoken")
print("csrftoken cookie:", csrftoken.value if csrftoken else None)

resp_post = c.post(
    f"/organisations/{org.id}/dev-tools/reset/",
    {"confirmation": "RESET", "csrfmiddlewaretoken": csrftoken.value if csrftoken else ""},
)
print("auth POST status:", resp_post.status_code)
print(resp_post.content[:800])
