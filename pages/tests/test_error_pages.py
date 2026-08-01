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
