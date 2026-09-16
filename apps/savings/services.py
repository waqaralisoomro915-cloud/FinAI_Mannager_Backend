from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q, Sum

from rest_framework.exceptions import NotFound, ValidationError

from apps.wallets.models import Wallet

from .models import SavingsContribution, SavingsGoal


ZERO = Decimal("0.00")


def entry_total(queryset):
    totals = queryset.aggregate(
        contributions=Sum(
            "amount",
            filter=Q(entry_type="CONTRIBUTION"),
        ),
        withdrawals=Sum(
            "amount",
            filter=Q(entry_type="WITHDRAWAL"),
        ),
    )

    return (
        (totals["contributions"] or ZERO)
        - (totals["withdrawals"] or ZERO)
    )


def goal_saved(goal):
    return entry_total(
        SavingsContribution.objects.filter(goal_id=goal.pk)
    )


def wallet_reserved(wallet):
    # Include every goal. Archiving must never hide reserved money.
    return entry_total(
        SavingsContribution.objects.filter(goal__wallet_id=wallet.pk)
    )


def lock_owner(user):
    get_user_model().objects.select_for_update().get(pk=user.pk)


def locked_goal(user, goal_id):
    goal = (
        SavingsGoal.objects.select_for_update()
        .filter(pk=goal_id, user=user)
        .first()
    )

    if goal is None:
        raise NotFound("Savings goal not found.")

    return goal


@transaction.atomic
def save_goal(user, data, instance=None):
    lock_owner(user)
    data = dict(data)

    if instance is None:
        wallet_id = data.pop("wallet")

        wallet = (
            Wallet.objects.select_for_update()
            .filter(pk=wallet_id, user=user, is_active=True)
            .first()
        )

        if wallet is None:
            raise ValidationError({
                "wallet": "Select one of your active wallets."
            })

        return SavingsGoal.objects.create(
            user=user,
            wallet=wallet,
            **data,
        )

    goal = locked_goal(user, instance.pk)

    if "wallet" in data:
        if data["wallet"] != goal.wallet_id:
            raise ValidationError({
                "wallet": "A goal's wallet cannot be changed."
            })

        data.pop("wallet")

    for field in ("name", "target_amount", "deadline"):
        if field in data:
            setattr(goal, field, data[field])

    goal.save(update_fields=[
        "name",
        "target_amount",
        "deadline",
        "updated_at",
    ])

    return goal


@transaction.atomic
def record_savings_entry(user, goal_id, data):
    # Same owner lock used by transaction services.
    lock_owner(user)
    goal = locked_goal(user, goal_id)

    wallet = Wallet.objects.select_for_update().get(
        pk=goal.wallet_id,
        user=user,
    )

    entry_type = data["entry_type"]
    amount = data["amount"]

    if amount <= ZERO:
        raise ValidationError({
            "amount": "Amount must be greater than zero."
        })

    if entry_type == SavingsContribution.EntryType.CONTRIBUTION:
        if not goal.is_active:
            raise ValidationError({
                "detail": "Restore this goal before contributing."
            })

        if not wallet.is_active:
            raise ValidationError({
                "detail": "Cannot reserve money in an archived wallet."
            })

        # Local import avoids a circular import between services.
        from apps.transactions.services import wallet_balance

        available = wallet_balance(wallet) - wallet_reserved(wallet)

        if amount > available:
            raise ValidationError({
                "amount": "Insufficient unallocated wallet balance."
            })

    elif entry_type == SavingsContribution.EntryType.WITHDRAWAL:
        if amount > goal_saved(goal):
            raise ValidationError({
                "amount": "Withdrawal exceeds this goal's savings."
            })

        # Releasing funds is allowed even if the wallet is archived.

    else:
        raise ValidationError({
            "entry_type": "Invalid savings entry type."
        })

    return SavingsContribution.objects.create(
        goal=goal,
        entry_type=entry_type,
        amount=amount,
        note=data.get("note", ""),
    )


@transaction.atomic
def set_goal_active(user, goal_id, active):
    lock_owner(user)
    goal = locked_goal(user, goal_id)

    if not active and goal_saved(goal) != ZERO:
        raise ValidationError({
            "detail": "Withdraw reserved savings before archiving."
        })

    goal.is_active = active
    goal.save(update_fields=["is_active", "updated_at"])

    return goal