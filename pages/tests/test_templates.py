"""
Guards against a class of bug that has shipped twice: a multi-line ``{# ... #}``.

Django's ``{# #}`` comment is single-line only. When one spans lines the closing
``#}`` is never matched, and the comment text renders to the browser as visible
body copy. Multi-line notes need ``{% comment %} ... {% endcomment %}``.

These tests walk every template on disk, so a new leak fails the suite wherever
it is introduced.
"""

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

TEMPLATE_DIR = Path(settings.BASE_DIR) / "templates"


def template_files():
    return sorted(TEMPLATE_DIR.rglob("*.html"))


class TemplateCommentTests(SimpleTestCase):
    def test_no_multiline_django_comments(self):
        """Every ``{#`` must be closed by ``#}`` on the same line."""
        offenders = []
        for path in template_files():
            for lineno, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                for match in re.finditer(r"\{#", line):
                    if "#}" not in line[match.end():]:
                        rel = path.relative_to(settings.BASE_DIR)
                        offenders.append(f"{rel}:{lineno}: {line.strip()[:70]}")

        self.assertEqual(
            offenders,
            [],
            "Unclosed {# #} comment(s) — these render as visible text. "
            "Use {% comment %}...{% endcomment %} for multi-line notes:\n"
            + "\n".join(offenders),
        )

    def test_comment_tags_are_balanced(self):
        """An unclosed {% comment %} swallows the rest of the page silently."""
        offenders = []
        for path in template_files():
            text = path.read_text(encoding="utf-8")
            opens = len(re.findall(r"\{%\s*comment\s*%\}", text))
            closes = len(re.findall(r"\{%\s*endcomment\s*%\}", text))
            if opens != closes:
                rel = path.relative_to(settings.BASE_DIR)
                offenders.append(f"{rel}: {opens} open, {closes} closed")

        self.assertEqual(offenders, [], "Unbalanced comment tags:\n" + "\n".join(offenders))
