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
)

from django.contrib.auth.models import User


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


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = "__all__"


class UserProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = UserProfile
        fields = "__all__"


class HardwareSerializer(serializers.ModelSerializer):
    references = ReferenceSerializer(many=True, required=False)
    users = LegacyUserSerializer(many=True, required=False)

    class Meta:
        model = Hardware
        fields = "__all__"


class SoftwareSerializer(serializers.ModelSerializer):
    references = ReferenceSerializer(many=True, required=False)
    users = LegacyUserSerializer(many=True, required=False)

    class Meta:
        model = Software
        fields = "__all__"


class SpeciesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Species
        fields = "__all__"


class StrainSerializer(serializers.ModelSerializer):
    class Meta:
        model = Strain
        fields = "__all__"


class ProtocolSerializer(serializers.ModelSerializer):
    user = LegacyUserSerializer(read_only=True)

    class Meta:
        model = Protocol
        fields = "__all__"


class SoftwareVersionSerializer(serializers.ModelSerializer):
    software = SoftwareSerializer(read_only=True)

    class Meta:
        model = SoftwareVersion
        fields = "__all__"


class RecordingSessionSerializer(serializers.ModelSerializer):
    protocol = ProtocolSerializer(read_only=True)
    acquisition_software = SoftwareVersionSerializer(
        source="equipment_acquisition_software", many=True, read_only=True
    )

    class Meta:
        model = RecordingSession
        fields = "__all__"


class SubjectSerializer(serializers.ModelSerializer):
    user = LegacyUserSerializer(read_only=True)
    strain = StrainSerializer(read_only=True)

    class Meta:
        model = Subject
        fields = "__all__"


class AnimalProfileSerializer(serializers.ModelSerializer):
    subject = SubjectSerializer(read_only=True)

    class Meta:
        model = AnimalProfile
        fields = "__all__"


class FileSerializer(serializers.ModelSerializer):
    repository = RepositorySerializer(required=False)
    recording_session = RecordingSessionSerializer()
    subject = SubjectSerializer(required=False)

    class Meta:
        model = File
        fields = "__all__"


class DatasetSerializer(serializers.ModelSerializer):
    files = FileSerializer(many=True, required=False)

    class Meta:
        model = Dataset
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class PageViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = PageView
        fields = "__all__"


class TrackPageSerializer(serializers.Serializer):
    path = serializers.CharField(max_length=255)
