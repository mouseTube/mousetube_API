"""Dataset metadata as JSON: export (public API route) and import (management command).

Format (same as the `metadata` field of the datasets of mouseTube 0.5):

    {"dataset": {"name", "description", "recording_session_list": [ session, ... ]}}

where a session carries its protocol, laboratory, animal profiles, equipment, references and
its `file_list`. Contact e-mails are never exported: the route is public.
"""

import datetime as dt
import os

import requests
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django_countries import countries

from mousetube_api.models import (
    AnimalProfile,
    Dataset,
    File,
    Hardware,
    Laboratory,
    Protocol,
    RecordingSession,
    Reference,
    Repository,
    Software,
    SoftwareVersion,
    Species,
    Strain,
    Study,
    Subject,
)

HARDWARE_FIELDS = {
    "equipment_acquisition_hardware_soundcards": "soundcard",
    "equipment_acquisition_hardware_speakers": "speaker",
    "equipment_acquisition_hardware_amplifiers": "amplifier",
    "equipment_acquisition_hardware_microphones": "microphone",
}


# ----------------------------------------------------------------------------
# Export
# ----------------------------------------------------------------------------
def _reference(r):
    return {
        "name": r.name,
        "description": r.description,
        "url": r.url,
        "doi": r.doi,
        "status": r.status,
    }


def _strain(s):
    return {
        "name": s.name,
        "background": s.background,
        "species": {"name": s.species.name},
        "bibliography": s.bibliography,
        "status": s.status,
    }


def _animal_profile(a):
    return {
        "name": a.name,
        "description": a.description,
        "strain": _strain(a.strain),
        "sex": a.sex,
        "age": a.age,
        "genotype": a.genotype,
        "treatment": a.treatment,
        "status": a.status,
    }


def _hardware(h):
    return {
        "name": h.name,
        "type": h.type,
        "made_by": h.made_by,
        "description": h.description,
        "references": [_reference(r) for r in h.references.all()],
        "status": h.status,
    }


def _software_version(v):
    s = v.software
    return {
        "software": {
            "name": s.name,
            "type": s.type,
            "made_by": s.made_by,
            "description": s.description,
            "technical_requirements": s.technical_requirements,
            "references": [_reference(r) for r in s.references.all()],
            "status": s.status,
        },
        "version": v.version,
        "release_date": v.release_date,
    }


def _subject(s):
    return {
        "name": s.name,
        "identifier": s.identifier,
        "cohort": s.cohort,
        "origin": s.origin,
        "animal_profile": _animal_profile(s.animal_profile)
        if s.animal_profile
        else None,
    }


def _repository(r):
    return {
        "name": r.name,
        "description": r.description,
        "logo": r.logo.name if r.logo else None,
        "area": countries.name(r.area) if r.area else None,
        "url": r.url,
        "url_api": r.url_api,
    }


def _file(f):
    return {
        "name": f.name,
        "link": f.link,
        "subjects": [_subject(s) for s in f.subjects.all()],
        "date": f.date,
        "duration": f.duration,
        "format": f.format,
        "sampling_rate": f.sampling_rate,
        "bit_depth": f.bit_depth,
        "notes": f.notes,
        "size": f.size,
        "doi": f.doi,
        "number": f.number,
        "is_valid_link": f.is_valid_link,
        "downloads": f.downloads,
        "repository": _repository(f.repository) if f.repository else None,
        "external_id": f.external_id,
        "external_url": f.external_url,
        "status": f.status,
    }


def _session(rs):
    p, lab = rs.protocol, rs.laboratory
    data = {
        "name": rs.name,
        "is_multiple": rs.is_multiple,
        "protocol": p
        and {
            "name": p.name,
            "animals_sex": p.animals_sex,
            "animals_age": p.animals_age,
            "animals_housing": p.animals_housing,
            "context_number_of_animals": p.context_number_of_animals,
            "context_duration": p.context_duration,
            "context_cage": p.context_cage,
            "context_bedding": p.context_bedding,
            "context_light_cycle": p.context_light_cycle,
        },
        "studies": [
            {
                "name": s.name,
                "description": s.description,
                "start_date": s.start_date,
                "end_date": s.end_date,
                "status": s.status,
            }
            for s in rs.studies.all()
        ],
        "description": rs.description,
        "date": rs.date,
        "status": rs.status,
        "duration": rs.duration,
        "laboratory": lab
        and {
            "name": lab.name,
            "institution": lab.institution,
            "unit": lab.unit,
            "address": lab.address,
            "country": countries.name(lab.country) if lab.country else None,
            "status": lab.status,
        },
        "animal_profiles": [_animal_profile(a) for a in rs.animal_profiles.all()],
        "context_temperature_value": rs.context_temperature_value,
        "context_temperature_unit": rs.context_temperature_unit,
        "context_brightness": rs.context_brightness,
        "equipment_acquisition_software": [
            _software_version(v) for v in rs.equipment_acquisition_software.all()
        ],
    }
    for field in HARDWARE_FIELDS:
        data[field] = [_hardware(h) for h in getattr(rs, field).all()]
    data["equipment_channels"] = rs.equipment_channels
    data["equipment_sound_isolation"] = rs.equipment_sound_isolation
    data["references"] = [_reference(r) for r in rs.references.all()]
    data["file_list"] = [
        _file(f)
        for f in File.objects.filter(recording_session=rs)
        .select_related("repository")
        .prefetch_related("subjects__animal_profile__strain__species")
        .order_by("name")
    ]
    return data


