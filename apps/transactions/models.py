from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class Transaction(models.Model):
    class TransactionType(models.TextChoices):
        INCOME = "INCOME", "Income"
        EXPENSE = "EXPENSE", "Expense"
        TRANSFER = "TRANSFER", "Transfer"

    user = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="transactions",  )

    wallet = models.ForeignKey("wallets.Wallet",on_delete=models.PROTECT,related_name="transactions",)

    destination_wallet = models.ForeignKey("wallets.Wallet",on_delete=models.PROTECT,related_name="incoming_transfers",null=True,blank=True,)

    category = models.ForeignKey("categories.Category",on_delete=models.PROTECT,related_name="transactions",null=True,blank=True,)

    transaction_type = models.CharField(max_length=10,choices=TransactionType.choices,)

    amount = models.DecimalField(max_digits=14,decimal_places=2,validators=[MinValueValidator(Decimal("0.01"))],)

    description = models.CharField(max_length=500,blank=True,)

    transaction_date = models.DateField(default=timezone.localdate,)

    is_void = models.BooleanField(default=False)
    void_reason = models.CharField(max_length=250, blank=True)
    voided_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-transaction_date", "-id"]
        indexes = [
            models.Index(fields=["user", "transaction_date"]),
        ]

        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="transaction_amount_positive",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        transaction_type="TRANSFER",
                        destination_wallet__isnull=False,
                        category__isnull=True,
                    )
                    |
                    models.Q(
                        transaction_type__in=["INCOME", "EXPENSE"],
                        destination_wallet__isnull=True,
                        category__isnull=False,
                    )
                ),
                name="transaction_valid_relationships",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(destination_wallet__isnull=True)
                    | ~models.Q(wallet=models.F("destination_wallet"))
                ),
                name="transaction_different_wallets",
            ),
        ]

    def __str__(self):
        return f"{self.transaction_type}: {self.amount}"