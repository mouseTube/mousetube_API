from djoser.views import UserViewSet
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from mousetube_api.utils.registration import confirm_email_and_notify_admin


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
