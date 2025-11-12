"""
Created by Nicolas Torquet at 27/10/2023
torquetn@igbmc.fr
Copyright: CNRS - INSERM - UNISTRA - ICS - IGBMC
CNRS - Mouse Clinical Institute
PHENOMIN, CNRS UMR7104, INSERM U964, Université de Strasbourg
Code under GPL v3.0 licence
"""

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count, Q
from django_countries.serializer_fields import CountryField
from djoser.serializers import UserCreateSerializer as BaseUserCreateSerializer
from rest_framework import serializers

from mousetube_api.utils.validators import (
    validate_doi,
    validate_doi_link_consistency,
    validate_url,
)

from .models import (
    AnimalProfile,
    Contact,
    Dataset,
    Favorite,
    File,
    Hardware,
    Laboratory,
    LegacyUser,
    PageView,
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


class CustomUserCreateSerializer(BaseUserCreateSerializer):
    orcid = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta(BaseUserCreateSerializer.Meta):
        fields = (
            "id",
            "username",
            "email",
            "password",
            "first_name",
            "last_name",
            "orcid",
        )

    def validate(self, attrs):
        orcid = attrs.pop("orcid", None)
        attrs = super().validate(attrs)
        self._orcid = orcid
        return attrs

    def create(self, validated_data):
        user = super().create(validated_data)
        orcid = getattr(self, "_orcid", None)
        if orcid:
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.orcid = orcid
            profile.save()
        return user


class RepositorySerializer(serializers.ModelSerializer):
    area = serializers.CharField(source="area.name")

    class Meta:
        model = Repository
        fields = "__all__"


class ReferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reference
        fields = "__all__"

        def validate_doi(self, value):
            return validate_doi(value)

        def validate_url(self, value):
            return validate_url(value)


class LegacyUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = LegacyUser
        fields = "__all__"


class LaboratorySerializer(serializers.ModelSerializer):
    country = CountryField()

    class Meta:
        model = Laboratory
        fields = "__all__"


class CustomUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "email"]


class UserProfileSerializer(serializers.ModelSerializer):
    user = CustomUserSerializer(read_only=True)
    laboratory = LaboratorySerializer(read_only=True)
    laboratory_id = serializers.PrimaryKeyRelatedField(
        queryset=Laboratory.objects.all(),
        source="laboratory",
        write_only=True,
        required=False,
    )
    country = CountryField()

    class Meta:
        model = UserProfile
        fields = "__all__"


class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = "__all__"