def build_dataset_metadata(dataset):
    sessions = dataset.recording_session_list.select_related(
        "protocol", "laboratory"
    ).prefetch_related(
        "studies",
        "animal_profiles__strain__species",
        "equipment_acquisition_software__software__references",
        "equipment_acquisition_hardware_soundcards__references",
        "equipment_acquisition_hardware_speakers__references",
        "equipment_acquisition_hardware_amplifiers__references",
        "equipment_acquisition_hardware_microphones__references",
        "references",
    )
    return {
        "dataset": {
            "name": dataset.name,
            "description": dataset.description,
            "doi": dataset.doi,
            "link": dataset.link,
            "recording_session_list": [
                _session(rs) for rs in sessions.order_by("name")
            ],
        }
    }


# ----------------------------------------------------------------------------
# Import
# ----------------------------------------------------------------------------
class Stats(dict):
    """created / already existing, per model name."""

    def add(self, model, created):
        entry = self.setdefault(model, {"created": 0, "existing": 0})
        entry["created" if created else "existing"] += 1


def _name(d):
    return ((d or {}).get("name") or "").strip()


def _clean(d, *keys):
    """Keep the given keys, turning None into '' for text columns that are not nullable."""
    return {k: d.get(k) for k in keys if d.get(k) is not None}


def _country_code(value):
    if not value:
        return ""
    if value in countries:  # already an ISO code
        return value
    return countries.by_name(value) or ""


def _date(value):
    """A date (File.date) from an ISO string, a date or a datetime."""
    if isinstance(value, str):
        return parse_date(value[:10]) if value else None
    return value.date() if isinstance(value, dt.datetime) else value


def _datetime(value):
    """An aware datetime (RecordingSession.date) from an ISO string, date or datetime."""
    if isinstance(value, str):
        value = parse_datetime(value) or parse_date(value) if value else None
    if value is None:
        return None
    if not isinstance(value, dt.datetime):
        value = dt.datetime.combine(value, dt.time.min)
    return (
        timezone.make_aware(value, dt.timezone.utc)
        if timezone.is_naive(value)
        else value
    )


MAX_IMAGE_BYTES = 20 * 1024 * 1024


