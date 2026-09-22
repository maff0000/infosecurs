from django.contrib.auth.decorators import login_required
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import redirect


def home(request):
    """Entry point: send authenticated users into the product, others to login."""
    if request.user.is_authenticated:
        return redirect("organisations:list")
    return redirect("login")


def healthz(request):
    """Unauthenticated liveness/readiness proof (PID.md §6 runtime scaffold)."""
    db_ok = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        db_ok = False

    status = "ok" if db_ok else "degraded"
    return JsonResponse({"status": status, "database": db_ok}, status=200 if db_ok else 503)
