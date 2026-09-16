from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class SavingsGoal(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="savings_goals",
    )

    wallet = models.ForeignKey(
        "wallets.Wallet",
        on_delete=models.PROTECT,
        related_name="savings_goals",
    )

    name = models.CharField(max_length=100)

    target_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    deadline = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]

        constraints = [
            models.CheckConstraint(
                condition=models.Q(target_amount__gt=0),
                name="savings_target_positive",
            ),
        ]

    def __str__(self):
        return self.name


class SavingsContribution(models.Model):
    class EntryType(models.TextChoices):
        CONTRIBUTION = "CONTRIBUTION", "Contribution"
        WITHDRAWAL = "WITHDRAWAL", "Withdrawal"

    goal = models.ForeignKey(
        SavingsGoal,
        on_delete=models.PROTECT,
        related_name="contributions",
    )

    entry_type = models.CharField(
        max_length=12,
        choices=EntryType.choices,
    )

    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    note = models.CharField(max_length=250, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="savings_entry_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    entry_type__in=["CONTRIBUTION", "WITHDRAWAL"]
                ),
                name="savings_entry_valid_type",
            ),
        ]

    def __str__(self):
        return f"{self.entry_type}: {self.amount}"