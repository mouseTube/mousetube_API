"""The description and the keywords of a Zenodo record made from a recording session.

Written like the descriptions of the other communities of Zenodo (a few lines saying who
submitted it and where it comes from, then lists of facts with their labels in bold, keywords
and the year), in the HTML Zenodo accepts. Everything that comes from a user is escaped.
"""

import html

from django.conf import settings
from django.utils import timezone

from mousetube_api.utils.ontologies import session_terms


def esc(value):
    return html.escape(str(value), quote=True)


def link(url, text):
    return f'<a href="{esc(url)}">{esc(text)}</a>'


def term(t):
    """An ontology term as a link to its definition."""
    return link(t.iri, t.label) if t and t.iri else esc(t.label) if t else ""


def _facts(pairs):
    """<ul> of "label: value" for the pairs that have a value (a value is already HTML)."""
    rows = [
        f"<li><strong>{esc(label)}:</strong> {value}</li>"
        for label, value in pairs
        if value not in (None, "", [])
    ]
    return f"<ul>{''.join(rows)}</ul>" if rows else ""


def _section(title, body):
    return f"<p><strong>{esc(title)}</strong></p>{body}" if body else ""


def _joined(values, sep=", "):
    return sep.join(str(v) for v in values if v not in (None, ""))


def _names(manager):
    return ", ".join(esc(o) for o in manager.all())


def _person(user):
    if not user:
        return ""
    name = f"{user.first_name} {user.last_name}".strip() or user.username
    orcid = getattr(getattr(user, "user_profile", None), "orcid", None)
    return esc(name) + (
        f" ({link('https://orcid.org/' + orcid, orcid)})" if orcid else ""
    )


def _laboratory(lab):
    if not lab:
        return ""
    text = esc(_joined([lab.name, lab.institution, lab.unit, lab.country]))
    if lab.organization and lab.organization.iri:
        text += f" ({link('https://ror.org/' + lab.organization.curie.split(':')[-1], 'ROR')})"
    return text


def _animal(profile):
    strain = profile.strain
    species = strain.species if strain else None
    parts = [
        esc(profile.name),
        _facts_inline(
            [
                (
                    "Species",
                    term(species.ontology_term)
                    if species and species.ontology_term
                    else esc(species.name)
                    if species
                    else "",
                ),
                (
                    "Strain",
                    term(strain.ontology_term)
                    if strain and strain.ontology_term
                    else esc(strain.name)
                    if strain
                    else "",
                ),
                (
                    "Sex",
                    term(profile.sex_term) if profile.sex_term else esc(profile.sex),
                ),
                (
                    "Age",
                    term(profile.age_term) if profile.age_term else esc(profile.age),
                ),
                ("Genotype", esc(profile.genotype or "")),
                (
                    "Treatment",
                    term(profile.treatment_term)
                    if profile.treatment_term
                    else esc(profile.treatment or ""),
                ),
            ]
        ),
    ]
    return f"<li><strong>{parts[0]}</strong>: {parts[1]}</li>"


def _facts_inline(pairs):
    return " · ".join(f"{esc(label)} {value}" for label, value in pairs if value)


def _ref_url(ref):
    return ref.url or (f"https://doi.org/{ref.doi}" if ref.doi else "")


def _equipment_item(obj, version=""):
    """The name of a piece of equipment, linked to its own documentation when it has one.
    Returns (html, ids of the references it used)."""
    name = f"{obj.name} {version}".strip()
    refs = [r for r in obj.references.all() if _ref_url(r)]
    if not refs:
        return esc(name), set()
    text = link(_ref_url(refs[0]), name)
    if len(refs) > 1:
        more = ", ".join(link(_ref_url(r), r.name) for r in refs[1:])
        text += f" (see also {more})"
    return text, {r.pk for r in refs}


def _equipment(objects, versions=None):
    items, used = [], set()
    for obj in objects:
        html_text, ids = _equipment_item(obj, (versions or {}).get(obj.pk, ""))
        items.append(html_text)
        used |= ids
    return ", ".join(items), used


def _reference(ref):
    url = _ref_url(ref)
    return f"<li>{link(url, ref.name) if url else esc(ref.name)}</li>"


def keywords(session):
    """Words to find the record: what the vocabularies say, and the usual ones."""
    words = ["ultrasonic vocalizations", "mouseTube"]
    words += [t.label for t in session_terms(session)]
    seen, kept = set(), []
    for word in words:
        if word and word.lower() not in seen:
            seen.add(word.lower())
            kept.append(word)
    return kept


