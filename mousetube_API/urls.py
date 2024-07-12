"""
Created by Nicolas Torquet at 15/11/2023
torquetn@igbmc.fr
Copyright: CNRS - INSERM - UNISTRA - ICS - IGBMC
CNRS - Mouse Clinical Institute
PHENOMIN, CNRS UMR7104, INSERM U964, Université de Strasbourg
Code under GPL v3.0 licence

URL configuration for mousetube_API project.

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
from django.urls import path, include
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from .views import *

router = DefaultRouter()
# router.register('country', CountryViewSet, basename='country')
router.register('repository', RepositoryViewSet, basename='repository')
router.register('reference', ReferenceViewSet, basename='reference')
router.register('contact', ContactViewSet, basename='contact')
router.register('user', UserViewSet, basename='user')
router.register('user_profile', UserProfileViewSet, basename='user_profile')
router.register('species', SpeciesViewSet, basename='species')
router.register('strain', StrainViewSet, basename='strain')
router.register('metadata', MetadataViewSet, basename='metadata')
router.register('protocol', ProtocolViewSet, basename='protocol')
router.register('file', FileViewSet, basename='file')
# router.register('software', SoftwareViewSet, basename='software')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('api/software/', SoftwareAPIView.as_view()),
    path('api/hardware/', HardwareAPIView.as_view()),
    path('api/country/',  CountryAPIView.as_view(), name='country')
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)