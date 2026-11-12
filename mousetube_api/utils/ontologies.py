"""Controlled vocabularies for some fields, checked at their source.

Terms come from the EBI Ontology Lookup Service (OLS) and, for organizations, from the ROR
registry. The server only talks to these two fixed hosts, with a short timeout, and keeps
the answers for a day. A term is never stored on the word of the browser: it is looked up
at its source first (or already known from a previous lookup).
"""

import hashlib
import re
from urllib.parse import quote

import requests
from django.core.cache import cache

OLS = "https://www.ebi.ac.uk/ols4/api"
ROR = "https://api.ror.org/v2/organizations"
TIMEOUT = 5  # seconds
CACHE_SECONDS = 24 * 3600

# The fields that have a vocabulary, and where it comes from.
FIELDS = {
    "species": {"source": "ols", "ontologies": ["ncbitaxon"], "name": "NCBI Taxonomy"},
    "sex": {"source": "ols", "ontologies": ["pato"], "name": "PATO"},
    "age": {
        "source": "ols",
        "ontologies": ["mmusdv"],
        "name": "Mouse Developmental Stages",
    },
    "treatment": {"source": "ols", "ontologies": ["chebi"], "name": "ChEBI"},
    "behavior": {
        "source": "ols",
        "ontologies": ["nbo"],
        "name": "Neuro Behavior Ontology",
    },
    "organization": {"source": "ror", "ontologies": ["ror"], "name": "ROR registry"},
}

# What sex_term is set to when only the sex ("male" / "female") is given
SEX_TERMS = {
    "male": ("PATO:0000384", "male"),
    "female": ("PATO:0000383", "female"),
}

# Species whose NCBI Taxonomy term is known (checked in the Ontology Lookup Service)
SPECIES_TERMS = {
    "mus musculus": ("NCBITaxon:10090", "Mus musculus"),
    "rattus norvegicus": ("NCBITaxon:10116", "Rattus norvegicus"),
}

# The units of the numeric fields (Units Ontology), for the documentation of the API
UNITS = {
    "sampling_rate": {"unit": "hertz", "curie": "UO:0000106"},
    "duration": {"unit": "second", "curie": "UO:0000010"},
    "context_temperature": {"unit": "degree Celsius", "curie": "UO:0000027"},
    "context_brightness": {"unit": "lux", "curie": "UO:0000116"},
}

# The prefix as the sources write it: OLS looks identifiers up with the exact case
PREFIXES = {
    "ncbitaxon": "NCBITaxon",
    "pato": "PATO",
    "mmusdv": "MmusDv",
    "chebi": "CHEBI",
    "nbo": "NBO",
}

CURIE = re.compile(r"^([A-Za-z][A-Za-z0-9]*):([A-Za-z0-9_.-]+)$")


class OntologyError(Exception):
    """The vocabulary could not answer, or the term does not exist."""


def _get(url, **params):
    key = (
        "onto:" + hashlib.sha256(f"{url}|{sorted(params.items())}".encode()).hexdigest()
    )
    cached = cache.get(key)
    if cached is not None:
        return cached
    try:
        response = requests.get(
            url,
            params=params,
            timeout=TIMEOUT,
            headers={"User-Agent": "mouseTube", "Accept": "application/json"},
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise OntologyError("The vocabulary service did not answer.") from exc
    cache.set(key, data, CACHE_SECONDS)
    return data


def _ror_label(item):
    names = item.get("names") or []
    for kind in ("ror_display", "label"):
        for name in names:
            if kind in (name.get("types") or []):
                return name["value"]
    return names[0]["value"] if names else item["id"].rsplit("/", 1)[-1]


def _ror_place(item):
    place = ((item.get("locations") or [{}])[0]).get("geonames_details") or {}
    return ", ".join(x for x in (place.get("name"), place.get("country_name")) if x)


def search(field, text, rows=10):
    """Terms of the vocabulary of `field` that match `text`: [{curie, label, ...}]."""
    spec = FIELDS[field]
    text = (text or "").strip()
    if len(text) < 2:
        return []
    if spec["source"] == "ror":
        data = _get(ROR, query=text)
        return [
            {
                "curie": "ROR:" + item["id"].rsplit("/", 1)[-1],
                "label": _ror_label(item),
                "ontology": "ror",
                "iri": item["id"],
                "detail": _ror_place(item),
            }
            for item in (data.get("items") or [])[:rows]
        ]
    data = _get(
        f"{OLS}/search",
        q=text,
        ontology=",".join(spec["ontologies"]),
        type="class",
        rows=rows,
        fieldList="iri,label,obo_id,ontology_name",
    )
    docs = (data.get("response") or {}).get("docs") or []
    return [
        {
            "curie": doc["obo_id"],
            "label": doc["label"],
            "ontology": doc["ontology_name"],
            "iri": doc["iri"],
            "detail": "",
        }
        for doc in docs
        if doc.get("obo_id") and doc.get("label")
    ][:rows]


def lookup(field, curie):
    """The term `curie` as its source describes it, or an OntologyError.

    The identifier must belong to one of the vocabularies of `field`.
    """
    spec = FIELDS[field]
    match = CURIE.match(curie or "")
    if not match:
        raise OntologyError(f"'{curie}' is not a term identifier like PATO:0000384.")
    prefix, local = match.group(1).lower(), match.group(2)
    if prefix not in spec["ontologies"]:
        raise OntologyError(
            f"A term of {spec['name']} is expected here, not '{curie}'."
        )
    if spec["source"] == "ror":
        data = _get(f"{ROR}/{quote(local, safe='')}")
        if not data.get("id"):
            raise OntologyError(f"'{curie}' is not in the ROR registry.")
        return {
            "curie": f"ROR:{local}",
            "label": _ror_label(data),
            "ontology": "ror",
            "iri": data["id"],
        }
    data = _get(
        f"{OLS}/ontologies/{prefix}/terms",
        obo_id=f"{PREFIXES.get(prefix, prefix)}:{local}",
    )
    terms = (data.get("_embedded") or {}).get("terms") or []
    terms = [t for t in terms if not t.get("is_obsolete")]
    if not terms:
        raise OntologyError(f"'{curie}' is not a current term of {spec['name']}.")
    term = terms[0]
    return {
        "curie": term["obo_id"],
        "label": term["label"],
        "ontology": term["ontology_name"],
        "iri": term["iri"],
    }


def get_or_create_term(field, curie):
    """The stored OntologyTerm for `curie`: known already, or checked at its source."""
    from mousetube_api.models import OntologyTerm

    spec = FIELDS[field]
    match = CURIE.match(curie or "")
    if match and match.group(1).lower() in spec["ontologies"]:
        known = OntologyTerm.objects.filter(
            curie__iexact=f"{match.group(1)}:{match.group(2)}"
        ).first()
        if known:
            return known
    found = lookup(field, curie)
    term, _ = OntologyTerm.objects.get_or_create(
        curie=found["curie"],
        defaults={
            "label": found["label"],
            "ontology": found["ontology"],
            "iri": found["iri"],
        },
    )
    return term


def known_term(curie, label):
    """The OntologyTerm of an identifier we already know, without any network call."""
    from mousetube_api.models import OntologyTerm

    term, _ = OntologyTerm.objects.get_or_create(
        curie=curie,
        defaults={
            "label": label,
            "ontology": curie.split(":")[0].lower(),
            "iri": f"http://purl.obolibrary.org/obo/{curie.replace(':', '_')}",
        },
    )
    return term


def sex_term(sex):
    """The PATO term of "male" / "female", without any network call (None otherwise)."""
    known = SEX_TERMS.get(sex)
    return known_term(*known) if known else None