class DatasetImporter:
    def __init__(self, created_by=None, images_from=None):
        self.created_by = created_by
        self.images_from = images_from  # site that serves the 0.5 /media/ images
        self.images = {}  # file name -> {"spectrogram": path, "plot": path}
        self.stats = Stats()

    def _get_or_create(self, model, lookup, defaults=None):
        obj, created = model.objects.get_or_create(**lookup, defaults=defaults or {})
        self.stats.add(model.__name__, created)
        return obj

    # -- small objects ----------------------------------------------------
    def reference(self, d):
        if not _name(d):
            return None  # empty placeholder
        return self._get_or_create(
            Reference,
            {"name": _name(d)},
            {
                **_clean(d, "description", "url", "doi"),
                "status": "validated",
                "created_by": self.created_by,
            },
        )

    def references(self, items):
        refs = [self.reference(r) for r in items or []]
        return [r for r in refs if r]

    def strain(self, d):
        species = self._get_or_create(
            Species, {"name": _name(d.get("species"))}, {"created_by": self.created_by}
        )
        return self._get_or_create(
            Strain,
            {"name": _name(d), "species": species},
            {
                "background": d.get("background") or "",
                **_clean(d, "bibliography"),
                "status": "validated",
                "created_by": self.created_by,
            },
        )

    def animal_profile(self, d):
        if not _name(d) or not _name(d.get("strain")):
            return None
        strain = self.strain(d["strain"])
        return self._get_or_create(
            AnimalProfile,
            {"name": _name(d), "strain": strain},
            {
                "sex": d.get("sex") or "male",
                "genotype": d.get("genotype") or "",
                **_clean(d, "age", "description", "treatment"),
                "status": "validated",
                "created_by": self.created_by,
            },
        )

    def hardware(self, d):
        if not _name(d):
            return None
        hw = self._get_or_create(
            Hardware,
            {"name": _name(d), "type": d.get("type")},
            {
                **_clean(d, "made_by", "description"),
                "status": "validated",
                "created_by": self.created_by,
            },
        )
        hw.references.add(*self.references(d.get("references")))
        return hw

    def software_version(self, d):
        s = d.get("software") or {}
        if not _name(s):
            return None
        software = self._get_or_create(
            Software,
            {"name": _name(s)},
            {
                **_clean(s, "type", "made_by", "description", "technical_requirements"),
                "status": "validated",
                "created_by": self.created_by,
            },
        )
        software.references.add(*self.references(s.get("references")))
        return self._get_or_create(
            SoftwareVersion,
            {"software": software, "version": d.get("version") or ""},
            {"release_date": d.get("release_date"), "created_by": self.created_by},
        )

    def repository(self, d):
        if not _name(d):
            return None
        return self._get_or_create(
            Repository,
            {"name": _name(d)},
            {
                **_clean(d, "description", "url", "url_api"),
                "area": _country_code(d.get("area")),
                "logo": d.get("logo") or "",
                "created_by": self.created_by,
            },
        )

    def subject(self, d):
        if not _name(d):
            return None
        return self._get_or_create(
            Subject,
            {"name": _name(d)},
            {
                **_clean(d, "identifier", "cohort", "origin"),
                "animal_profile": self.animal_profile(d.get("animal_profile") or {}),
                "created_by": self.created_by,
            },
        )

    # -- sessions and files -------------------------------------------------
    def session(self, d):
        protocol = laboratory = None
        if _name(d.get("protocol")):
            p = d["protocol"]
            # Protocol.save() replaces the name by a code built from these fields, so the
            # fields are the identity of a protocol (the 0.5 label is not kept).
            attrs = {
                k: p.get(k) or "unspecified"
                for k in (
                    "animals_sex",
                    "animals_age",
                    "animals_housing",
                    "context_number_of_animals",
                    "context_duration",
                    "context_cage",
                    "context_bedding",
                    "context_light_cycle",  # absent from the 0.5 export
                )
            }
            protocol = self._get_or_create(
                Protocol,
                attrs,
                {"name": _name(p), "created_by": self.created_by},
            )
        if _name(d.get("laboratory")):
            lab = d["laboratory"]
            laboratory = self._get_or_create(
                Laboratory,
                {"name": _name(lab)},
                {
                    **_clean(lab, "institution", "unit", "address"),
                    "country": _country_code(lab.get("country")),
                    "status": "validated",
                    "created_by": self.created_by,
                },
            )

        files = d.get("file_list") or []
        date = _datetime(d.get("date"))
        is_multiple = bool(d.get("is_multiple"))
        if not is_multiple and date is None:
            # a single session needs a start date: take the one of its first file
            first = next(
                (_datetime(f.get("date")) for f in files if f.get("date")), None
            )
            date, is_multiple = first, first is None

        rs, created = RecordingSession.objects.get_or_create(
            name=_name(d),
            protocol=protocol,
            defaults={
                "is_multiple": is_multiple,
                "date": date,
                "laboratory": laboratory,
                "status": "shared",
                "created_by": self.created_by,
                **_clean(
                    d,
                    "description",
                    "duration",
                    "context_temperature_value",
                    "context_temperature_unit",
                    "context_brightness",
                    "equipment_channels",
                    "equipment_sound_isolation",
                ),
            },
        )
        self.stats.add("RecordingSession", created)

        studies = [
            self._get_or_create(
                Study,
                {"name": _name(s)},
                {
                    **_clean(s, "description", "start_date", "end_date"),
                    "status": "validated",
                    "created_by": self.created_by,
                },
            )
            for s in d.get("studies") or []
            if _name(s)
        ]
        rs.studies.add(*studies)
        profiles = d.get("animal_profiles") or []
        profiles = (
            [profiles] if isinstance(profiles, dict) else profiles
        )  # 0.5: one dict
        rs.animal_profiles.add(*[a for a in map(self.animal_profile, profiles) if a])
        rs.equipment_acquisition_software.add(
            *[
                v
                for v in map(
                    self.software_version, d.get("equipment_acquisition_software") or []
                )
                if v
            ]
        )
        for field in HARDWARE_FIELDS:
            getattr(rs, field).add(
                *[h for h in map(self.hardware, d.get(field) or []) if h]
            )
        rs.references.add(*self.references(d.get("references")))

        for f in files:
            self.file(rs, f)
        return rs

    def file(self, rs, d):
        if not _name(d):
            return None
        f = self._get_or_create(
            File,
            {"recording_session": rs, "name": _name(d)},
            {
                **_clean(
                    d,
                    "link",
                    "duration",
                    "format",
                    "sampling_rate",
                    "bit_depth",
                    "notes",
                    "size",
                    "doi",
                    "number",
                    "is_valid_link",
                    "downloads",
                    "external_id",
                    "external_url",
                ),
                "date": _date(d.get("date")),
                "repository": self.repository(d.get("repository") or {}),
                "status": "done",
                "created_by": self.created_by,
            },
        )
        f.subjects.add(*[s for s in map(self.subject, d.get("subjects") or []) if s])
        self.fetch_images(f)
        return f

    def fetch_images(self, f):
        """From the 0.5 list of files: download counter, then spectrogram and plot."""
        paths = self.images.get(f.name) or {}
        if paths.get("downloads") and not f.downloads:
            # the counter of the 0.5 list is the real one (the one in `metadata` is 0)
            f.downloads = paths["downloads"]
            f.save(update_fields=["downloads"])
        for field in ("spectrogram", "plot"):
            path = paths.get(field)
            if not path or not self.images_from:
                continue
            if getattr(f, field):
                self.stats.add("Image", False)
                continue
            url = self.images_from.rstrip("/") + "/" + path.lstrip("/")
            try:
                response = requests.get(url, timeout=60)
            except requests.RequestException:
                self.stats.add("Image (failed)", True)
                continue
            is_image = response.headers.get("content-type", "").startswith("image/")
            too_big = len(response.content) > MAX_IMAGE_BYTES
            if response.status_code != 200 or not is_image or too_big:
                self.stats.add("Image (failed)", True)
                continue
            getattr(f, field).save(
                os.path.basename(path), ContentFile(response.content), save=True
            )
            self.stats.add("Image", True)

    # -- datasets ---------------------------------------------------------------
    def dataset(self, d):
        dataset, created = Dataset.objects.get_or_create(
            name=_name(d),
            defaults={
                "description": d.get("description") or "",
                "doi": d.get("doi"),
                "link": d.get("link"),
                "created_by": self.created_by,
            },
        )
        self.stats.add("Dataset", created)
        self.images = d.get("_images") or {}
        dataset.recording_session_list.add(
            *[
                self.session(s)
                for s in d.get("recording_session_list") or []
                if _name(s)
            ]
        )
        return dataset


