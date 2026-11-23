from typing import TYPE_CHECKING

from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.request import Request

if TYPE_CHECKING:
    from rest_framework.views import APIView


class IsAdminOrIfAuthenticatedReadOnly(BasePermission):
    """Admins can do everything, authenticated users can only read."""

    def has_permission(self, request: Request, view: "APIView") -> bool:
        return bool(
            (
                request.method in SAFE_METHODS
                and request.user
                and request.user.is_authenticated
            )
            or (request.user and request.user.is_staff)
        )
