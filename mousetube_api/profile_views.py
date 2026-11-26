"""The signed-in user's own account: unlink ORCID, statistics, export of the data."""

import json

from allauth.socialaccount.models import SocialAccount
from django.apps import apps
from django.core import serializers
from django.core.cache import cache
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Sum
from django.http import HttpResponse
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from mousetube_api.models import Favorite, File, UserProfile


class UnlinkOrcidView(APIView):
    """Remove the ORCID iD of the account (it stays linkable, here or by another account).

    The password is asked: a stolen session must not be enough to change how the account is
    reached. Signing in with the password is not affected.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={200: dict, 400: dict})
    def post(self, request):
        if not request.user.check_password(request.data.get("current_password", "")):
            return Response(
                {"current_password": ["The password is not correct."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        UserProfile.objects.filter(user=request.user).update(orcid=None)
        SocialAccount.objects.filter(user=request.user, provider="orcid").delete()
        return Response({"status": "unlinked"})


class MyStatsView(APIView):
    """Dates of the account and the downloads of the files the user added."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: dict})
    def get(self, request):
        user = request.user
        files = File.objects.filter(created_by=user)
        return Response(
            {
                "date_joined": user.date_joined,
                "last_login": user.last_login,
                "files": files.count(),
                "downloads": files.aggregate(n=Sum("downloads"))["n"] or 0,
            }
        )


def _own_rows(user):
    """Every row the user added (`created_by`) or marked as favorite, by model."""
    for model in apps.get_app_config("mousetube_api").get_models():
        if model is UserProfile:
            continue
        if model is Favorite:
            yield model, model.objects.filter(user=user)
        elif any(
            f.name == "created_by" and f.related_model is type(user)
            for f in model._meta.get_fields()
        ):
            yield model, model.objects.filter(created_by=user)


class MyDataView(APIView):
    """The account and what the user added, as a JSON file (right of access, GDPR).

    Not in it: the password, the sign-in tokens, the other users' data. Once a minute.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: dict, 429: dict})
    def get(self, request):
        user = request.user
        if not cache.add(f"my-data:{user.pk}", 1, 60):
            return Response(
                {"detail": "Wait a minute before asking again."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        profile = UserProfile.objects.filter(user=user)
        data = {
            "account": {
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "date_joined": user.date_joined,
                "last_login": user.last_login,
                "is_staff": user.is_staff,
            },
            "profile": [
                {k: v for k, v in row["fields"].items() if k != "sessions_revoked_at"}
                for row in serializers.serialize("python", profile)
            ],
            "contributions": {
                model._meta.label: [
                    {"id": row["pk"], **row["fields"]}
                    for row in serializers.serialize("python", rows)
                ]
                for model, rows in _own_rows(user)
                if rows.exists()
            },
        }
        response = HttpResponse(
            json.dumps(data, cls=DjangoJSONEncoder, indent=2, ensure_ascii=False),
            content_type="application/json",
        )
        response["Content-Disposition"] = (
            f'attachment; filename="mousetube-data-{user.pk}.json"'
        )
        return response
