"""
Created by Nicolas Torquet at 27/10/2023
torquetn@igbmc.fr
Copyright: CNRS - INSERM - UNISTRA - ICS - IGBMC
CNRS - Mouse Clinical Institute
PHENOMIN, CNRS UMR7104, INSERM U964, Université de Strasbourg
Code under GPL v3.0 licence
"""

from django.contrib import admin

from .models import (
    UserProfile,
    LegacyUser,
    Repository,
    Reference,
    Species,
    Strain,
    MetadataCategory,
    MetadataField,
    Metadata,
    Protocol,
    File,
    Dataset,
    Software,
    Hardware,
    RecordingSession,
    SubjectSession,
    Subject,
)


class LegacyUserAdmin(admin.ModelAdmin):
    list_display = (
        "first_name_user",
        "name_user",
        "email_user",
        "unit_user",
        "institution_user",
        "country_user",
    )
    search_fields = ("first_name_user", "name_user", "email_user")
    list_filter = ("country_user",)


class StrainAdmin(admin.ModelAdmin):
    list_display = ("name", "background")
    search_fields = ("name",)
    list_filter = ("background",)


class SubjectAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "strain",
        "user",
        "sex",
        "genotype",
    )
    search_fields = (
        "name",
        "strain__name",
        "user__first_name_user",
    )
    list_filter = ("strain", "sex", "user")


class ProtocolAdmin(admin.ModelAdmin):
    list_display = ("name", "number_files", "user")
    search_fields = ("name", "user__first_name_user")
    list_filter = ("user",)


class RecordingSessionAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "protocol",
        "date",
        "temperature",
        "light_cycle",
        "sampling_rate",
    )
    search_fields = ("name", "protocol__name")
    list_filter = ("protocol", "date")


class FileAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "experiment",
        "subject",
        "number",
        "link",
        "doi",
        "is_valid_link",
    )
    search_fields = (
        "name",
        "link",
        "doi",
        "experiment__name",
        "subject__name",
    )
    list_filter = ("is_valid_link", "experiment", "subject")


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
    filter_horizontal = ("references", "users")


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


admin.site.register(UserProfile)
admin.site.register(LegacyUser, LegacyUserAdmin)
admin.site.register(Repository)
admin.site.register(Reference, ReferenceAdmin)
admin.site.register(Species)
admin.site.register(Strain, StrainAdmin)
admin.site.register(MetadataCategory)
admin.site.register(MetadataField)
admin.site.register(Metadata)
admin.site.register(Protocol, ProtocolAdmin)
admin.site.register(File, FileAdmin)
admin.site.register(Dataset)
admin.site.register(Software, SoftwareAdmin)
admin.site.register(Hardware)
admin.site.register(RecordingSession, RecordingSessionAdmin)
admin.site.register(SubjectSession)
admin.site.register(Subject, SubjectAdmin)
admin.site.site_header = "Mousetube Admin"
admin.site.site_title = "Mousetube Admin"
admin.site.index_title = "Mousetube Admin"
