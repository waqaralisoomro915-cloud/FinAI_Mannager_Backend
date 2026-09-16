from rest_framework import serializers

from .models import Category


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category

        fields = [
            "id",
            "user",
            "name",
            "category_type",
            "description",
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

        # We validate the owner-dependent uniqueness rule below.
        validators = []

    def validate_name(self, value):
        # Remove leading/trailing and repeated whitespace.
        value = " ".join(value.split())

        if not value:
            raise serializers.ValidationError(
                "Category name cannot be empty."
            )

        return value

    def validate(self, attrs):
        user = self.context["request"].user
        instance = self.instance

        if instance is not None:
            if (
                "category_type" in attrs
                and attrs["category_type"] != instance.category_type
            ):
                raise serializers.ValidationError({
                    "category_type": (
                        "Category type cannot be changed after creation."
                    )
                })

        name = attrs.get(
            "name",
            instance.name if instance else None,
        )
        category_type = attrs.get(
            "category_type",
            instance.category_type if instance else None,
        )

        duplicates = Category.objects.filter(
            user=user,
            name__iexact=name,
            category_type=category_type,
        )

        if instance is not None:
            duplicates = duplicates.exclude(pk=instance.pk)

        if duplicates.exists():
            raise serializers.ValidationError({
                "name": (
                    "You already have this category for the selected type. "
                    "If it is archived, restore it."
                )
            })

        return attrs