def description(session, creator=None):
    """The HTML description of the record of `session` (the page of the record lists the files)."""
    protocol = session.protocol
    parts = []

    if creator:
        parts.append(
            "<p><strong>📤 Submitted via mouseTube on behalf of:</strong> "
            f"{_person(creator)}</p>"
        )
    parts.append(
        "<p><strong>🔗 mouseTube:</strong> "
        f"{link(settings.FRONT_URL + '/vocalizations', settings.FRONT_URL)} · "
        f"session “{esc(session.name)}”</p>"
    )
    if session.description:
        parts.append(f"<p>{esc(session.description).replace(chr(10), '<br>')}</p>")

    parts.append(
        _section(
            "🎧 Recording session",
            _facts(
                [
                    (
                        "Date",
                        esc(session.date.date().isoformat())
                        if session.date and not session.is_multiple
                        else "several days"
                        if session.is_multiple
                        else "",
                    ),
                    ("Duration", f"{session.duration} s" if session.duration else ""),
                    ("Laboratory", _laboratory(session.laboratory)),
                    ("Studies", _names(session.studies)),
                    (
                        "Temperature",
                        esc(
                            _joined(
                                [
                                    session.context_temperature_value,
                                    session.context_temperature_unit,
                                ],
                                " ",
                            )
                        )
                        if session.context_temperature_value
                        else "",
                    ),
                    (
                        "Brightness",
                        f"{esc(session.context_brightness)} lux"
                        if session.context_brightness is not None
                        else "",
                    ),
                    ("Channels", esc(session.equipment_channels or "")),
                    ("Sound isolation", esc(session.equipment_sound_isolation or "")),
                    (
                        "Behaviors",
                        ", ".join(term(t) for t in session.behavior_terms.all()),
                    ),
                ]
            ),
        )
    )
    if protocol:
        parts.append(
            _section(
                "🧪 Protocol",
                _facts(
                    [
                        ("Name", esc(protocol.name)),
                        ("Animals sex", esc(protocol.animals_sex or "")),
                        ("Animals age", esc(protocol.animals_age or "")),
                        ("Housing", esc(protocol.animals_housing or "")),
                        (
                            "Number of animals",
                            esc(protocol.context_number_of_animals or ""),
                        ),
                        ("Duration", esc(protocol.context_duration or "")),
                        ("Cage", esc(protocol.context_cage or "")),
                        ("Bedding", esc(protocol.context_bedding or "")),
                        ("Light cycle", esc(protocol.context_light_cycle or "")),
                    ]
                ),
            )
        )
    profiles = list(session.animal_profiles.select_related("strain__species"))
    if profiles:
        parts.append(
            _section("🐭 Animals", f"<ul>{''.join(_animal(p) for p in profiles)}</ul>")
        )

    used = set()

    def equipment(label, objects, versions=None):
        text, ids = _equipment(objects, versions)
        used.update(ids)
        return label, text

    software_versions = list(
        session.equipment_acquisition_software.select_related("software").all()
    )
    software = [v.software for v in software_versions]
    versions = {v.software.pk: v.version or "" for v in software_versions}
    parts.append(
        _section(
            "🎙️ Equipment",
            _facts(
                [
                    equipment(
                        "Microphones",
                        session.equipment_acquisition_hardware_microphones.all(),
                    ),
                    equipment(
                        "Soundcards",
                        session.equipment_acquisition_hardware_soundcards.all(),
                    ),
                    equipment(
                        "Amplifiers",
                        session.equipment_acquisition_hardware_amplifiers.all(),
                    ),
                    equipment(
                        "Speakers",
                        session.equipment_acquisition_hardware_speakers.all(),
                    ),
                    equipment("Acquisition software", software, versions),
                ]
            ),
        )
    )
    # the references of the session itself, except those already behind a piece of equipment
    references = [r for r in session.references.all() if r.pk not in used]
    if references:
        parts.append(
            _section(
                "📚 Related references",
                f"<ul>{''.join(_reference(r) for r in references)}</ul>",
            )
        )
    words = keywords(session)
    parts.append(
        "<p><strong>🏷️ Keywords:</strong></p>"
        f"<ul>{''.join(f'<li>{esc(w)}</li>' for w in words)}</ul>"
    )
    parts.append(f"<p><strong>📅 Publication year:</strong> {timezone.now().year}</p>")
    return "".join(p for p in parts if p)
