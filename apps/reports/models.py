from django.conf import settings
from django.db import models

from .storage import private_report_storage


class ReportSchedule(models.Model):
    class Frequency(models.TextChoices):
        WEEKLY = "WEEKLY", "Weekly"
        MONTHLY = "MONTHLY", "Monthly"

    class TimeZone(models.TextChoices):
        KARACHI = "Asia/Karachi", "Pakistan"
        UTC = "UTC", "UTC"

    user = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="report_schedules",)
    frequency = models.CharField(max_length=10,choices=Frequency.choices,)
    timezone_name = models.CharField(max_length=50,choices=TimeZone.choices,default=TimeZone.KARACHI,)
    next_run = models.DateTimeField()
    last_scheduled_for = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.user_id}: {self.frequency}"


class GeneratedReport(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    user = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT, related_name="generated_reports",)

    schedule = models.ForeignKey(ReportSchedule,on_delete=models.PROTECT,related_name="reports",null=True, blank=True,)

    # Identifies one occurrence of a recurring schedule.
    scheduled_for = models.DateTimeField(null=True, blank=True)

    date_from = models.DateField()
    date_to = models.DateField()

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )

    file = models.FileField(
        storage=private_report_storage,
        upload_to="transactions/",
        blank=True,
    )

    error_message = models.CharField(max_length=250, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]

        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    date_to__gte=models.F("date_from")
                ),
                name="generated_report_valid_dates",
            ),
            models.UniqueConstraint(
                fields=["schedule", "scheduled_for"],
                name="report_unique_schedule_occurrence",
            ),
        ]

    def __str__(self):
        return f"Report {self.pk}: {self.status}"