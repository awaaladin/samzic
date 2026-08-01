"""Throwaway verification for the signup rebuild, flash restyle and no-reload work."""

import json
import os
import re

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.test.utils import setup_test_environment

setup_test_environment()

from django.test import Client  # noqa: E402

from menu.models import FoodItem  # noqa: E402

results = []


def check(label, condition, detail=""):
    results.append((label, bool(condition), detail))


c = Client()

# --- Signup / login templates -------------------------------------------------
r = c.get("/accounts/signup/")
html = r.content.decode()
check("signup 200", r.status_code == 200, str(r.status_code))
check(
    "signup has no raw validator <ul> dump",
    "Your password can&#x27;t be too similar" not in html
    and "Your password must contain at least 8 characters" not in html,
)
check(
    "signup shows designed rules checklist",
    all(f'data-rule="{name}"' in html for name in ("len", "notnum", "notname", "common")),
)
check("signup has autocomplete=new-password", 'autocomplete="new-password"' in html)

r = c.post("/accounts/signup/", {"username": "x", "email": "nope", "password1": "a", "password2": "b"})
html = r.content.decode()
check("signup invalid re-renders 200", r.status_code == 200, str(r.status_code))
check("signup shows error summary", "We could not create the account yet" in html)

r = c.get("/accounts/login/")
check("login 200", r.status_code == 200, str(r.status_code))
r = c.post("/accounts/login/", {"username": "nobody", "password": "wrong"})
html = r.content.decode()
check("login invalid shows summary", "That did not let you in" in html)
check(
    "login invalid raises no duplicate flash",
    html.count("Invalid username or password") == 0,
)

# --- Flash stack --------------------------------------------------------------
r = c.get("/")
html = r.content.decode()
check("flash stack mount point present", 'id="flash-stack"' in html)
check("cart count hook present", "data-cart-count" in html)
check("app.js script tag present", "js/app.js" in html)
check("CART_MAX_QUANTITY exposed", re.search(r"window\.CART_MAX_QUANTITY = \d+", html))

# --- Static asset actually serves --------------------------------------------
# Deliberately not tested here: Django's test Client does not route /static/,
# so a GET always 404s even when the file is on disk and staticfiles is wired.
# Verified against the running server with curl instead.

# --- Cart JSON contract -------------------------------------------------------
item = FoodItem.objects.filter(available=True).first()
c2 = Client()
r = c2.post(
    f"/cart/add/{item.id}/",
    {"quantity": 2, "with_summary": 1},
    headers={"x-requested-with": "XMLHttpRequest"},
)
check("cart add returns JSON", r["Content-Type"].startswith("application/json"), r["Content-Type"])
data = r.json()
check("payload ok", data.get("ok") is True)
check("payload count", data.get("count") == 2, str(data.get("count")))
check("payload has totals", set(data.get("totals", {})) >= {"subtotal", "delivery_fee", "total"})
check("payload has rows keyed by id", str(item.id) in data.get("rows", {}))
check("payload carries summary_html", "summary_html" in data and "&#8358;" in data["summary_html"])
check("payload message", bool(data.get("message")), data.get("message", ""))

r = c2.post(
    f"/cart/update/{item.id}/",
    {"quantity": 5, "with_summary": 1},
    headers={"x-requested-with": "XMLHttpRequest"},
)
check("cart update JSON count", r.json().get("count") == 5, str(r.json().get("count")))

r = c2.post(f"/cart/remove/{item.id}/", headers={"x-requested-with": "XMLHttpRequest"})
data = r.json()
check("cart remove reports removed_id", str(data.get("removed_id")) == str(item.id))
check("cart remove marks empty", data.get("empty") is True)

# --- No-JS path unchanged -----------------------------------------------------
c3 = Client()
r = c3.post(f"/cart/add/{item.id}/", {"quantity": 1})
check("cart add without header still redirects", r.status_code == 302, str(r.status_code))

r = c3.get("/cart/")
html = r.content.decode()
check("cart row is one form per line", html.count("data-cart-form data-item=") == 1)
check("cart page also has the clear-cart form", html.count("data-cart-form") == 2)
# At quantity 1 both the minus button and Remove point at the remove endpoint.
check("row buttons carry formaction", html.count('formaction="/cart/remove/') == 2)
check("cart summary partial rendered", 'id="cart-summary"' in html and "Subtotal" in html)
check("cart empty state present but hidden", 'id="cart-empty"' in html)

# --- Menu region ids ----------------------------------------------------------
r = c.get("/menu/")
html = r.content.decode()
for region in ["menu-grid", "menu-count", "menu-pagination", "menu-filters", "menu-heading"]:
    check(f"menu region #{region}", f'id="{region}"' in html)
check("sort select has no inline onchange", "onchange=\"this.form.submit()\"" not in html)
check("food card forms hooked", 'data-cart-form' in html)

# --- Report -------------------------------------------------------------------
passed = sum(1 for _, ok, _ in results if ok)
for label, ok, detail in results:
    print(f"{'PASS' if ok else 'FAIL'}  {label}{('  -> ' + str(detail)) if detail and not ok else ''}")
print(f"\n{passed}/{len(results)} checks passed")