def datasets_from_payload(payload):
    """Accepts the 0.5 API list, the list of this API's metadata route, or one document."""
    if isinstance(payload, dict) and "results" in payload:  # 0.5 /api/dataset/
        payload = payload["results"]
    if isinstance(payload, dict):
        payload = payload.get("datasets") or [payload]
    found = []
    for item in payload:
        if "metadata" in item:
            # 0.5 item {"id", "name", "description", "files", "metadata": {"dataset": ...}}.
            # Its own name and description win: the JSON inside is not reliable (on the
            # production, the "Rat dataset" metadata is named "Mouse dataset").
            dataset = dict(item["metadata"]["dataset"])
            dataset["name"] = item.get("name") or dataset.get("name")
            dataset["description"] = item.get("description") or dataset.get(
                "description"
            )
            dataset["_images"] = {
                f["name"]: {
                    "spectrogram": f.get("spectrogram"),
                    "plot": f.get("plot"),
                    "downloads": f.get("downloads") or 0,
                }
                for f in item.get("files") or []
                if f.get("name")
            }
            found.append(dataset)
        else:
            found.append(item["dataset"])
    return found


@transaction.atomic
def import_datasets(payload, created_by=None, dry_run=False, images_from=None):
    # no download in a dry run: nothing would be kept anyway
    importer = DatasetImporter(
        created_by=created_by, images_from=None if dry_run else images_from
    )
    for d in datasets_from_payload(payload):
        importer.dataset(d)
    if dry_run:
        transaction.set_rollback(True)
    return importer.stats
