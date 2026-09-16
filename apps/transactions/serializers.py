from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from .models import Transaction
from .services import create_transaction


class TransactionSerializer(serializers.ModelSerializer):
    wallet_name = serializers.CharField(
        source="wallet.name",
        read_only=True,
    )

    destination_wallet_name = serializers.CharField(
        source="destination_wallet.name",
        read_only=True,
        allow_null=True,
    )

    category_name = serializers.CharField(
        source="category.name",
        read_only=True,
        allow_null=True,
    )

    currency = serializers.CharField(
        source="wallet.currency",
        read_only=True,
    )

    class Meta:
        model = Transaction

        fields = [
            "id",
            "user",
            "wallet",
            "wallet_name",
            "destination_wallet",
            "destination_wallet_name",
            "category",
            "category_name",
            "transaction_type",
            "amount",
            "currency",
            "description",
            "transaction_date",
            "is_void",
            "void_reason",
            "voided_at",
            "created_at",
        ]

        read_only_fields = fields


class TransactionCreateSerializer(serializers.Serializer):
    wallet = serializers.IntegerField(min_value=1)

    destination_wallet = serializers.IntegerField(
        min_value=1,
        required=False,
        allow_null=True,
    )

    category = serializers.IntegerField(
        min_value=1,
        required=False,
        allow_null=True,
    )

    transaction_type = serializers.ChoiceField(
        choices=Transaction.TransactionType.choices,
    )

    amount = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )

    description = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        default="",
    )

    transaction_date = serializers.DateField(
        default=timezone.localdate,
    )

    def create(self, validated_data):
        return create_transaction(
            user=self.context["request"].user,
            data=validated_data,
        )

    def to_representation(self, instance):
        return TransactionSerializer(
            instance,
            context=self.context,
        ).data


class VoidTransactionSerializer(serializers.Serializer):
    reason = serializers.CharField(
        max_length=250,
        allow_blank=False,
        trim_whitespace=True,
    )


class TransactionFilterSerializer(serializers.Serializer):
    wallet = serializers.IntegerField(min_value=1, required=False)
    category = serializers.IntegerField(min_value=1, required=False)

    transaction_type = serializers.ChoiceField(
        choices=Transaction.TransactionType.choices,
        required=False,
    )

    is_void = serializers.BooleanField(required=False)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)

    def validate(self, attrs):
        start = attrs.get("date_from")
        end = attrs.get("date_to")

        if start and end and start > end:
            raise serializers.ValidationError(
                "date_from must be on or before date_to."
            )

        return attrs