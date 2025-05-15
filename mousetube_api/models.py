"""
Created by Nicolas Torquet at 27/10/2023
torquetn@igbmc.fr
Copyright: CNRS - INSERM - UNISTRA - ICS - IGBMC
CNRS - Mouse Clinical Institute
PHENOMIN, CNRS UMR7104, INSERM U964, Université de Strasbourg
Code under GPL v3.0 licence
"""

from django.db import models
from django.conf import settings
from django.contrib.auth.models import User
from django_countries.fields import CountryField


def get_display(key, list):
    d = dict(list)
    if key in d:
        return d[key]
    return None


class UserProfile(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        related_name="user_profile",
        on_delete=models.SET_NULL,
    )
    description = models.TextField(blank=True, null=True)
    phone = models.CharField(max_length=255, blank=True, null=True)
    unit = models.CharField(max_length=255, blank=True, null=True)
    institution = models.CharField(max_length=255, blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    country = CountryField(blank=True, null=True)
    orcid = models.CharField(max_length=255, blank=True, null=True)
    administrator = models.IntegerField(blank=True, null=True)
    date_joined = models.DateTimeField(auto_now_add=True, null=True)

    modified_at = models.DateTimeField(auto_now=True, null=True)
    created_by = models.ForeignKey(
        User,
        null=True,
        related_name="userprofile_created_by",
        on_delete=models.SET_NULL,
    )  # who entered the info in the database

    def __str__(self):
        return self.user.username


class Contact(models.Model):
    firstname = models.CharField(max_length=255, blank=True, null=True)
    lastname = models.CharField(max_length=255, blank=True, null=True)
    email = models.EmailField(max_length=255, blank=True, null=True)
    id_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        related_name="contact_user_profile",
        on_delete=models.SET_NULL,
    )

    created_at = models.DateTimeField(auto_now_add=True, null=True)
    modified_at = models.DateTimeField(auto_now=True, null=True)
    created_by = models.ForeignKey(
        User, null=True, related_name="contact_created_by", on_delete=models.SET_NULL
    )  # who entered the info in the database

    def __str__(self):
        if self.firstname and self.lastname:
            return self.firstname + " " + self.lastname
        else:
            return self.email

    class Meta:
        verbose_name = "Contact"
        verbose_name_plural = "Contacts"


class Repository(models.Model):
    name_repository = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    logo = models.ImageField(blank=True, null=True, upload_to="logo")
    area = CountryField(blank=True, null=True)
    url = models.URLField(blank=True, null=True)
    url_api = models.URLField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True, null=True)
    modified_at = models.DateTimeField(auto_now=True, null=True)
    created_by = models.ForeignKey(
        User, null=True, related_name="repository_created_by", on_delete=models.SET_NULL
    )  # who entered the info in the database

    def __str__(self):
        return self.name_repository

    class Meta:
        verbose_name = "Repository"
        verbose_name_plural = "Repositories"


class Reference(models.Model):
    name_reference = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    url = models.URLField(max_length=255, blank=True, null=True)
    doi = models.CharField(max_length=255, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, null=True, related_name="reference_created_by", on_delete=models.SET_NULL
    )  # who entered the info in the database

    def __str__(self):
        return self.name_reference

    class Meta:
        verbose_name = "Reference"
        verbose_name_plural = "References"


class Software(models.Model):
    CHOICES_SOFTWARE = (
        ("acquisition", "acquisition"),
        ("analysis", "analysis"),
        ("acquisition and analysis", "acquisition and analysis"),
    )

    software_name = models.CharField(max_length=255)
    software_type = models.CharField(
        max_length=255, null=True, default="acquisition", choices=CHOICES_SOFTWARE
    )
    made_by = models.TextField(default="", blank=True)
    description = models.TextField(default="", blank=True)
    technical_requirements = models.TextField(default="", blank=True)
    references_and_tutorials = models.ManyToManyField(
        Reference, related_name="software", blank=True
    )
    contacts = models.ManyToManyField(
        Contact, related_name="software_to_contact", blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, null=True, related_name="software_created_by", on_delete=models.SET_NULL
    )  # who entered the info in the database

    def __str__(self):
        return self.software_name

    class Meta:
        verbose_name = "Software"
        verbose_name_plural = "Software"


class Hardware(models.Model):
    CHOICES_HARDWARE = (
        ("soundcard", "soundcard"),
        ("microphone", "microphone"),
        ("speaker", "speaker"),
        ("amplifier", "amplifier"),
    )

    hardware_name = models.CharField(max_length=255)
    hardware_type = models.CharField(
        max_length=255, null=True, default="", choices=CHOICES_HARDWARE
    )
    made_by = models.TextField(default="", blank=True)
    description = models.TextField(default="", blank=True)
    reference = models.ManyToManyField(
        Reference, related_name="harware_reference", blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, null=True, related_name="hardware_created_by", on_delete=models.SET_NULL
    )  # who entered the info in the database

    def __str__(self):
        return self.hardware_name

    class Meta:
        verbose_name = "Hardware"
        verbose_name_plural = "Hardware"


class Species(models.Model):
    name_species = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, null=True, related_name="species_created_by", on_delete=models.SET_NULL
    )  # who entered the info in the database

    def __str__(self):
        return self.name_species

    class Meta:
        verbose_name = "Species"
        verbose_name_plural = "Species"


