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
from rest_framework.pagination import PageNumberPagination
from rest_framework import permissions
import json
from rest_framework import viewsets, status, filters
from django_filters.rest_framework import DjangoFilterBackend
from django.http import Http404
from rest_framework.exceptions import PermissionDenied
from django.db.models import Count, Q, Sum
from rest_framework.generics import GenericAPIView
from django.db.models import OuterRef, Exists, IntegerField
from django.db.models.functions import Cast
from django.contrib.contenttypes.models import ContentType
from .models import (
    Repository,
    Reference,
    LegacyUser,
    UserProfile,
    Software,
    SoftwareVersion,
    Hardware,
    Species,
    Strain,
    Protocol,
    File,
    Subject,
    RecordingSession,
    PageView,
    Study,
    AnimalProfile,
    Laboratory,
    Favorite,
)
from .serializers import (
    SpeciesSerializer,
    StrainReadSerializer,
    StrainWriteSerializer,
    AnimalProfileSerializer,
    LaboratorySerializer,
    ProtocolSerializer,
    FileSerializer,
    HardwareSerializer,
    SoftwareSerializer,
    SoftwareVersionSerializer,
    RepositorySerializer,
    ReferenceSerializer,
    LegacyUserSerializer,
    UserProfileSerializer,
    TrackPageSerializer,
    SubjectSerializer,
    RecordingSessionSerializer,
    PageViewSerializer,
    StudySerializer,
    FavoriteSerializer,
)
from django_countries import countries
from django.utils.timezone import now
from django.db.models import F
from django.core.cache import cache
from django.core.management import call_command
from drf_spectacular.utils import (
    extend_schema,
    OpenApiParameter,
    extend_schema_serializer,
)
from django.shortcuts import render
from django.conf import settings
import os
from rest_framework.permissions import (
    IsAuthenticated,
    AllowAny,
)
from django.shortcuts import get_object_or_404


# ----------------------------
# Link ORCID
# ----------------------------
@extend_schema(
    request=None,
    responses={200: dict, 400: dict, 409: dict},
)
class LinkOrcidView(APIView):
    permission_classes = [IsAuthenticated]

    """
        Link an ORCID iD to the currently authenticated user.

        This endpoint is used after an ORCID OAuth2 authentication with the
        `process=connect` flag to associate the ORCID iD with an existing account.

        Behavior:
        - Validates that an ORCID iD is provided.
        - Returns an error if the ORCID is already linked to another user.
        - Returns an error if the current user already has a different ORCID set.
        - If valid:
            - Links the ORCID to the user's profile.
            - Sets the user's first and last name if those fields are still empty.

        Returns:
            - 200 OK with {"status": "linked"} if the association is successful.
            - 400 Bad Request or 409 Conflict on validation errors.

        Example error responses:
            - {"error": "Missing ORCID"}
            - {"error": "This ORCID is already linked to another user."}
            - {"error": "ORCID already linked to this account."}
    """

    def post(self, request):
        orcid = request.data.get("orcid", "").strip()
        first_name = request.data.get("firstName", "").strip()
        last_name = request.data.get("lastName", "").strip()
        user = request.user

        if not orcid:
            return Response(
                {"error": "Missing ORCID"}, status=status.HTTP_400_BAD_REQUEST
            )

        # ORCID already bind to another user
        if UserProfile.objects.filter(orcid=orcid).exclude(user=user).exists():
            return Response(
                {"error": "This ORCID is already linked to another user."},
                status=status.HTTP_409_CONFLICT,
            )

        profile, _ = UserProfile.objects.get_or_create(user=user)

        # Forbid ORCID modifification if already exist
        if profile.orcid and profile.orcid != orcid:
            return Response(
                {"error": "ORCID already linked to this account."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if first_name and not user.first_name:
            user.first_name = first_name
        if last_name and not user.last_name:
            user.last_name = last_name
        user.save()
        profile.orcid = orcid
        profile.save()

        return Response({"status": "linked"}, status=status.HTTP_200_OK)


# ----------------------------
# Pagination
# ----------------------------
class FilePagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


# ----------------------------
# Permissions
# ----------------------------
class IsCreatorOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow the creator of an object to edit or delete it.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.created_by == request.user


# ----------------------------
# Country
# ----------------------------
@extend_schema(
    request=None,
    responses={200: dict},
)
class CountryAPIView(APIView):
    def get(self, request, *args, **kwargs):
        return Response(countries)


# ----------------------------
# Laboratory
# ----------------------------
class LaboratoryAPIView(viewsets.ModelViewSet):
    queryset = Laboratory.objects.all().order_by("name")
    serializer_class = LaboratorySerializer

    def get_permissions(self):
        if self.action in ["create"]:
            return [permissions.IsAuthenticated()]
        if self.action in ["update", "partial_update", "destroy"]:
            return [permissions.IsAuthenticated(), IsCreatorOrReadOnly()]
        # list / retrieve
        return [permissions.AllowAny()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


# ----------------------------
# Repository
# ----------------------------
class RepositoryAPIView(APIView):
    serializer_class = RepositorySerializer

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="search", description="text search", required=False, type=str
            ),
        ]
    )
    def get(self, request, *args, **kwargs):
        search_query = request.GET.get("search", "")
        repositories = Repository.objects.all()

        # Search
        if search_query:
            search_fields = [
                "name",
                "description",
                "area",
                "url",
            ]
            search_q = Q()
            for field in search_fields:
                search_q |= Q(**{f"{field}__icontains": search_query})
            repositories = repositories.filter(search_q)

        repositories = repositories.order_by(F("name").asc(nulls_last=True))
        paginator = FilePagination()
        paginated_repositories = paginator.paginate_queryset(repositories, request)
        serializer = self.serializer_class(paginated_repositories, many=True)
        return paginator.get_paginated_response(serializer.data)


