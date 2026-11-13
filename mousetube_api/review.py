"""What waits for an administrator's decision, in one place: the data of the "Review" page.

Accounts to activate, recording sessions and catalog entries (software, hardware, ...) that
users submitted. The decisions are the ones of the Django admin (utils.moderation): this is
only an easier door to them.
"""

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.paginator import EmptyPage, Paginator
from django.urls import reverse
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from mousetube_api.models import (
    AnimalProfile,
    Contact,
    Hardware,
    Laboratory,
    RecordingSession,
    Reference,
    Software,
    Strain,
    Study,
)
from mousetube_api.utils.moderation import (
    WAITING,
    approve_entries,
    approve_sessions,
    send_back,
    session_pending_entries,
)
from mousetube_api.utils.registration import (
    email_is_verified,
    pending_review_count,
    send_account_activated_email,
    send_account_rejected_email,
)

User = get_user_model()
PAGE_SIZE = 20

# kind -> (label, model, the fields told to the reviewer)
ENTRIES = {
    "sessions": (
        "Recording sessions",
        RecordingSession,
        ["date", "duration", "protocol", "laboratory", "description"],
    ),
    "software": (
        "Software",
        Software,
        ["type", "made_by", "description", "technical_requirements"],
    ),
    "hardware": ("Hardware", Hardware, ["type", "made_by", "description"]),
    "laboratories": (
        "Laboratories",
        Laboratory,
        ["institution", "unit", "address", "country", "organization"],
    ),
    "references": ("References", Reference, ["description", "url", "doi"]),
    "contacts": (
        "Contacts",
        Contact,
        ["email", "institution", "unit", "address", "country"],
    ),
    "studies": ("Studies", Study, ["description", "start_date", "end_date"]),
    "strains": ("Strains", Strain, ["background", "species", "bibliography"]),
    "animal-profiles": (
        "Animal profiles",
        AnimalProfile,
        ["strain", "sex", "age", "genotype", "treatment", "description"],
    ),
}
KINDS = ["accounts", *ENTRIES]
LABELS = {"accounts": "Account requests", **{k: v[0] for k, v in ENTRIES.items()}}


def _accounts():
    """Inactive accounts whose e-mail is confirmed, brand new, oldest request first."""
    ids = EmailAddress.objects.filter(verified=True, user__is_active=False).values(
        "user"
    )
    return User.objects.filter(pk__in=ids).order_by("date_joined", "pk")


def _entries(kind):
    model = ENTRIES[kind][1]
    return model.objects.filter(status=WAITING).order_by("modified_at", "pk")


def counts():
    result = {"accounts": pending_review_count()}
    for kind in ENTRIES:
        result[kind] = _entries(kind).count()
    return result


def _short(value, limit=240):
    text = str(value)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _facts(obj, fields):
    facts = []
    for name in fields:
        value = getattr(obj, name, None)
        if value in (None, ""):
            continue
        field = obj._meta.get_field(name)
        shown = getattr(obj, f"get_{name}_display", None)
        facts.append(
            {
                "label": str(field.verbose_name).capitalize(),
                "value": _short(shown() if shown else value),
            }
        )
    return facts


def _person(user):
    if not user:
        return None
    return {
        "username": user.username,
        "name": f"{user.first_name} {user.last_name}".strip(),
        "email": user.email,
    }


def _admin_url(obj):
    meta = obj._meta
    return reverse(f"admin:{meta.app_label}_{meta.model_name}_change", args=[obj.pk])


def describe_account(user):
    profile = getattr(user, "user_profile", None)
    facts = [
        {"label": "E-mail", "value": user.email},
        {"label": "Username", "value": user.username},
    ]
    if getattr(profile, "orcid", None):
        facts.append({"label": "ORCID", "value": profile.orcid})
    if getattr(profile, "laboratory", None):
        facts.append({"label": "Laboratory", "value": str(profile.laboratory)})
    return {
        "id": user.pk,
        "kind": "accounts",
        "title": f"{user.first_name} {user.last_name}".strip() or user.username,
        "subtitle": "wants an account",
        "facts": facts,
        "created_by": None,
        "waiting_since": user.date_joined.isoformat(),
        "admin_url": _admin_url(user),
        "pending": [],
        "can_validate": email_is_verified(user),
    }


