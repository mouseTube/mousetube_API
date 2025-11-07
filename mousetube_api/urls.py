"""
Created by Nicolas Torquet at 15/11/2023
torquetn@igbmc.fr
Copyright: CNRS - INSERM - UNISTRA - ICS - IGBMC
CNRS - Mouse Clinical Institute
PHENOMIN, CNRS UMR7104, INSERM U964, Université de Strasbourg
Code under GPL v3.0 licence

URL configuration for mousetube_api project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

import os

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.urls import include, path
from django.views.static import serve
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from .views import (
    AnimalProfileViewSet,
    CountryAPIView,
    DatasetViewSet,
    FavoriteViewSet,
    FileAPIView,
    FileDetailAPIView,
    FileUploadAsyncView,
    HardwareAPIView,
    HardwareDetailAPIView,
    LaboratoryAPIView,
    LegacyUserAPIView,
    LinkOrcidView,
    ProtocolViewSet,
    PublishSessionView,
    RecordingSessionViewSet,
    ReferenceAPIView,
    RepositoryAPIView,
    SchemaDetailView,
    SoftwareVersionViewSet,
    SoftwareViewSet,
    SpeciesViewSet,
    StrainViewSet,
    StudyViewSet,
    SubjectViewSet,
    TrackPageView,
    UserProfileDetailAPIView,
    UserProfileListAPIView,
    file_task_status,
    get_task_status,
    repository_metadata_payload,
    repository_metadata_schema,
)

router = DefaultRouter()
router.register(r"protocol", ProtocolViewSet, basename="protocol")
router.register(
    r"recording-session", RecordingSessionViewSet, basename="recording-session"
)
router.register(r"species", SpeciesViewSet, basename="species")
router.register(r"strain", StrainViewSet, basename="strain")
router.register(r"animalprofile", AnimalProfileViewSet, basename="animalprofile")
router.register(r"subject", SubjectViewSet, basename="subject")
router.register(r"laboratory", LaboratoryAPIView, basename="laboratory")
router.register(
    r"software-version", SoftwareVersionViewSet, basename="software-version"
)
router.register(r"study", StudyViewSet, basename="study")
router.register(r"software", SoftwareViewSet, basename="software")
router.register(r"favorite", FavoriteViewSet, basename="favorite")
router.register(r"dataset", DatasetViewSet, basename="dataset")

urlpatterns = [
    path(
        "admin/stats/",
        staff_member_required(serve),
        {
            "document_root": os.path.join(settings.BASE_DIR, "logs"),
            "path": "latest.html",
        },
        name="admin-stats",
    ),
    path("admin/", admin.site.urls),
    path("api/", include(router.urls)),
    path("api/repository/", RepositoryAPIView.as_view(), name="repository"),
    path(
        "api/repository/<int:repo_id>/schema/",
        repository_metadata_schema,
        name="repository-metadata-schema",
    ),
    path(
        "api/repository/<int:repository_id>/sessions/<int:recording_session_id>/payload/",
        repository_metadata_payload,
        name="repository-metadata-payload",
    ),
    path("api/reference/", ReferenceAPIView.as_view(), name="reference"),
    path("api/legacy_user/", LegacyUserAPIView.as_view(), name="legacy_user"),
    path("api/user_profile/", UserProfileListAPIView.as_view(), name="user_profile"),
    path(
        "api/user_profile/<int:pk>/",
        UserProfileDetailAPIView.as_view(),
        name="user_profile-detail",
    ),
    path("api/file/", FileAPIView.as_view(), name="file"),
    path("api/file/<int:file_id>/status/", file_task_status, name="file-status"),
    path("api/file/upload_async/", FileUploadAsyncView.as_view(), name="file-upload"),
    path(
        "api/file/publish_session/",
        PublishSessionView.as_view(),
        name="publish-session",
    ),
    path("api/recording-session/get_task_status", get_task_status, name="file-status"),
    path("api/hardware/", HardwareAPIView.as_view(), name="hardware"),
    path(
        "api/hardware/<int:pk>/",
        HardwareDetailAPIView.as_view(),
        name="hardware-detail",
    ),
    path("api/country/", CountryAPIView.as_view(), name="country"),
    path("api/file/<int:pk>/", FileDetailAPIView.as_view(), name="file-detail"),
    path("api/track-page/", TrackPageView.as_view(), name="track-page"),
    path(
        "api/schema/<str:filename>/", SchemaDetailView.as_view(), name="schema-detail"
    ),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "swagger/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"
    ),
    path("auth/", include("djoser.urls")),
    path("auth/", include("djoser.urls.jwt")),
    path("accounts/", include("allauth.socialaccount.urls")),
    path("accounts/", include("allauth.urls")),
    path("api/link-orcid/", LinkOrcidView.as_view(), name="link-orcid"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
