"""Signup, login/logout and the profile page."""

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from .forms import LoginForm, ProfileForm, SignUpForm, UserDetailsForm
from .models import Profile


def signup(request):
    """Create an account and log the customer straight in."""
    if request.user.is_authenticated:
        return redirect("menu:home")

    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(
                request,
                f"Welcome to Samzic Foods Empire, {user.username}! "
                "Add your delivery details so checkout is one tap.",
            )
            # Straight to the profile page: an empty address blocks checkout.
            return redirect("accounts:profile")
    else:
        form = SignUpForm()

    return render(request, "accounts/signup.html", {"form": form})


class CustomLoginView(LoginView):
    """Built-in login flow with our Tailwind-styled form."""

    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        messages.success(self.request, f"Welcome back, {form.get_user().username}.")
        return super().form_valid(form)

    def form_invalid(self, form):
        # No messages.error here — the template renders an error summary inside
        # the card, and a flash saying the same thing twice reads as two faults.
        return super().form_invalid(form)


class CustomLogoutView(LogoutView):
    """POST-only logout (Django 5 no longer allows GET)."""

    next_page = reverse_lazy("menu:home")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            messages.info(request, "You have been logged out. Come back hungry!")
        return super().dispatch(request, *args, **kwargs)


@login_required
def profile(request):
    """View and edit delivery details — the source of truth for checkout."""
    # get_or_create covers users made before the signal existed (e.g. fixtures).
    profile_obj, _ = Profile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        profile_form = ProfileForm(request.POST, instance=profile_obj)
        user_form = UserDetailsForm(request.POST, instance=request.user)
        if profile_form.is_valid() and user_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, "Your profile has been updated.")
            return redirect("accounts:profile")
        messages.error(request, "Please correct the highlighted fields.")
    else:
        profile_form = ProfileForm(instance=profile_obj)
        user_form = UserDetailsForm(instance=request.user)

    context = {
        "profile_form": profile_form,
        "user_form": user_form,
        "profile": profile_obj,
    }
    return render(request, "accounts/profile.html", context)
