"""
Created by Nicolas Torquet at 27/10/2023
torquetn@igbmc.fr
Copyright: CNRS - INSERM - UNISTRA - ICS - IGBMC
CNRS - Mouse Clinical Institute
PHENOMIN, CNRS UMR7104, INSERM U964, Université de Strasbourg
Code under GPL v3.0 licence
"""

from allauth.account.models import EmailAddress
from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.db.models import Count, Exists, OuterRef
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.html import format_html, format_html_join

from .models import (
    AnimalProfile,
    Contact,
    Dataset,
    File,
    Hardware,
    Laboratory,
    OntologyTerm,
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
    UserProfile,
)
from .utils.moderation import (
    approve_entries,
    approve_sessions,
    send_back,
    session_pending_entries,
)
from .utils.registration import (
    email_is_verified,
    send_account_activated_email,
    send_account_rejected_email,
)


class ModerationAdminMixin:
    """Review of what users add: validate in bulk, or send back to draft with a reason.

    Filter by status (the dashboard links to "waiting validation"), then select and act.
    Validating entries also shares the sessions that were only waiting for them.
    """

    actions = ("validate_selected", "send_back_to_draft")

    @admin.action(description="Validate the selected entries")
    def validate_selected(self, request, queryset):
        changed, shared = approve_entries(queryset.exclude(status="validated"))
        message = f"{changed} entr{'y' if changed == 1 else 'ies'} validated."
        if shared:
            message += f" {len(shared)} session(s) shared as a result."
        self.message_user(request, message, messages.SUCCESS)

    @admin.action(description="Send back to draft (with a reason)")
    def send_back_to_draft(self, request, queryset):
        entries = queryset.exclude(status="draft")
        if "apply" not in request.POST:
            return TemplateResponse(
                request,
                "admin/send_back.html",
                {
                    **self.admin_site.each_context(request),
                    "title": f"Send back {self.model._meta.verbose_name_plural}",
                    "opts": self.model._meta,
                    "entries": entries,
                    "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
                    "action": "send_back_to_draft",
                },
            )
        sent = send_back(entries, request.POST.get("reason", "").strip())
        self.message_user(request, f"{len(sent)} sent back to draft.", messages.SUCCESS)
        return None


class ContactAdmin(ModerationAdminMixin, admin.ModelAdmin):
    list_display = (
        "first_name",
        "last_name",
        "email",
        "institution",
        "country",
        "status",
    )
    search_fields = ("first_name", "last_name", "email", "institution")
    list_filter = ("country", "status")


class StrainAdmin(ModerationAdminMixin, admin.ModelAdmin):
    list_display = ("name", "background", "species", "status")
    search_fields = ("name",)
    list_filter = ("status", "background")


class SubjectAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "animal_profile",
    )
    search_fields = (
        "name",
        "animal_profile__name",
    )


class ProtocolAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


class RecordingSessionAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "id",
        "status",
        "to_validate",
        "protocol",
        "display_studies",
        "date",
        "laboratory",
        "display_equipment_acquisition_software",
    )
    search_fields = ("name", "protocol__name")
    list_filter = ("status", "protocol", "date")
    readonly_fields = ("entries_to_validate",)
    actions = ("validate_sessions", "send_back_sessions")

    @admin.display(description="Studies")
    def display_studies(self, obj):
        return ", ".join([str(study) for study in obj.studies.all()])

    @admin.display(description="Acquisition Software")
    def display_equipment_acquisition_software(self, obj):
        return ", ".join(
            [str(soft) for soft in obj.equipment_acquisition_software.all()]
        )

    @admin.display(description="New entries to validate")
    def to_validate(self, obj):
        return len(session_pending_entries(obj))

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if "status" in form.base_fields:
            form.base_fields["status"].help_text = (
                "A shared or published session is public, so everything it uses "
                "(protocol, laboratory, animals, equipment, references...) is validated "
                "with it when you save: set it to Shared to validate it all at once."
            )
        return form

    def save_related(self, request, form, formsets, change):
        """A public session only uses validated entries: saving one as shared (or edited
        while shared) validates what it uses, which is only known once its links are saved."""
        super().save_related(request, form, formsets, change)
        session = form.instance
        if session.status not in ("shared", "published"):
            return
        if session.status == "published":
            from .utils.publication import schedule_sync

            schedule_sync(session)  # its record follows, once what it uses is validated
        entries = session_pending_entries(session)
        if not entries:
            return
        changed, _shared = approve_entries([obj for _kind, obj in entries])
        self.message_user(
            request,
            f"The session is {session.status}: the {changed} entr"
            f"{'y' if changed == 1 else 'ies'} it uses "
            f"({', '.join(sorted({kind for kind, _ in entries}))}) "
            f"{'was' if changed == 1 else 'were'} validated with it.",
            messages.INFO,
        )

    @admin.display(description="Entries nobody validated yet")
    def entries_to_validate(self, obj):
        if not obj.pk:
            return "-"
        pending = session_pending_entries(obj)
        if not pending:
            return "Nothing: everything this session uses is validated."
        return format_html(
            "<p>Validating the session (the action, or the status set to Shared) validates "
            "all of these with it.</p><ul>{}</ul>",
            format_html_join(
                "",
                '<li>{}: <a href="{}">{}</a> ({})</li>',
                (
                    (
                        kind,
                        reverse(
                            f"admin:{o._meta.app_label}_{o._meta.model_name}_change",
                            args=[o.pk],
                        ),
                        o,
                        o.status,
                    )
                    for kind, o in pending
                ),
            ),
        )

    @admin.action(
        description="Validate the sessions and everything they use, then share"
    )
    def validate_sessions(self, request, queryset):
        shared, entries = approve_sessions(queryset.exclude(status="published"))
        self.message_user(
            request,
            f"{shared} session(s) shared, {entries} entr"
            f"{'y' if entries == 1 else 'ies'} validated.",
            messages.SUCCESS,
        )

    @admin.action(description="Send back to draft (with a reason)")
    def send_back_sessions(self, request, queryset):
        sessions = queryset.exclude(status__in=("draft", "published"))
        if "apply" not in request.POST:
            return TemplateResponse(
                request,
                "admin/send_back.html",
                {
                    **self.admin_site.each_context(request),
                    "title": "Send back recording sessions",
                    "opts": self.model._meta,
                    "entries": sessions,
                    "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
                    "action": "send_back_sessions",
                },
            )
        sent = send_back(sessions, request.POST.get("reason", "").strip())
        self.message_user(
            request, f"{len(sent)} session(s) sent back to draft.", messages.SUCCESS
        )
        return None


