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
)

admin.site.register(UserProfile)
admin.site.register(LegacyUser)
admin.site.register(Repository)
admin.site.register(Reference)
admin.site.register(Species)
admin.site.register(Strain)
admin.site.register(MetadataCategory)
admin.site.register(MetadataField)
admin.site.register(Metadata)
admin.site.register(Protocol)
admin.site.register(File)
admin.site.register(Dataset)
admin.site.register(Software)
admin.site.register(Hardware)