class HardwareSerializer(serializers.ModelSerializer):
    references = ReferenceSerializer(many=True, read_only=True)
    users = LegacyUserSerializer(many=True, required=False)

    references_ids = serializers.PrimaryKeyRelatedField(
        queryset=Reference.objects.all(),
        source="references",
        many=True,
        write_only=True,
        required=False,
    )

    class Meta:
        model = Hardware
        fields = "__all__"

    def create(self, validated_data):
        references_data = validated_data.pop("references", [])
        users_data = validated_data.pop("users", [])
        hardware = Hardware.objects.create(**validated_data)

        # assign references
        if references_data:
            hardware.references.set(references_data)

        # assign users
        if users_data:
            user_ids = [user["id"] for user in users_data if "id" in user]
            hardware.users.set(user_ids)

        return hardware

    def update(self, instance, validated_data):
        references_data = validated_data.pop("references", None)
        users_data = validated_data.pop("users", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if references_data is not None:
            instance.references.set(references_data)

        if users_data is not None:
            user_ids = [user["id"] for user in users_data if "id" in user]
            if user_ids:
                instance.users.set(user_ids)

        return instance


class SoftwareSerializer(serializers.ModelSerializer):
    references = ReferenceSerializer(many=True, read_only=True)
    users = LegacyUserSerializer(many=True, required=False)
    contacts = ContactSerializer(many=True, read_only=True)

    references_ids = serializers.PrimaryKeyRelatedField(
        queryset=Reference.objects.all(),
        source="references",
        many=True,
        write_only=True,
        required=False,
    )
    contacts_ids = serializers.PrimaryKeyRelatedField(
        queryset=Contact.objects.all(),
        source="contacts",
        many=True,
        write_only=True,
        required=False,
    )

    linked_sessions_count = serializers.IntegerField(read_only=True)
    linked_sessions_from_other_users = serializers.IntegerField(read_only=True)

    class Meta:
        model = Software
        fields = "__all__"
        read_only_fields = [
            "created_at",
            "modified_at",
            "created_by",
            "linked_sessions_count",
            "linked_sessions_from_other_users",
        ]

    @staticmethod
    def annotate_queryset(queryset, user=None, detail=False):
        """
        Annotate linked session counts uniquement si detail=True
        """
        if detail:
            queryset = queryset.annotate(
                linked_sessions_count=Count(
                    "versions__recording_sessions_as_software", distinct=True
                ),
                linked_sessions_from_other_users=Count(
                    "versions__recording_sessions_as_software",
                    filter=~Q(
                        versions__recording_sessions_as_software__created_by=user
                    ),
                    distinct=True,
                ),
            )
        return queryset

    def create(self, validated_data):
        references_data = validated_data.pop("references", [])
        contacts_data = validated_data.pop("contacts", [])
        users_data = validated_data.pop("users", [])

        software = Software.objects.create(**validated_data)

        # ✅ assign existing references
        if references_data:
            software.references.set(references_data)

        # ✅ assign existing contacts
        if contacts_data:
            software.contacts.set(contacts_data)

        # ✅ assign existing users
        if users_data:
            user_ids = [user["id"] for user in users_data if "id" in user]
            software.users.set(user_ids)

        return software

    def update(self, instance, validated_data):
        references_data = validated_data.pop("references", None)
        contacts_data = validated_data.pop("contacts", None)
        users_data = validated_data.pop("users", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # ✅ update references if provided
        if references_data is not None:
            instance.references.set(references_data)

        # ✅ update contacts if provided
        if contacts_data is not None:
            instance.contacts.set(contacts_data)

        # ✅ update users if provided
        if users_data is not None:
            user_ids = [user["id"] for user in users_data if "id" in user]
            instance.users.set(user_ids)

        instance.save()
        return instance


class SpeciesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Species
        fields = "__all__"


class ProtocolSerializer(serializers.ModelSerializer):
    user = LegacyUserSerializer(read_only=True)

    class Meta:
        model = Protocol
        fields = "__all__"
        read_only_fields = ("created_by", "created_at", "modified_at")


class SoftwareVersionSerializer(serializers.ModelSerializer):
    software = SoftwareSerializer(read_only=True)
    software_id = serializers.PrimaryKeyRelatedField(
        source="software",
        queryset=Software.objects.all(),
        write_only=True,
    )
    software_name = serializers.CharField(source="software.name", read_only=True)

    linked_sessions_count = serializers.IntegerField(read_only=True)
    linked_sessions_from_other_users = serializers.IntegerField(read_only=True)

    class Meta:
        model = SoftwareVersion
        fields = [
            "id",
            "software",
            "software_id",
            "software_name",
            "version",
            "release_date",
            "created_at",
            "modified_at",
            "created_by",
            "linked_sessions_count",
            "linked_sessions_from_other_users",
        ]
        read_only_fields = [
            "created_at",
            "modified_at",
            "created_by",
            "linked_sessions_count",
            "linked_sessions_from_other_users",
        ]


class StrainSerializer(serializers.ModelSerializer):
    species = SpeciesSerializer(read_only=True)  # lecture complète
    species_id = serializers.PrimaryKeyRelatedField(
        queryset=Species.objects.all(), write_only=True, source="species"
    )

    class Meta:
        model = Strain
        fields = "__all__"

    def create(self, validated_data):
        return Strain.objects.create(**validated_data)

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


# class StrainSerializer(serializers.ModelSerializer):
#     species = SpeciesSerializer()

#     class Meta:
#         model = Strain
#         fields = "__all__"

#     def create(self, validated_data):
#         species_data = validated_data.pop("species")
#         species = Species.objects.create(**species_data)
#         strain = Strain.objects.create(species=species, **validated_data)
#         return strain

#     def update(self, instance, validated_data):
#         species_data = validated_data.pop("species", None)
#         if species_data:
#             species = instance.species
#             for attr, value in species_data.items():
#                 setattr(species, attr, value)
#             species.save()
#         for attr, value in validated_data.items():
#             setattr(instance, attr, value)
#         instance.save()
#         return instance


# class AnimalProfileWriteSerializer(serializers.ModelSerializer):
#     strain = serializers.PrimaryKeyRelatedField(queryset=Strain.objects.all())

#     class Meta:
#         model = AnimalProfile
#         fields = "__all__"


# class AnimalProfileReadSerializer(serializers.ModelSerializer):
#     strain = StrainReadSerializer()

#     class Meta:
#         model = AnimalProfile
#         fields = "__all__"


class AnimalProfileSerializer(serializers.ModelSerializer):
    strain = StrainSerializer(read_only=True)
    strain_id = serializers.PrimaryKeyRelatedField(
        queryset=Strain.objects.all(), write_only=True, source="strain"
    )

    class Meta:
        model = AnimalProfile
        fields = "__all__"


# class AnimalProfileSerializer(serializers.ModelSerializer):
#     strain = StrainSerializer()

#     class Meta:
#         model = AnimalProfile
#         fields = "__all__"

#     def create(self, validated_data):
#         strain_data = validated_data.pop("strain")
#         strain = StrainSerializer.create(StrainSerializer(), validated_data=strain_data)
#         animal_profile = AnimalProfile.objects.create(strain=strain, **validated_data)
#         return animal_profile

#     def update(self, instance, validated_data):
#         strain_data = validated_data.pop("strain", None)
#         if strain_data:
#             strain_serializer = StrainSerializer(instance.strain, data=strain_data)
#             if strain_serializer.is_valid():
#                 strain_serializer.save()
#         for attr, value in validated_data.items():
#             setattr(instance, attr, value)
#         instance.save()
#         return instance


# class SubjectSerializer(serializers.ModelSerializer):
#     user = LegacyUserSerializer(read_only=True)
#     strain = StrainSerializer(read_only=True)
#     animal_profile = AnimalProfileSerializer()

#     class Meta:
#         model = Subject
#         fields = "__all__"

#     def update(self, instance, validated_data):
#         animal_profile_data = validated_data.pop("animal_profile", None)

#         for attr, value in validated_data.items():
#             setattr(instance, attr, value)
#         instance.save()

#         if animal_profile_data:
#             animal_profile = instance.animal_profile

#             if animal_profile:
#                 for attr, value in animal_profile_data.items():
#                     setattr(animal_profile, attr, value)
#                 animal_profile.save()
#             else:
#                 new_animal_profile = AnimalProfile.objects.create(**animal_profile_data)
#                 instance.animal_profile = new_animal_profile
#                 instance.save()

#         return instance

#     def create(self, validated_data):
#         animal_profile_data = validated_data.pop("animal_profile", None)

#         subject = Subject.objects.create(**validated_data)

#         if animal_profile_data:
#             animal_profile = AnimalProfile.objects.create(**animal_profile_data)
#             subject.animal_profile = animal_profile
#             subject.save()

#         return subject


# class SubjectReadSerializer(serializers.ModelSerializer):
#     user = LegacyUserSerializer(read_only=True)
#     strain = StrainReadSerializer(read_only=True)
#     animal_profile = AnimalProfileReadSerializer()

#     class Meta:
#         model = Subject
#         fields = "__all__"


# class SubjectWriteSerializer(serializers.ModelSerializer):
#     animal_profile = AnimalProfileWriteSerializer()

#     class Meta:
#         model = Subject
#         fields = "__all__"

#     def create(self, validated_data):
#         animal_profile_data = validated_data.pop("animal_profile", None)

#         subject = Subject.objects.create(**validated_data)

#         if animal_profile_data:
#             animal_profile = AnimalProfileWriteSerializer().create(animal_profile_data)
#             subject.animal_profile = animal_profile
#             subject.save()

#         return subject

#     def update(self, instance, validated_data):
#         animal_profile_data = validated_data.pop("animal_profile", None)

#         for attr, value in validated_data.items():
#             setattr(instance, attr, value)
#         instance.save()

#         if animal_profile_data:
#             if instance.animal_profile:
#                 serializer = AnimalProfileWriteSerializer(
#                     instance=instance.animal_profile, data=animal_profile_data, partial=True
#                 )
#                 serializer.is_valid(raise_exception=True)
#                 serializer.save()
#             else:
#                 instance.animal_profile = AnimalProfileWriteSerializer().create(animal_profile_data)
#                 instance.save()

#         return instance


# ------------------------
# Subject Serializer
# ------------------------
class SubjectSerializer(serializers.ModelSerializer):
    user = LegacyUserSerializer(read_only=True)
    animal_profile = AnimalProfileSerializer()

    class Meta:
        model = Subject
        fields = "__all__"

    def create(self, validated_data):
        animal_profile_data = validated_data.pop("animal_profile", None)
        subject = Subject.objects.create(**validated_data)

        if animal_profile_data:
            serializer = AnimalProfileSerializer(data=animal_profile_data)
            serializer.is_valid(raise_exception=True)
            animal_profile = serializer.save()
            subject.animal_profile = animal_profile
            subject.save()

        return subject

    def update(self, instance, validated_data):
        animal_profile_data = validated_data.pop("animal_profile", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if animal_profile_data:
            if instance.animal_profile:
                serializer = AnimalProfileSerializer(
                    instance=instance.animal_profile,
                    data=animal_profile_data,
                    partial=True,
                )
                serializer.is_valid(raise_exception=True)
                serializer.save()
            else:
                serializer = AnimalProfileSerializer(data=animal_profile_data)
                serializer.is_valid(raise_exception=True)
                instance.animal_profile = serializer.save()
                instance.save()

        return instance


class StudyShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Study
        fields = ("id", "name", "description")


class RecordingSessionSerializer(serializers.ModelSerializer):
    # ---- Nested serializers GET (read only) ----
    protocol = ProtocolSerializer(read_only=True)
    studies = StudyShortSerializer(many=True, read_only=True)
    laboratory = LaboratorySerializer(read_only=True)
    animal_profiles = AnimalProfileSerializer(many=True, read_only=True)
    equipment_acquisition_software = SoftwareVersionSerializer(
        many=True, read_only=True
    )
    equipment_acquisition_hardware_soundcards = HardwareSerializer(
        many=True, read_only=True
    )
    equipment_acquisition_hardware_speakers = HardwareSerializer(
        many=True, read_only=True
    )
    equipment_acquisition_hardware_amplifiers = HardwareSerializer(
        many=True, read_only=True
    )
    equipment_acquisition_hardware_microphones = HardwareSerializer(
        many=True, read_only=True
    )
    references = ReferenceSerializer(many=True, read_only=True)

    # ---- Write fields POST/PUT/PATCH ----
    protocol_id = serializers.PrimaryKeyRelatedField(
        queryset=Protocol.objects.all(),
        source="protocol",
        write_only=True,
        required=False,
        allow_null=True,
    )
    study_ids = serializers.PrimaryKeyRelatedField(
        queryset=Study.objects.all(),
        source="studies",
        many=True,
        write_only=True,
        required=False,
    )
    laboratory_id = serializers.PrimaryKeyRelatedField(
        queryset=Laboratory.objects.all(),
        source="laboratory",
        write_only=True,
        required=False,
        allow_null=True,
    )
    animal_profile_ids = serializers.PrimaryKeyRelatedField(
        queryset=AnimalProfile.objects.all(),
        source="animal_profiles",
        many=True,
        write_only=True,
        required=False,
    )
    equipment_acquisition_software_ids = serializers.PrimaryKeyRelatedField(
        queryset=SoftwareVersion.objects.all(),
        source="equipment_acquisition_software",
        many=True,
        write_only=True,
        required=False,
    )
    equipment_acquisition_hardware_soundcard_ids = serializers.PrimaryKeyRelatedField(
        queryset=Hardware.objects.filter(type="soundcard"),
        source="equipment_acquisition_hardware_soundcards",
        many=True,
        write_only=True,
        required=False,
    )
    equipment_acquisition_hardware_speaker_ids = serializers.PrimaryKeyRelatedField(
        queryset=Hardware.objects.filter(type="speaker"),
        source="equipment_acquisition_hardware_speakers",
        many=True,
        write_only=True,
        required=False,
    )
    equipment_acquisition_hardware_amplifier_ids = serializers.PrimaryKeyRelatedField(
        queryset=Hardware.objects.filter(type="amplifier"),
        source="equipment_acquisition_hardware_amplifiers",
        many=True,
        write_only=True,
        required=False,
    )
    equipment_acquisition_hardware_microphone_ids = serializers.PrimaryKeyRelatedField(
        queryset=Hardware.objects.filter(type="microphone"),
        source="equipment_acquisition_hardware_microphones",
        many=True,
        write_only=True,
        required=False,
    )
    references_ids = serializers.PrimaryKeyRelatedField(
        queryset=Reference.objects.all(),
        source="references",
        many=True,
        write_only=True,
        required=False,
    )

    equipment_channels = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    equipment_sound_isolation = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )

    context_temperature_value = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    context_temperature_unit = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    context_brightness = serializers.FloatField(required=False, allow_null=True)

    is_multiple = serializers.BooleanField(required=False, default=False)

    class Meta:
        model = RecordingSession
        fields = "__all__"

    # ---- Validation ----
    def validate(self, data):
        errors = {}
        user = self.context["request"].user

        # 1️⃣ validation on date if is_multiple is False
        is_multiple = data.get(
            "is_multiple", getattr(self.instance, "is_multiple", False)
        )

        if (
            not is_multiple
            and not data.get("date")
            and not getattr(self.instance, "date", None)
        ):
            errors["date"] = "A date is required for single recording sessions."

        # 2️⃣ Validation of non-None fields
        for field in ["name", "date"]:
            if field in data and data[field] is None:
                if field == "date" and is_multiple:
                    continue
                errors[field] = f"{field} cannot be None."

        # 3️⃣ Validation of uniqueness per user
        name = data.get("name", getattr(self.instance, "name", None))
        if name:
            qs = RecordingSession.objects.filter(name=name, created_by=user)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                errors["name"] = "You already have a recording session with this name."

        # 4️⃣ Raise ValidationError if necessary
        if errors:
            raise serializers.ValidationError(errors)

        return data

    # ---- Helpers ----
    def _extract_m2m(self, validated_data):
        return {
            "studies": validated_data.pop("studies", None),
            "animal_profiles": validated_data.pop("animal_profiles", None),
            "equipment_acquisition_software": validated_data.pop(
                "equipment_acquisition_software", None
            ),
            "equipment_acquisition_hardware_soundcards": validated_data.pop(
                "equipment_acquisition_hardware_soundcards", None
            ),
            "equipment_acquisition_hardware_microphones": validated_data.pop(
                "equipment_acquisition_hardware_microphones", None
            ),
            "equipment_acquisition_hardware_speakers": validated_data.pop(
                "equipment_acquisition_hardware_speakers", None
            ),
            "equipment_acquisition_hardware_amplifiers": validated_data.pop(
                "equipment_acquisition_hardware_amplifiers", None
            ),
            "references": validated_data.pop("references", None),
        }

    def _assign_m2m(self, instance, m2m_fields):
        for field, value in m2m_fields.items():
            if value is not None:
                getattr(instance, field).set(value)

    # ---- Create ----
    def create(self, validated_data):
        m2m_fields = self._extract_m2m(validated_data)
        laboratory = validated_data.pop("laboratory", None)

        if (
            validated_data.get("status") == "published"
            and validated_data.get("protocol") is None
        ):
            raise serializers.ValidationError(
                {"protocol_id": "A protocol is required for published sessions."}
            )

        instance = RecordingSession.objects.create(
            **validated_data, laboratory=laboratory
        )
        self._assign_m2m(instance, m2m_fields)
        return instance

    # ---- Update ----
    def update(self, instance, validated_data):
        m2m_fields = self._extract_m2m(validated_data)

        if (
            validated_data.get("status") == "published"
            and validated_data.get("protocol") is None
        ):
            raise serializers.ValidationError(
                {"protocol_id": "A protocol is required for published sessions."}
            )

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if "laboratory" in validated_data:
            instance.laboratory = validated_data["laboratory"]

        self._assign_m2m(instance, m2m_fields)
        instance.save()
        return instance


class RecordingSessionShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecordingSession
        fields = ("id", "name")


class StudySerializer(serializers.ModelSerializer):
    recording_sessions = RecordingSessionShortSerializer(many=True, required=False)

    class Meta:
        model = Study
        fields = "__all__"


class FileSerializer(serializers.ModelSerializer):
    repository_id = serializers.PrimaryKeyRelatedField(
        source="repository",
        queryset=Repository.objects.all(),
        required=False,
        write_only=True,
    )
    repository = RepositorySerializer(required=False)
    recording_session_id = serializers.PrimaryKeyRelatedField(
        source="recording_session",
        queryset=RecordingSession.objects.all(),
        required=False,
        write_only=True,
    )
    recording_session = RecordingSessionSerializer(required=False)
    subjects = SubjectSerializer(many=True, required=False)

    class Meta:
        model = File
        fields = "__all__"

    def validate(self, attrs):
        # Validate DOI format
        if "doi" in attrs:
            attrs["doi"] = validate_doi(attrs["doi"])

        # Valider URL format
        if "link" in attrs:
            attrs["link"] = validate_url(attrs["link"])

        # Validate consistency between DOI and link
        return validate_doi_link_consistency(attrs)


class DatasetSerializer(serializers.ModelSerializer):
    files = FileSerializer(many=True, required=False)

    class Meta:
        model = Dataset
        fields = "__all__"


MODEL_MAP = {
    "protocol": Protocol,
    "software": Software,
    "hardware": Hardware,
    "animalprofile": AnimalProfile,
    "strain": Strain,
    "species": Species,
    "reference": Reference,
    "contact": Contact,
}


class FavoriteSerializer(serializers.ModelSerializer):
    content_type = serializers.SerializerMethodField()
    content_type_name = serializers.CharField(write_only=True)

    class Meta:
        model = Favorite
        fields = "__all__"
        read_only_fields = ("user", "created_at")

    def get_content_type(self, obj):
        return obj.content_type.model.lower()

    def validate(self, data):
        user = self.context["request"].user
        model_name = (data.get("content_type_name") or "").lower()

        if model_name not in Favorite.ALLOWED_MODELS:
            raise serializers.ValidationError(
                f"Favorites of type '{model_name}' are not allowed."
            )

        try:
            content_type = ContentType.objects.get(
                app_label="mousetube_api", model=MODEL_MAP[model_name]._meta.model_name
            )
        except ContentType.DoesNotExist:
            raise serializers.ValidationError(
                f"ContentType '{model_name}' does not exist."
            )

        object_id = data.get("object_id")
        if object_id is None:
            raise serializers.ValidationError("object_id is required.")

        ModelClass = MODEL_MAP[model_name]
        try:
            obj = ModelClass.objects.get(pk=object_id)
        except ModelClass.DoesNotExist:
            raise serializers.ValidationError(
                f"{model_name.capitalize()} with id {object_id} does not exist."
            )

        is_owner = getattr(obj, "created_by", None) == user
        is_validated = getattr(obj, "status", None) == "validated"
        if not (is_owner or is_validated):
            raise serializers.ValidationError(
                f"You can only favorite your own {model_name}s or validated ones."
            )
        data["content_type"] = content_type

        return data

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        validated_data.pop("content_type_name", None)
        return super().create(validated_data)


class PageViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = PageView
        fields = "__all__"


class TrackPageSerializer(serializers.Serializer):
    path = serializers.CharField(max_length=255)
