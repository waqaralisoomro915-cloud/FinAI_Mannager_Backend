from django.utils import timezone
from rest_framework import serializers

from .jobs import next_occurrence
from .models import GeneratedReport, ReportSchedule
from .serializers import ReportPeriodSerializer


class GeneratedReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeneratedReport

        fields = [
            "id",
            "schedule",
            "scheduled_for",
            "date_from",
            "date_to",
            "status",
            "error_message",
            "created_at",
            "completed_at",
        ]

        read_only_fields = [
            "id",
            "schedule",
            "scheduled_for",
            "status",
            "error_message",
            "created_at",
            "completed_at",
        ]

    def validate(self, attrs):
        period = ReportPeriodSerializer(data={
            "date_from": attrs["date_from"],
            "date_to": attrs["date_to"],
        })
        period.is_valid(raise_exception=True)
        return attrs


class ReportScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportSchedule

        fields = [
            "id",
            "frequency",
            "timezone_name",
            "next_run",
            "last_scheduled_for",
            "is_active",
            "created_at",
        ]

        read_only_fields = [
            "id",
            "next_run",
            "last_scheduled_for",
            "is_active",
            "created_at",
        ]

    def create(self, validated_data):
        zone = validated_data.get("timezone_name", "Asia/Karachi")

        return ReportSchedule.objects.create(
            **validated_data,
            next_run=next_occurrence(
                timezone.now(),
                validated_data["frequency"],
                zone,
            ),
        )