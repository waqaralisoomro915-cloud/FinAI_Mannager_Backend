from django.utils import timezone
from rest_framework import serializers


class ReportPeriodSerializer(serializers.Serializer):
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)

    def validate(self, attrs):
        end = attrs.get("date_to", timezone.localdate())
        start = attrs.get("date_from", end.replace(day=1))

        if start > end:
            raise serializers.ValidationError({
                "date_to": "End date must be on or after start date."
            })

        if (end - start).days > 365:
            raise serializers.ValidationError({
                "detail": "Select a period of at most 366 days."
            })

        return {
            "date_from": start,
            "date_to": end,
        }