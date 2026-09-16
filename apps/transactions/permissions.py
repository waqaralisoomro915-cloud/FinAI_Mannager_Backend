from rest_framework.permissions import BasePermission


class IsTransactionOwner(BasePermission):
    message = "You can only access your own transactions."

    def has_object_permission(self, request, view, obj):
        return obj.user_id == request.user.id