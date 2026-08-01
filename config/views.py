"""Error handlers.

Django only routes to these when DEBUG=False. To preview them locally, see the
"Previewing error pages" note in README.md.
"""

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


def server_error(request):
    # Kept context-free on purpose: a 500 means something is already broken, so
    # this template must not depend on context processors or the database.
    return render(request, "500.html", status=500)
