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
        return self.user.username if self.user else "No user"

    class Meta:
        verbose_name = "UserProfile"
        verbose_name_plural = "UserProfiles"


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

    class Meta:
        verbose_name = "LegacyUser"
        verbose_name_plural = "LegacyUsers"


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


class AnimalProfile(models.Model):
    """
    Represents the profile of animal used in experiments.

    Attributes:
        name (str): The name of the animal profil.
        description (str, optional): A description of the animal profil.
        strain (Strain): The strain associated with the animal profil.
        sex (str, optional): The sex of the subject.
        genotype (str, optional): The genotype of the animal.
        treatment (str, optional): The treatment applied to the animal.
        created_at (DateTimeField): Timestamp when the animal profil was created.
        modified_at (DateTimeField): Last modification timestamp.
        created_by (ForeignKey): User who created the animal profil entry.
    """

    SEX_CHOICES = [
        ("male", "Male"),
        ("female", "Female"),
    ]

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)
    strain = models.ForeignKey(Strain, on_delete=models.CASCADE)
    sex = models.CharField(max_length=6, choices=SEX_CHOICES, blank=True, null=True)
    genotype = models.CharField(max_length=255, blank=True, null=True)
    treatment = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    modified_at = models.DateTimeField(auto_now=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        related_name="animaltype_created_by",
        on_delete=models.SET_NULL,
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Animal Profile"
        verbose_name_plural = "Animal Profiles"


class Subject(models.Model):
    """
    Represents a subject (mouse) in the system.

    Attributes:
        name (str): The name of the subject.
        origin (str, optional): The origin of the subject.
        cohort (str, optional): The group the subject belongs to.
        animal_profile (AnimalProfile, optional): The profil of the animals used.
        user (LegacyUser): The user associated with the subject.
        created_at (DateTimeField): Timestamp when the animal profil was created.
        modified_at (DateTimeField): Last modification timestamp.
        created_by (ForeignKey): User who created the animal profil entry.
    """

    SEX_CHOICES = [
        ("male", "Male"),
        ("female", "Female"),
    ]

    name = models.CharField(max_length=255, unique=True)
    origin = models.CharField(max_length=255, blank=True, null=True)
    cohort = models.CharField(max_length=255, blank=True, null=True)
    animal_profile = models.ForeignKey(
        AnimalProfile, on_delete=models.CASCADE, null=True, blank=True
    )
    user = models.ForeignKey(LegacyUser, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    modified_at = models.DateTimeField(auto_now=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        related_name="subject_created_by",
        on_delete=models.SET_NULL,
    )

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
    description = models.TextField(default="")
    user = models.ForeignKey(LegacyUser, on_delete=models.CASCADE)
    # Animals
    animals_sex = models.CharField(
        max_length=32,
        choices=[
            ("male(s)", "male(s)"),
            ("female(s)", "female(s)"),
            ("male(s) & female(s)", "male(s) & female(s)"),
        ],
        blank=True,
        null=True,
    )
    animals_age = models.CharField(
        max_length=32,
        choices=[("pup", "pup"), ("juvenile", "juvenile"), ("adult", "adult")],
        blank=True,
        null=True,
    )
    animals_housing = models.CharField(
        max_length=32,
        choices=[
            ("grouped", "grouped"),
            ("isolated", "isolated"),
            ("grouped & isolated", "grouped & isolated"),
        ],
        blank=True,
        null=True,
    )
    animals_species = models.CharField(max_length=255, blank=True, null=True)

    # Context
    context_number_of_animals = models.PositiveIntegerField(blank=True, null=True)
    context_duration = models.CharField(
        max_length=32,
        choices=[
            ("short term (<1h)", "short term (<1h)"),
            ("mid term (<1day)", "mid term (<1day)"),
            ("long term (>=1day)", "long term (>=1day)"),
        ],
        blank=True,
        null=True,
    )
    context_cage = models.CharField(
        max_length=64,
        choices=[
            ("unfamiliar test cage", "unfamiliar test cage"),
            ("familiar test cage", "familiar test cage"),
            ("home cage", "home cage"),
        ],
        blank=True,
        null=True,
    )
    context_bedding = models.CharField(
        max_length=16,
        choices=[("bedding", "bedding"), ("no bedding", "no bedding")],
        blank=True,
        null=True,
    )
    context_light_cycle = models.CharField(
        max_length=8,
        choices=[("day", "day"), ("night", "night")],
        blank=True,
        null=True,
    )
    context_temperature_value = models.CharField(max_length=16, blank=True, null=True)
    context_temperature_unit = models.CharField(
        max_length=4, choices=[("°C", "°C"), ("°F", "°F")], blank=True, null=True
    )
    context_brightness = models.FloatField(help_text="in Lux", blank=True, null=True)

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
        temperature (str, optional): The temperature during the experiment.
        microphone (str, optional): The microphone used during the experiment.
        acquisition_hardware (str, optional): The hardware used for data acquisition.
        acquisition_software (str, optional): The software used for data acquisition.
        animal_profiles (ManyToManyField): The animal profiles used in the experiment.
        laboratory (str, optional): The laboratory where the experiment was conducted.
        created_at (DateTimeField): Timestamp when the experiment was created.
        modified_at (DateTimeField): Last modification timestamp.
        created_by (ForeignKey): User who created the experiment record.
    """

    name = models.CharField(max_length=255, unique=True)
    protocol = models.ForeignKey(Protocol, on_delete=models.CASCADE)
    date = models.DateField(blank=True, null=True)
    temperature_value = models.CharField(max_length=255, blank=True, null=True)
    temperature_unit = models.CharField(
        max_length=4,
        choices=[("°C", "°C"), ("°F", "°F")],
        blank=True,
        null=True,
        default="°C",
    )
    microphone = models.CharField(max_length=255, blank=True, null=True)
    acquisition_hardware = models.CharField(max_length=255, blank=True, null=True)
    acquisition_software = models.CharField(max_length=255, blank=True, null=True)
    laboratory = models.CharField(max_length=255, blank=True, null=True)
    animal_profiles = models.ManyToManyField(
        AnimalProfile, blank=True, related_name="animal_profiles"
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    modified_at = models.DateTimeField(auto_now=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        related_name="recording_session_created_by",
        on_delete=models.SET_NULL,
    )

    def __str__(self):
        """
        Returns the name of the experiment.

        Returns:
            str: The name of the experiment.
        """
        return self.name

    class Meta:
        verbose_name = "Recording Session"
        verbose_name_plural = "Recording Sessions"


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
    Represents a file associated with an recording session or a subject.

    Attributes:
        recording_session (RecordingSession, optional): The experiment associated with the file.
        subject (Subject, optional): The subject associated with the file.
        number (int, optional): The number of vocalizations in a file.
        link (str, optional): The URL link to the file.
        notes (str, optional): Notes about the file.
        doi (str, optional): The DOI of the file.
        is_valid_link (bool): Whether the link is valid.
        downloads (int): The number of downloads for the file.
        repository (ForeignKey): Repositories associated with the file.
        date (date): The date of the file.
        sampling_rate (int): The sampling rate of the file.
        bit_depth (int): The bit depth of the file.
        size (int): The size of the file in bytes.
    """

    name = models.CharField(max_length=255, blank=True, null=True)
    recording_session = models.ForeignKey(
        RecordingSession, on_delete=models.CASCADE, blank=True, null=True
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, blank=True, null=True
    )
    number = models.IntegerField(blank=True, null=True)
    link = models.URLField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    doi = models.CharField(max_length=255, blank=True, null=True)
    is_valid_link = models.BooleanField(default=False)
    downloads = models.IntegerField(default=0)
    repository = models.ForeignKey(
        Repository, on_delete=models.SET_NULL, null=True, blank=True
    )
    date = models.DateField(blank=True, null=True)
    sampling_rate = models.PositiveIntegerField(blank=True, null=True)
    bit_depth = models.PositiveSmallIntegerField(
        choices=[(8, "8"), (16, "16"), (24, "24"), (32, "32")], blank=True, null=True
    )
    size = models.PositiveBigIntegerField(
        help_text="File size in bytes", blank=True, null=True
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
    # metadata = GenericRelation(Metadata)
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
        verbose_name = "PageView"
        verbose_name_plural = "PageViews"

    def __str__(self):
        """
        Returns a string representation of the page view.

        Returns:
            str: The path, date, and count of the page view.
        """
        return f"{self.path} - {self.date} ({self.count})"
