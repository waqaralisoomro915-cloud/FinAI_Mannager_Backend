from django.conf import settings
from django.db import models


class Notification(models.Model):
    class Kind(models.TextChoices):
        BUDGET = "BUDGET", "Budget"
        SAVINGS = "SAVINGS", "Savings"
        REPORT = "REPORT", "Report"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )

    kind = models.CharField(
        max_length=10,
        choices=Kind.choices,
    )

    title = models.CharField(max_length=150)
    message = models.TextField()

    target_id = models.PositiveBigIntegerField()

    event_key = models.CharField(max_length=150)

    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

        indexes = [
            models.Index(fields=["recipient", "read_at"]),
        ]

        constraints = [
            models.UniqueConstraint(
                fields=["recipient", "event_key"],
                name="notification_unique_recipient_event",
            ),
        ]

    def __str__(self):
        return self.title