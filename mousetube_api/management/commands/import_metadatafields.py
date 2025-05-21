import json
from pathlib import Path

from django.core.management.base import BaseCommand
from mousetube_api.models import MetadataCategory, MetadataField


class Command(BaseCommand):
    help = "Load metadata categories and fields from JSON schemas (recursive parser)"

    def handle(self, *args, **kwargs):
        schema_dir = Path("static/json/schemas/")
        if not schema_dir.exists():
            self.stderr.write("❌ Schema directory does not exist.")
            return

        for json_file in schema_dir.glob("*.json"):
            source = json_file.stem
            self.stdout.write(f"📂 Processing {json_file.name}...")

            with open(json_file, encoding="utf-8") as f:
                try:
                    schema = json.load(f)
                except json.JSONDecodeError as e:
                    self.stderr.write(f"❌ JSON error in {json_file.name}: {e}")
                    continue

            # Start recursive parsing
            self._parse_node(schema, parent_category=None, source=source)

        self.stdout.write(self.style.SUCCESS("✅ All metadata schemas loaded."))

    def _parse_node(self, node, parent_category, source, current_name=None):
        """
        Recursive function to parse the schema node.
        Creates MetadataCategory for objects, and MetadataField for properties.
        """
        node_type = node.get("type")
        description = node.get("description", "")
        properties = node.get("properties", {})

        if node_type == "object" and properties:
            category_name = current_name or node.get("title", "Root")
            category, _ = MetadataCategory.objects.get_or_create(
                name=category_name,
                source=source,
                defaults={"description": description}
            )
            if description and not category.description:
                category.description = description
                category.save()

            # Link to parent if provided
            if parent_category:
                category.parents.add(parent_category)

            # Recurse into each subproperty
            for prop_name, prop_node in properties.items():
                self._parse_node(prop_node, parent_category=category, source=source, current_name=prop_name)

        else:
            # Terminal field
            field_name = current_name
            if not field_name:
                return  # skip if no name

            field, _ = MetadataField.objects.get_or_create(
                name=field_name,
                source=source,
                defaults={"description": description}
            )
            if description and not field.description:
                field.description = description
                field.save()

            if parent_category:
                field.metadata_category.add(parent_category)