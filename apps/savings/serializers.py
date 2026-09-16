from decimal import Decimal, ROUND_HALF_UP

from rest_framework import serializers

from .models import SavingsContribution, SavingsGoal
from .services import goal_saved, save_goal


class SavingsGoalSerializer(serializers.ModelSerializer):
    wallet = serializers.IntegerField(min_value=1)

    wallet_name = serializers.CharField(
        source="wallet.name",
        read_only=True,
    )

    currency = serializers.CharField(
        source="wallet.currency",
        read_only=True,
    )

    saved_amount = serializers.SerializerMethodField()
    remaining_amount = serializers.SerializerMethodField()
    progress_percentage = serializers.SerializerMethodField()
    is_completed = serializers.SerializerMethodField()

    class Meta:
        model = SavingsGoal

        fields = [
            "id",
            "user",
            "wallet",
            "wallet_name",
            "currency",
            "name",
            "target_amount",
            "deadline",
            "saved_amount",
            "remaining_amount",
            "progress_percentage",
            "is_completed",
            "is_active",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "user",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_cache = {}

    def _saved(self, obj):
        if obj.pk not in self._saved_cache:
            self._saved_cache[obj.pk] = goal_saved(obj)

        return self._saved_cache[obj.pk]

    def to_representation(self, instance):
        # The input field accepts an integer ID; the model stores an object.
        # Return the wallet ID explicitly through a read-only serializer.
        return SavingsGoalReadSerializer(
            instance,
            context=self.context,
        ).data

    def validate_name(self, value):
        value = " ".join(value.split())

        if not value:
            raise serializers.ValidationError(
                "Goal name cannot be empty."
            )

        return value

    def get_saved_amount(self, obj):
        return format(self._saved(obj), ".2f")

    def get_remaining_amount(self, obj):
        remaining = max(
            obj.target_amount - self._saved(obj),
            Decimal("0.00"),
        )
        return format(remaining, ".2f")

    def get_progress_percentage(self, obj):
        progress = (
            self._saved(obj) / obj.target_amount * Decimal("100")
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

        return format(progress, ".2f")

    def get_is_completed(self, obj):
        return self._saved(obj) >= obj.target_amount

    def create(self, validated_data):
        return save_goal(
            user=self.context["request"].user,
            data=validated_data,
        )

    def update(self, instance, validated_data):
        return save_goal(
            user=self.context["request"].user,
            data=validated_data,
            instance=instance,
        )


class SavingsGoalReadSerializer(SavingsGoalSerializer):
    wallet = serializers.IntegerField(
        source="wallet_id",
        read_only=True,
    )

    def to_representation(self, instance):
        return serializers.ModelSerializer.to_representation(
            self,
            instance,
        )


class SavingsEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = SavingsContribution

        fields = [
            "id",
            "goal",
            "entry_type",
            "amount",
            "note",
            "created_at",
        ]

        read_only_fields = ["id", "goal", "created_at"]