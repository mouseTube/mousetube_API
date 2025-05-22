# Created by Nicolas Torquet at 09/01/2025
# torquetn@igbmc.fr
# Modified by Laurent Bouri 04/2025
# bouril@igbmc.fr
# Copyright: CNRS - INSERM - UNISTRA - ICS - IGBMC
# CNRS - Mouse Clinical Institute
# PHENOMIN, CNRS UMR7104, INSERM U964, Université de Strasbourg
# Code under GPL v3.0 licence

from django.db import models
from django.conf import settings
from django_countries.fields import CountryField
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.fields import GenericRelation


class UserProfile(models.Model):
    """
    Extended profile information for a user.

    Fields:
        user (OneToOneField): Linked user account.
        description (TextField): Optional textual description of the user.
        phone (CharField): Contact phone number.
        unit (CharField): Organizational unit or department.
        institution (CharField): Institution name (e.g., university, company).
        address (CharField): Physical address of the user.
        country (CountryField): Country of the user.
        orcid (CharField): ORCID researcher identifier.
        administrator (BooleanField): Whether the user has admin privileges.
        date_joined (DateTimeField): Timestamp when the profile was created.
        modified_at (DateTimeField): Last modification timestamp.
        created_by (ForeignKey): User who created this profile.
    """

    user = models.OneToOneField(
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
    administrator = models.BooleanField(blank=True, null=True)
    date_joined = models.DateTimeField(auto_now_add=True, null=True)

    modified_at = models.DateTimeField(auto_now=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        related_name="userprofile_created_by",
        on_delete=models.SET_NULL,
    )  # who entered the info in the database

    def __str__(self):
        return self.user.username


class LegacyUser(models.Model):
    """
    Represents a user of the last system.

    Attributes:
        name_user (str): The last name of the user.
        first_name_user (str): The first name of the user.
        email_user (str): The email address of the user.
        unit_user (str, optional): The unit the user belongs to.
        institution_user (str, optional): The institution the user belongs to.
        address_user (str, optional): The address of the user.
        country_user (str, optional): The country of the user.
    """

    name_user = models.CharField(max_length=255, null=True)
    first_name_user = models.CharField(max_length=255, null=True)
    email_user = models.CharField(max_length=255)
    unit_user = models.CharField(max_length=255, blank=True, null=True)
    institution_user = models.CharField(max_length=255, blank=True, null=True)
    address_user = models.CharField(max_length=255, blank=True, null=True)
    country_user = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        """
        Returns the full name of the user.

        Returns:
            str: The full name of the user.
        """
        return f"{self.first_name_user} {self.name_user}"


class MetadataCategory(models.Model):
    """
    Category used to organize metadata fields hierarchically.

    Fields:
        name (CharField): Name of the category.
        description (TextField): Optional description of the category.
        source (CharField): Source of the metadata category.
        parents (ManyToManyField): Parent categories for nested structure.
    """

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    source = models.CharField(max_length=50, null=True, blank=True)
    parents = models.ManyToManyField("self", symmetrical=False, related_name="children")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Metadata category"
        verbose_name_plural = "Metadata categories"
        unique_together = ("name", "source")


class MetadataField(models.Model):
    """
    Field used to store a single metadata attribute.

    Fields:
        name (CharField): Name of the metadata field.
        description (TextField): Optional description of the field.
        source (CharField): Source of the metadata field.
        metadata_category (ManyToManyField): Categories this field belongs to.
    """

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    source = models.CharField(max_length=50, null=True, blank=True)
    metadata_category = models.ManyToManyField(
        MetadataCategory, blank=True, related_name="metadatafield_categories"
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Metadata Field"
        verbose_name_plural = "Metadata Fields"
        unique_together = ("name", "source")


class Metadata(models.Model):
    """
    A set of metadata fields grouped under a name.

    Fields:
        metadata_field (ForeignKey): Fields included in this metadata.
        value (JSONField): JSON representation of the metadata values.
        created_at (DateTimeField): Timestamp when the metadata was created.
        modified_at (DateTimeField): Last modification timestamp.
        created_by (ForeignKey): User who created the metadata.
    """

    metadata_field = models.ForeignKey(
        MetadataField,
        null=True,
        related_name="metadata_field",
        on_delete=models.CASCADE,
    )
    value = models.JSONField(blank=True, null=True)
    content_type = models.ForeignKey(
        ContentType, blank=True, null=True, on_delete=models.CASCADE
    )
    object_id = models.PositiveIntegerField(blank=True, null=True)
    content_object = GenericForeignKey("content_type", "object_id")

    def __str__(self):
        return f"{self.metadata_field.name}: {self.value}"

    class Meta:
        verbose_name = "Metadata"
        verbose_name_plural = "Metadata"


class Species(models.Model):
    """
    Represents a biological species relevant to the data.

    Fields:
        name (CharField): Scientific or common name of the species.
        created_at (DateTimeField): Timestamp when the species entry was created.
        modified_at (DateTimeField): Last modification timestamp.
        created_by (ForeignKey): User who created the species entry.
    """

    name = models.CharField(max_length=255, unique=True)
    metadata = GenericRelation(Metadata)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        related_name="species_created_by",
        on_delete=models.SET_NULL,
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Species"
        verbose_name_plural = "Species"


class Strain(models.Model):
    """
    Represents a strain of a mouse.

    Attributes:
        name (str): The name of the strain.
        background (str): The genetic background of the strain.
        species (Species): The species associated with the strain.
        bibliography (str, optional): Bibliographical references related to the strain.
        created_at (DateTimeField): Timestamp when the species entry was created.
        modified_at (DateTimeField): Last modification timestamp.
        created_by (ForeignKey): User who created the species entry.
    """

    name = models.CharField(max_length=255, unique=True)
    background = models.CharField(max_length=255)
    species = models.ForeignKey(Species, on_delete=models.CASCADE, null=True)
    bibliography = models.TextField(blank=True, null=True)
    metadata = GenericRelation(Metadata)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    modified_at = models.DateTimeField(auto_now=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        related_name="strain_created_by",
        on_delete=models.SET_NULL,
    )

    def __str__(self):
        """
        Returns the name of the strain as a string.

        Returns:
            str: The name of the strain.
        """
        return self.name

    class Meta:
        verbose_name = "Strain"
        verbose_name_plural = "Strains"


class Subject(models.Model):
    """
    Represents a subject (mouse) in the system.

    Attributes:
        name (str): The name of the subject.
        strain (Strain): The strain associated with the subject.
        origin (str, optional): The origin of the subject.
        sex (str, optional): The sex of the subject.
        group (str, optional): The group the subject belongs to.
        genotype (str, optional): The genotype of the subject.
        treatment (str, optional): The treatment applied to the subject.
        user (LegacyUser): The user associated with the subject.
    """

    SEX_CHOICES = [
        ("male", "Male"),
        ("female", "Female"),
    ]

    name = models.CharField(max_length=255, unique=True)
    strain = models.ForeignKey(Strain, on_delete=models.CASCADE)
    origin = models.CharField(max_length=255, blank=True, null=True)
    sex = models.CharField(max_length=6, choices=SEX_CHOICES, blank=True, null=True)
    group = models.CharField(max_length=255, blank=True, null=True)
    genotype = models.CharField(max_length=255, blank=True, null=True)
    treatment = models.CharField(max_length=255, blank=True, null=True)
    metadata = GenericRelation(Metadata)
    user = models.ForeignKey(LegacyUser, on_delete=models.CASCADE)

    def __str__(self):
        """
        Returns the name of the subject.

        Returns:
            str: The name of the subject.
        """
        return self.name

    class Meta:
        verbose_name = "Subject"
        verbose_name_plural = "Subjects"


class Protocol(models.Model):
    """
    Represents an experimental protocol.

    Attributes:
        name (str): The name of the protocol.
        number_files (int, optional): The number of files associated with the protocol.
        description (str): A description of the protocol.
        user (LegacyUser): The user associated with the protocol.
    """

    name = models.CharField(max_length=255)
    number_files = models.IntegerField(blank=True, null=True)
    description = models.TextField(default="")
    user = models.ForeignKey(LegacyUser, on_delete=models.CASCADE)
    metadata = GenericRelation(Metadata)

    def __str__(self):
        """
        Returns the name of the protocol.

        Returns:
            str: The name of the protocol.
        """
        return self.name

    class Meta:
        verbose_name = "Protocol"
        verbose_name_plural = "Protocols"


class RecordingSession(models.Model):
    """
    Represents an experiment.

    Attributes:
        name (str): The name of the experiment.
        protocol (Protocol): The protocol associated with the experiment.
        date (date, optional): The date of the experiment.
        laboratory (str, optional): The laboratory where the experiment was conducted.
    """

    name = models.CharField(max_length=255, unique=True)
    protocol = models.ForeignKey(Protocol, on_delete=models.CASCADE)
    date = models.DateField(blank=True, null=True)
    temperature = models.CharField(max_length=255, blank=True, null=True)
    light_cycle = models.CharField(max_length=255, blank=True, null=True)
    microphone = models.CharField(max_length=255, blank=True, null=True)
    acquisition_hardware = models.CharField(max_length=255, blank=True, null=True)
    acquisition_software = models.CharField(max_length=255, blank=True, null=True)
    sampling_rate = models.FloatField(blank=True, null=True)
    bit_depth = models.FloatField(blank=True, null=True)
    laboratory = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        """
        Returns the name of the experiment.

        Returns:
            str: The name of the experiment.
        """
        return self.name

    class Meta:
        verbose_name = "Experiment"
        verbose_name_plural = "Experiments"


class SubjectSession(models.Model):
    """
    Represents a Session subjects in the system.

    Attributes:
        session (str): The recording Session.
        subject (Strain): The subjects used during the selected recording session.
    """

    recording_session = models.ForeignKey(RecordingSession, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "SessionSubject"
        verbose_name_plural = "SessionSubjects"


class Repository(models.Model):
    """
    Represents an external or internal data repository.

    Fields:
        name (CharField): Repository name.
        description (TextField): Optional description of the repository.
        logo (ImageField): Optional logo image.
        area (CountryField): Country or region associated with the repository.
        url (URLField): Main URL of the repository.
        url_api (URLField): URL to the repository's API endpoint.
        created_at (DateTimeField): Timestamp when the repository was created.
        modified_at (DateTimeField): Last modification timestamp.
        created_by (ForeignKey): User who created the repository record.
    """

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    logo = models.ImageField(blank=True, null=True, upload_to="logo")
    area = CountryField(blank=True, null=True)
    url = models.URLField(blank=True, null=True)
    url_api = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    modified_at = models.DateTimeField(auto_now=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        related_name="repository_created_by",
        on_delete=models.SET_NULL,
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Repository"
        verbose_name_plural = "Repositories"


class File(models.Model):
    """
    Represents a file associated with an experiment or subject.

    Attributes:
        experiment (Experiment, optional): The experiment associated with the file.
        subject (Subject, optional): The subject associated with the file.
        link (str, optional): The URL link to the file.
        notes (str, optional): Notes about the file.
        doi (str, optional): The DOI of the file.
        is_valid_link (bool): Whether the link is valid.
        downloads (int): The number of downloads for the file.
        spectrogram_image (str, optional): The path to the spectrogram image associated with the file.
        metadata (GenericRelation): Metadata associated with the file.
        repository (ForeignKey): Repositories associated with the file.
    """

    name = models.CharField(max_length=255, blank=True, null=True)
    recording_session = models.ForeignKey(
        RecordingSession, on_delete=models.CASCADE, blank=True, null=True
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, blank=True, null=True
    )
    link = models.URLField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    doi = models.CharField(max_length=255, blank=True, null=True)
    is_valid_link = models.BooleanField(default=False)
    downloads = models.IntegerField(default=0)
    spectrogram_image = models.ImageField(
        upload_to="audio_images/", null=True, blank=True
    )
    metadata = GenericRelation(Metadata)
    repository = models.ForeignKey(
        Repository, on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        """
        Returns the link to the file.

        Returns:
            str: The URL link to the file.
        """
        return self.link

    class Meta:
        verbose_name = "File"
        verbose_name_plural = "Files"


class Reference(models.Model):
    """
    Model representing a reference (e.g., research paper, article, or website).

    Attributes:
        name_reference (str): The name of the reference (e.g., title of a paper).
        description (str): A detailed description of the reference.
        url (str): The URL pointing to the reference, if available.
        doi (str): The DOI (Digital Object Identifier) of the reference, if applicable.

    Meta:
        verbose_name (str): Human-readable name for the model.
        verbose_name_plural (str): Plural version of the human-readable name.
    """

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    url = models.URLField(max_length=255, blank=True, null=True)
    doi = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Reference"
        verbose_name_plural = "References"


class Software(models.Model):
    """
    Model representing a software tool, which can be used for acquisition, analysis, or both.

    Attributes:
        software_name (str): The name of the software tool.
        software_type (str): The type of the software, categorized as 'acquisition', 'analysis', or both.
        made_by (str): The entity or individual who created the software.
        description (str): A description of the software, including its functionality.
        technical_requirements (str): The technical requirements for using the software.
        references (ManyToManyField): A list of references and tutorials related to the software.
        users (ManyToManyField): A list of users who are associated with the software.

    Meta:
        verbose_name (str): Human-readable name for the model.
        verbose_name_plural (str): Plural version of the human-readable name.
    """

    CHOICES_SOFTWARE = (
        ("acquisition", "acquisition"),
        ("analysis", "analysis"),
        ("acquisition and analysis", "acquisition and analysis"),
    )

    name = models.CharField(max_length=255)
    type = models.CharField(
        max_length=255, null=True, default="acquisition", choices=CHOICES_SOFTWARE
    )
    made_by = models.TextField(default="", blank=True)
    description = models.TextField(default="", blank=True)
    technical_requirements = models.TextField(default="", blank=True)
    references = models.ManyToManyField(Reference, related_name="software", blank=True)
    users = models.ManyToManyField(
        LegacyUser, related_name="software_to_user", blank=True
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Software"
        verbose_name_plural = "Software"


class Hardware(models.Model):
    """
    Describes a hardware component used in data collection or playback.

    Fields:
        name (CharField): Name of the hardware.
        type (CharField): Type of hardware (microphone, speaker, etc.).
        made_by (TextField): Manufacturer or source of the hardware.
        description (TextField): Optional details about the hardware.
        references (ManyToManyField): References or publications related to the hardware.
        created_at (DateTimeField): Timestamp when the hardware record was created.
        modified_at (DateTimeField): Last modification timestamp.
        created_by (ForeignKey): User who created the hardware record.
    """

    CHOICES_HARDWARE = (
        ("soundcard", "soundcard"),
        ("microphone", "microphone"),
        ("speaker", "speaker"),
        ("amplifier", "amplifier"),
    )

    name = models.CharField(max_length=255)
    type = models.CharField(
        max_length=255, null=True, default="", choices=CHOICES_HARDWARE
    )
    made_by = models.TextField(default="", blank=True)
    description = models.TextField(default="", blank=True)
    references = models.ManyToManyField(
        Reference, related_name="harware_reference", blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        related_name="hardware_created_by",
        on_delete=models.SET_NULL,
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Hardware"
        verbose_name_plural = "Hardware"


class Dataset(models.Model):
    """
    A collection of files grouped together with associated metadata.

    Fields:
        name (CharField): Name of the dataset.
        list_files (ManyToManyField): Files included in the dataset.
        link (CharField): External link or identifier for the dataset.
        doi (CharField): DOI of the dataset, if applicable.
        metadata_json (JSONField): Free-form metadata in JSON format.
        metadata (ManyToManyField): Structured metadata linked to the dataset.
        created_at (DateTimeField): Timestamp when the dataset was created.
        modified_at (DateTimeField): Last modification timestamp.
        created_by (ForeignKey): User who created the dataset.
    """

    name = models.CharField(max_length=255)
    list_files = models.ManyToManyField(
        File, related_name="file_in_dataset", blank=True
    )
    link = models.CharField(max_length=255)
    doi = models.CharField(max_length=255, null=True, blank=True)
    metadata_json = models.JSONField(blank=True, null=True)
    metadata = GenericRelation(Metadata)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        related_name="dataset_created_by",
        on_delete=models.SET_NULL,
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Dataset"
        verbose_name_plural = "Datasets"


class PageView(models.Model):
    """
    Represents a page view for tracking purposes.

    Attributes:
        path (str): The path of the page.
        date (date): The date of the page view.
        count (int): The number of views for the page on the given date.
    """

    path = models.CharField(max_length=255)
    date = models.DateField(auto_now_add=True)
    count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("path", "date")

    def __str__(self):
        """
        Returns a string representation of the page view.

        Returns:
            str: The path, date, and count of the page view.
        """
        return f"{self.path} - {self.date} ({self.count})"
