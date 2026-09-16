from django.conf import settings
from django.db import models
from django.db.models.functions import Lower


class Category(models.Model):
    class CategoryType(models.TextChoices):
        INCOME = "INCOME", "Income"
        EXPENSE = "EXPENSE", "Expense"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="categories",
    )

    name = models.CharField(max_length=100)

    category_type = models.CharField(
        max_length=10,
        choices=CategoryType.choices,
    )

    description = models.TextField(
        max_length=500,
        blank=True,
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]

        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                "user",
                "category_type",
                name="category_unique_name_per_user_type",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    category_type__in=["INCOME", "EXPENSE"]
                ),
                name="category_valid_type",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_category_type_display()})"