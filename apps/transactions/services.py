from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction as db_transaction
from django.db.models import Q, Sum
from django.utils import timezone

from rest_framework.exceptions import NotFound, ValidationError
from ..savings.services import wallet_reserved
from ..categories.models import Category
from ..wallets.models import Wallet

from .models import Transaction


ZERO = Decimal("0.00")


def wallet_balance(wallet, exclude_transaction_id=None):
    entries = Transaction.objects.filter(is_void=False)

    if exclude_transaction_id is not None:
        entries = entries.exclude(pk=exclude_transaction_id)

    totals = entries.aggregate(
        income=Sum(
            "amount",
            filter=Q(
                wallet_id=wallet.pk,
                transaction_type="INCOME",
            ),
        ),
        outgoing=Sum(
            "amount",
            filter=Q(
                wallet_id=wallet.pk,
                transaction_type__in=["EXPENSE", "TRANSFER"],
            ),
        ),
        incoming=Sum(
            "amount",
            filter=Q(
                destination_wallet_id=wallet.pk,
                transaction_type="TRANSFER",
            ),
        ),
    )

    return (
        wallet.opening_balance
        + (totals["income"] or ZERO)
        + (totals["incoming"] or ZERO)
        - (totals["outgoing"] or ZERO)
    )


def lock_owner(user):
    # Serialize transaction writes for this owner on databases
    # that support SELECT FOR UPDATE.
    get_user_model().objects.select_for_update().get(pk=user.pk)


def get_locked_wallets(user, wallet_ids):
    wallets = {
        wallet.pk: wallet
        for wallet in (
            Wallet.objects.select_for_update()
            .filter(user=user, pk__in=wallet_ids)
            .order_by("pk")
        )
    }

    if len(wallets) != len(set(wallet_ids)):
        raise ValidationError({
            "wallet": "One or more wallets are unavailable."
        })

    return wallets


@db_transaction.atomic
def create_transaction(user, data):
    lock_owner(user)

    data = dict(data)

    source_id = data.pop("wallet")
    destination_id = data.pop("destination_wallet", None)
    category_id = data.pop("category", None)

    transaction_type = data["transaction_type"]
    amount = data["amount"]



    if amount <= ZERO:
        raise ValidationError({"amount": "Amount must be positive."})

    if data["transaction_date"] > timezone.localdate():
        raise ValidationError({
            "transaction_date": "Future transactions are not supported."
        })

    wallet_ids = [source_id]

    if destination_id is not None:
        wallet_ids.append(destination_id)

    wallets = get_locked_wallets(user, wallet_ids)
    source = wallets[source_id]
    destination = (
        wallets[destination_id]
        if destination_id is not None
        else None
    )

    if any(not wallet.is_active for wallet in wallets.values()):
        raise ValidationError({
            "wallet": "Archived wallets cannot receive new transactions."
        })

    category = None

    if transaction_type == Transaction.TransactionType.TRANSFER:
        if destination is None:
            raise ValidationError({
                "destination_wallet": "Select a destination wallet."
            })

        if source.pk == destination.pk:
            raise ValidationError({
                "destination_wallet": "Select a different wallet."
            })

        if source.currency != destination.currency:
            raise ValidationError({
                "destination_wallet": "Wallet currencies must match."
            })

        if category_id is not None:
            raise ValidationError({
                "category": "Transfers must not have a category."
            })

    else:
        if destination is not None:
            raise ValidationError({
                "destination_wallet": "Only transfers use this field."
            })

        if category_id is None:
            raise ValidationError({
                "category": "Select a category."
            })

        category = (
            Category.objects.select_for_update()
            .filter(
                pk=category_id,
                user=user,
                is_active=True,
            )
            .first()
        )

        if category is None:
            raise ValidationError({
                "category": "Category is unavailable or archived."
            })

        if category.category_type != transaction_type:
            raise ValidationError({
                "category": "Category type must match the transaction."
            })

    if transaction_type in ("EXPENSE", "TRANSFER"):
        available = wallet_balance(source) - wallet_reserved(source)

        if amount > available:
            raise ValidationError({
                "amount": (
                    "Insufficient available balance. "
                    "Some money may be reserved for savings."
                )
            })

    return Transaction.objects.create(
        user=user,
        wallet=source,
        destination_wallet=destination,
        category=category,
        **data,
    )


@db_transaction.atomic
def void_transaction(user, transaction_id, reason):
    lock_owner(user)

    entry = (
        Transaction.objects.select_for_update()
        .filter(pk=transaction_id, user=user)
        .first()
    )

    if entry is None:
        raise NotFound("Transaction not found.")

    if entry.is_void:
        raise ValidationError({
            "detail": "This transaction is already void."
        })

    wallet_ids = [entry.wallet_id]

    if entry.destination_wallet_id is not None:
        wallet_ids.append(entry.destination_wallet_id)

    wallets = get_locked_wallets(user, wallet_ids)

    for wallet in wallets.values():
        resulting_balance = wallet_balance(
            wallet,
            exclude_transaction_id=entry.pk,
        )

        if resulting_balance < wallet_reserved(wallet):
            raise ValidationError({
                "detail": (
                    "Cannot void this transaction because an affected "
                    "wallet would lack enough money to cover its savings."
                )
            })

    entry.is_void = True
    entry.void_reason = reason
    entry.voided_at = timezone.now()

    entry.save(update_fields=[
        "is_void",
        "void_reason",
        "voided_at",
    ])

    return entry