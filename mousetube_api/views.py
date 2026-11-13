"""
Created by Nicolas Torquet at 27/10/2023
torquetn@igbmc.fr
Copyright: CNRS - INSERM - UNISTRA - ICS - IGBMC
CNRS - Mouse Clinical Institute
PHENOMIN, CNRS UMR7104, INSERM U964, Université de Strasbourg
Code under GPL v3.0 licence
"""

import hashlib
import json
import os
import uuid

import django_filters
from celery.result import AsyncResult
from django.apps import apps
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core import signing
from django.core.cache import cache
from django.db.models import (
    BooleanField,
    Case,
    Count,
    Exists,
    F,
    IntegerField,
    Max,
    OuterRef,
    Q,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Cast
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.utils.text import get_valid_filename
from django.utils.timezone import now
from django_countries import countries
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import (
    OpenApiParameter,
    extend_schema,
)
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import GenericAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import (
    AllowAny,
    IsAdminUser,
    IsAuthenticated,
)
from rest_framework.response import Response
from rest_framework.throttling import BaseThrottle, ScopedRateThrottle
from rest_framework.views import APIView

from mousetube_api.tasks import (
    delete_file_from_repository,
    export_page_views,
    process_file,
    publish_session_deposition,
)
from mousetube_api.utils import ontologies
from mousetube_api.utils.dataset_metadata import build_dataset_metadata
from mousetube_api.utils.email_domains import PERSONAL_EMAIL_DOMAINS
from mousetube_api.utils.file_handler import (
    UploadError,
    get_progress,
    purge_temp_files,
    remove_temp,
)
from mousetube_api.utils.moderation import (
    SESSION_LOCKED,
    SESSION_PUBLIC,
    session_pending_entries,
)
from mousetube_api.utils.orcid_proof import read_orcid_proof
from mousetube_api.utils.repository import (
    build_repository_metadata_payload,
    get_repository_metadata_schema,
)

from .celery import app
from .models import (
    AnimalProfile,
    Contact,
    Dataset,
    Favorite,
    File,
    Hardware,
    Laboratory,
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
from .serializers import (
    AnimalProfileSerializer,
    ContactSerializer,
    DatasetSerializer,
    FavoriteSerializer,
    FileSerializer,
    HardwareSerializer,
    LaboratorySerializer,
    PageViewSerializer,
    ProtocolSerializer,
    RecordingSessionSerializer,
    ReferenceSerializer,
    RepositorySerializer,
    SoftwareSerializer,
    SoftwareVersionSerializer,
    SpeciesSerializer,
    StrainSerializer,
    StudySerializer,
    SubjectSerializer,
    TrackPageSerializer,
    UserProfileSerializer,
)


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
        try:
            # Only an iD proven by the ORCID login is accepted, never a free-text one.
            orcid = read_orcid_proof(request.data.get("orcid_proof", ""))
        except signing.BadSignature:
            orcid = ""
        first_name = request.data.get("firstName", "").strip()
        last_name = request.data.get("lastName", "").strip()
        user = request.user

        if not orcid:
            return Response(
                {"error": "Missing or expired ORCID proof"},
                status=status.HTTP_400_BAD_REQUEST,
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
def visible_to(queryset, user):
    """Published objects and the user's own (administrators see everything)."""
    if user.is_staff:
        return queryset
    condition = Q(status="validated")
    if user.is_authenticated:
        condition |= Q(created_by=user)
    return queryset.filter(condition)


def can_change(user, obj):
    """The creator of an object, or an administrator."""
    return user.is_staff or obj.created_by_id == user.id


class IsCreatorOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow the creator of an object to edit or delete it.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if request.user.is_staff:
            return True  # administrators moderate: they may change or remove anything
        if obj.created_by != request.user:
            return False
        status = getattr(obj, "status", None)
        if status == "validated":
            return False  # validated by an administrator: it can no longer be changed
        # a session under review or shared is not deleted by its owner
        return not (request.method == "DELETE" and status in SESSION_LOCKED)


# ----------------------------
# Ontology terms (autocomplete of the fields that have a vocabulary)
# ----------------------------
class OntologySearchView(APIView):
    """GET /api/ontology/search/?field=sex&q=male -> terms of that field's vocabulary.

    Signed-in users only and rate limited: the server asks the vocabulary service for them.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ontology"

    def get(self, request):
        field = request.query_params.get("field", "")
        if field not in ontologies.FIELDS:
            return Response(
                {"field": f"One of: {', '.join(sorted(ontologies.FIELDS))}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            terms = ontologies.search(
                field,
                request.query_params.get("q", ""),
                ontology=request.query_params.get("ontology"),
            )
        except ontologies.OntologyError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(
            {
                "vocabulary": ontologies.FIELDS[field]["name"],
                "results": terms,
            }
        )


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
    serializer_class = LaboratorySerializer

    def get_queryset(self):
        request = self.request
        user = request.user
        search_query = request.GET.get("search", "")
        status_query = request.GET.get("status", "")

        queryset = Laboratory.objects.all().order_by("name")

        if not user.is_authenticated:
            queryset = queryset.filter(status="validated")
        else:
            if status_query:
                queryset = queryset.filter(status=status_query)
            else:
                queryset = queryset.filter(Q(created_by=user) | Q(status="validated"))

        if search_query:
            search_fields = ["name", "unit", "institution", "address", "status"]
            search_q = Q()
            for field in search_fields:
                search_q |= Q(**{f"{field}__icontains": search_query})
            queryset = queryset.filter(search_q)

        if user.is_authenticated:
            favorite_ids = Favorite.objects.filter(
                user=user,
                content_type=ContentType.objects.get_for_model(Laboratory),
            ).values_list("object_id", flat=True)

            queryset = queryset.annotate(
                is_favorite=Case(
                    When(id__in=favorite_ids, then=Value(True)),
                    default=Value(False),
                    output_field=BooleanField(),
                )
            ).order_by(
                F("is_favorite").desc(),
                F("status").desc(),
                F("name").asc(nulls_last=True),
            )
        else:
            queryset = queryset.order_by("name")

        return queryset

    def get_permissions(self):
        if self.action == "create":
            return [permissions.IsAuthenticated()]
        if self.action in ["update", "partial_update", "destroy"]:
            return [permissions.IsAuthenticated(), IsCreatorOrReadOnly()]
        # list / retrieve
        return [permissions.AllowAny()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


# ----------------------------
# Personal e-mail domains (for the registration form)
# ----------------------------
@extend_schema(exclude=True)
@api_view(["GET"])
@permission_classes([AllowAny])
def personal_email_domains(request):
    """Same list the API enforces, so the website can warn before submitting."""
    return Response(
        {
            "enforced": settings.REQUIRE_INSTITUTIONAL_EMAIL,
            "domains": sorted(PERSONAL_EMAIL_DOMAINS),
        }
    )


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


@api_view(["GET"])
def repository_metadata_schema(request, repo_id):
    """
    Return the metadata schema for a given repository.
    """
    repository = get_object_or_404(Repository, id=repo_id)
    try:
        schema = get_repository_metadata_schema(repository)
    except NotImplementedError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    return Response(schema)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def repository_metadata_payload(request, repository_id: int, recording_session_id: int):
    """
    Return the metadata payload for a given repository and recording session.
    """
    try:
        repository = Repository.objects.get(pk=repository_id)
    except Repository.DoesNotExist:
        return Response(
            {"error": "Repository not found."}, status=status.HTTP_404_NOT_FOUND
        )

    try:
        recording_session = RecordingSession.objects.get(pk=recording_session_id)
    except RecordingSession.DoesNotExist:
        return Response(
            {"error": "Recording session not found."}, status=status.HTTP_404_NOT_FOUND
        )

    if recording_session.created_by != request.user and not request.user.is_staff:
        return Response({"detail": "Not authorized."}, status=status.HTTP_403_FORBIDDEN)

    files = File.objects.filter(recording_session=recording_session).exclude(
        status__in=["pending", "processing", "error"]
    )

    if not files.exists():
        return Response(
            {"error": "No valid files for this session."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        payload = build_repository_metadata_payload(
            repository, recording_session, files
        )
    except NotImplementedError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    return Response(payload, status=status.HTTP_200_OK)


# ----------------------------
# Reference
# ----------------------------
@extend_schema(
    request=ReferenceSerializer,
    responses={200: ReferenceSerializer(many=True), 201: ReferenceSerializer},
)
class ReferenceAPIView(GenericAPIView):
    serializer_class = ReferenceSerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [permissions.IsAuthenticated()]
        elif self.request.method in ["PUT", "PATCH", "DELETE"]:
            return [permissions.IsAuthenticated(), IsCreatorOrReadOnly()]
        return [permissions.AllowAny()]

    def get_queryset(self):
        search_query = self.request.GET.get("search", "")
        status_query = self.request.GET.get("status", "")

        queryset = Reference.objects.all().order_by("name")

        if not self.request.user.is_authenticated:
            queryset = queryset.filter(status="validated")
        else:
            if status_query:
                queryset = queryset.filter(status=status_query)
            else:
                queryset = queryset.filter(
                    Q(created_by=self.request.user) | Q(status="validated")
                )

        if search_query:
            search_fields = ["name", "description", "doi", "status"]
            search_q = Q()
            for field in search_fields:
                search_q |= Q(**{f"{field}__icontains": search_query})
            queryset = queryset.filter(search_q)

        if self.request.user.is_authenticated:
            favorite_ids = Favorite.objects.filter(
                user=self.request.user,
                content_type=ContentType.objects.get_for_model(Reference),
            ).values_list("object_id", flat=True)

            queryset = queryset.annotate(
                is_favorite=Case(
                    When(id__in=favorite_ids, then=Value(True)),
                    default=Value(False),
                    output_field=BooleanField(),
                )
            ).order_by(
                F("is_favorite").desc(),
                F("status").desc(),
                F("name").asc(nulls_last=True),
            )
        else:
            queryset = queryset.order_by("name")

        return queryset

    def get(self, request, *args, **kwargs):
        paginator = FilePagination()
        queryset = self.get_queryset()
        paginated_queryset = paginator.paginate_queryset(queryset, request)
        serializer = self.serializer_class(paginated_queryset, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            serializer.save(created_by=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ----------------------------
# Reference (detail : get / put / delete)
# ----------------------------
@extend_schema(
    request=ReferenceSerializer,
    responses={200: ReferenceSerializer, 204: None},
)
class ReferenceDetailAPIView(GenericAPIView):
    serializer_class = ReferenceSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsCreatorOrReadOnly]

    def get_object(self, pk):
        reference = get_object_or_404(
            visible_to(Reference.objects.all(), self.request.user), pk=pk
        )
        # a hand-made lookup does not check the object permission by itself
        self.check_object_permissions(self.request, reference)
        return reference

    def get(self, request, pk, *args, **kwargs):
        instance = self.get_object(pk)
        serializer = self.serializer_class(instance, context={"request": request})
        return Response(serializer.data)

    def put(self, request, pk, *args, **kwargs):
        instance = self.get_object(pk)
        serializer = self.serializer_class(
            instance, data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk, *args, **kwargs):
        instance = self.get_object(pk)
        serializer = self.serializer_class(
            instance, data=request.data, partial=True, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk, *args, **kwargs):
        instance = self.get_object(pk)
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ----------------------------
# UserProfile
# ----------------------------
class UserProfileListAPIView(GenericAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    @extend_schema(operation_id="api_user_profile_list_get")
    def get(self, request, *args, **kwargs):
        # an account created before the profile existed has none: make it on first use
        UserProfile.objects.get_or_create(user=request.user)
        queryset = UserProfile.objects.all()
        if not request.user.is_staff:  # profiles expose e-mails: own profile only
            queryset = queryset.filter(user=request.user)
        user_id = request.query_params.get("user_id")
        if user_id:
            queryset = queryset.filter(user__id=user_id)
        serializer = self.get_serializer(queryset, many=True)
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


def filter_catalog(qs, request, used_in):
    """The filters the catalog lists (software, hardware) share, from the query string:
    `type` (comma separated), `used` (in a shared or published session), `documented`
    (has references) and, when signed in, `favorites` and `mine`."""
    get = request.GET
    types = [v.strip() for v in get.get("type", "").split(",") if v.strip()]
    if types:
        qs = qs.filter(type__in=types)
    if get.get("used") == "1":
        used = Q()
        for path in used_in:
            used |= Q(**{f"{path}__status__in": SESSION_PUBLIC})
        qs = qs.filter(used)
    if get.get("documented") == "1":
        qs = qs.filter(references__isnull=False)
    if request.user.is_authenticated:
        if get.get("favorites") == "1":
            qs = qs.filter(
                id__in=Favorite.objects.filter(
                    user=request.user,
                    content_type=ContentType.objects.get_for_model(qs.model),
                ).values_list("object_id", flat=True)
            )
        if get.get("mine") == "1":
            qs = qs.filter(created_by=request.user)
    return qs.distinct()


# ----------------------------
# Hardware
# ----------------------------
class HardwareAPIView(GenericAPIView):
    serializer_class = HardwareSerializer
    queryset = Hardware.objects.all().order_by("name")

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
            OpenApiParameter(
                name="status", description="filter by status", required=False, type=str
            ),
        ],
    )
    def get(self, request, *args, **kwargs):
        search_query = request.GET.get("search", "")
        filter_query = request.GET.get("filter", "")
        status_query = request.GET.get("status", "")
        hardware = Hardware.objects.all().order_by("name")

        if not request.user.is_authenticated:
            hardware = hardware.filter(status="validated")
        else:
            hardware = hardware.filter(
                Q(status="validated") | Q(created_by=request.user)
            )

            if status_query:
                hardware = hardware.filter(status=status_query)

        # Search
        if search_query:
            search_fields = [
                "name",
                "type",
                "made_by",
                "references__name",
                "description",
                "status",
            ]
            search_q = Q()
            for field in search_fields:
                search_q |= Q(**{f"{field}__icontains": search_query})
            hardware = hardware.filter(search_q)

        # Filter by type

        ALLOWED_FILTERS = ["microphone", "speaker", "soundcard", "amplifier"]

        if filter_query and filter_query in ALLOWED_FILTERS:
            hardware = hardware.filter(type=filter_query)
        hardware = filter_catalog(
            hardware,
            request,
            [
                "recording_sessions_as_soundcard",
                "recording_sessions_as_speaker",
                "recording_sessions_as_amplifier",
                "recording_sessions_as_microphone",
            ],
        )

        if request.user.is_authenticated:
            favorite_ids = Favorite.objects.filter(
                user=request.user,
                content_type=ContentType.objects.get_for_model(Hardware),
            ).values_list("object_id", flat=True)

            # Annoter les favoris et trier dessus
            hardware = hardware.annotate(
                is_favorite=Case(
                    When(id__in=favorite_ids, then=Value(True)),
                    default=Value(False),
                    output_field=BooleanField(),
                )
            ).order_by(F("is_favorite").desc(), F("name").asc(nulls_last=True))
        else:
            hardware = hardware.order_by(F("name").asc(nulls_last=True))

        hardware = hardware.order_by(F("name").asc(nulls_last=True))
        paginator = FilePagination()
        paginated_hardware = paginator.paginate_queryset(hardware, request)
        serializer = self.serializer_class(paginated_hardware, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            hardware = serializer.save(created_by=request.user)
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
            return [IsAuthenticated(), IsCreatorOrReadOnly()]
        return [AllowAny()]

    def get_hardware(self, request, pk):
        # drafts are private; the object permission is NOT automatic with a hand-made
        # lookup: without this call anybody could change or delete any hardware
        hardware = get_object_or_404(
            visible_to(Hardware.objects.all(), request.user), pk=pk
        )
        self.check_object_permissions(request, hardware)
        return hardware

    def get(self, request, pk, *args, **kwargs):
        hardware = self.get_hardware(request, pk)
        serializer = self.serializer_class(hardware, context={"request": request})
        return Response(serializer.data)

    def put(self, request, pk, *args, **kwargs):
        hardware = self.get_hardware(request, pk)
        serializer = self.serializer_class(
            hardware, data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk, *args, **kwargs):
        hardware = self.get_hardware(request, pk)
        serializer = self.serializer_class(
            hardware, data=request.data, partial=True, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk, *args, **kwargs):
        hardware = self.get_hardware(request, pk)
        hardware.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ----------------------------
# Subject
# ----------------------------
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


# ----------------------------
# Protocol
# ----------------------------
class ProtocolPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


def get_protocol_ct():
    Protocol = apps.get_model("mousetube_api", "Protocol")
    return ContentType.objects.get_for_model(Protocol)


class ProtocolViewSet(viewsets.ModelViewSet):
    queryset = Protocol.objects.all()
    serializer_class = ProtocolSerializer
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ["name"]
    filterset_fields = [
        "animals_sex",
        "animals_age",
        "animals_housing",
        "context_number_of_animals",
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

        qs = Protocol.objects.all()

        if user.is_authenticated:
            favorite_subquery = Favorite.objects.filter(
                user=user, content_type=get_protocol_ct(), object_id=OuterRef("pk")
            )
            qs = qs.annotate(
                is_favorite_int=Cast(Exists(favorite_subquery), IntegerField())
            )
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

    def perform_create(self, serializer):
        SEX_MAP = {"male(s)": "M", "female(s)": "F", "male(s) & female(s)": "M+F"}
        AGE_MAP = {"pup": "P", "juvenile": "J", "adult": "A", "unspecified": "U"}
        HOUSING_MAP = {"grouped": "G", "isolated": "I", "grouped & isolated": "G+I"}
        DURATION_MAP = {
            "short term (<1h)": "S",
            "mid term (<1day)": "M",
            "long term (>=1day)": "L",
        }
        CAGE_MAP = {
            "unfamiliar test cage": "UC",
            "familiar test cage": "FC",
            "home cage": "HC",
        }
        BEDDING_MAP = {
            "bedding": "B",
            "no bedding": "NB",
        }
        LIGHT_MAP = {
            "day": "D",
            "night": "N",
            "both": "B",
        }
        validated_data = serializer.validated_data
        name = (
            f"{validated_data['context_number_of_animals']}{SEX_MAP[validated_data['animals_sex']]}"
            f"{AGE_MAP[validated_data['animals_age']]}{HOUSING_MAP[validated_data['animals_housing']]}_"
            f"{DURATION_MAP[validated_data['context_duration']]}_"
            f"{CAGE_MAP[validated_data['context_cage']]}{BEDDING_MAP[validated_data['context_bedding']]}{LIGHT_MAP[validated_data['context_light_cycle']]}"
        )

        # Check if a protocol with the same name already exists
        protocol, _created = Protocol.objects.get_or_create(
            name=name,
            defaults={
                **validated_data,
                "status": "validated",
                "created_by": self.request.user,
            },
        )

        # If the protocol already existed, do not create but return the existing object
        serializer.instance = protocol


# ----------------------------
# Species
# ----------------------------
class SpeciesViewSet(viewsets.ModelViewSet):
    queryset = Species.objects.all().order_by("name")
    serializer_class = SpeciesSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["name"]

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAuthenticated(), IsAdminUser()]
        return [permissions.AllowAny()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


# ----------------------------
# Strain
# ----------------------------
class StrainViewSet(viewsets.ModelViewSet):
    queryset = Strain.objects.all()
    serializer_class = StrainSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["name"]

    def get_queryset(self):
        qs = visible_to(super().get_queryset(), self.request.user)
        user = self.request.user
        if user.is_authenticated:
            content_type = ContentType.objects.get_for_model(Strain)
            favorite_ids = Favorite.objects.filter(
                user=user, content_type=content_type
            ).values_list("object_id", flat=True)
            qs = qs.annotate(
                is_favorite=Case(
                    When(id__in=favorite_ids, then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            ).order_by("-is_favorite", "name")
        else:
            qs = qs.order_by("name")
        return qs

    def get_permissions(self):
        if self.action == "create":
            return [IsAuthenticated()]
        if self.action in ["update", "partial_update", "destroy"]:
            return [IsAuthenticated(), IsCreatorOrReadOnly()]
        return [permissions.AllowAny()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


# ----------------------------
# Animal Profile
# ----------------------------
class AnimalProfileFilter(django_filters.FilterSet):
    species = django_filters.CharFilter(
        field_name="strain__species__id", lookup_expr="iexact"
    )
    strain = django_filters.CharFilter(field_name="strain__id", lookup_expr="iexact")

    class Meta:
        model = AnimalProfile
        fields = ["sex", "age", "genotype", "status", "strain", "treatment", "species"]


class AnimalProfileViewSet(viewsets.ModelViewSet):
    queryset = AnimalProfile.objects.all()
    serializer_class = AnimalProfileSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_class = AnimalProfileFilter
    search_fields = ["name"]

    def get_queryset(self):
        qs = visible_to(super().get_queryset(), self.request.user)
        user = self.request.user
        if user.is_authenticated:
            content_type = ContentType.objects.get_for_model(AnimalProfile)
            favorite_ids = Favorite.objects.filter(
                user=user, content_type=content_type
            ).values_list("object_id", flat=True)

            qs = qs.annotate(
                is_favorite=Case(
                    When(id__in=favorite_ids, then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            ).order_by("-is_favorite", "name")
        else:
            qs = qs.order_by("name")
        return qs

    def get_permissions(self):
        if self.action == "create":
            return [IsAuthenticated()]
        if self.action in ["update", "partial_update", "destroy"]:
            return [IsAuthenticated(), IsCreatorOrReadOnly()]
        return [permissions.AllowAny()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


# ----------------------------
# Study
# ----------------------------
class StudyViewSet(viewsets.ModelViewSet):
    queryset = Study.objects.all().order_by("name")
    serializer_class = StudySerializer

    def get_queryset(self):
        user = self.request.user
        return visible_to(Study.objects.all(), user).order_by("name")

    def get_permissions(self):
        if self.action == "create":
            return [IsAuthenticated()]
        if self.action in ["update", "partial_update", "destroy"]:
            return [IsAuthenticated(), IsCreatorOrReadOnly()]
        return [permissions.AllowAny()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


# ----------------------------
# Recording Session
# ----------------------------
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
    filterset_fields = ["is_multiple", "laboratory", "status", "protocol"]
    ordering_fields = [
        "name",
        "date",
        "status",
        "protocol__name",
        "laboratory__name",
        "modified_at",
    ]
    ordering = ["name"]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def get_queryset(self):
        return (
            RecordingSession.objects.filter(created_by=self.request.user)
            .prefetch_related("publication_versions")
            .annotate(
                files_count=Count("file", distinct=True),
                first_doi=Max("file__doi"),
                files_to_deposit=Count(
                    "file",
                    filter=Q(file__doi__isnull=True) | Q(file__doi=""),
                    distinct=True,
                ),
            )
        )


# The facets of the list of files that describe the animals: filter name -> lookup on the
# animal profile (the animals of a file are those of its subjects or of its session)
ANIMAL_FACETS = {
    "species": "strain__species__name",
    "sex": "sex",
    "age": "age",
}


def visible_files(user):
    """The files `user` may see: those of a shared or published session, and their own."""
    files = File.objects.all()
    if user.is_staff:
        return files
    visible = Q(recording_session__status__in=SESSION_PUBLIC)
    if user.is_authenticated:
        visible |= Q(created_by=user) | Q(recording_session__created_by=user)
    return files.filter(visible)


# ----------------------------
# File
# ----------------------------
class FileAPIView(GenericAPIView):
    serializer_class = FileSerializer

    # -----------------------------
    # Permissions
    # -----------------------------
    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated()]
        return [AllowAny()]

    # -----------------------------
    # Dynamic queryset
    # -----------------------------
    def get_queryset(self):
        request = self.request
        # --- Visibility: files of a draft session are private to their owner ---
        files = visible_files(request.user)

        # --- Filter by RecordingSession ---
        recording_session_id = request.GET.get("recording_session")
        if recording_session_id:
            try:
                recording_session_id_int = int(recording_session_id)
                files = files.filter(recording_session_id=recording_session_id_int)
            except ValueError:
                pass

        # --- Global text search ---
        search_query = request.GET.get("search", "").strip()
        if search_query:
            file_fields = ["name", "number", "link", "notes", "doi"]

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

            subject_fields = ["name", "identifier", "origin", "cohort"]

            # the author is the owner of the recording session
            author_fields = ["first_name", "last_name"]

            strain_fields = [
                "animal_profile__strain__name",
                "animal_profile__strain__background",
                "animal_profile__strain__bibliography",
                "animal_profile__strain__species__name",
            ]

            protocol_fields = [
                "name",
                "animals_sex",
                "animals_age",
                "animals_housing",
                "context_cage",
                "context_duration",
                "context_light_cycle",
                "status",
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
            ]

            study_fields = ["name", "description"]

            def build_query(prefix, fields, term):
                q = Q()
                for f in fields:
                    lookup = f"{prefix}{f}__icontains" if prefix else f"{f}__icontains"
                    q |= Q(**{lookup: term})
                return q

            # every word must be found somewhere (name, session, author, protocol...)
            for term in search_query.split():
                files = files.filter(
                    build_query("", file_fields, term)
                    | build_query("recording_session__", recording_session_fields, term)
                    | build_query("subjects__", subject_fields, term)
                    | build_query(
                        "recording_session__created_by__", author_fields, term
                    )
                    | build_query("subjects__", strain_fields, term)
                    | build_query(
                        "recording_session__protocol__", protocol_fields, term
                    )
                    | build_query(
                        "subjects__animal_profile__", animal_profile_fields, term
                    )
                    | build_query(
                        "recording_session__laboratory__", laboratory_fields, term
                    )
                    | build_query("recording_session__studies__", study_fields, term)
                )
            files = files.distinct()

        # --- Filtres ---
        ALLOWED_FILTERS = ["is_valid_link"]
        filter_query = request.GET.get("filter", "")
        if filter_query:
            for filter_name in filter_query.split(","):
                if filter_name in ALLOWED_FILTERS and filter_name == "is_valid_link":
                    files = files.filter(is_valid_link=True)

        # --- Facets: a comma separated list per name, one of the values must match ---
        def values(name):
            return [
                v.strip() for v in request.GET.get(name, "").split(",") if v.strip()
            ]

        for name, lookup in ANIMAL_FACETS.items():
            chosen = values(name)
            if chosen:
                files = files.filter(
                    Q(**{f"subjects__animal_profile__{lookup}__in": chosen})
                    | Q(**{f"recording_session__animal_profiles__{lookup}__in": chosen})
                )
        # not "format": DRF reads ?format= as the wanted rendering (json, api...)
        if values("file_format"):
            files = files.filter(format__in=[v.upper() for v in values("file_format")])
        if values("repository"):
            files = files.filter(repository__name__in=values("repository"))
        files = files.distinct()

        # a page of files is serialized with its session, animals and equipment: load
        # them in a few queries instead of a few per row
        files = files.select_related(
            "repository",
            "recording_session__protocol",
            "recording_session__laboratory",
            "recording_session__created_by__user_profile",
            "created_by__user_profile",
        ).prefetch_related(
            "subjects__animal_profile__strain__species",
            "subjects__animal_profile__strain__ontology_term",
            "subjects__animal_profile__sex_term",
            "subjects__animal_profile__age_term",
            "subjects__animal_profile__treatment_term",
            "recording_session__behavior_terms",
            "recording_session__studies",
            "recording_session__references",
            "recording_session__animal_profiles__strain__species",
            "recording_session__animal_profiles__strain__ontology_term",
            "recording_session__animal_profiles__sex_term",
            "recording_session__animal_profiles__age_term",
            "recording_session__animal_profiles__treatment_term",
            "recording_session__equipment_acquisition_software__software__references",
            "recording_session__equipment_acquisition_hardware_soundcards__references",
            "recording_session__equipment_acquisition_hardware_speakers__references",
            "recording_session__equipment_acquisition_hardware_amplifiers__references",
            "recording_session__equipment_acquisition_hardware_microphones__references",
        )
        files = files.order_by(F("name").asc(nulls_last=True))
        return files

    # -----------------------------
    # GET with pagination
    # -----------------------------
    @extend_schema(
        operation_id="api_file_list",
        parameters=[
            OpenApiParameter(
                name="search",
                description="Recherche textuelle globale",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="filter",
                description="Filtre (ex: is_valid_link)",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="recording_session",
                description="Filtrer par ID de session d’enregistrement",
                required=False,
                type=int,
            ),
        ],
    )
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        paginator = FilePagination()
        paginated_files = paginator.paginate_queryset(queryset, request)
        serializer = self.serializer_class(paginated_files, many=True)
        return paginator.get_paginated_response(serializer.data)

    # -----------------------------
    # POST Celery
    # -----------------------------
    def post(self, request, *args, **kwargs):
        if not request.user.is_staff and (
            "plot" in request.data or "spectrogram" in request.data
        ):
            return Response(
                {"detail": "Only administrators can set plot or spectrogram."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = self.serializer_class(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        session = serializer.validated_data.get("recording_session")
        if session is not None and not can_change(request.user, session):
            return Response(
                {"detail": "This recording session belongs to someone else."},
                status=status.HTTP_403_FORBIDDEN,
            )

        file = serializer.save(created_by=request.user)

        if not file.repository:
            # Zenodo is the default repository; any repository is better than none
            default_repo = (
                Repository.objects.filter(name__iexact="zenodo").first()
                or Repository.objects.order_by("pk").first()
            )
            if default_repo is None:
                file.delete()
                return Response(
                    {"error": "No repository is configured."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            file.repository = default_repo
            file.save(update_fields=["repository"])

        # Start background task to process the file if no DOI
        if not file.doi:
            file.status = "pending"
            file.save(update_fields=["status"])
            try:
                task = process_file.delay(file.id, file.repository.id)
                file.celery_task_id = task.id
                file.save(update_fields=["celery_task_id"])
            except Exception as e:  # noqa: BLE001 - any broker error must flag the file
                file.status = "error"
                file.save(update_fields=["status"])
                return Response(
                    {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        elif file.doi and file.link:
            file.status = "done"
            file.save(update_fields=["status"])

        return Response(
            self.serializer_class(file).data, status=status.HTTP_201_CREATED
        )


# ----------------------------
# File status endpoint
# ----------------------------
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def file_task_status(request, file_id):
    file = get_object_or_404(File, id=file_id)

    if not file.celery_task_id:
        return Response({"error": "No task associated"}, status=404)

    result = AsyncResult(file.celery_task_id, app=app)

    response = {
        "id": file.id,
        "task_state": result.state,  # PENDING, STARTED, SUCCESS, FAILURE
        "status": file.status,
        "progress": get_progress(file.id) if file.status == "processing" else 0,
        "error_message": file.error_message,
    }

    # error text can contain the Zenodo URL with its access_token: staff only,
    # unless it was written for the user (UploadError)
    if result.failed() and isinstance(result.result, UploadError):
        response["task_error"] = str(result.result)
    elif result.failed() and request.user.is_staff:
        response["task_error"] = str(result.result)
        response["task_traceback"] = result.traceback

    return Response(response)


# ----------------------------
# File Upload endpoint
# ----------------------------
class FileUploadAsyncView(APIView):
    """
    Handles asynchronous file uploads.

    Requires authentication.
    """

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated()]
        return [AllowAny()]

    def post(self, request):
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return Response({"error": "No file provided"}, status=400)

        # refuse now what the processing would refuse later, so nothing useless is stored
        if uploaded_file.size > settings.MAX_UPLOAD_SIZE:
            return Response(
                {
                    "error": f"File too large: the limit is "
                    f"{settings.MAX_UPLOAD_SIZE // 1024**2} MB."
                },
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )
        extension = os.path.splitext(uploaded_file.name)[1].lstrip(".").upper()
        if extension not in {choice[0].upper() for choice in File.FORMAT_CHOICES}:
            return Response(
                {"error": f"Unsupported file type: .{extension.lower()}"}, status=400
            )

        temp_dir = os.path.join(settings.MEDIA_ROOT, "temp")
        os.makedirs(temp_dir, exist_ok=True)
        purge_temp_files()  # uploads nobody took over within a day

        # unique prefix: two users uploading "a.wav" must not overwrite each other
        safe_name = f"{uuid.uuid4().hex}_{get_valid_filename(uploaded_file.name)}"
        temp_path = os.path.join(temp_dir, safe_name)
        try:
            with open(temp_path, "wb+") as dest:
                dest.writelines(uploaded_file.chunks())
        except OSError:
            remove_temp(temp_path)  # no half-written file left behind (disk full...)
            return Response(
                {"error": "The file could not be stored."},
                status=status.HTTP_507_INSUFFICIENT_STORAGE,
            )

        return Response({"temp_path": f"/media/temp/{safe_name}"})


# ----------------------------
# File Publish session endpoint
# ----------------------------
class PublishSessionView(APIView):
    """
    Triggers a background task to publish a recording session to a repository.

    Requires authentication.
    """

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated()]
        return [AllowAny()]

    def post(self, request):
        recording_session_id = request.data.get("recording_session_id")
        if not recording_session_id:
            return Response({"error": "recording_session_id required"}, status=400)

        repository_id = request.data.get("repository_id")
        if not repository_id:
            return Response({"error": "repository_id required"}, status=400)

        payload = request.data.get("payload")

        session = get_object_or_404(RecordingSession, pk=recording_session_id)
        if session.created_by != request.user and not request.user.is_staff:
            return Response(
                {"detail": "Not authorized."}, status=status.HTTP_403_FORBIDDEN
            )
        if session.status == "published":
            # a published session has a new version to publish when files were added since
            waiting = File.objects.filter(
                recording_session=session, external_id__isnull=False, status="done"
            ).filter(Q(doi__isnull=True) | Q(doi=""))
            if not waiting.exists():
                return Response(
                    {
                        "detail": "Nothing new to publish: add a file to make a new "
                        "version of the record."
                    },
                    status=status.HTTP_409_CONFLICT,
                )
            if session_pending_entries(session):
                return Response(
                    {
                        "detail": "The session now uses entries that wait for an "
                        "administrator: the new version can be published once they "
                        "are validated."
                    },
                    status=status.HTTP_409_CONFLICT,
                )
        elif session.status != "shared" and not request.user.is_staff:
            return Response(
                {
                    "detail": "Share the session first: an administrator has to validate "
                    "its new entries before it can be deposited in a repository."
                },
                status=status.HTTP_409_CONFLICT,
            )

        task = publish_session_deposition.delay(
            recording_session_id, repository_id, payload
        )

        return Response(
            {
                "message": "Publishing started. You’ll be notified when complete.",
                "task_id": task.id,
            },
            status=202,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_task_status(request):
    task_id = request.query_params.get("task_id")
    if not task_id:
        return Response({"error": "Missing task_id"}, status=400)

    result = AsyncResult(task_id)

    response_data = {
        "task_id": task_id,
        "state": result.state,  # PENDING, STARTED, SUCCESS, FAILURE
        "success": result.successful(),
        "error": str(result.result)
        if result.failed()
        and (request.user.is_staff or isinstance(result.result, UploadError))
        else None,
        "progress": 0,
    }

    if result.info and isinstance(result.info, dict):
        response_data["progress"] = result.info.get("progress", 0)

    return Response(response_data)


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
        if not can_change(request.user, file):
            return Response(
                {"detail": "Only the creator of a file can change it."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not request.user.is_staff and (
            "plot" in request.data or "spectrogram" in request.data
        ):
            return Response(
                {"detail": "Only administrators can set plot or spectrogram."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = self.serializer_class(file, data=request.data)
        if serializer.is_valid():
            file = serializer.save()
            return Response(self.serializer_class(file).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, *args, **kwargs):
        file = self.get_object(kwargs["pk"])
        if not file:
            return Response(
                {"detail": "File not found"}, status=status.HTTP_404_NOT_FOUND
            )

        if not can_change(request.user, file):
            return Response(
                {"detail": "Only the creator of a file can delete it."},
                status=status.HTTP_403_FORBIDDEN,
            )
        session = file.recording_session
        if (
            file.doi
            and file.external_id
            and session is not None
            and session.publication_versions.exists()
            and not request.user.is_staff
        ):
            return Response(
                {
                    "detail": "This file is part of a published version of the record: "
                    "it cannot be removed."
                },
                status=status.HTTP_409_CONFLICT,
            )

        # 🔹 Start async deletion
        if not file.repository:
            file.delete()
            return Response(
                {"detail": "File deleted locally (no repository linked)."},
                status=status.HTTP_204_NO_CONTENT,
            )

        if not file.external_id:
            file.delete()
            return Response(
                {"detail": "File deleted locally (no external ID)."},
                status=status.HTTP_204_NO_CONTENT,
            )

        task = delete_file_from_repository.delay(file.id, file.repository.id)
        file.celery_task_id = task.id
        file.save(update_fields=["celery_task_id", "status"])

        return Response(
            {"detail": "File deletion scheduled.", "celery_task_id": task.id},
            status=status.HTTP_202_ACCEPTED,
        )


class FileDownloadView(APIView):
    """Counts a download. Open to everybody (visitors download too), once per visitor
    and file per hour so that reloading or clicking twice does not inflate the number."""

    permission_classes = [AllowAny]
    authentication_classes = []  # a stale token must not turn a visitor into a 401

    @extend_schema(exclude=True)
    def post(self, request, pk):
        file = get_object_or_404(visible_files(request.user), pk=pk)
        visitor = hashlib.sha256(BaseThrottle().get_ident(request).encode()).hexdigest()
        counted = cache.add(f"download:{file.pk}:{visitor}", 1, 3600)
        if counted:
            File.objects.filter(pk=file.pk).update(downloads=F("downloads") + 1)
            file.refresh_from_db(fields=["downloads"])
        return Response({"downloads": file.downloads, "counted": counted})


class FileFilterOptionsView(APIView):
    """What the filters of the list of files can offer: the values that exist among the
    files the user may see."""

    permission_classes = [AllowAny]

    @extend_schema(exclude=True)
    def get(self, request):
        files = visible_files(request.user)

        def distinct(*paths):
            found = set()
            for path in paths:
                found |= set(files.values_list(path, flat=True))
            return sorted(v for v in found if v)

        return Response(
            {
                name: distinct(
                    f"subjects__animal_profile__{lookup}",
                    f"recording_session__animal_profiles__{lookup}",
                )
                for name, lookup in ANIMAL_FACETS.items()
            }
            | {
                "format": distinct("format"),
                "repository": distinct("repository__name"),
            }
        )


# ----------------------------
# Contact
# ----------------------------
class ContactViewSet(viewsets.ModelViewSet):
    queryset = Contact.objects.all().order_by("last_name")
    serializer_class = ContactSerializer

    def get_permissions(self):
        if self.action == "create":
            return [IsAuthenticated()]
        if self.action in ["update", "partial_update", "destroy"]:
            return [IsAuthenticated(), IsCreatorOrReadOnly()]
        return [permissions.AllowAny()]

    def get_queryset(self):
        user = self.request.user
        search_query = self.request.GET.get("search", "").strip()
        status_query = self.request.GET.get("status", "")

        qs = Contact.objects.all().order_by("last_name")

        if not user.is_authenticated:
            qs = qs.filter(status="validated")
        else:
            if status_query:
                qs = qs.filter(status=status_query)
            else:
                qs = qs.filter(Q(created_by=user) | Q(status="validated"))

        if search_query:
            search_fields = ["last_name", "first_name", "institution", "status"]
            if user.is_authenticated:  # e-mail is hidden from anonymous users
                search_fields.append("email")
            q = Q()
            for f in search_fields:
                q |= Q(**{f"{f}__icontains": search_query})
            qs = qs.filter(q).distinct()

        if user.is_authenticated:
            favorite_ids = Favorite.objects.filter(
                user=user,
                content_type=ContentType.objects.get_for_model(Contact),
            ).values_list("object_id", flat=True)

            qs = qs.annotate(
                is_favorite=Case(
                    When(id__in=favorite_ids, then=Value(True)),
                    default=Value(False),
                    output_field=BooleanField(),
                )
            ).order_by(
                F("is_favorite").desc(),
                F("status").desc(),
                F("last_name").asc(nulls_last=True),
            )
        else:
            qs = qs.order_by(F("last_name").asc(nulls_last=True))

        return qs

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        paginator = FilePagination()
        paginated = paginator.paginate_queryset(queryset, request)
        serializer = self.get_serializer(paginated, many=True)
        return paginator.get_paginated_response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        contact = serializer.save(created_by=request.user)
        return Response(
            self.get_serializer(contact).data, status=status.HTTP_201_CREATED
        )

    def perform_create(self, serializer):
        # kept for compatibility if other code calls perform_create
        serializer.save(created_by=self.request.user)


# ----------------------------
# Software
# ----------------------------
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

        if not self.request.user.is_authenticated:
            qs = qs.filter(status="validated")
        else:
            qs = qs.filter(Q(status="validated") | Q(created_by=self.request.user))

            status_query = self.request.GET.get("status")
            if status_query:
                qs = qs.filter(status=status_query)

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
            contact_fields = ["last_name", "institution"]
            if self.request.user.is_authenticated:
                contact_fields.append(
                    "email"
                )  # hidden from visitors: do not let them probe it

            # every word must be found somewhere (name, maker, references, contacts...)
            for term in search_query.split():
                q = Q()
                for f in software_fields:
                    q |= Q(**{f"{f}__icontains": term})
                for f in reference_fields:
                    q |= Q(**{f"references__{f}__icontains": term})
                for f in contact_fields:
                    q |= Q(**{f"contacts__{f}__icontains": term})
                qs = qs.filter(q)
            qs = qs.distinct()

        filter_query = self.request.GET.get("filter")
        ALLOWED_FILTERS = ["acquisition", "analysis", "acquisition and analysis"]
        if filter_query in ALLOWED_FILTERS:
            qs = qs.filter(type=filter_query)
        qs = filter_catalog(
            qs, self.request, ["versions__recording_sessions_as_software"]
        )

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

        if not self.request.user.is_authenticated:
            queryset = queryset.filter(software__status="validated")
        else:
            queryset = queryset.filter(
                Q(software__status="validated")
                | Q(software__created_by=self.request.user)
            )

        search_query = self.request.query_params.get("search")
        if search_query:
            queryset = queryset.filter(
                Q(software__name__icontains=search_query)
                | Q(version__icontains=search_query)
            )

        if self.action == "retrieve":
            # for a visitor, every linked session belongs to "other users"
            others = (
                ~Q(recording_sessions_as_software__created_by=self.request.user)
                if self.request.user.is_authenticated
                else None
            )
            queryset = queryset.annotate(
                linked_sessions_count=Count("recording_sessions_as_software"),
                linked_sessions_from_other_users=Count(
                    "recording_sessions_as_software", filter=others
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


# ----------------------------
# Favorite
# ----------------------------
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


# ----------------------------
# Track Page
# ----------------------------
class TrackPageView(GenericAPIView):
    serializer_class = TrackPageSerializer
    permission_classes = [AllowAny]

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

        # cache.add is atomic and the cache is shared (Redis): one export per day
        if cache.add(f"pageview-log-generated-{today}", True, 60 * 60 * 24):
            export_page_views.delay()

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


# ----------------------------
# Dataset
# ----------------------------
class DatasetViewSet(viewsets.ModelViewSet):
    queryset = Dataset.objects.all().order_by("name")
    serializer_class = DatasetSerializer
    filter_backends = [filters.SearchFilter]
    # the name, but also what people look for: a file, a session, an animal profile, a DOI
    search_fields = [
        "name",
        "description",
        "doi",
        "recording_session_list__name",
        "recording_session_list__file__name",
        "recording_session_list__file__doi",
        "recording_session_list__animal_profiles__name",
        # what the file rows show as chips (sex, age, duration, cage, bedding)
        "recording_session_list__protocol__animals_sex",
        "recording_session_list__protocol__animals_age",
        "recording_session_list__protocol__context_duration",
        "recording_session_list__protocol__context_cage",
        "recording_session_list__protocol__context_bedding",
    ]

    def get_permissions(self):
        # get_permissions replaces the permission_classes given to @action, so every
        # admin-only action must be listed here
        if self.action in [
            "create",
            "update",
            "partial_update",
            "destroy",
            "session_choices",
        ]:
            return [IsAuthenticated(), IsAdminUser()]
        return [permissions.AllowAny()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @extend_schema(exclude=True)
    @action(
        detail=False,
        methods=["get"],
        url_path="metadata",
        permission_classes=[AllowAny],
    )
    def metadata_all(self, request):
        """Metadata JSON of every dataset (public, like the Dataset page)."""
        return Response(
            {
                "datasets": [
                    build_dataset_metadata(d)["dataset"] for d in self.get_queryset()
                ]
            }
        )

    @extend_schema(exclude=True)
    @action(
        detail=True, methods=["get"], url_path="metadata", permission_classes=[AllowAny]
    )
    def metadata(self, request, pk=None):
        """Metadata JSON of one dataset: sessions, protocols, animals, equipment, files."""
        return Response(build_dataset_metadata(self.get_object()))

    @extend_schema(exclude=True)
    @action(
        detail=False,
        methods=["get"],
        url_path="session-choices",
        permission_classes=[IsAuthenticated, IsAdminUser],
    )
    def session_choices(self, request):
        """Sessions an admin can put in a dataset (all of them, not only their own)."""
        search = request.query_params.get("search", "").strip()
        sessions = RecordingSession.objects.select_related("laboratory").annotate(
            files_count=Count("file")
        )
        if search:
            sessions = sessions.filter(
                Q(name__icontains=search) | Q(laboratory__name__icontains=search)
            )
        return Response(
            [
                {
                    "id": rs.id,
                    "name": rs.name,
                    "laboratory": rs.laboratory.name if rs.laboratory else None,
                    "files_count": rs.files_count,
                }
                for rs in sessions.order_by("name")[:50]
            ]
        )
