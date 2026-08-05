"""Error handlers.

Django only routes to these when DEBUG=False. To preview them locally, see the
"Previewing error pages" note in README.md.
"""

from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render


def page_not_found(request, exception):  # noqa: ARG001 - signature fixed by Django
    return render(request, "404.html", status=404)


def permission_denied(request, exception):  # noqa: ARG001 - signature fixed by Django
    return render(request, "403.html", status=403)


def bad_request(request, exception):  # noqa: ARG001 - signature fixed by Django
    return render(request, "400.html", status=400)


def csrf_failure(request, reason=""):  # noqa: ARG001 - signature fixed by Django
    """Rendered when a POST arrives with a bad or missing CSRF token.

    Django's default is an unstyled debug page, and the usual cause is benign —
    a form left open until the token expired — so this explains the fix rather
    than implying wrongdoing. Wired via CSRF_FAILURE_VIEW in settings.
    """
    return render(request, "403_csrf.html", status=403)


@staff_member_required
def control_room(request):
    context = admin.site.each_context(request)
    try:
        context["dashboard"] = admin.site.dashboard_stats()
    except Exception:
        context["dashboard"] = None
    context["title"] = "Control room"
    return render(request, "admin/control_room.html", context)


@staff_member_required
def change_history(request):
    """Site-wide admin audit trail — savory-serve's admin/history.html.

    Django records every admin add/change/delete in LogEntry but only exposes it
    per object, so there is no way to answer "what changed today, and who did
    it". This is that view. It is read-only by design: the log is evidence, and
    editing it would defeat the point.

    Deliberately not named "admin/history.html": that template path is Django's
    own per-object history page, and a file there would shadow it site-wide.
    """
    entries = LogEntry.objects.select_related("user", "content_type").order_by(
        "-action_time"
    )

    query = request.GET.get("q", "").strip()
    if query:
        entries = entries.filter(
            Q(user__username__icontains=query)
            | Q(user__email__icontains=query)
            | Q(object_repr__icontains=query)
            | Q(content_type__model__icontains=query)
            | Q(change_message__icontains=query)
        )

    action = request.GET.get("action", "").strip()
    # Values match LogEntry's ADDITION/CHANGE/DELETION flags (1/2/3).
    if action in {"1", "2", "3"}:
        entries = entries.filter(action_flag=int(action))

    page = Paginator(entries, 50).get_page(request.GET.get("page"))

    context = admin.site.each_context(request)
    context.update(
        {
            "title": "Change history",
            "page_obj": page,
            "query": query,
            "action": action,
            "total": page.paginator.count,
        }
    )
    return render(request, "admin/change_history.html", context)


def server_error(request):
    # Kept context-free on purpose: a 500 means something is already broken, so
    # this template must not depend on context processors or the database.
    return render(request, "500.html", status=500)
