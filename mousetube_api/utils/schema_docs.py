"""The database schema page of the documentation, kept in step with the models.

The page (`docs/assets/schema/`) draws one card per table from `schema-en.json` and `schema-fr.json`. What
is *structure* (the tables, the fields, their type, null, unique, the table a link points to) is read
from the models here; what is *words* (the description of a table and of a field) is written by hand.
`sync` brings the structure up to date and leaves the words alone; a field or a table that is new gets a
`TODO` description, and the test fails until it is written.

    python manage.py sync_schema_docs          # update both files, then write the TODO descriptions
    python manage.py sync_schema_docs --check  # only say what differs (what the test does)
"""

import json
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.db import models

SCHEMA_DIR = Path(settings.BASE_DIR) / "docs" / "assets" / "schema"
LANGUAGES = ("en", "fr")
TODO = {
    "en": "TODO: describe this field.",
    "fr": "TODO : décrire ce champ.",
}
TODO_TABLE = {"en": "TODO: describe this table.", "fr": "TODO : décrire cette table."}
# in the page but not a column of its table
NOT_COLUMNS = {"Favorite": {"content_object"}}
# a column of a table of Django that is not shown
NOT_SHOWN = {"User": {"groups", "user_permissions"}}
# where a table that is new is drawn until somebody places it (family, column)
NEW_TABLE_PLACE = ("oth", 5)
# links that are not drawn: every table has one, it would hide the schema
NOT_DRAWN = {"created_by"}


def file_of(lang):
    return SCHEMA_DIR / f"schema-{lang}.json"


def read(lang):
    return json.loads(file_of(lang).read_text(encoding="utf-8"))


def write(lang, data):
    file_of(lang).write_text(
        json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )


def documented_models():
    """The models whose table is in the page: those of the API and the Django user."""
    return [
        m
        for m in apps.get_models()
        if m._meta.app_label == "mousetube_api"
        or (m._meta.app_label == "auth" and m.__name__ == "User")
    ]


def column_type(field):
    """The type written in a card: `char(255)`, `datetime`, `fk → User`, `M2M → Hardware`..."""
    from django_countries.fields import CountryField

    if field.many_to_many:
        return f"M2M → {field.related_model.__name__}"
    if field.is_relation:
        return f"fk → {field.related_model.__name__}"
    # the subclasses before their parents (an e-mail is a char, a datetime is a date...)
    ordered = [
        (CountryField, "country"),
        (models.EmailField, "email"),
        (models.URLField, "url"),
        (models.CharField, f"char({getattr(field, 'max_length', '')})"),
        (models.TextField, "text"),
        (models.BooleanField, "bool"),
        (models.DateTimeField, "datetime"),
        (models.DateField, "date"),
        (models.ImageField, "image"),
        (models.FileField, "file"),
        (models.JSONField, "json"),
        (models.FloatField, "float"),
        (models.PositiveBigIntegerField, "biguint"),
        (models.PositiveSmallIntegerField, "smallint"),
        (models.PositiveIntegerField, "uint"),
        (models.BigIntegerField, "bigint"),
        (models.SmallIntegerField, "smallint"),
        (models.IntegerField, "int"),
    ]
    for kind, label in ordered:
        if isinstance(field, kind):
            return label
    return field.get_internal_type().lower()


def column_flags(field):
    """`u` unique, `n` may be empty (null), `f` foreign key, `m` many to many, `o` one to one."""
    flags = ""
    # `created_by` is on every table: its badge would only be noise (the link is not drawn either)
    if field.is_relation and not field.many_to_many and field.name not in NOT_DRAWN:
        flags += "f"
    if isinstance(field, models.OneToOneField):
        flags += "o"
    if field.many_to_many:
        flags += "m"
    if getattr(field, "unique", False) and not field.primary_key and not flags:
        flags += "u"
    if field.null and not field.many_to_many and "o" not in flags:
        flags += "n"
    return flags