class DatasetAdmin(admin.ModelAdmin):
    """Add a dataset: pick its sessions in a searchable two-column list."""

    list_display = ("name", "id", "sessions_count", "files_count", "doi", "created_at")
    search_fields = ("name", "description", "doi")
    filter_horizontal = ("recording_session_list",)
    readonly_fields = ("created_at", "modified_at")
    fields = (
        "name",
        "description",
        "doi",
        "link",
        "recording_session_list",
        "created_by",
        "created_at",
        "modified_at",
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(
                _sessions=Count("recording_session_list", distinct=True),
                _files=Count("recording_session_list__file", distinct=True),
            )
        )

    @admin.display(description="Sessions", ordering="_sessions")
    def sessions_count(self, obj):
        return obj._sessions

    @admin.display(description="Files", ordering="_files")
    def files_count(self, obj):
        return obj._files

    def save_model(self, request, obj, form, change):
        if obj.created_by is None:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class FileAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "recording_session",
        "repository",
        "display_subjects",
        "link",
        "doi",
        "is_valid_link",
    )
    search_fields = (
        "name",
        "link",
        "doi",
        "recording_session__name",
        "subjects__name",
    )
    list_filter = ("is_valid_link", "recording_session", "subjects")

    @admin.display(description="Subjects")
    def display_subjects(self, obj):
        return ", ".join([str(s) for s in obj.subjects.all()])


class SoftwareAdmin(ModerationAdminMixin, admin.ModelAdmin):
    list_display = (
        "name",
        "type",
        "made_by",
        "status",
        "description",
        "technical_requirements",
    )
    list_filter = ("status", "type")
    search_fields = (
        "name",
        "type",
        "made_by",
        "description",
        "technical_requirements",
    )
    filter_horizontal = ("references", "contacts")


class ReferenceAdmin(ModerationAdminMixin, admin.ModelAdmin):
    list_display = (
        "name",
        "description",
        "url",
        "doi",
        "status",
    )
    list_filter = ("status",)
    search_fields = (
        "name",
        "description",
        "url",
        "doi",
    )


class HardwareAdmin(ModerationAdminMixin, admin.ModelAdmin):
    list_display = (
        "name",
        "type",
        "made_by",
        "status",
        "description",
    )
    list_filter = ("status", "type")
    search_fields = (
        "name",
        "type",
        "made_by",
        "description",
    )
    filter_horizontal = ("references",)


class OntologyTermAdmin(admin.ModelAdmin):
    list_display = ("curie", "label", "ontology")
    list_filter = ("ontology",)
    search_fields = ("curie", "label")


class LaboratoryAdmin(ModerationAdminMixin, admin.ModelAdmin):
    list_display = ("name", "institution", "unit", "country", "status")
    list_filter = ("status", "country")
    search_fields = ("name", "institution", "unit")


class StudyAdmin(ModerationAdminMixin, admin.ModelAdmin):
    list_display = ("name", "start_date", "end_date", "status")
    list_filter = ("status",)
    search_fields = ("name",)


class AnimalProfileAdmin(ModerationAdminMixin, admin.ModelAdmin):
    list_display = ("name", "strain", "sex", "age", "genotype", "status")
    list_filter = ("status", "sex", "age")
    search_fields = ("name", "genotype")


