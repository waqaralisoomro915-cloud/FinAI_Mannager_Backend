from rest_framework import serializers

from .models import Wallet


class WalletSerializer(serializers.ModelSerializer):
    current_balance = serializers.SerializerMethodField()

    class Meta:
        model = Wallet

        fields = [
            "id",
            "user",
            "name",
            "wallet_type",
            "currency",
            "opening_balance",
            "current_balance",
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

    def get_current_balance(self, obj):
        from ..transactions.services import wallet_balance

        return format(wallet_balance(obj), ".2f")

    def validate_name(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Wallet name cannot be empty."
            )

        return value

    def validate(self, attrs):
        if self.instance is not None:
            errors = {}

            for field in ("opening_balance", "currency"):
                if (
                    field in attrs
                    and attrs[field] != getattr(self.instance, field)
                ):
                    errors[field] = (
                        "This field cannot be changed after wallet creation."
                    )

            if errors:
                raise serializers.ValidationError(errors)

        return attrs