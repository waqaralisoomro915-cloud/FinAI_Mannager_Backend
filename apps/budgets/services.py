from django.contrib.auth import get_user_model
from django.db import transaction

from rest_framework.exceptions import NotFound, ValidationError

from ..categories.models import Category

from .models import Budget


@transaction.atomic
def save_budget(user, data, instance=None):
    # Keeps overlapping-budget checks consistent during
    # concurrent writes on PostgreSQL.
    get_user_model().objects.select_for_update().get(pk=user.pk)

    if instance is not None:
        instance = (
            Budget.objects.select_for_update()
            .filter(pk=instance.pk, user=user)
            .first()
        )

        if instance is None:
            raise NotFound("Budget not found.")

    category = data.get(
        "category",
        instance.category if instance else None,
    )
    amount = data.get(
        "amount",
        instance.amount if instance else None,
    )
    start_date = data.get(
        "start_date",
        instance.start_date if instance else None,
    )
    end_date = data.get(
        "end_date",
        instance.end_date if instance else None,
    )

    if category is None:
        raise ValidationError({"category": "Select a category."})

    # Read the category again under a lock.
    category = (
        Category.objects.select_for_update()
        .filter(
            pk=category.pk,
            user=user,
            category_type=Category.CategoryType.EXPENSE,
        )
        .first()
    )

    if category is None:
        raise ValidationError({
            "category": "Select one of your expense categories."
        })

    category_changed = (
        instance is None or category.pk != instance.category_id
    )

    if category_changed and not category.is_active:
        raise ValidationError({
            "category": "Cannot select an archived category."
        })

    if amount is None or amount <= 0:
        raise ValidationError({
            "amount": "Budget amount must be greater than zero."
        })

    if start_date is None or end_date is None:
        raise ValidationError({
            "detail": "Both start_date and end_date are required."
        })

    if start_date > end_date:
        raise ValidationError({
            "end_date": "End date must be on or after start date."
        })

    overlapping = Budget.objects.filter(
        user=user,
        category=category,
        start_date__lte=end_date,
        end_date__gte=start_date,
    )

    if instance is not None:
        overlapping = overlapping.exclude(pk=instance.pk)

    if overlapping.exists():
        raise ValidationError({
            "detail": (
                "A budget already overlaps these dates "
                "for this category."
            )
        })

    if instance is None:
        return Budget.objects.create(
            user=user,
            category=category,
            amount=amount,
            start_date=start_date,
            end_date=end_date,
        )

    instance.category = category
    instance.amount = amount
    instance.start_date = start_date
    instance.end_date = end_date

    instance.save(update_fields=[
        "category",
        "amount",
        "start_date",
        "end_date",
        "updated_at",
    ])

    return instance