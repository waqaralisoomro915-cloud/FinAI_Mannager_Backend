from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Wallet(models.Model):
    class WalletType(models.TextChoices):
        CASH = "CASH", "Cash"
        BANK = "BANK", "Bank Account"
        MOBILE = "MOBILE", "Mobile Wallet"

    class Currency(models.TextChoices):
        PKR = "PKR", "Pakistani Rupee"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="wallets",
    )

    name = models.CharField(max_length=100)

    wallet_type = models.CharField(
        max_length=10,
        choices=WalletType.choices,
        default=WalletType.CASH,
    )

    currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        default=Currency.PKR,
    )

    opening_balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]

        constraints = [
            models.CheckConstraint(
                condition=models.Q(opening_balance__gte=0),
                name="wallet_opening_balance_non_negative",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.currency})"