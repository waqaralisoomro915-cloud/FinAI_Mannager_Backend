from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = Notification

        fields = [
            "id",
            "kind",
            "title",
            "message",
            "target_id",
            "is_read",
            "read_at",
            "created_at",
        ]

        read_only_fields = fields

    def get_is_read(self, obj):
        return obj.read_at is not None


class NotificationFilterSerializer(serializers.Serializer):
    is_read = serializers.BooleanField(required=False)

    kind = serializers.ChoiceField(
        choices=Notification.Kind.choices,
        required=False,
    )