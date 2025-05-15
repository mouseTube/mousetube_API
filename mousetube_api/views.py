"""
Created by Nicolas Torquet at 27/10/2023
torquetn@igbmc.fr
Copyright: CNRS - INSERM - UNISTRA - ICS - IGBMC
CNRS - Mouse Clinical Institute
PHENOMIN, CNRS UMR7104, INSERM U964, Université de Strasbourg
Code under GPL v3.0 licence
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import viewsets
from .models import *
from .serializers import *
from django_countries import countries


class CountryAPIView(APIView):
    def get(self, *arg, **kwargs):
        country = countries
        return Response(country)


class RepositoryViewSet(viewsets.ModelViewSet):
    queryset = Repository.objects.all()
    serializer_class = RepositorySerializer


class ReferenceViewSet(viewsets.ModelViewSet):
    queryset = Reference.objects.all()
    serializer_class = ReferenceSerializer


class ContactViewSet(viewsets.ModelViewSet):
    queryset = Contact.objects.all()
    serializer_class = ContactSerializer


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer


class UserProfileViewSet(viewsets.ModelViewSet):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer


class SoftwareViewSet(viewsets.ModelViewSet):
    queryset = Software.objects.all()
    serializer_class = SoftwareSerializer


class SoftwareAPIView(APIView):
    def get(self, *arg, **kwargs):
        software = Software.objects.all()
        serializer = SoftwareSerializer(software, many=True)
        return Response(serializer.data)


class AcquisitionSoftwareAPIView(APIView):
    def get(self, *arg, **kwargs):
        software = Software.objects.filter(software_type="acquisition")
        serializer = SoftwareSerializer(software, many=True)
        return Response(serializer.data)


class AnalysisSoftwareAPIView(APIView):
    def get(self, *arg, **kwargs):
        software = Software.objects.filter(software_type="analysis")
        serializer = SoftwareSerializer(software, many=True)
        return Response(serializer.data)


class AcquisitionAndAnalysisSoftwareAPIView(APIView):
    def get(self, *arg, **kwargs):
        software = Software.objects.filter(software_type="acquisition and analysis")
        serializer = SoftwareSerializer(software, many=True)
        return Response(serializer.data)


class SoftwareViewSet(viewsets.ModelViewSet):
    queryset = Software.objects.all()
    serializer_class = SoftwareSerializer


class HardwareAPIView(APIView):
    def get(self, *arg, **kwargs):
        hardware = Hardware.objects.all()
        serializer = HardwareSerializer(hardware, many=True)
        return Response(serializer.data)


class SpeciesViewSet(viewsets.ModelViewSet):
    queryset = Species.objects.all()
    serializer_class = SpeciesSerializer


class StrainViewSet(viewsets.ModelViewSet):
    queryset = Strain.objects.all()
    serializer_class = StrainSerializer


class MetadataViewSet(viewsets.ModelViewSet):
    queryset = Metadata.objects.all()
    serializer_class = MetadataSerializer


class ProtocolViewSet(viewsets.ModelViewSet):
    queryset = Protocol.objects.all()
    serializer_class = ProtocolSerializer


class FileViewSet(viewsets.ModelViewSet):
    queryset = File.objects.all()
    serializer_class = FileSerializer


class ProtocolMetadataViewSet(viewsets.ModelViewSet):
    queryset = Metadata.objects.filter(
        metadata_field__metadata_category__metadata_categories__name_metadata_category="protocol"
    )
    #  https://dev.to/azayshrestha/understanding-djangos-prefetchrelated-and-prefetch-4i2o
    serializer_class = ProtocolMetadataSerializer
