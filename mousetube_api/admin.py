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
admin.site.register(Dataset)
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
