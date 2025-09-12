"""
Created by Nicolas Torquet at 27/10/2023
torquetn@igbmc.fr
Copyright: CNRS - INSERM - UNISTRA - ICS - IGBMC
CNRS - Mouse Clinical Institute
PHENOMIN, CNRS UMR7104, INSERM U964, Université de Strasbourg
Code under GPL v3.0 licence
"""

from rest_framework import serializers
from django_countries.serializer_fields import CountryField
from django.db.models import Count, Q
from .models import (
    Repository,
    Reference,
    LegacyUser,
    UserProfile,
    Hardware,
    Software,
    Species,
    Strain,
    Protocol,
    File,
    RecordingSession,
    Subject,
    PageView,
    SoftwareVersion,
    AnimalProfile,
    Dataset,
    Laboratory,
    Study,
    Favorite,
)

from django.contrib.auth.models import User
from djoser.serializers import UserCreateSerializer as BaseUserCreateSerializer
from django.contrib.contenttypes.models import ContentType


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
    class Meta:
        model = Repository
        fields = "__all__"


class ReferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reference
        fields = "__all__"


class LegacyUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = LegacyUser
        fields = "__all__"


class LaboratorySerializer(serializers.ModelSerializer):
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
    country = CountryField()

    class Meta:
        model = UserProfile
        fields = "__all__"


