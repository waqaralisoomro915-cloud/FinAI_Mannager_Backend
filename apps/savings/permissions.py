from rest_framework.permissions import BasePermission


class IsSavingsGoalOwner(BasePermission):
    message = "You can only access your own savings goals."

    def has_object_permission(self, request, view, obj):
        return obj.user_id == request.user.id