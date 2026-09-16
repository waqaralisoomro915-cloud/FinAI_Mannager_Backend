from django.db import transaction
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .jobs import next_occurrence
from .models import GeneratedReport, ReportSchedule
from .saved_serializers import (
    GeneratedReportSerializer,
    ReportScheduleSerializer,
)
from .views import PrivateReportMixin, ReportPagination


class GeneratedReportViewSet(
    PrivateReportMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = GeneratedReportSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ReportPagination

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return GeneratedReport.objects.none()

        return GeneratedReport.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        report = self.get_object()

        if report.status != GeneratedReport.Status.COMPLETED:
            raise ValidationError({
                "detail": "Report is not ready to download."
            })

        if not report.file:
            raise NotFound("Report file is unavailable.")

        try:
            file_handle = report.file.open("rb")
        except FileNotFoundError:
            raise NotFound("Report file is unavailable.")

        return FileResponse(
            file_handle,
            as_attachment=True,
            filename=f"finai-report-{report.pk}.csv",
            content_type="text/csv; charset=utf-8",
        )

    @action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        report = self.get_object()

        changed = GeneratedReport.objects.filter(
            pk=report.pk,
            user=request.user,
            status=GeneratedReport.Status.FAILED,
        ).update(
            status=GeneratedReport.Status.PENDING,
            error_message="",
        )

        if not changed:
            raise ValidationError({
                "detail": "Only failed reports can be retried."
            })

        report.refresh_from_db()
        return Response(
            self.get_serializer(report).data,
            status=status.HTTP_202_ACCEPTED,
        )


class ReportScheduleViewSet(
    PrivateReportMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = ReportScheduleSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ReportPagination

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return ReportSchedule.objects.none()

        return ReportSchedule.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["post"])
    def pause(self, request, pk=None):
        with transaction.atomic():
            schedule = get_object_or_404(
                ReportSchedule.objects.select_for_update(),
                pk=pk,
                user=request.user,
            )
            schedule.is_active = False
            schedule.save(update_fields=["is_active"])

        return Response(self.get_serializer(schedule).data)

    @action(detail=True, methods=["post"])
    def resume(self, request, pk=None):
        with transaction.atomic():
            schedule = get_object_or_404(
                ReportSchedule.objects.select_for_update(),
                pk=pk,
                user=request.user,
            )

            if not schedule.is_active:
                # Paused periods are intentionally skipped.
                schedule.next_run = next_occurrence(
                    timezone.now(),
                    schedule.frequency,
                    schedule.timezone_name,
                )
                schedule.is_active = True
                schedule.save(update_fields=["next_run", "is_active"])

        return Response(self.get_serializer(schedule).data)