class Strain(models.Model):
    name_strain = models.CharField(max_length=255, unique=True)
    species = models.ForeignKey(
        Species, null=True, related_name="strain_species", on_delete=models.SET_NULL
    )
    background = models.CharField(max_length=255)
    biblio_strain = models.TextField(blank=True, null=True)
    references = models.ManyToManyField(Reference, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, null=True, related_name="strain_created_by", on_delete=models.SET_NULL
    )  # who entered the info in the database

    def __str__(self):
        return self.name_strain

    class Meta:
        verbose_name = "Strain"
        verbose_name_plural = "Strains"


# class ProtocolType(models.Model):
#     name_protocol_type = models.CharField(max_length=255, unique=True)
#     protocol_type_description = models.TextField(default='')
#
#     def __str__(self):
#         return self.name_protocol_type
#
#     class Meta:
#         verbose_name = 'Protocol type'
#         verbose_name_plural = 'Protocol types'


class MetadataCategory(models.Model):
    name_metadata_category = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)
    metadata_categories = models.ManyToManyField(
        "self", blank=True, related_name="metadata_categories_categories"
    )

    def __str__(self):
        return self.name_metadata_category

    class Meta:
        verbose_name = "Metadata category"
        verbose_name_plural = "Metadata categories"


class MetadataField(models.Model):
    name_metadata_field = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)
    metadata_category = models.ManyToManyField(
        MetadataCategory, blank=True, related_name="metadatafield_categories"
    )

    def __str__(self):
        return self.name_metadata_field

    class Meta:
        verbose_name = "Metadata Field"
        verbose_name_plural = "Metadata Fields"


class Metadata(models.Model):
    name_metadata = models.CharField(max_length=255, unique=True)
    metadata_field = models.ManyToManyField(
        MetadataField, blank=True, related_name="metadata_field"
    )

    def __str__(self):
        return self.name_metadata

    class Meta:
        verbose_name = "Metadata"
        verbose_name_plural = "Metadata"


class Protocol(models.Model):
    name_protocol = models.CharField(max_length=255)
    # protocol_type = models.ForeignKey(ProtocolType, null=True, related_name='protocol_protocol_type', on_delete=models.SET_NULL)
    protocol_description = models.TextField(default="")
    protocol_metadata = models.ManyToManyField(
        Metadata, blank=True, related_name="protocol_metadata"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        blank=True,
        null=True,
        related_name="protocol_created_by",
        on_delete=models.SET_NULL,
    )  # who entered the info in the database
    references = models.ManyToManyField(Reference, blank=True)

    def __str__(self):
        return self.name_protocol

    class Meta:
        verbose_name = "Protocol"
        verbose_name_plural = "Protocols"


class File(models.Model):
    name_file = models.CharField(max_length=255)
    file_number = models.IntegerField(null=True, blank=True)
    link_file = models.CharField(max_length=255)
    doi_file = models.CharField(max_length=255, null=True, blank=True)
    file = models.FileField(upload_to="uploaded/", null=True, blank=True)
    protocol = models.ForeignKey(
        Protocol, related_name="file_protocol", null=True, on_delete=models.SET_NULL
    )
    number_of_channels = models.PositiveSmallIntegerField(
        default=1, null=True, blank=True
    )  # mono or stereo, or more channels
    file_weight = models.CharField(max_length=255, null=True, blank=True)
    spectrogram = models.ImageField(upload_to="spectrogram/", null=True, blank=True)
    repository = models.ManyToManyField(
        Repository, related_name="file_repository", blank=True
    )
    microphones = models.ManyToManyField(
        Hardware, related_name="file_microphones", blank=True
    )
    acquisition_hardware = models.ForeignKey(
        Hardware,
        related_name="file_acquisition_hardware",
        null=True,
        on_delete=models.SET_NULL,
    )
    acquisition_software = models.ForeignKey(
        Software,
        related_name="file_acquisition_software",
        null=True,
        on_delete=models.SET_NULL,
    )
    species = models.ForeignKey(
        Species, null=True, related_name="file_species", on_delete=models.SET_NULL
    )
    strains = models.ManyToManyField(Strain, related_name="file_strains", blank=True)
    metadata_json = models.JSONField(blank=True, null=True)
    metadata = models.ManyToManyField(
        Metadata, related_name="file_metadata", blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, null=True, related_name="file_created_by", on_delete=models.SET_NULL
    )  # who entered the info in the database

    def __str__(self):
        return self.name_file

    class Meta:
        verbose_name = "File"
        verbose_name_plural = "Files"


class Dataset(models.Model):
    name_dataset = models.CharField(max_length=255)
    list_files = models.ManyToManyField(
        File, related_name="file_in_dataset", blank=True
    )
    link_dataset = models.CharField(max_length=255)
    doi_dataset = models.CharField(max_length=255, null=True, blank=True)
    metadata_json = models.JSONField(blank=True, null=True)
    metadata = models.ManyToManyField(
        Metadata, related_name="dataset_metadata", blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, null=True, related_name="dataset_created_by", on_delete=models.SET_NULL
    )  # who entered the info in the database

    def __str__(self):
        return self.name_dataset

    class Meta:
        verbose_name = "Dataset"
        verbose_name_plural = "Datasets"
