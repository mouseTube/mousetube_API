from djoser.views import UserViewSet
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from mousetube_api.utils import email_change
from mousetube_api.utils.registration import confirm_email_and_notify_admin


class ChangeEmailSerializer(serializers.Serializer):
    new_email = serializers.EmailField(max_length=254)
    current_password = serializers.CharField(write_only=True, trim_whitespace=False)


class ConfirmEmailChangeSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=1000)


class CustomUserViewSet(UserViewSet):
    """djoser's activation endpoint, but the link only confirms the e-mail address.

    The account stays inactive until an administrator activates it.
    """

    @action(["post"], detail=False)
    def activation(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)  # checks uid + token
        confirm_email_and_notify_admin(serializer.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(["post"], detail=False, permission_classes=[IsAuthenticated])
    def change_email(self, request, *args, **kwargs):
        """Ask to use another address: a link is sent to it (see utils/email_change.py).

        202 whether or not the mail was sent (taken address, too many requests): the answer
        does not tell which addresses have an account.
        """
        serializer = ChangeEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if not request.user.check_password(data["current_password"]):
            raise serializers.ValidationError(
                {"current_password": ["The password is not correct."]}
            )
        try:
            new_email = email_change.check_new_email(request.user, data["new_email"])
            email_change.request_change(request.user, new_email)
        except email_change.EmailChangeError as error:
            raise serializers.ValidationError({"new_email": [str(error)]}) from None
        except email_change.MailNotSent:
            return Response(
                {"detail": "The e-mail could not be sent. Try again later."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(status=status.HTTP_202_ACCEPTED)

    @action(["post"], detail=False, permission_classes=[IsAuthenticated])
    def confirm_email_change(self, request, *args, **kwargs):
        """The link of the mail: signed in as the user it was made for, it applies the change."""
        serializer = ConfirmEmailChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            email = email_change.confirm_change(
                request.user, serializer.validated_data["token"]
            )
        except email_change.EmailChangeError as error:
            raise serializers.ValidationError({"token": [str(error)]}) from None
        return Response({"email": email})
