'''
Created by Nicolas Torquet at 27/10/2023
torquetn@igbmc.fr
Copyright: CNRS - INSERM - UNISTRA - ICS - IGBMC
CNRS - Mouse Clinical Institute
PHENOMIN, CNRS UMR7104, INSERM U964, Université de Strasbourg
Code under GPL v3.0 licence
'''
from django_countries.fields import Country
from djoser.serializers import UserSerializer
from rest_framework import serializers
from rest_framework.serializers import Serializer, FileField
from .models import *
from django_countries.serializer_fields import CountryField


# class CountrySerializer(serializers.Serializer):
#     country = CountryField()
#     class Meta:
#         fields = '__all__'

class RepositorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Repository
        fields = '__all__'


class ReferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reference
        fields = '__all__'


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = '__all__'

class UserProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    class Meta:
        model = UserProfile
        fields = '__all__'

class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = '__all__'


class HardwareSerializer(serializers.ModelSerializer):
    reference = ReferenceSerializer(many=True, required=False)

    class Meta:
        model = Hardware
        fields = "__all__"
        # extra_kwargs = {'references_and_tutorials': {'required': False},
        #                 'contacts': {'required': False}}



class SoftwareSerializer(serializers.ModelSerializer):
    references_and_tutorials = ReferenceSerializer(many=True, required=False)
    contacts = ContactSerializer(many=True, required=False)

    class Meta:
        model = Software
        fields = "__all__"
        # extra_kwargs = {'references_and_tutorials': {'required': False},
        #                 'contacts': {'required': False}}


class SpeciesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Species
        fields = '__all__'


class StrainSerializer(serializers.ModelSerializer):
    class Meta:
        model = Strain
        fields = '__all__'


class MetadataCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = MetadataCategory
        fields = '__all__'

class MetadataFieldSerializer(serializers.ModelSerializer):
    metadata_category = MetadataCategorySerializer(many=True, required=False)
    class Meta:
        model = MetadataField
        fields = '__all__'

class MetadataSerializer(serializers.ModelSerializer):
    metadata_field = MetadataFieldSerializer(many=True, required=False)
    class Meta:
        model = Metadata
        fields = '__all__'


class ProtocolSerializer(serializers.ModelSerializer):
    protocol_keywords = MetadataSerializer(many=True, required=False)
    class Meta:
        model = Protocol
        fields = '__all__'



class FileSerializer(serializers.ModelSerializer):
    repository = RepositorySerializer(many=True, required=False)
    microphones = HardwareSerializer(many=True, required=False)
    acquisition_hardware = HardwareSerializer(required=False)
    acquisition_software = SoftwareSerializer(required=False)
    strains = StrainSerializer(many=True, required=False)
    protocol = ProtocolSerializer(required=False)
    created_by = UserProfileSerializer(required=False)
    class Meta:
        model = File
        fields = '__all__'


class ProtocolMetadataSerializer(serializers.ModelSerializer):
    metadata_field = MetadataFieldSerializer(many=True)
    class Meta:
        model = Metadata
        fields = '__all__'