from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Sum
from rest_framework import serializers

from ..categories.models import Category
from ..transactions.models import Transaction

from .models import Budget
from .services import save_budget


class BudgetSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.none()
    )

    category_name = serializers.CharField(
        source="category.name",
        read_only=True,
    )

    currency = serializers.SerializerMethodField()
    spent = serializers.SerializerMethodField()
    remaining = serializers.SerializerMethodField()
    usage_percentage = serializers.SerializerMethodField()
    is_exceeded = serializers.SerializerMethodField()

    class Meta:
        model = Budget

        fields = [
            "id",
            "user",
            "category",
            "category_name",
            "currency",
            "amount",
            "start_date",
            "end_date",
            "spent",
            "remaining",
            "usage_percentage",
            "is_exceeded",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "user",
            "created_at",
            "updated_at",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        request = self.context.get("request")

        if request and request.user.is_authenticated:
            self.fields["category"].queryset = Category.objects.filter(
                user=request.user,
                category_type=Category.CategoryType.EXPENSE,
            )

        # Avoid repeating the spending query for every calculated field.
        self._spent_cache = {}

    def _get_spent(self, obj):
        if obj.pk not in self._spent_cache:
            total = Transaction.objects.filter(
                user_id=obj.user_id,
                category_id=obj.category_id,
                transaction_type=Transaction.TransactionType.EXPENSE,
                is_void=False,
                wallet__currency="PKR",
                transaction_date__range=(
                    obj.start_date,
                    obj.end_date,
                ),
            ).aggregate(total=Sum("amount"))["total"]

            self._spent_cache[obj.pk] = total or Decimal("0.00")

        return self._spent_cache[obj.pk]

    def get_currency(self, obj):
        return "PKR"

    def get_spent(self, obj):
        return format(self._get_spent(obj), ".2f")

    def get_remaining(self, obj):
        remaining = obj.amount - self._get_spent(obj)
        return format(remaining, ".2f")

    def get_usage_percentage(self, obj):
        percentage = (
            self._get_spent(obj) / obj.amount * Decimal("100")
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

        return format(percentage, ".2f")

    def get_is_exceeded(self, obj):
        return self._get_spent(obj) > obj.amount

    def create(self, validated_data):
        return save_budget(
            user=self.context["request"].user,
            data=validated_data,
        )

    def update(self, instance, validated_data):
        return save_budget(
            user=self.context["request"].user,
            data=validated_data,
            instance=instance,
        )