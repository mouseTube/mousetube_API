"""The database schema page of the documentation follows the models (docs/assets/schema/).

A table or a field added, renamed or removed in `models.py` without the page fails here; so does a
description left as TODO, and an English page that differs from the French one. `python manage.py
sync_schema_docs` does the structure; the descriptions are written by hand.
"""

import json

from django.test import SimpleTestCase

from mousetube_api.utils import schema_docs


class DocumentedSchemaTests(SimpleTestCase):
    def test_the_page_follows_the_models(self):
        problems = schema_docs.check()
        self.assertEqual(
            problems,
            [],
            "run `python manage.py sync_schema_docs`, then write the TODO descriptions "
            "(docs/assets/schema/schema-en.json and schema-fr.json)",
        )

    def test_sync_adds_what_is_new_and_removes_what_is_gone(self):
        for lang in schema_docs.LANGUAGES:
            data = json.loads(json.dumps(schema_docs.read(lang)))
            tables = {t["id"]: t for t in data["tables"]}
            diet = next(f for f in tables["AnimalProfile"]["fields"] if f[0] == "diet")
            tables["AnimalProfile"]["fields"].remove(diet)  # a field that is new
            data["tables"].remove(tables["PageView"])  # a table that is new
            tables["File"]["fields"].append(
                ["gone", "text", "", "no more"]
            )  # one that is gone
            tables["Strain"]["fields"][0][1] = "int"  # a type that changed

            changes = schema_docs.sync(data, lang)

            self.assertTrue(
                any("AnimalProfile.diet: field not described" in c for c in changes)
            )
            self.assertTrue(any("PageView: table not described" in c for c in changes))
            self.assertTrue(
                any("File.gone: the field no longer exists" in c for c in changes)
            )
            self.assertTrue(
                any("Strain.name" in c and "should be" in c for c in changes)
            )
            tables = {t["id"]: t for t in data["tables"]}
            # what is new is there, with a description to write; what is gone is not
            self.assertIn("diet", [f[0] for f in tables["AnimalProfile"]["fields"]])
            self.assertIn("PageView", tables)
            self.assertTrue(tables["PageView"]["note"].startswith("TODO"))
            self.assertNotIn("gone", [f[0] for f in tables["File"]["fields"]])
            self.assertEqual(tables["Strain"]["fields"][0][1], "char(255)")
            # the words that were written stay, and what is left to write is told
            again = schema_docs.sync(data, lang, apply=False)
            self.assertTrue(any(c.endswith("describe the field") for c in again))
            self.assertFalse(any("not described" in c for c in again))