# ----------------------------
# Reference
# ----------------------------
@extend_schema_serializer(component_name="ReferenceNested")
class ReferenceSerializerNested(ReferenceSerializer):
    pass


@extend_schema(
    request=None,
    responses={200: ReferenceSerializerNested(many=True)},
)
class ReferenceAPIView(GenericAPIView):
    serializer_class = ReferenceSerializerNested

    def get(self, request, *args, **kwargs):
        queryset = Reference.objects.all()
        serializer = self.serializer_class(queryset, many=True)
        return Response(serializer.data)


# ----------------------------
# LegacyUser
# ----------------------------
class LegacyUserAPIView(GenericAPIView):
    serializer_class = LegacyUserSerializer

    def get(self, request, *args, **kwargs):
        queryset = LegacyUser.objects.all()
        serializer = self.serializer_class(queryset, many=True)
        return Response(serializer.data)


# ----------------------------
# UserProfile
# ----------------------------
class UserProfileListAPIView(GenericAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    @extend_schema(operation_id="api_user_profile_list_get")
    def get(self, request, *args, **kwargs):
        queryset = UserProfile.objects.all()
        user_id = request.query_params.get("user_id")
        if user_id:
            queryset = queryset.filter(user__id=user_id)
        serializer = self.serializer_class(queryset, many=True)
        return Response(serializer.data)


class UserProfileDetailAPIView(GenericAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    @extend_schema(operation_id="api_user_profile_detail_patch")
    def patch(self, request, *args, **kwargs):
        profile_id = kwargs.get("pk")
        if not profile_id:
            return Response(
                {"detail": "UserProfile id required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_profile = get_object_or_404(UserProfile, id=profile_id)
        if user_profile.user != request.user:
            return Response(
                {"detail": "Not authorized."}, status=status.HTTP_403_FORBIDDEN
            )

        serializer = self.serializer_class(
            user_profile, data=request.data, partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ----------------------------
# Hardware
# ----------------------------
class HardwareAPIView(GenericAPIView):
    serializer_class = HardwareSerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated()]
        return [AllowAny()]

    @extend_schema(
        operation_id="api_hardware_list",
        parameters=[
            OpenApiParameter(
                name="search", description="text search", required=False, type=str
            ),
            OpenApiParameter(
                name="filter", description="filter by type", required=False, type=str
            ),
        ],
    )
    def get(self, request, *args, **kwargs):
        search_query = request.GET.get("search", "")
        filter_query = request.GET.get("filter", "")
        hardware = Hardware.objects.all()

        # Search
        if search_query:
            search_fields = [
                "name",
                "type",
                "made_by",
                "references__name",
                "description",
            ]
            search_q = Q()
            for field in search_fields:
                search_q |= Q(**{f"{field}__icontains": search_query})
            hardware = hardware.filter(search_q)

        # Filter by type

        ALLOWED_FILTERS = ["microphone", "speaker", "soundcard", "amplifier"]

        if filter_query and filter_query in ALLOWED_FILTERS:
            hardware = hardware.filter(type=filter_query)

        hardware = hardware.order_by(F("name").asc(nulls_last=True))
        paginator = FilePagination()
        paginated_hardware = paginator.paginate_queryset(hardware, request)
        serializer = self.serializer_class(paginated_hardware, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            hardware = serializer.save()
            return Response(
                self.serializer_class(hardware).data, status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ----------------------------
# HardwareDetail
# ----------------------------
class HardwareDetailAPIView(GenericAPIView):
    serializer_class = HardwareSerializer

    def get_permissions(self):
        if self.request.method in ["PUT", "PATCH", "DELETE"]:
            return [IsAuthenticated()]
        return [AllowAny()]

    def get(self, request, pk, *args, **kwargs):
        hardware = get_object_or_404(Hardware, pk=pk)
        serializer = self.serializer_class(hardware)
        return Response(serializer.data)

    def put(self, request, pk, *args, **kwargs):
        hardware = get_object_or_404(Hardware, pk=pk)
        serializer = self.serializer_class(hardware, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk, *args, **kwargs):
        hardware = get_object_or_404(Hardware, pk=pk)
        serializer = self.serializer_class(hardware, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk, *args, **kwargs):
        hardware = get_object_or_404(Hardware, pk=pk)
        hardware.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SubjectViewSet(viewsets.ModelViewSet):
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer

    def get_permissions(self):
        if self.action == "create":
            return [IsAuthenticated()]
        if self.action in ["update", "partial_update", "destroy"]:
            return [IsAuthenticated(), IsCreatorOrReadOnly()]
        return [permissions.AllowAny()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class ProtocolPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


PROTOCOL_CT = ContentType.objects.get_for_model(Protocol)


class ProtocolViewSet(viewsets.ModelViewSet):
    queryset = Protocol.objects.all()
    serializer_class = ProtocolSerializer
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ["name"]
    filterset_fields = [
        "animals_sex",
        "animals_age",
        "animals_housing",
        "context_duration",
        "context_cage",
        "context_bedding",
        "context_light_cycle",
        "status",
    ]
    pagination_class = ProtocolPagination

    def get_permissions(self):
        if self.action == "create":
            return [permissions.IsAuthenticated()]
        if self.action in ["update", "partial_update", "destroy"]:
            return [permissions.IsAuthenticated(), IsCreatorOrReadOnly()]
        return [permissions.AllowAny()]

    def get_queryset(self):
        user = self.request.user
        ordering = self.request.query_params.get("ordering")

        if user.is_authenticated:
            qs = Protocol.objects.filter(Q(created_by=user) | Q(status="validated"))
            # annotation is_favorite_int
            favorite_subquery = Favorite.objects.filter(
                user=user, content_type=PROTOCOL_CT, object_id=OuterRef("pk")
            )
            qs = qs.annotate(
                is_favorite_int=Cast(Exists(favorite_subquery), IntegerField())
            )
            # Appliquer ordering si demandé, sinon par défaut
            if ordering:
                ordering_fields = []
                for field in ordering.split(","):
                    field = field.strip()
                    if field.lstrip("-") in ["name", "created_at", "is_favorite_int"]:
                        ordering_fields.append(field)
                if ordering_fields:
                    qs = qs.order_by(*ordering_fields)
                else:
                    qs = qs.order_by("-is_favorite_int", "name")
            else:
                qs = qs.order_by("-is_favorite_int", "name")
        else:
            qs = Protocol.objects.filter(status="validated")
            if ordering:
                ordering_fields = []
                for field in ordering.split(","):
                    field = field.strip()
                    if field.lstrip("-") in ["name", "created_at"]:
                        ordering_fields.append(field)
                if ordering_fields:
                    qs = qs.order_by(*ordering_fields)
                else:
                    qs = qs.order_by("name")
            else:
                qs = qs.order_by("name")

        return qs

    # -------------------------
    # Création
    # -------------------------
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class SpeciesViewSet(viewsets.ModelViewSet):
    queryset = Species.objects.all().order_by("name")
    serializer_class = SpeciesSerializer

    def get_permissions(self):
        if self.action == "create":
            return [IsAuthenticated()]
        if self.action in ["update", "partial_update", "destroy"]:
            return [IsAuthenticated(), IsCreatorOrReadOnly()]
        return [permissions.AllowAny()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class StrainViewSet(viewsets.ModelViewSet):
    queryset = Strain.objects.all().order_by("name")

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return StrainWriteSerializer
        return StrainReadSerializer

    def get_permissions(self):
        if self.action == "create":
            return [IsAuthenticated()]
        if self.action in ["update", "partial_update", "destroy"]:
            return [IsAuthenticated(), IsCreatorOrReadOnly()]
        return [permissions.AllowAny()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class AnimalProfileViewSet(viewsets.ModelViewSet):
    queryset = AnimalProfile.objects.all().order_by("name")
    serializer_class = AnimalProfileSerializer

    # def get_serializer_class(self):
    #     if self.action in ["create", "update", "partial_update"]:
    #         return AnimalProfileWriteSerializer
    #     return AnimalProfileReadSerializer

    def get_permissions(self):
        if self.action == "create":
            return [IsAuthenticated()]
        if self.action in ["update", "partial_update", "destroy"]:
            return [IsAuthenticated(), IsCreatorOrReadOnly()]
        return [permissions.AllowAny()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class StudyViewSet(viewsets.ModelViewSet):
    queryset = Study.objects.all().order_by("name")
    serializer_class = StudySerializer

    def get_permissions(self):
        if self.action == "create":
            return [IsAuthenticated()]
        if self.action in ["update", "partial_update", "destroy"]:
            return [IsAuthenticated(), IsCreatorOrReadOnly()]
        return [permissions.AllowAny()]


class RecordingSessionViewSet(viewsets.ModelViewSet):
    queryset = RecordingSession.objects.all().order_by("name")
    serializer_class = RecordingSessionSerializer
    permission_classes = [IsAuthenticated, IsCreatorOrReadOnly]

    filter_backends = [
        filters.SearchFilter,
        DjangoFilterBackend,
        filters.OrderingFilter,
    ]
    search_fields = ["name", "description"]
    filterset_fields = ["is_multiple"]
    ordering_fields = ["name", "date", "status", "protocol__name", "laboratory__name"]
    ordering = ["name"]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def get_queryset(self):
        return RecordingSession.objects.filter(created_by=self.request.user)


class FileAPIView(GenericAPIView):
    serializer_class = FileSerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated()]
        return [AllowAny()]

    @extend_schema(
        operation_id="api_file_list",
        parameters=[
            OpenApiParameter(
                name="search", description="text search", required=False, type=str
            ),
            OpenApiParameter(
                name="filter", description="filter", required=False, type=str
            ),
        ],
    )
    def get(self, request, *args, **kwargs):
        search_query = request.GET.get("search", "")
        filter_query = request.GET.get("filter", "")
        recording_session_id = request.GET.get("recording_session")
        files = File.objects.all()
        if recording_session_id:
            try:
                recording_session_id_int = int(recording_session_id)
                files = files.filter(recording_session__id=recording_session_id_int)
            except ValueError:
                pass

        if search_query:
            file_fields = ["number", "link", "notes", "doi"]

            # Fields for RecordingSession model
            recording_session_fields = [
                "name",
                "equipment_acquisition_software__software__name",
                "equipment_acquisition_hardware_soundcards__name",
                "equipment_acquisition_hardware_speakers__name",
                "equipment_acquisition_hardware_amplifiers__name",
                "equipment_acquisition_hardware_microphones__name",
                "description",
                "date",
                "duration",
            ]

            # Fields for Subject model
            subject_fields = [
                "name",
                "identifier",
                "origin",
                "cohort",
            ]

            # Fields for User model (related to Subject)
            user_fields = [
                "name_user",
                "first_name_user",
                "email_user",
                "unit_user",
                "institution_user",
                "address_user",
                "country_user",
            ]

            # Fields for Strain model (related to Subject)
            strain_fields = [
                "animal_profile__strain__name",
                "animal_profile__strain__background",
                "animal_profile__strain__bibliography",
                "animal_profile__strain__species__name",
            ]

            # Fields for Protocol model (related to RecordingSession)
            protocol_fields = [
                "name",
                "description",
                "user__name_user",
                "animals_sex",
                "animals_age",
                "animals_housing",
                "animals_species",
                "context_number_of_animals",
                "context_duration",
                "context_cage",
                "context_bedding",
                "context_light_cycle",
                "context_temperature_value",
                "context_temperature_unit",
                "context_brightness",
            ]

            animal_profile_fields = [
                "name",
                "description",
                "sex",
                "genotype",
                "treatment",
            ]

            laboratory_fields = [
                "name",
                "institution",
                "unit",
                "address",
                "country",
                "contact",
            ]

            study_fields = ["name", "description"]

            # Build dynamic Q objects for File fields
            file_query = Q()
            for field in file_fields:
                lookup = f"{field}__icontains"
                file_query |= Q(**{lookup: search_query})

            # Build dynamic Q objects for RecordingSession fields
            recording_session_query = Q()
            for field in recording_session_fields:
                lookup = f"recording_session__{field}__icontains"
                recording_session_query |= Q(**{lookup: search_query})

            # Build dynamic Q objects for Subject fields
            subject_query = Q()
            for field in subject_fields:
                lookup = f"subjects__{field}__icontains"
                subject_query |= Q(**{lookup: search_query})

            # Build dynamic Q objects for User fields (via Subject)
            user_query = Q()
            for field in user_fields:
                lookup = f"subjects__user__{field}__icontains"
                user_query |= Q(**{lookup: search_query})

            # Build dynamic Q objects for Strain fields (via Subject)
            strain_query = Q()
            for field in strain_fields:
                lookup = f"subjects__{field}__icontains"
                strain_query |= Q(**{lookup: search_query})

            # Build dynamic Q objects for Protocol fields (via RecordingSession)
            protocol_query = Q()
            for field in protocol_fields:
                lookup = f"recording_session__protocol__{field}__icontains"
                protocol_query |= Q(**{lookup: search_query})

            # Build dynamic Q objects for AnimalProfile fields (via Subject)
            animal_profile_query = Q()
            for field in animal_profile_fields:
                lookup = f"subjects__animal_profile__{field}__icontains"
                animal_profile_query |= Q(**{lookup: search_query})

            # Build dynamic Q objects for Laboratory fields (via RecordingSession)
            laboratory_query = Q()
            for field in laboratory_fields:
                lookup = f"recording_session__laboratory__{field}__icontains"
                laboratory_query |= Q(**{lookup: search_query})

            # Build dynamic Q objects for Study fields (via RecordingSession)
            study_query = Q()
            for field in study_fields:
                lookup = f"recording_session__studies__{field}__icontains"
                study_query |= Q(**{lookup: search_query})

            # Combine all queries
            files = files.filter(
                file_query
                | recording_session_query
                | subject_query
                | user_query
                | strain_query
                | protocol_query
                | animal_profile_query
                | laboratory_query
                | study_query
            )

        ALLOWED_FILTERS = ["is_valid_link"]

        # Apply filters
        if filter_query:
            for filter_name in filter_query.split(","):
                if filter_name not in ALLOWED_FILTERS:
                    continue  # Ignore invalid filters

                if filter_name == "is_valid_link":
                    files = files.filter(is_valid_link=True)

        # Add explicit ordering to avoid UnorderedObjectListWarning
        files = files.order_by(F("name").asc(nulls_last=True))
        paginator = FilePagination()
        paginated_files = paginator.paginate_queryset(files, request)
        serializer = self.serializer_class(paginated_files, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            file = serializer.save()
            return Response(
                self.serializer_class(file).data, status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class FileDetailAPIView(GenericAPIView):
    serializer_class = FileSerializer

    def get_permissions(self):
        if self.request.method in ["PUT", "PATCH", "DELETE"]:
            return [IsAuthenticated()]
        return [AllowAny()]

    def get_object(self, pk):
        try:
            return File.objects.get(pk=pk)
        except File.DoesNotExist:
            return None

    def get(self, request, *args, **kwargs):
        file = self.get_object(kwargs["pk"])
        if not file:
            return Response(
                {"detail": "File not found"}, status=status.HTTP_404_NOT_FOUND
            )
        serializer = self.serializer_class(file)
        return Response(serializer.data)

    def put(self, request, *args, **kwargs):
        file = self.get_object(kwargs["pk"])
        if not file:
            return Response(
                {"detail": "File not found"}, status=status.HTTP_404_NOT_FOUND
            )
        serializer = self.serializer_class(file, data=request.data)
        if serializer.is_valid():
            file = serializer.save()
            return Response(self.serializer_class(file).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(exclude=True)
    def patch(self, request, *args, **kwargs):
        try:
            file = File.objects.get(pk=kwargs["pk"])
        except File.DoesNotExist:
            return Response(
                {"detail": "File not found"}, status=status.HTTP_404_NOT_FOUND
            )

        if "downloads" in request.data and request.data["downloads"] == "increment":
            updated = File.objects.filter(pk=kwargs["pk"]).update(
                downloads=F("downloads") + 1
            )
            if updated == 0:
                return Response(
                    {"detail": "File not found or update failed"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            file.refresh_from_db()
            return Response({"downloads": file.downloads}, status=status.HTTP_200_OK)

        return Response(
            {"detail": "Invalid request body"}, status=status.HTTP_400_BAD_REQUEST
        )

    def delete(self, request, *args, **kwargs):
        file = self.get_object(kwargs["pk"])
        if not file:
            return Response(
                {"detail": "File not found"}, status=status.HTTP_404_NOT_FOUND
            )
        file.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    parameters=[OpenApiParameter("id", type=int, location=OpenApiParameter.PATH)]
)
class SoftwareViewSet(viewsets.ModelViewSet):
    serializer_class = SoftwareSerializer
    lookup_field = "pk"

    def get_permissions(self):
        if self.action in ["create"]:
            return [permissions.IsAuthenticated()]
        if self.action in ["update", "partial_update", "destroy"]:
            return [permissions.IsAuthenticated(), IsCreatorOrReadOnly()]
        return [permissions.AllowAny()]

    def get_queryset(self):
        qs = Software.objects.all()
        search_query = self.request.GET.get("search", "")
        if search_query:
            software_fields = [
                "name",
                "type",
                "made_by",
                "description",
                "technical_requirements",
            ]
            reference_fields = ["name", "description", "url", "doi"]
            user_fields = [
                "name_user",
                "first_name_user",
                "email_user",
                "unit_user",
                "institution_user",
                "address_user",
                "country_user",
            ]

            q = Q()
            for f in software_fields:
                q |= Q(**{f"{f}__icontains": search_query})
            for f in reference_fields:
                q |= Q(**{f"references__{f}__icontains": search_query})
            for f in user_fields:
                q |= Q(**{f"users__{f}__icontains": search_query})

            qs = qs.filter(q).distinct()

        filter_query = self.request.GET.get("filter")
        ALLOWED_FILTERS = ["acquisition", "analysis", "acquisition and analysis"]
        if filter_query in ALLOWED_FILTERS:
            qs = qs.filter(type=filter_query)

        if self.action == "retrieve":
            qs = SoftwareSerializer.annotate_queryset(
                qs, user=self.request.user, detail=True
            )

        return qs.order_by("name")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["detail"] = self.action == "retrieve"
        context["user"] = self.request.user
        return context

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="search", description="Text search", required=False, type=str
            ),
            OpenApiParameter(
                name="filter", description="Type filter", required=False, type=str
            ),
        ]
    )
    def _check_editable(self, software):
        other_sessions_count = (
            software.versions.annotate(
                cnt=Count(
                    "recording_sessions_as_software",
                    filter=~Q(
                        recording_sessions_as_software__created_by=self.request.user
                    ),
                )
            ).aggregate(total=Sum("cnt"))["total"]
            or 0
        )

        if other_sessions_count > 0:
            raise PermissionDenied(
                "This software is linked to recording sessions from other users and cannot be edited or deleted."
            )

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        paginator = FilePagination()
        paginated = paginator.paginate_queryset(queryset, request)
        serializer = self.get_serializer(paginated, many=True)
        return paginator.get_paginated_response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        software = serializer.save(created_by=request.user)
        return Response(
            self.get_serializer(software).data, status=status.HTTP_201_CREATED
        )

    def retrieve(self, request, *args, **kwargs):
        software = self.get_object()
        serializer = self.get_serializer(software)
        return Response(serializer.data)

    def update(self, request, *args, **kwargs):
        software = self.get_object()
        self._check_editable(software)
        serializer = self.get_serializer(software, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        software = self.get_object()
        self._check_editable(software)
        serializer = self.get_serializer(software, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        software = self.get_object()
        self._check_editable(software)
        software.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    parameters=[OpenApiParameter("id", type=int, location=OpenApiParameter.PATH)]
)
class SoftwareVersionViewSet(viewsets.ModelViewSet):
    serializer_class = SoftwareVersionSerializer
    pagination_class = FilePagination
    filterset_fields = ["software"]

    def get_permissions(self):
        if self.action in ["create"]:
            return [permissions.IsAuthenticated()]
        if self.action in ["update", "partial_update", "destroy"]:
            return [permissions.IsAuthenticated(), IsCreatorOrReadOnly()]
        return [permissions.AllowAny()]

    def get_queryset(self):
        queryset = SoftwareVersion.objects.all().order_by("software__name", "version")

        search_query = self.request.query_params.get("search")
        if search_query:
            queryset = queryset.filter(
                Q(software__name__icontains=search_query)
                | Q(version__icontains=search_query)
            )

        if self.action == "retrieve":
            queryset = queryset.annotate(
                linked_sessions_count=Count("recording_sessions_as_software"),
                linked_sessions_from_other_users=Count(
                    "recording_sessions_as_software",
                    filter=~Q(
                        recording_sessions_as_software__created_by=self.request.user
                    ),
                ),
            )

        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def _check_editable(self, version: SoftwareVersion):
        other_sessions_count = version.recording_sessions_as_software.exclude(
            created_by=self.request.user
        ).count()
        if other_sessions_count > 0:
            raise PermissionDenied(
                "This software version is linked to recording sessions from other users "
                "and cannot be edited or deleted."
            )

    def update(self, request, *args, **kwargs):
        version = self.get_object()
        self._check_editable(version)
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        version = self.get_object()
        self._check_editable(version)
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        version = self.get_object()
        self._check_editable(version)
        return super().destroy(request, *args, **kwargs)


class FavoriteViewSet(viewsets.ModelViewSet):
    """
    Manage user favorites (protocol, software, hardware).
    - Only authenticated users can access.
    - Users can only see, add, or remove their own favorites.
    """

    serializer_class = FavoriteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Favorite.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        favorite = self.get_object()
        obj = favorite.content_object
        if (
            favorite.user != request.user
            and getattr(obj, "status", None) != "validated"
        ):
            return Response(
                {
                    "detail": "You can only remove favorites for validated objects of other users."
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)


class TrackPageView(GenericAPIView):
    serializer_class = TrackPageSerializer

    @extend_schema(exclude=True)
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        path = serializer.validated_data["path"]

        today = now().date()

        obj, created = PageView.objects.get_or_create(
            path=path, date=today, defaults={"count": 1}
        )

        if not created:
            PageView.objects.filter(pk=obj.pk).update(count=F("count") + 1)

        cache_key = f"pageview-log-generated-{today}"

        if not cache.get(cache_key):
            call_command("export_page_view", verbosity=0)
            cache.set(cache_key, True, 60 * 60 * 24)

        return Response(PageViewSerializer(obj).data, status=status.HTTP_200_OK)


def stats_view(request):
    year = now().year
    filename = f"stats_{year}.html"
    output_path = os.path.join(settings.LOGS_DIR, filename)

    if not os.path.exists(output_path):
        return render(request, "error.html", {"message": "Stat file not found!"})

    with open(output_path, "r") as f:
        content = f.read()

    return render(request, "stats_view.html", {"content": content})


@extend_schema(exclude=True)
class SchemaDetailView(APIView):
    """
    Return the content of a JSON schema file from static/json/schemas/,
    with local $ref resolved (non-recursively).
    """

    def get(self, request, filename):
        schema_dir = os.path.join(settings.BASE_DIR, "static", "json", "schemas")
        file_path = os.path.join(schema_dir, filename)

        if not os.path.isfile(file_path):
            raise Http404("Schema file not found")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                schema = json.load(f)

            # Inline local $ref files (basic version, non-recursive)
            schema = self.resolve_refs(schema, schema_dir)

            return Response(schema)

        except json.JSONDecodeError:
            return Response(
                {"error": "Invalid JSON format."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def resolve_refs(self, schema, schema_dir):
        """
        Resolve local $ref keys pointing to other .json files (non-recursive).
        """
        if isinstance(schema, dict):
            for key, value in list(schema.items()):
                if key == "$ref" and isinstance(value, str) and value.endswith(".json"):
                    ref_path = os.path.join(schema_dir, value)
                    if os.path.isfile(ref_path):
                        with open(ref_path, "r", encoding="utf-8") as ref_file:
                            ref_content = json.load(ref_file)
                        return self.resolve_refs(ref_content, schema_dir)
                else:
                    schema[key] = self.resolve_refs(value, schema_dir)

        elif isinstance(schema, list):
            return [self.resolve_refs(item, schema_dir) for item in schema]

        return schema
