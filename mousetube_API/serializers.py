'''
Created by Nicolas Torquet at 27/10/2023
torquetn@igbmc.fr
Copyright: CNRS - INSERM - UNISTRA - ICS - IGBMC
CNRS - Mouse Clinical Institute
PHENOMIN, CNRS UMR7104, INSERM U964, Université de Strasbourg
Code under GPL v3.0 licence
'''

from rest_framework import serializers
from rest_framework.serializers import Serializer, FileField
from .models import *

class ReferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reference
        fields = '__all__'

class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = '__all__'


class SpeciesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Species
        fields = '__all__'


class ProtocolTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProtocolType
        fields = '__all__'


class SoftwareSerializer(serializers.ModelSerializer):
    references_and_tutorials = ReferenceSerializer(read_only=True, many=True)
    contacts = ContactSerializer(read_only=True, many=True)

    class Meta:
        model = Software
        fields = '__all__'