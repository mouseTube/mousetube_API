"""
Created by Nicolas Torquet at 27/10/2023
torquetn@igbmc.fr
Copyright: CNRS - INSERM - UNISTRA - ICS - IGBMC
CNRS - Mouse Clinical Institute
PHENOMIN, CNRS UMR7104, INSERM U964, Université de Strasbourg
Code under GPL v3.0 licence
"""

# from djoser.serializers import UserSerializer
from rest_framework import serializers
from django_countries.serializer_fields import CountryField
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
)

from django.contrib.auth.models import User
from djoser.serializers import UserCreateSerializer as BaseUserCreateSerializer


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


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "email"]


class UserProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
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

    class Meta:
        model = Software
        fields = "__all__"

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


# class SpeciesSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Species
#         fields = "__all__"


# class StrainSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Strain
#         fields = "__all__"


class ProtocolSerializer(serializers.ModelSerializer):
    user = LegacyUserSerializer(read_only=True)

    class Meta:
        model = Protocol
        fields = "__all__"


class SoftwareVersionSerializer(serializers.ModelSerializer):
    software_name = serializers.CharField(source="software.name", read_only=True)
    software = SoftwareSerializer(read_only=True)

    class Meta:
        model = SoftwareVersion
        fields = [
            "id",
            "software",
            "software_name",
            "version",
            "release_date",
            "created_at",
            "modified_at",
            "created_by",
        ]
        read_only_fields = ["created_at", "modified_at", "created_by"]


class SpeciesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Species
        fields = "__all__"


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
    id = serializers.IntegerField(required=False)
    user = LegacyUserSerializer(read_only=True)
    animal_profile = AnimalProfileSerializer()

    class Meta:
        model = Subject
        fields = "__all__"


class LaboratorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Laboratory
        fields = "__all__"


class StudyShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Study
        fields = ("id", "name", "description")