def describe_entry(kind, obj):
    _label, _model, fields = ENTRIES[kind]
    item = {
        "id": obj.pk,
        "kind": kind,
        "title": str(obj),
        "subtitle": "",
        "facts": _facts(obj, fields),
        "created_by": _person(obj.created_by),
        "waiting_since": obj.modified_at.isoformat() if obj.modified_at else None,
        "admin_url": _admin_url(obj),
        "pending": [],
        "can_validate": True,
    }
    if kind == "sessions":
        pending = session_pending_entries(obj)
        item["pending"] = [
            {"kind": k, "name": str(e), "status": e.status} for k, e in pending
        ]
        item["files_count"] = obj.file_set.count()
        item["subtitle"] = (
            f"uses {len(pending)} new entr{'y' if len(pending) == 1 else 'ies'}"
            if pending
            else "uses only validated entries"
        )
    return item


class ReviewSummaryView(APIView):
    """How many things wait for a decision, per kind."""

    permission_classes = [IsAdminUser]

    @extend_schema(exclude=True)
    def get(self, request):
        per_kind = counts()
        return Response(
            {
                "total": sum(per_kind.values()),
                "kinds": [
                    {"kind": k, "label": LABELS[k], "count": per_kind[k]} for k in KINDS
                ],
            }
        )


class ReviewListView(APIView):
    """The things of one kind that wait for a decision, oldest first."""

    permission_classes = [IsAdminUser]

    @extend_schema(exclude=True)
    def get(self, request, kind):
        if kind not in KINDS:
            return Response({"detail": "Unknown kind."}, status=404)
        queryset = _accounts() if kind == "accounts" else _entries(kind)
        if kind != "accounts":
            queryset = queryset.select_related("created_by")
        try:
            page = Paginator(queryset, PAGE_SIZE).page(request.GET.get("page") or 1)
        except EmptyPage:
            return Response({"detail": "No such page."}, status=404)
        describe = (
            describe_account
            if kind == "accounts"
            else lambda obj: describe_entry(kind, obj)
        )
        return Response(
            {
                "count": page.paginator.count,
                "pages": page.paginator.num_pages,
                "page": page.number,
                "results": [describe(obj) for obj in page.object_list],
            }
        )


class ReviewDecisionView(APIView):
    """Validate, or send back / reject, one or several things of a kind."""

    permission_classes = [IsAdminUser]

    @extend_schema(exclude=True)
    def post(self, request, kind):
        if kind not in KINDS:
            return Response({"detail": "Unknown kind."}, status=404)
        action = request.data.get("action")
        reason = str(request.data.get("reason") or "").strip()[:1000]
        ids = request.data.get("ids")
        if action not in ("validate", "send_back") or not isinstance(ids, list):
            return Response({"detail": "action and ids are required."}, status=400)
        ids = [i for i in ids if isinstance(i, int)][:200]

        skipped = []
        if kind == "accounts":
            done = self._accounts(ids, action, reason, skipped)
        elif kind == "sessions":
            objs = RecordingSession.objects.filter(pk__in=ids, status=WAITING)
            if action == "validate":
                done, _entries_count = approve_sessions(list(objs))
            else:
                done = len(send_back(list(objs), reason))
        else:
            objs = list(ENTRIES[kind][1].objects.filter(pk__in=ids, status=WAITING))
            if action == "validate":
                done, _shared = approve_entries(objs)
            else:
                done = len(send_back(objs, reason))
        per_kind = counts()
        return Response(
            {
                "done": done,
                "skipped": skipped,
                "total": sum(per_kind.values()),
                "kinds": [
                    {"kind": k, "label": LABELS[k], "count": per_kind[k]} for k in KINDS
                ],
            }
        )

    def _accounts(self, ids, action, reason, skipped):
        done = 0
        for user in _accounts().filter(pk__in=ids):
            if action == "validate":
                if not email_is_verified(user):
                    skipped.append(
                        {"id": user.pk, "reason": "The e-mail is not confirmed yet."}
                    )
                    continue
                user.is_active = True
                user.save(update_fields=["is_active"])
                send_account_activated_email(user)
                done += 1
                continue
            # rejecting: only a brand-new request, never an account that was used or staff
            if user.is_staff or user.is_superuser or user.last_login:
                skipped.append({"id": user.pk, "reason": "This account was used."})
                continue
            try:
                send_account_rejected_email(user, reason)
            except Exception:  # noqa: BLE001 - keep the request so it can be retried
                skipped.append(
                    {"id": user.pk, "reason": "The e-mail could not be sent."}
                )
                continue
            user.delete()
            done += 1
        return done
