from datetime import date
from decimal import Decimal

from django.db.models import Q, Sum
from django.db.models.functions import TruncMonth

from ..savings.models import SavingsContribution
from ..savings.services import entry_total
from ..transactions.models import Transaction
from ..wallets.models import Wallet


ZERO = Decimal("0.00")


def money(value):
    return format(value or ZERO, ".2f")


def user_transactions(user):
    return Transaction.objects.filter(
        user=user,
        is_void=False,
        wallet__currency="PKR",
    )


def period_transactions(user, start, end):
    return user_transactions(user).filter(
        transaction_date__range=(start, end),
    )


def income_expense_totals(queryset):
    return queryset.aggregate(
        income=Sum(
            "amount",
            filter=Q(transaction_type="INCOME"),
        ),
        expenses=Sum(
            "amount",
            filter=Q(transaction_type="EXPENSE"),
        ),
    )


def period_summary(user, start, end):
    queryset = period_transactions(user, start, end)
    totals = income_expense_totals(queryset)

    income = totals["income"] or ZERO
    expenses = totals["expenses"] or ZERO

    return {
        "income": money(income),
        "expenses": money(expenses),
        "net_income": money(income - expenses),
        "transaction_count": queryset.count(),
    }


def current_balances(user):
    # Include archived wallets: archiving does not remove their money.
    wallets = Wallet.objects.filter(user=user, currency="PKR")

    opening = (
        wallets.aggregate(total=Sum("opening_balance"))["total"]
        or ZERO
    )

    totals = income_expense_totals(user_transactions(user))

    current = (
        opening
        + (totals["income"] or ZERO)
        - (totals["expenses"] or ZERO)
    )

    # Internal transfers cancel out across all the user's wallets.
    reserved = entry_total(
        SavingsContribution.objects.filter(
            goal__user=user,
            goal__wallet__currency="PKR",
        )
    )

    return {
        "current_balance": money(current),
        "reserved_balance": money(reserved),
        "available_balance": money(current - reserved),
        "wallet_count": wallets.count(),
        "active_wallet_count": wallets.filter(is_active=True).count(),
    }


def category_spending(user, start, end):
    rows = (
        period_transactions(user, start, end)
        .filter(transaction_type="EXPENSE")
        .order_by()
        .values("category_id", "category__name")
        .annotate(spent=Sum("amount"))
        .order_by("-spent", "category_id")
    )

    return [
        {
            "category": row["category_id"],
            "category_name": row["category__name"],
            "spent": money(row["spent"]),
        }
        for row in rows
    ]


def monthly_trends(user, start, end):
    rows = (
        period_transactions(user, start, end)
        .filter(transaction_type__in=["INCOME", "EXPENSE"])
        .order_by()
        .annotate(month=TruncMonth("transaction_date"))
        .values("month")
        .annotate(
            income=Sum(
                "amount",
                filter=Q(transaction_type="INCOME"),
            ),
            expenses=Sum(
                "amount",
                filter=Q(transaction_type="EXPENSE"),
            ),
        )
        .order_by("month")
    )

    by_month = {
        (row["month"].year, row["month"].month): row
        for row in rows
    }

    results = []
    month = start.replace(day=1)
    final_month = end.replace(day=1)

    while month <= final_month:
        row = by_month.get((month.year, month.month), {})

        income = row.get("income") or ZERO
        expenses = row.get("expenses") or ZERO

        results.append({
            "month": month.strftime("%Y-%m"),
            "income": money(income),
            "expenses": money(expenses),
            "net_income": money(income - expenses),
        })

        if month.month == 12:
            month = date(month.year + 1, 1, 1)
        else:
            month = date(month.year, month.month + 1, 1)

    return results


def safe_csv_text(value):
    text = str(value or "")

    # Prevent user-entered text from being interpreted as a formula.
    if text.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + text

    if text.startswith(("\t", "\r", "\n")):
        return "'" + text

    return text