class RecordingSessionSerializer(serializers.ModelSerializer):
    # ---- Nested serializers pour GET (read only) ----
    protocol = ProtocolSerializer(read_only=True)
    studies = StudyShortSerializer(many=True, read_only=True)
    laboratory = LaboratorySerializer(read_only=True)
    animal_profiles = AnimalProfileSerializer(many=True, read_only=True)
    equipment_acquisition_software = SoftwareVersionSerializer(many=True, read_only=True)
    equipment_acquisition_hardware_soundcards = HardwareSerializer(many=True, read_only=True)
    equipment_acquisition_hardware_speakers = HardwareSerializer(many=True, read_only=True)
    equipment_acquisition_hardware_amplifiers = HardwareSerializer(many=True, read_only=True)
    equipment_acquisition_hardware_microphones = HardwareSerializer(many=True, read_only=True)

    # ---- Write fields pour POST/PUT/PATCH ----
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

    # ---- Champs context et equipment ----
    context = serializers.DictField(write_only=True, required=False)
    equipment = serializers.DictField(write_only=True, required=False)

    class Meta:
        model = RecordingSession
        fields = "__all__"

    # ---- Validation globale du payload ----
    def validate(self, data):
        errors = {}

        # Champs simples
        simple_fields = ["name", "description", "date", "duration", "status", "protocol", "laboratory"]
        for field in simple_fields:
            if field in data and data[field] is None:
                errors[field] = f"{field} cannot be None."

        # M2M fields
        m2m_fields = [
            "studies", "animal_profiles", "equipment_acquisition_software",
            "equipment_acquisition_hardware_soundcards",
            "equipment_acquisition_hardware_speakers",
            "equipment_acquisition_hardware_amplifiers",
            "equipment_acquisition_hardware_microphones",
        ]
        for field in m2m_fields:
            if field in data and not isinstance(data[field], list):
                errors[field] = f"{field} must be a list of IDs."

        # Context
        context = data.get("context")
        if context is not None:
            if not isinstance(context, dict):
                errors["context"] = "Context must be a dictionary."
            else:
                temp = context.get("temperature")
                if temp and (not isinstance(temp, dict) or "value" not in temp or "unit" not in temp):
                    errors["context.temperature"] = "Temperature must be a dict with 'value' and 'unit'."
                brightness = context.get("brightness")
                if brightness is not None and not isinstance(brightness, (int, float)):
                    errors["context.brightness"] = "Brightness must be a number."

        # Equipment
        equipment = data.get("equipment")
        if equipment is not None:
            if not isinstance(equipment, dict):
                errors["equipment"] = "Equipment must be a dictionary."
            else:
                allowed_keys = {"channels", "sound_isolation", "soundcards", "microphones", "speakers", "amplifiers", "acquisition_software"}
                for key, val in equipment.items():
                    if key not in allowed_keys:
                        errors[f"equipment.{key}"] = f"Unexpected key '{key}' in equipment."
                    if key in {"soundcards", "microphones", "speakers", "amplifiers", "acquisition_software"} and not isinstance(val, list):
                        errors[f"equipment.{key}"] = f"{key} must be a list of IDs."

        if errors:
            raise serializers.ValidationError(errors)

        return data

    # ---- Helpers ----
    def _extract_m2m(self, validated_data):
        return {
            "studies": validated_data.pop("studies", None),
            "animal_profiles": validated_data.pop("animal_profiles", None),
            "equipment_acquisition_software": validated_data.pop("equipment_acquisition_software", None),
            "equipment_acquisition_hardware_soundcards": validated_data.pop("equipment_acquisition_hardware_soundcards", None),
            "equipment_acquisition_hardware_microphones": validated_data.pop("equipment_acquisition_hardware_microphones", None),
            "equipment_acquisition_hardware_speakers": validated_data.pop("equipment_acquisition_hardware_speakers", None),
            "equipment_acquisition_hardware_amplifiers": validated_data.pop("equipment_acquisition_hardware_amplifiers", None),
        }

    def _assign_m2m(self, instance, m2m_fields):
        for field, value in m2m_fields.items():
            if value is not None:
                getattr(instance, field).set(value)

    def _assign_context_equipment(self, instance, validated_data):
        # Context
        context_data = validated_data.pop("context", {})
        if "temperature" in context_data:
            temp = context_data["temperature"]
            instance.context_temperature_value = temp.get("value")
            instance.context_temperature_unit = temp.get("unit")
        instance.context_brightness = context_data.get("brightness")

        # Equipment
        equipment_data = validated_data.pop("equipment", {})
        instance.equipment_channels = equipment_data.get("channels")
        instance.equipment_sound_isolation = equipment_data.get("sound_isolation")

        # Hardware / software M2M
        if "soundcards" in equipment_data:
            instance.equipment_acquisition_hardware_soundcards.set(
                Hardware.objects.filter(id__in=equipment_data["soundcards"])
            )
        if "microphones" in equipment_data:
            instance.equipment_acquisition_hardware_microphones.set(
                Hardware.objects.filter(id__in=equipment_data["microphones"])
            )
        if "speakers" in equipment_data:
            instance.equipment_acquisition_hardware_speakers.set(
                Hardware.objects.filter(id__in=equipment_data["speakers"])
            )
        if "amplifiers" in equipment_data:
            instance.equipment_acquisition_hardware_amplifiers.set(
                Hardware.objects.filter(id__in=equipment_data["amplifiers"])
            )
        if "acquisition_software" in equipment_data:
            instance.equipment_acquisition_software.set(
                SoftwareVersion.objects.filter(id__in=equipment_data["acquisition_software"])
            )

    # ---- Création ----
    def create(self, validated_data):
        m2m_fields = self._extract_m2m(validated_data)
        laboratory = validated_data.pop("laboratory", None)

        # Validation protocole
        if validated_data.get("status") == "published" and validated_data.get("protocol") is None:
            raise serializers.ValidationError({"protocol_id": "A protocol is required for published sessions."})

        instance = RecordingSession.objects.create(**validated_data, laboratory=laboratory)
        self._assign_m2m(instance, m2m_fields)
        self._assign_context_equipment(instance, validated_data)
        instance.save()
        return instance

    # ---- Mise à jour ----
    def update(self, instance, validated_data):
        m2m_fields = self._extract_m2m(validated_data)
        laboratory = validated_data.pop("laboratory", None)

        # Validation protocole
        if validated_data.get("status") == "published" and validated_data.get("protocol") is None:
            raise serializers.ValidationError({"protocol_id": "A protocol is required for published sessions."})

        # Champs simples
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if laboratory is not None:
            instance.laboratory = laboratory

        self._assign_context_equipment(instance, validated_data)
        self._assign_m2m(instance, m2m_fields)
        instance.save()
        return instance


    # def validate(self, data):
    #     # add rules for validation if needed
    #     return data

    # def create(self, validated_data):
    #     return super().create(validated_data)

    # def update(self, instance, validated_data):
    #     return super().update(instance, validated_data)


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


class DatasetSerializer(serializers.ModelSerializer):
    files = FileSerializer(many=True, required=False)

    class Meta:
        model = Dataset
        fields = "__all__"


class PageViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = PageView
        fields = "__all__"


class TrackPageSerializer(serializers.Serializer):
    path = serializers.CharField(max_length=255)
