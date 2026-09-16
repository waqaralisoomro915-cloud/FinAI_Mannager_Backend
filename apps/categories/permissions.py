from rest_framework.permissions import BasePermission


class IsCategoryOwner(BasePermission):
    message = "You can only access your own categories."

    def has_object_permission(self, request, view, obj):
        return obj.user_id == request.user.id