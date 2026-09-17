from rest_framework.permissions import BasePermission


class IsNotificationRecipient(BasePermission):
    message = "You can only access your own notifications."

    def has_object_permission(self, request, view, obj):
        return obj.recipient_id == request.user.id