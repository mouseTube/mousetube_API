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

from django.contrib import admin
from django.urls import path
from django.conf.urls.static import static
from .views import (
    RepositoryAPIView,
    LegacyUserAPIView,
    UserProfileAPIView,
    SpeciesAPIView,
    StrainAPIView,
    MetadataAPIView,
    ProtocolAPIView,
    FileAPIView,
    SoftwareAPIView,
    HardwareAPIView,
    CountryAPIView,
    ReferenceAPIView,
    SubjectAPIView,
    RecordingSessionAPIView,
    SubjectSessionAPIView,
)
from django.conf import settings

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/repository/", RepositoryAPIView.as_view(), name="repository"),
    path("api/reference/", ReferenceAPIView.as_view(), name="reference"),
    path("api/legacy_user/", LegacyUserAPIView.as_view(), name="legacy_user"),
    path("api/user_profile/", UserProfileAPIView.as_view(), name="user_profile"),
    path("api/species/", SpeciesAPIView.as_view(), name="species"),
    path("api/strain/", StrainAPIView.as_view(), name="strain"),
    path("api/metadata/", MetadataAPIView.as_view(), name="metadata"),
    path("api/protocol/", ProtocolAPIView.as_view(), name="protocol"),
    path("api/file/", FileAPIView.as_view(), name="file"),
    path("api/software/", SoftwareAPIView.as_view(), name="software"),
    path("api/hardware/", HardwareAPIView.as_view(), name="hardware"),
    path("api/country/", CountryAPIView.as_view(), name="country"),
    path("api/subject/", SubjectAPIView.as_view(), name="subject"),
    path(
        "api/recording_session/",
        RecordingSessionAPIView.as_view(),
        name="recording_session",
    ),
    path(
        "api/subject_session/", SubjectSessionAPIView.as_view(), name="subject_session"
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
