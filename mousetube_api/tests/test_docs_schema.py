"""The database schema of the documentation (docs/assets/schema/schema-<lang>.json) follows the
models: a table or a field added, renamed or removed without the page fails here, and the English
and French pages keep the same tables and fields."""

import json
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.test import SimpleTestCase

SCHEMA = Path(settings.BASE_DIR) / "docs" / "assets" / "schema"
# in the page but not a column of the table, or a table of Django that is not documented
NOT_COLUMNS = {"Favorite": {"content_object"}}
NOT_DOCUMENTED = {"User": {"groups", "user_permissions"}}


def load(lang):
    return json.loads((SCHEMA / f"schema-{lang}.json").read_text(encoding="utf-8"))[
        "tables"
    ]


def model_fields():
    found = {}
    for model in apps.get_models():
        label = model._meta.app_label
        if label == "mousetube_api" or (label == "auth" and model.__name__ == "User"):
            found[model.__name__] = {
                f.name
                for f in model._meta.get_fields()
                if (f.concrete or f.many_to_many)
                and not f.auto_created
                and f.name != "id"
            }
    return found


class DocumentedSchemaTests(SimpleTestCase):
    def test_every_table_and_field_of_the_models_is_described(self):
        models = model_fields()
        for lang in ("en", "fr"):
            documented = {
                t["id"]: {name.strip() for f in t["fields"] for name in f[0].split("·")}
                for t in load(lang)
            }
            self.assertEqual(set(documented), set(models), f"tables ({lang})")
            for table, fields in models.items():
                expected = fields - NOT_DOCUMENTED.get(table, set())
                found = documented[table] - NOT_COLUMNS.get(table, set())
                self.assertEqual(
                    found,
                    expected,
                    f"{table} ({lang}): add or remove it in the schema page",
                )

    def test_the_english_and_the_french_pages_describe_the_same_structure(self):
        def shape(tables):
            return [
                (
                    t["id"],
                    t["g"],
                    t["col"],
                    [tuple(f[:3]) + tuple(f[4:]) for f in t["fields"]],
                )
                for t in tables
            ]

        self.assertEqual(shape(load("en")), shape(load("fr")))
