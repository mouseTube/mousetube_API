'''
Created by Nicolas Torquet at 27/10/2023
torquetn@igbmc.fr
Copyright: CNRS - INSERM - UNISTRA - ICS - IGBMC
CNRS - Mouse Clinical Institute
PHENOMIN, CNRS UMR7104, INSERM U964, Université de Strasbourg
Code under GPL v3.0 licence
'''
from django_countries.fields import Country
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


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = '__all__'

class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = '__all__'


class SpeciesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Species
        fields = '__all__'


class StrainSerializer(serializers.ModelSerializer):
    class Meta:
        model = Strain
        fields = '__all__'


class ProtocolTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProtocolType
        fields = '__all__'


class ProtocolSerializer(serializers.ModelSerializer):
    protocolType = ProtocolTypeSerializer(many=True, required=False)
    class Meta:
        model = Protocol
        fields = '__all__'


class ExperimentSerializer(serializers.ModelSerializer):
    protocol = ProtocolSerializer(many=True, required=False)
    class Meta:
        model = Experiment
        fields = '__all__'


class FileSerializer(serializers.ModelSerializer):
    experiment = ExperimentSerializer(many=True, required=False)
    class Meta:
        model = File
        fields = '__all__'

class SoftwareSerializer(serializers.ModelSerializer):
    references_and_tutorials = ReferenceSerializer(many=True, required=False)
    contacts = ContactSerializer(many=True, required=False)

    class Meta:
        model = Software
        fields = "__all__"
        # extra_kwargs = {'references_and_tutorials': {'required': False},
        #                 'contacts': {'required': False}}
