"""Views for the About, Catering and Contact pages."""

from django.contrib import messages
from django.shortcuts import redirect, render

from .forms import CateringRequestForm, ContactMessageForm


def about(request):
    """Static story page."""
    return render(request, "pages/about.html")


def catering(request):
    """Catering page with the quote request form."""
    if request.method == "POST":
        form = CateringRequestForm(request.POST)
        if form.is_valid():
            enquiry = form.save()
            messages.success(
                request,
                f"Thanks {enquiry.full_name.split()[0]} — your request is in. "
                "We reply with a full quote within 24 hours.",
            )
            # Redirect after POST so a refresh cannot resubmit the enquiry.
            return redirect("pages:catering")
        messages.error(request, "Please check the highlighted fields and try again.")
    else:
        form = CateringRequestForm(initial=_profile_initial(request))

    return render(request, "pages/catering.html", {"form": form})


def contact(request):
    """Contact page with the general enquiry form."""
    if request.method == "POST":
        form = ContactMessageForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(
                request, "Message sent — we usually reply within a few hours."
            )
            return redirect("pages:contact")
        messages.error(request, "Please check the highlighted fields and try again.")
    else:
        form = ContactMessageForm(initial=_profile_initial(request))

    return render(request, "pages/contact.html", {"form": form})


def _profile_initial(request):
    """Prefill name/email/phone for a signed-in customer.

    Anonymous visitors get an empty form; there is nothing to prefill from.
    """
    user = request.user
    if not user.is_authenticated:
        return {}

    initial = {
        "full_name": user.get_full_name() or user.username,
        "email": user.email,
    }
    profile = getattr(user, "profile", None)
    if profile:
        initial["full_name"] = profile.full_name or initial["full_name"]
        initial["phone_number"] = profile.phone_number
    return initial