admin.site.register(UserProfile)
admin.site.register(OntologyTerm, OntologyTermAdmin)
admin.site.register(Repository)
admin.site.register(Reference, ReferenceAdmin)
admin.site.register(Species)
admin.site.register(Strain, StrainAdmin)
admin.site.register(Protocol, ProtocolAdmin)
admin.site.register(File, FileAdmin)
admin.site.register(Dataset, DatasetAdmin)
admin.site.register(Software, SoftwareAdmin)
admin.site.register(Hardware, HardwareAdmin)
admin.site.register(RecordingSession, RecordingSessionAdmin)
admin.site.register(Subject, SubjectAdmin)
admin.site.register(AnimalProfile, AnimalProfileAdmin)
admin.site.register(SoftwareVersion)
admin.site.register(Laboratory, LaboratoryAdmin)
admin.site.register(Study, StudyAdmin)
admin.site.register(Contact, ContactAdmin)
admin.site.site_header = "Mousetube Admin"
admin.site.site_title = "Mousetube Admin"
admin.site.index_title = "Mousetube Database"


# ----------------------------
# User accounts: review of registration requests
# ----------------------------
User = get_user_model()
admin.site.unregister(User)


class AccountRequestFilter(admin.SimpleListFilter):
    title = "account request"
    parameter_name = "account_request"

    def lookups(self, request, model_admin):
        return [
            ("review", "To review (e-mail confirmed)"),
            ("unconfirmed", "Waiting for e-mail confirmation"),
        ]

    def queryset(self, request, queryset):
        # queryset comes from UserAccountAdmin.get_queryset, so _email_confirmed exists
        if self.value() == "review":
            return queryset.filter(is_active=False, _email_confirmed=True)
        if self.value() == "unconfirmed":
            # accounts without a usable password are the authors imported from mouseTube
            # 0.5 (they only carry a name): nobody is waiting for them
            return queryset.filter(is_active=False, _email_confirmed=False).exclude(
                password__startswith="!"
            )
        return queryset


@admin.register(User)
class UserAccountAdmin(DjangoUserAdmin):
    """Account requests: who confirmed their e-mail, activate or reject in bulk."""

    list_display = (*DjangoUserAdmin.list_display, "is_active", "email_confirmed")
    list_filter = (AccountRequestFilter, "is_active", *DjangoUserAdmin.list_filter)
    actions = ("activate_accounts", "reject_accounts")

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(
                _email_confirmed=Exists(
                    EmailAddress.objects.filter(
                        user=OuterRef("pk"), email=OuterRef("email"), verified=True
                    )
                )
            )
        )

    @admin.display(
        boolean=True, description="E-mail confirmed", ordering="_email_confirmed"
    )
    def email_confirmed(self, obj):
        return obj._email_confirmed

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if change and "is_active" in form.changed_data and obj.is_active:
            send_account_activated_email(obj)

    @admin.action(
        description="Activate selected accounts (e-mail must be confirmed)",
        permissions=["change"],
    )
    def activate_accounts(self, request, queryset):
        activated = 0
        for user in queryset.filter(is_active=False):
            if not email_is_verified(user):
                self.message_user(
                    request,
                    f"{user.username}: e-mail not confirmed yet, not activated.",
                    messages.WARNING,
                )
                continue
            user.is_active = True
            user.save(update_fields=["is_active"])
            send_account_activated_email(user)
            activated += 1
        self.message_user(request, f"{activated} account(s) activated.")

    @admin.action(
        description="Reject selected requests (delete and notify by e-mail)",
        permissions=["delete"],
    )
    def reject_accounts(self, request, queryset):
        # Only brand-new requests: never an account that was ever used or that has staff rights.
        requests = queryset.filter(
            is_active=False, is_staff=False, is_superuser=False, last_login__isnull=True
        )
        if "apply" not in request.POST:
            return TemplateResponse(
                request,
                "admin/reject_accounts.html",
                {
                    **self.admin_site.each_context(request),
                    "title": "Reject account requests",
                    "opts": self.model._meta,
                    "requests": requests,
                    "skipped": queryset.count() - requests.count(),
                    "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
                },
            )

        reason = request.POST.get("reason", "").strip()
        rejected = 0
        for user in requests:
            try:
                send_account_rejected_email(user, reason)
            except Exception as exc:  # noqa: BLE001 - keep the request so it can be retried
                self.message_user(
                    request,
                    f"{user.username}: e-mail could not be sent ({exc}); request kept.",
                    messages.ERROR,
                )
                continue
            user.delete()
            rejected += 1
        self.message_user(request, f"{rejected} request(s) rejected and deleted.")
        return None


# ----------------------------
# Dashboard: what waits for a decision (accounts and entries), like the account requests
# ----------------------------
_original_index = admin.site.index


def _index_with_moderation(request, extra_context=None):
    from .utils.moderation import pending_counts
    from .utils.registration import pending_review_count

    rows = [
        {
            "label": "Account requests",
            "count": pending_review_count(),
            "url": reverse("admin:auth_user_changelist") + "?account_request=review",
        },
        *pending_counts(),
    ]
    context = {
        "moderation_rows": rows,
        "moderation_total": sum(row["count"] for row in rows),
    }
    return _original_index(request, {**context, **(extra_context or {})})


admin.site.index = _index_with_moderation
admin.site.index_template = "admin/moderation_index.html"
