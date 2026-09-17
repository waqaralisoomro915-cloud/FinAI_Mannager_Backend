from decimal import Decimal

from django.db.models import Sum

from .models import Notification


ZERO = Decimal("0.00")


def create_notification(
    *,
    user,
    kind,
    target_id,
    event_key,
    title,
    message,
):
    notification, _ = Notification.objects.get_or_create(
        recipient=user,
        event_key=event_key,
        defaults={
            "kind": kind,
            "target_id": target_id,
            "title": title,
            "message": message,
        },
    )

    return notification


def notify_budget(budget):
    from apps.transactions.models import Transaction

    spent = (
        Transaction.objects.filter(
            user_id=budget.user_id,
            category_id=budget.category_id,
            transaction_type="EXPENSE",
            is_void=False,
            wallet__currency="PKR",
            transaction_date__range=(
                budget.start_date,
                budget.end_date,
            ),
        )
        .aggregate(total=Sum("amount"))["total"]
        or ZERO
    )

    if spent > budget.amount:
        threshold = "EXCEEDED"
        title = "Budget exceeded"
    elif spent == budget.amount:
        threshold = "100"
        title = "Budget limit reached"
    elif spent >= budget.amount * Decimal("0.80"):
        threshold = "80"
        title = "Budget is at least 80% used"
    else:
        return None

    return create_notification(
        user=budget.user,
        kind=Notification.Kind.BUDGET,
        target_id=budget.pk,
        event_key=f"budget:{budget.pk}:{threshold}",
        title=title,
        message=(
            f"{budget.category.name}: PKR {spent:.2f} spent "
            f"against a PKR {budget.amount:.2f} budget "
            f"for {budget.start_date} to {budget.end_date}."
        ),
    )


def notify_expense_budgets(entry):
    if entry.transaction_type != "EXPENSE" or entry.is_void:
        return

    from apps.budgets.models import Budget

    budgets = (
        Budget.objects.filter(
            user_id=entry.user_id,
            category_id=entry.category_id,
            start_date__lte=entry.transaction_date,
            end_date__gte=entry.transaction_date,
        )
        .select_related("user", "category")
    )

    for budget in budgets:
        notify_budget(budget)


def notify_savings_goal(goal):
    from apps.savings.services import goal_saved

    saved = goal_saved(goal)

    if saved < goal.target_amount:
        return None

    return create_notification(
        user=goal.user,
        kind=Notification.Kind.SAVINGS,
        target_id=goal.pk,
        event_key=f"savings:{goal.pk}:completed",
        title="Savings goal reached",
        message=(
            f"You have saved {goal.wallet.currency} {saved:.2f} "
            f"toward {goal.name}. "
            f"Your target was {goal.target_amount:.2f}."
        ),
    )


def notify_report(report):
    from apps.reports.models import GeneratedReport

    if report.status == GeneratedReport.Status.COMPLETED:
        title = "Your report is ready"
        message = (
            f"Your transaction report for {report.date_from} "
            f"to {report.date_to} is ready to download."
        )
    elif report.status == GeneratedReport.Status.FAILED:
        title = "Report generation failed"
        message = (
            f"Your report for {report.date_from} to "
            f"{report.date_to} could not be generated. "
            "Open the report to retry."
        )
    else:
        return None

    return create_notification(
        user=report.user,
        kind=Notification.Kind.REPORT,
        target_id=report.pk,
        event_key=f"report:{report.pk}:{report.status}",
        title=title,
        message=message,
    )