import re

from rest_framework import serializers


def validate_doi(value: str) -> str:
    """Validate DOI format."""
    if value:
        doi_pattern = re.compile(r"^10\.\d{4,9}/[-._;()/:A-Z0-9]+$", re.I)
        if not doi_pattern.match(value.strip()):
            raise serializers.ValidationError("Invalid DOI format.")
    return value


def validate_url(value: str) -> str:
    """Validate URL format."""
    if value:
        url_pattern = re.compile(
            r"^(https?://)"
            r"(([A-Z0-9][A-Z0-9_-]*)(\.[A-Z0-9][A-Z0-9_-]*)+)"
            r"(:\d+)?"
            r"(/.*)?$",
            re.IGNORECASE,
        )
        if not url_pattern.match(value.strip()):
            raise serializers.ValidationError("Invalid URL format.")
    return value


def validate_doi_link_consistency(attrs):
    """Ensure consistency between DOI and link fields."""
    doi = attrs.get("doi")
    link = attrs.get("link")

    if doi and not link:
        raise serializers.ValidationError(
            {"link": "A link is required when a DOI is provided."}
        )

    if link and not doi:
        if not (
            link.startswith("http://127.0.0.1")
            or link.startswith("http://localhost")
            or link.startswith("http://mousetube.fr")
            or "/media/" in link
        ):
            raise serializers.ValidationError(
                {"doi": "A DOI is required when providing an external link."}
            )
    return attrs
