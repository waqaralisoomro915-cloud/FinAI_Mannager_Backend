import tempfile

from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.files.storage import FileSystemStorage
from django.urls import reverse

from rest_framework.test import APITestCase

from .jobs import (
    enqueue_due_schedule,
    previous_period,
    process_report,
)
from .models import GeneratedReport, ReportSchedule


User = get_user_model()


class SavedReportTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="waqar@example.com",
            password="Testing!Reports2026",
        )
        self.other_user = User.objects.create_user(
            email="other@example.com",
            password="Testing!Reports2026",
        )

        self.client.force_authenticate(user=self.user)

        self.temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)

        field = GeneratedReport._meta.get_field("file")

        self.storage_patch = patch.object(
            field,
            "storage",
            FileSystemStorage(location=self.temp_directory.name),
        )
        self.storage_patch.start()
        self.addCleanup(self.storage_patch.stop)

    def create_report(self):
        response = self.client.post(
            reverse("reports:generated-report-list"),
            {
                "date_from": "2026-08-01",
                "date_to": "2026-08-31",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        return GeneratedReport.objects.get(pk=response.data["id"])

    def test_report_starts_pending(self):
        report = self.create_report()

        self.assertEqual(report.user_id, self.user.pk)
        self.assertEqual(report.status, "PENDING")

        response = self.client.get(
            reverse(
                "reports:generated-report-download",
                args=[report.pk],
            )
        )
        self.assertEqual(response.status_code, 400)

    def test_generation_and_private_download(self):
        report = self.create_report()

        self.assertTrue(process_report(report.pk))
        report.refresh_from_db()
        self.assertEqual(report.status, "COMPLETED")

        url = reverse(
            "reports:generated-report-download",
            args=[report.pk],
        )

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        content = b"".join(response.streaming_content)
        response.close()

        self.assertIn(b"Destination Wallet", content)

        self.client.force_authenticate(user=self.other_user)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_schedule_occurrence_is_not_duplicated(self):
        due = datetime(
            2026, 9, 1, 9, 0,
            tzinfo=ZoneInfo("Asia/Karachi"),
        )

        schedule = ReportSchedule.objects.create(
            user=self.user,
            frequency="MONTHLY",
            timezone_name="Asia/Karachi",
            next_run=due,
        )

        self.assertTrue(enqueue_due_schedule(schedule.pk, now=due))
        self.assertFalse(enqueue_due_schedule(schedule.pk, now=due))

        self.assertEqual(schedule.reports.count(), 1)

        report = schedule.reports.get()
        self.assertEqual(report.date_from.isoformat(), "2026-08-01")
        self.assertEqual(report.date_to.isoformat(), "2026-08-31")

    def test_previous_week_period(self):
        start, end = previous_period(
            datetime(
                2026, 9, 14, 9, 0,
                tzinfo=ZoneInfo("Asia/Karachi"),
            ),
            "WEEKLY",
            "Asia/Karachi",
        )

        self.assertEqual(start.isoformat(), "2026-09-07")
        self.assertEqual(end.isoformat(), "2026-09-13")

    def test_generation_failure_can_be_retried(self):
        report = self.create_report()

        with patch(
            "apps.reports.jobs.build_csv",
            side_effect=RuntimeError("Test failure"),
        ):
            self.assertFalse(process_report(report.pk))

        report.refresh_from_db()
        self.assertEqual(report.status, "FAILED")

        response = self.client.post(
            reverse(
                "reports:generated-report-retry",
                args=[report.pk],
            )
        )
        self.assertEqual(response.status_code, 202)

        self.assertTrue(process_report(report.pk))

    def test_other_user_cannot_pause_schedule(self):
        schedule = ReportSchedule.objects.create(
            user=self.user,
            frequency="MONTHLY",
            next_run=datetime(
                2026, 10, 1, 9, 0,
                tzinfo=ZoneInfo("Asia/Karachi"),
            ),
        )

        self.client.force_authenticate(user=self.other_user)

        response = self.client.post(
            reverse(
                "reports:report-schedule-pause",
                args=[schedule.pk],
            )
        )

        self.assertEqual(response.status_code, 404)