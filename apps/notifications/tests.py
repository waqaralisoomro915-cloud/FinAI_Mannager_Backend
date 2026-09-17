from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from rest_framework.test import APIClient, APITestCase

from ..budgets.models import Budget
from ..categories.models import Category
from ..reports.models import GeneratedReport
from ..savings.models import SavingsContribution, SavingsGoal
from ..wallets.models import Wallet

from .models import Notification
from .services import (
    create_notification,
    notify_report,
    notify_savings_goal,
)


User = get_user_model()


class NotificationAPITests(APITestCase):
    client: APIClient

    def setUp(self):
        self.user = User.objects.create_user(
            email="waqar@example.com",
            password="Testing!Notifications2026",
        )

        self.other_user = User.objects.create_user(
            email="other@example.com",
            password="Testing!Notifications2026",
        )

        self.client.force_authenticate(user=self.user)

        self.notification = create_notification(
            user=self.user,
            kind="REPORT",
            target_id=1,
            event_key="test:own",
            title="Your report is ready",
            message="Open your saved report.",
        )

        self.foreign_notification = create_notification(
            user=self.other_user,
            kind="REPORT",
            target_id=2,
            event_key="test:other",
            title="Private report",
            message="Another user's report.",
        )

        self.list_url = reverse("notification-list")

    def test_authentication_required(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 401)

    def test_list_only_own_notifications(self):
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["id"],
            self.notification.pk,
        )

    def test_cannot_access_another_users_notification(self):
        detail_url = reverse(
            "notification-detail",
            args=[self.foreign_notification.pk],
        )

        mark_read_url = reverse(
            "notification-mark-read",
            args=[self.foreign_notification.pk],
        )

        self.assertEqual(
            self.client.get(detail_url).status_code,
            404,
        )

        self.assertEqual(
            self.client.post(mark_read_url).status_code,
            404,
        )

        self.foreign_notification.refresh_from_db()
        self.assertIsNone(self.foreign_notification.read_at)

    def test_read_actions_and_unread_count(self):
        count_url = reverse("notification-unread-count")

        response = self.client.get(count_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["unread_count"], 1)

        mark_read_url = reverse(
            "notification-mark-read",
            args=[self.notification.pk],
        )

        response = self.client.post(mark_read_url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_read"])

        self.notification.refresh_from_db()
        original_read_at = self.notification.read_at
        self.assertIsNotNone(original_read_at)

        # Marking it again must preserve its first read timestamp.
        self.client.post(mark_read_url)
        self.notification.refresh_from_db()
        self.assertEqual(
            self.notification.read_at,
            original_read_at,
        )

        response = self.client.get(count_url)
        self.assertEqual(response.data["unread_count"], 0)

        unread = self.client.get(
            self.list_url,
            {"is_read": "false"},
        )
        self.assertEqual(unread.data["count"], 0)

        create_notification(
            user=self.user,
            kind="REPORT",
            target_id=3,
            event_key="test:second",
            title="Another report",
            message="Ready to download.",
        )

        response = self.client.post(
            reverse("notification-mark-all-read")
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["marked_read"], 1)

        self.foreign_notification.refresh_from_db()
        self.assertIsNone(self.foreign_notification.read_at)

    def test_users_cannot_create_notifications(self):
        response = self.client.post(
            self.list_url,
            {
                "title": "Fake notification",
                "message": "Not allowed",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 405)

    def test_expense_creates_budget_alert_once(self):
        wallet = Wallet.objects.create(
            user=self.user,
            name="Cash",
            opening_balance=Decimal("1000.00"),
        )

        category = Category.objects.create(
            user=self.user,
            name="Food",
            category_type="EXPENSE",
        )

        today = timezone.localdate()

        budget = Budget.objects.create(
            user=self.user,
            category=category,
            amount=Decimal("100.00"),
            start_date=today,
            end_date=today,
        )

        # Spending reaches 80%, then 85%.
        # Both events belong to the same notification threshold.
        for amount in ("80.00", "5.00"):
            response = self.client.post(
                reverse("transaction-list"),
                {
                    "wallet": wallet.pk,
                    "category": category.pk,
                    "transaction_type": "EXPENSE",
                    "amount": amount,
                },
                format="json",
            )

            self.assertEqual(
                response.status_code,
                201,
                response.data,
            )

        alerts = Notification.objects.filter(
            recipient=self.user,
            event_key=f"budget:{budget.pk}:80",
        )

        self.assertEqual(alerts.count(), 1)
        self.assertEqual(alerts.get().kind, "BUDGET")

    def test_savings_completion_notified_once(self):
        wallet = Wallet.objects.create(
            user=self.user,
            name="Savings Wallet",
            opening_balance=Decimal("1000.00"),
        )

        goal = SavingsGoal.objects.create(
            user=self.user,
            wallet=wallet,
            name="Books",
            target_amount=Decimal("100.00"),
        )

        SavingsContribution.objects.create(
            goal=goal,
            entry_type="CONTRIBUTION",
            amount=Decimal("100.00"),
        )

        notify_savings_goal(goal)
        notify_savings_goal(goal)

        self.assertEqual(
            Notification.objects.filter(
                recipient=self.user,
                event_key=f"savings:{goal.pk}:completed",
            ).count(),
            1,
        )

    def test_report_failure_and_success_have_separate_alerts(self):
        report = GeneratedReport.objects.create(
            user=self.user,
            date_from=date(2026, 8, 1),
            date_to=date(2026, 8, 31),
            status="FAILED",
        )

        notify_report(report)
        notify_report(report)

        report.status = "COMPLETED"
        report.save(update_fields=["status"])

        notify_report(report)
        notify_report(report)

        alerts = Notification.objects.filter(
            recipient=self.user,
            event_key__startswith=f"report:{report.pk}:",
        )

        self.assertEqual(alerts.count(), 2)
        self.assertSetEqual(
            set(alerts.values_list("event_key", flat=True)),
            {
                f"report:{report.pk}:FAILED",
                f"report:{report.pk}:COMPLETED",
            },
        )