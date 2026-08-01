"""Every custom error page must render with DEBUG=False.

These templates are only reachable in production, which is exactly where a
TemplateSyntaxError in one of them is most expensive: the handler raises while
handling an error, and the visitor gets Django's bare fallback instead.
"""

from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase, override_settings


@override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"])
class ErrorPageRequestTests(TestCase):
    """Full request cycle. Needs a database: base.html's context processors
    touch the session and the cart."""

    def test_404_renders_branded_page(self):
        response = self.client.get("/no-such-page-exists/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "This plate", status_code=404)

    def test_favicon_ico_redirects_to_static(self):
        response = self.client.get("/favicon.ico")
        self.assertEqual(response.status_code, 301)
        self.assertIn("favicon.ico", response["Location"])


class ErrorTemplateTests(SimpleTestCase):
    """Templates render standalone — catches a syntax error in a page that is
    only ever reached when something else has already gone wrong."""

    def test_403_template_renders(self):
        self.assertIn("That door stays shut", render_to_string("403.html"))

    def test_400_template_renders(self):
        self.assertIn("couldn", render_to_string("400.html"))

    def test_csrf_template_renders(self):
        self.assertIn("went cold", render_to_string("403_csrf.html"))

    def test_500_template_renders_without_context(self):
        """500.html must not depend on context processors or the database."""
        self.assertGreater(len(render_to_string("500.html")), 100)


@override_settings(DEBUG=True, BRANDED_ERROR_PAGES=True, ALLOWED_HOSTS=["testserver"])
class BrandedErrorPagesInDebugTests(TestCase):
    """The middleware exists so developers see the real pages, not Django's
    yellow debug page. Without it the branded templates are unreachable until
    the site is deployed, which is the wrong time to find a mistake in them."""

    def test_404_is_branded_even_with_debug_on(self):
        response = self.client.get("/no-such-page-exists/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "This plate", status_code=404)
        self.assertNotContains(response, "Using the URLconf", status_code=404)

    def test_ajax_404_is_left_alone(self):
        """app.js expects a small response, not a full page of storefront HTML."""
        response = self.client.get(
            "/no-such-page-exists/", headers={"x-requested-with": "XMLHttpRequest"}
        )
        self.assertEqual(response.status_code, 404)
        self.assertNotContains(response, "This plate", status_code=404)

    def test_admin_404_keeps_django_behaviour(self):
        response = self.client.get("/admin/no-such-admin-page/")
        self.assertNotContains(response, "This plate", status_code=404)

    @override_settings(BRANDED_ERROR_PAGES=False)
    def test_opt_out_restores_the_debug_page(self):
        """Turning it off must give back the URLconf listing, which is the
        reason someone would turn it off."""
        # MiddlewareNotUsed is evaluated when the chain is built, so the
        # override needs a fresh handler.
        from django.test import Client

        response = Client().get("/no-such-page-exists/")
        self.assertNotContains(response, "This plate", status_code=404)
