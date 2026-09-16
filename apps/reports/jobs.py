import csv
import io
import logging

from datetime import datetime, time, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from .models import GeneratedReport, ReportSchedule
from .services import money, period_transactions, safe_csv_text


logger = logging.getLogger(__name__)


def next_occurrence(after, frequency, timezone_name):
    zone = ZoneInfo(timezone_name)
    local = after.astimezone(zone)

    if frequency == ReportSchedule.Frequency.WEEKLY:
        day = local.date() - timedelta(days=local.weekday())
    else:
        day = local.date().replace(day=1)

    candidate = datetime.combine(day, time(9, 0), tzinfo=zone)

    if candidate <= local:
        if frequency == ReportSchedule.Frequency.WEEKLY:
            day += timedelta(days=7)
        else:
            day = (day.replace(day=28) + timedelta(days=4)).replace(day=1)

        candidate = datetime.combine(day, time(9, 0), tzinfo=zone)

    return candidate


def previous_period(scheduled_for, frequency, timezone_name):
    local_day = scheduled_for.astimezone(
        ZoneInfo(timezone_name)
    ).date()

    if frequency == ReportSchedule.Frequency.WEEKLY:
        this_monday = local_day - timedelta(days=local_day.weekday())
        end = this_monday - timedelta(days=1)
        start = end - timedelta(days=6)
    else:
        end = local_day.replace(day=1) - timedelta(days=1)
        start = end.replace(day=1)

    return start, end


@transaction.atomic
def enqueue_due_schedule(schedule_id, now=None):
    now = now or timezone.now()

    schedule = (
        ReportSchedule.objects.select_for_update()
        .filter(
            pk=schedule_id,
            is_active=True,
            user__is_active=True,
        )
        .first()
    )

    if schedule is None or schedule.next_run > now:
        return False

    occurrence = schedule.next_run

    start, end = previous_period(
        occurrence,
        schedule.frequency,
        schedule.timezone_name,
    )

    GeneratedReport.objects.get_or_create(
        schedule=schedule,
        scheduled_for=occurrence,
        defaults={
            "user": schedule.user,
            "date_from": start,
            "date_to": end,
        },
    )

    schedule.last_scheduled_for = occurrence
    schedule.next_run = next_occurrence(
        occurrence,
        schedule.frequency,
        schedule.timezone_name,
    )

    schedule.save(update_fields=[
        "last_scheduled_for",
        "next_run",
    ])

    return True


def build_csv(report):
    entries = list(
        period_transactions(
            report.user,
            report.date_from,
            report.date_to,
        )
        .select_related("wallet", "destination_wallet", "category")
        .order_by("transaction_date", "id")[:10001]
    )

    if len(entries) > 10000:
        raise ValueError("Report exceeds the 10,000-row limit.")

    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)

    writer.writerow([
        "ID",
        "Date",
        "Type",
        "Wallet",
        "Destination Wallet",
        "Category",
        "Amount",
        "Currency",
        "Description",
    ])

    for entry in entries:
        writer.writerow([
            entry.pk,
            entry.transaction_date.isoformat(),
            entry.transaction_type,
            safe_csv_text(entry.wallet.name),
            safe_csv_text(
                entry.destination_wallet.name
                if entry.destination_wallet else ""
            ),
            safe_csv_text(
                entry.category.name if entry.category else ""
            ),
            money(entry.amount),
            entry.wallet.currency,
            safe_csv_text(entry.description),
        ])

    return buffer.getvalue().encode("utf-8-sig")


def process_report(report_id):
    saved_name = None
    storage = None

    try:
        # Keep the claim and completion in one database transaction.
        # If the process stops, database changes roll back.
        with transaction.atomic():
            report = (
                GeneratedReport.objects.select_for_update()
                .select_related("user")
                .get(pk=report_id)
            )

            if report.status != GeneratedReport.Status.PENDING:
                return False

            if not report.user.is_active:
                report.status = GeneratedReport.Status.FAILED
                report.error_message = "Account is inactive."
                report.save(update_fields=["status", "error_message"])
                return False

            content = build_csv(report)
            filename = f"{report.pk}-{uuid4().hex}.csv"

            report.file.save(
                filename,
                ContentFile(content),
                save=False,
            )

            saved_name = report.file.name
            storage = report.file.storage

            report.status = GeneratedReport.Status.COMPLETED
            report.completed_at = timezone.now()
            report.error_message = ""

            report.save(update_fields=[
                "file",
                "status",
                "completed_at",
                "error_message",
            ])

        return True

    except Exception:
        logger.exception("Report generation failed: %s", report_id)

        if saved_name and storage:
            try:
                storage.delete(saved_name)
            except Exception:
                logger.exception("Could not clean up report file.")

        GeneratedReport.objects.filter(
            pk=report_id,
            status=GeneratedReport.Status.PENDING,
        ).update(
            status=GeneratedReport.Status.FAILED,
            error_message=(
                "Generation failed. Try a shorter period "
                "or check the server log."
            ),
        )

        return False