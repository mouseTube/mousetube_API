"""Signed proof that the browser really went through ORCID OAuth for a given iD."""

from django.core import signing

_SALT = "mousetube.orcid-proof"
MAX_AGE = 1800  # seconds: enough to fill in the registration form


def make_orcid_proof(orcid):
    return signing.dumps(orcid, salt=_SALT)


def read_orcid_proof(proof):
    """Return the ORCID iD, or raise signing.BadSignature (also on expiry)."""
    return signing.loads(proof, salt=_SALT, max_age=MAX_AGE)
