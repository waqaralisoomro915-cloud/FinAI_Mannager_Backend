from rest_framework.permissions import BasePermission


class IsWalletOwner(BasePermission):
    message = "You can only access your own wallets."

    def has_object_permission(self, request, view, obj):
        return obj.user_id == request.user.id