def describe(model):
    """The columns of a model as the page wants them: `{name: (type, flags, target)}`, in order."""
    names = {m.__name__ for m in documented_models()}
    out = {}
    for field in model._meta.get_fields():
        if not (field.concrete or field.many_to_many) or field.auto_created:
            continue
        if field.name == "id" or field.name in NOT_SHOWN.get(model.__name__, set()):
            continue
        target = None
        if field.is_relation and field.name not in NOT_DRAWN:
            related = field.related_model.__name__
            target = related if related in names else None
        out[field.name] = (column_type(field), column_flags(field), target)
    return out


def _names(row):
    return [part.strip() for part in row[0].split("·")]


def _row(name, structure, description):
    kind, flags, target = structure
    row = [name, kind, flags, description]
    if target:
        row.append(target)
    return row


def _structure(row):
    return (row[1], row[2], row[4] if len(row) > 4 else None)


def sync(data, lang, apply=True):
    """Bring `data` (the content of schema-<lang>.json) in step with the models.

    Args:
        data (dict): `{"ui": ..., "tables": [...]}`, changed in place when `apply` is true.
        lang (str): `en` or `fr`, the language of the descriptions to add.
        apply (bool): change `data`; when false, only list what would change.

    Returns:
        list[str]: what differs, empty when the page follows the models: a table or a field to add or
            remove, a type that changed, a description still to write.
    """
    problems = []
    tables = {t["id"]: t for t in data["tables"]}
    wanted = {m.__name__: m for m in documented_models()}
    for name in [n for n in tables if n not in wanted]:
        problems.append(f"{name}: the table no longer exists")
        if apply:
            data["tables"].remove(tables.pop(name))
    for name, model in wanted.items():
        columns = describe(model)
        table = tables.get(name)
        if table is None:
            problems.append(f"{name}: table not described")
            if apply:
                family, col = NEW_TABLE_PLACE
                table = {
                    "id": name,
                    "g": family,
                    "col": col,
                    "note": TODO_TABLE[lang],
                    "fields": [],
                }
                data["tables"].append(table)
                tables[name] = table
            else:
                continue
        if table["note"].startswith("TODO"):
            problems.append(f"{name}: describe the table")
        known = {n for row in table["fields"] for n in _names(row)}
        extra = NOT_COLUMNS.get(name, set())
        for row in list(table["fields"]):
            names = _names(row)
            gone = [n for n in names if n not in columns and n not in extra]
            if gone and len(gone) == len(names):
                problems.append(f"{name}.{', '.join(gone)}: the field no longer exists")
                if apply:
                    table["fields"].remove(row)
            elif gone:
                problems.append(
                    f"{name}.{', '.join(gone)}: edit the combined row by hand"
                )
            elif len(names) == 1 and names[0] in columns:
                structure = columns[names[0]]
                if _structure(row) != structure:
                    problems.append(
                        f"{name}.{names[0]}: {_structure(row)} should be {structure}"
                    )
                    if apply:
                        row[1:3] = [structure[0], structure[1]]
                        del row[4:]
                        if structure[2]:
                            row.append(structure[2])
            if row[3].startswith("TODO"):
                problems.append(f"{name}.{', '.join(names)}: describe the field")
        for field, structure in columns.items():
            if field in known:
                continue
            problems.append(f"{name}.{field}: field not described")
            if apply:
                help_text = ""
                if lang == "en":
                    help_text = str(
                        model._meta.get_field(field).help_text or ""
                    ).strip()
                table["fields"].append(_row(field, structure, help_text or TODO[lang]))
    return problems


def check():
    """What differs between the models and the two files, and between the two files."""
    problems = []
    shapes = {}
    for lang in LANGUAGES:
        data = json.loads(json.dumps(read(lang)))
        problems += [f"[{lang}] {p}" for p in sync(data, lang, apply=False)]
        shapes[lang] = [
            (
                t["id"],
                t["g"],
                t["col"],
                [tuple(f[:3]) + tuple(f[4:]) for f in t["fields"]],
            )
            for t in data["tables"]
        ]
    if shapes["en"] != shapes["fr"]:
        problems.append(
            "the English and the French pages do not have the same tables and fields"
        )
    return problems