class HardwareSerializer(serializers.ModelSerializer):
    references = ReferenceSerializer(many=True, required=False)
    users = LegacyUserSerializer(many=True, required=False)

    class Meta:
        model = Hardware
        fields = "__all__"

    def create(self, validated_data):
        references_data = validated_data.pop("references", [])
        users_data = validated_data.pop("users", [])
        hardware = Hardware.objects.create(**validated_data)

        for ref_data in references_data:
            Reference.objects.create(hardware=hardware, **ref_data)

        user_ids = [user["id"] for user in users_data if "id" in user]
        if user_ids:
            hardware.users.set(user_ids)

        return hardware

    def update(self, instance, validated_data):
        references_data = validated_data.pop("references", None)
        users_data = validated_data.pop("users", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if references_data is not None:
            instance.references.all().delete()
            for ref_data in references_data:
                Reference.objects.create(hardware=instance, **ref_data)

        if users_data is not None:
            user_ids = [user["id"] for user in users_data if "id" in user]
            if user_ids:
                instance.users.set(user_ids)

        return instance


class SoftwareSerializer(serializers.ModelSerializer):
    references = ReferenceSerializer(many=True, required=False)
    users = LegacyUserSerializer(many=True, required=False)

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
        users_data = validated_data.pop("users", [])

        software = Software.objects.create(**validated_data)

        for ref_data in references_data:
            Reference.objects.create(software=software, **ref_data)

        user_ids = [user_data["id"] for user_data in users_data if "id" in user_data]
        if user_ids:
            software.users.set(user_ids)

        return software

    def update(self, instance, validated_data):
        references_data = validated_data.pop("references", None)
        users_data = validated_data.pop("users", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if references_data is not None:
            instance.references.all().delete()
            for ref_data in references_data:
                Reference.objects.create(software=instance, **ref_data)

        if users_data is not None:
            user_ids = [
                user_data["id"] for user_data in users_data if "id" in user_data
            ]
            if user_ids:
                instance.users.set(user_ids)

        return instance


class SpeciesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Species
        fields = "__all__"


class ProtocolSerializer(serializers.ModelSerializer):
    user = LegacyUserSerializer(read_only=True)
    is_favorite = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Protocol
        fields = [
            "id",
            "name",
            "description",
            "user",
            "animals_sex",
            "animals_age",
            "animals_housing",
            "context_number_of_animals",
            "context_duration",
            "context_cage",
            "context_bedding",
            "context_light_cycle",
            "context_temperature_value",
            "context_temperature_unit",
            "context_brightness",
            "status",
            "created_at",
            "modified_at",
            "created_by",
            "is_favorite",
        ]
        read_only_fields = ("created_by", "created_at", "modified_at")

    def get_is_favorite(self, obj):
        user = self.context["request"].user
        if not user.is_authenticated:
            return False
        protocol_ct = ContentType.objects.get_for_model(Protocol)
        return Favorite.objects.filter(
            user=user,
            content_type=protocol_ct,
            object_id=obj.id
        ).exists()


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
    species = SpeciesSerializer()

    class Meta:
        model = Strain
        fields = "__all__"

    def create(self, validated_data):
        species_data = validated_data.pop("species")
        species = Species.objects.create(**species_data)
        strain = Strain.objects.create(species=species, **validated_data)
        return strain

    def update(self, instance, validated_data):
        species_data = validated_data.pop("species", None)
        if species_data:
            species = instance.species
            for attr, value in species_data.items():
                setattr(species, attr, value)
            species.save()
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class AnimalProfileSerializer(serializers.ModelSerializer):
    strain = StrainSerializer()

    class Meta:
        model = AnimalProfile
        fields = "__all__"

    def create(self, validated_data):
        strain_data = validated_data.pop("strain")
        strain = StrainSerializer.create(StrainSerializer(), validated_data=strain_data)
        animal_profile = AnimalProfile.objects.create(strain=strain, **validated_data)
        return animal_profile

    def update(self, instance, validated_data):
        strain_data = validated_data.pop("strain", None)
        if strain_data:
            strain_serializer = StrainSerializer(instance.strain, data=strain_data)
            if strain_serializer.is_valid():
                strain_serializer.save()
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class SubjectSerializer(serializers.ModelSerializer):
    user = LegacyUserSerializer(read_only=True)
    strain = StrainSerializer(read_only=True)
    animal_profile = AnimalProfileSerializer()

    class Meta:
        model = Subject
        fields = "__all__"

    def update(self, instance, validated_data):
        animal_profile_data = validated_data.pop("animal_profile", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if animal_profile_data:
            animal_profile = instance.animal_profile

            if animal_profile:
                for attr, value in animal_profile_data.items():
                    setattr(animal_profile, attr, value)
                animal_profile.save()
            else:
                new_animal_profile = AnimalProfile.objects.create(**animal_profile_data)
                instance.animal_profile = new_animal_profile
                instance.save()

        return instance

    def create(self, validated_data):
        animal_profile_data = validated_data.pop("animal_profile", None)

        subject = Subject.objects.create(**validated_data)

        if animal_profile_data:
            animal_profile = AnimalProfile.objects.create(**animal_profile_data)
            subject.animal_profile = animal_profile
            subject.save()

        return subject


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

        is_multiple = data.get(
            "is_multiple", getattr(self.instance, "is_multiple", False)
        )

        if (
            not is_multiple
            and not data.get("date")
            and not getattr(self.instance, "date", None)
        ):
            errors["date"] = "A date is required for single recording sessions."

        for field in ["name", "date"]:
            if field in data and data[field] is None:
                if field == "date" and is_multiple:
                    continue
                errors[field] = f"{field} cannot be None."

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
    repository = RepositorySerializer(required=False)
    recording_session = RecordingSessionSerializer()
    subjects = SubjectSerializer(many=True, required=False)

    class Meta:
        model = File
        fields = "__all__"

    def create(self, validated_data):
        subjects_data = validated_data.pop("subjects", [])
        file = File.objects.create(**validated_data)

        for subject_data in subjects_data:
            subject_id = subject_data.get("id")
            if subject_id:
                subject_obj = Subject.objects.get(id=subject_id)
                for attr, value in subject_data.items():
                    if attr != "id":
                        setattr(subject_obj, attr, value)
                subject_obj.save()
            else:
                subject_obj = Subject.objects.create(**subject_data)
            file.subjects.add(subject_obj)
        return file

    def update(self, instance, validated_data):
        subjects_data = validated_data.pop("subjects", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if subjects_data is not None:
            subject_objs = []
            for subject_data in subjects_data:
                subject_id = subject_data.get("id")
                if subject_id:
                    subject_obj = Subject.objects.get(id=subject_id)
                    for attr, value in subject_data.items():
                        if attr != "id":
                            setattr(subject_obj, attr, value)
                    subject_obj.save()
                else:
                    subject_obj = Subject.objects.create(**subject_data)
                subject_objs.append(subject_obj)
            instance.subjects.set(subject_objs)

        return instance


class DatasetSerializer(serializers.ModelSerializer):
    files = FileSerializer(many=True, required=False)

    class Meta:
        model = Dataset
        fields = "__all__"

MODEL_MAP = {
    "protocol": Protocol,
    "software": Software,
    "hardware": Hardware,
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
        user = self.context['request'].user
        model_name = (data.get("content_type_name") or "").lower()

        if model_name not in Favorite.ALLOWED_MODELS:
            raise serializers.ValidationError(
                f"Favorites of type '{model_name}' are not allowed."
            )

        try:
            content_type = ContentType.objects.get(app_label='mousetube_api', model=model_name)
        except ContentType.DoesNotExist:
            raise serializers.ValidationError(f"ContentType '{model_name}' does not exist.")

        object_id = data.get("object_id")
        if object_id is None:
            raise serializers.ValidationError("object_id is required.")

        ModelClass = MODEL_MAP[model_name]
        try:
            obj = ModelClass.objects.get(pk=object_id)
        except ModelClass.DoesNotExist:
            raise serializers.ValidationError(f"{model_name.capitalize()} with id {object_id} does not exist.")

        is_owner = getattr(obj, "created_by", None) == user
        is_validated = getattr(obj, "status", None) == "validated"
        if not (is_owner or is_validated):
            raise serializers.ValidationError(
                f"You can only favorite your own {model_name}s or validated ones."
            )
        data["content_type"] = content_type

        return data

    def create(self, validated_data):
        validated_data["user"] = self.context['request'].user
        validated_data.pop("content_type_name", None)
        return super().create(validated_data)


class PageViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = PageView
        fields = "__all__"


class TrackPageSerializer(serializers.Serializer):
    path = serializers.CharField(max_length=255)
