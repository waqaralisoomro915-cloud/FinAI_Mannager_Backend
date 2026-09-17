from django.utils import timezone
from rest_framework import serializers

from ..reports.serializers import ReportPeriodSerializer


class SpendingInsightRequestSerializer(ReportPeriodSerializer):
    def validate(self, attrs):
        attrs = super().validate(attrs)

        if attrs["date_to"] > timezone.localdate():
            raise serializers.ValidationError({
                "date_to": "Choose today or an earlier date."
            })

        return attrs