"""Create (or repair) the admin account from environment variables.

Usage::

    python manage.py seed_superuser                    # read ADMIN_USERNAME/ADMIN_PASSWORD
    python manage.py seed_superuser --reset-password   # also reset an existing account

Why a command and not ``createsuperuser``: the built-in one is interactive, and
its ``--noinput`` mode still cannot set a password. Deployments have no TTY, so
the admin account has to come from configuration. Re-running is safe — an
existing account is promoted to staff/superuser rather than duplicated, and the
password is left alone unless ``--reset-password`` is passed.

``ADMIN_USERNAME`` may be an email address (Django allows ``@ . + - _`` in
usernames). When it is, the email field is filled in from it too.
"""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import transaction

import environ

env = environ.Env()


class Command(BaseCommand):
    help = "Create or update the superuser defined by ADMIN_USERNAME / ADMIN_PASSWORD."

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            default=None,
            help="Override ADMIN_USERNAME.",
        )
        parser.add_argument(
            "--password",
            default=None,
            help="Override ADMIN_PASSWORD. Prefer the environment variable.",
        )
        parser.add_argument(
            "--email",
            default=None,
            help="Override the email. Defaults to ADMIN_USERNAME when that is an address.",
        )
        parser.add_argument(
            "--reset-password",
            action="store_true",
            help="Reset the password on an account that already exists.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()

        username = options["username"] or env("ADMIN_USERNAME", default="")
        password = options["password"] or env("ADMIN_PASSWORD", default="")

        if not username or not password:
            raise CommandError(
                "ADMIN_USERNAME and ADMIN_PASSWORD must both be set "
                "(in .env locally, or in the Vercel environment variables)."
            )

        email = options["email"]
        if email is None:
            # An email in ADMIN_USERNAME is the common case here, so use it for
            # both fields rather than leaving the account without an address.
            try:
                validate_email(username)
                email = username
            except ValidationError:
                email = ""

        user = User.objects.filter(username=username).first()

        if user is None:
            User.objects.create_superuser(
                username=username, email=email, password=password
            )
            self.stdout.write(
                self.style.SUCCESS(f"Created superuser {username!r}.")
            )
            return

        changed = []
        if not user.is_staff:
            user.is_staff = True
            changed.append("is_staff")
        if not user.is_superuser:
            user.is_superuser = True
            changed.append("is_superuser")
        if not user.is_active:
            user.is_active = True
            changed.append("is_active")
        if email and user.email != email:
            user.email = email
            changed.append("email")
        if options["reset_password"]:
            user.set_password(password)
            changed.append("password")

        if changed:
            user.save()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Updated existing account {username!r} ({', '.join(changed)})."
                )
            )
        else:
            self.stdout.write(
                f"Superuser {username!r} already exists and is correctly configured. "
                "Pass --reset-password to change the password."
            )
