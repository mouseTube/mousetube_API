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

from .models import (
    AnimalProfile,
    Contact,
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
    UserProfile,
)
from .utils.registration import (
    email_is_verified,
    send_account_activated_email,
    send_account_rejected_email,
)


class ContactAdmin(admin.ModelAdmin):
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


class StrainAdmin(admin.ModelAdmin):
    list_display = ("name", "background", "species")
    search_fields = ("name",)
    list_filter = ("background",)


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
        "protocol",
        "display_studies",
        "date",
        "laboratory",
        "display_equipment_acquisition_software",
    )
    search_fields = ("name", "protocol__name")
    list_filter = ("protocol", "date")

    @admin.display(description="Studies")
    def display_studies(self, obj):
        return ", ".join([str(study) for study in obj.studies.all()])

    @admin.display(description="Acquisition Software")
    def display_equipment_acquisition_software(self, obj):
        return ", ".join(
            [str(soft) for soft in obj.equipment_acquisition_software.all()]
        )


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


class SoftwareAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "type",
        "made_by",
        "description",
        "technical_requirements",
    )
    search_fields = (
        "name",
        "type",
        "made_by",
        "description",
        "technical_requirements",
    )
    filter_horizontal = ("references", "contacts")


class ReferenceAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "description",
        "url",
        "doi",
    )
    search_fields = (
        "name",
        "description",
        "url",
        "doi",
    )


class HardwareAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "type",
        "made_by",
        "description",
    )
    search_fields = (
        "name",
        "type",
        "made_by",
        "description",
    )
    filter_horizontal = ("references",)


admin.site.register(UserProfile)
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
admin.site.register(AnimalProfile)
admin.site.register(SoftwareVersion)
admin.site.register(Laboratory)
admin.site.register(Study)
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
            return queryset.filter(is_active=False, _email_confirmed=False)
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
