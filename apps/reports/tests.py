import csv
import io

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework.test import APIClient, APITestCase

from ..budgets.models import Budget
from ..categories.models import Category
from ..savings.models import SavingsContribution, SavingsGoal
from ..transactions.models import Transaction
from ..wallets.models import Wallet


User = get_user_model()


class ReportAPITests(APITestCase):
    client: APIClient

    def setUp(self):
        self.user = User.objects.create_user(
            email="waqar@example.com",
            password="Testing!Reports2026",
        )
        self.other_user = User.objects.create_user(
            email="other@example.com",
            password="Testing!Reports2026",
        )

        self.wallet = Wallet.objects.create(
            user=self.user,
            name="Cash",
            opening_balance=Decimal("500.00"),
        )
        self.destination = Wallet.objects.create(
            user=self.user,
            name="Bank",
        )

        self.income_category = Category.objects.create(
            user=self.user,
            name="Salary",
            category_type="INCOME",
        )
        self.expense_category = Category.objects.create(
            user=self.user,
            name="Food",
            category_type="EXPENSE",
        )

        self.add_transaction(
            "INCOME",
            "200.00",
            category=self.income_category,
        )
        self.expense = self.add_transaction(
            "EXPENSE",
            "125.00",
            category=self.expense_category,
            description="=1+1",
        )
        self.add_transaction(
            "TRANSFER",
            "50.00",
            destination_wallet=self.destination,
        )
        self.add_transaction(
            "EXPENSE",
            "999.00",
            category=self.expense_category,
            is_void=True,
        )

        # Outside the January reporting period.
        self.add_transaction(
            "INCOME",
            "25.00",
            category=self.income_category,
            transaction_date=date(2025, 12, 31),
        )

        self.goal = SavingsGoal.objects.create(
            user=self.user,
            wallet=self.wallet,
            name="Laptop",
            target_amount=Decimal("1000.00"),
        )
        SavingsContribution.objects.create(
            goal=self.goal,
            entry_type="CONTRIBUTION",
            amount=Decimal("100.00"),
        )

        Budget.objects.create(
            user=self.user,
            category=self.expense_category,
            amount=Decimal("250.00"),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
        )

        self.client.force_authenticate(user=self.user)

        self.period = {
            "date_from": "2026-01-01",
            "date_to": "2026-01-31",
        }

    def add_transaction(self, kind, amount, **extra):
        data = {
            "user": self.user,
            "wallet": self.wallet,
            "transaction_type": kind,
            "amount": Decimal(amount),
            "transaction_date": date(2026, 1, 10),
        }
        data.update(extra)
        return Transaction.objects.create(**data)

    def test_authentication_required_for_all_reports(self):
        self.client.force_authenticate(user=None)

        for name in (
            "dashboard",
            "categories",
            "monthly",
            "budgets",
            "savings",
            "export",
        ):
            with self.subTest(report=name):
                response = self.client.get(
                    reverse(f"reports:{name}"),
                    self.period,
                )
                self.assertEqual(response.status_code, 401)

    def test_dashboard_separates_period_and_current_balances(self):
        response = self.client.get(
            reverse("reports:dashboard"),
            self.period,
        )

        self.assertEqual(response.status_code, 200, response.data)

        summary = response.data["period_summary"]
        self.assertEqual(summary["income"], "200.00")
        self.assertEqual(summary["expenses"], "125.00")
        self.assertEqual(summary["net_income"], "75.00")
        self.assertEqual(summary["transaction_count"], 3)

        balances = response.data["current_balances"]

        # 500 opening + 200 income + 25 older income - 125 expense.
        # The internal transfer does not change combined wealth.
        self.assertEqual(balances["current_balance"], "600.00")
        self.assertEqual(balances["reserved_balance"], "100.00")
        self.assertEqual(balances["available_balance"], "500.00")

    def test_category_report_excludes_void_transactions(self):
        response = self.client.get(
            reverse("reports:categories"),
            self.period,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"], [
            {
                "category": self.expense_category.pk,
                "category_name": "Food",
                "spent": "125.00",
            },
        ])

    def test_monthly_report_includes_empty_months(self):
        response = self.client.get(
            reverse("reports:monthly"),
            {
                "date_from": "2026-01-01",
                "date_to": "2026-02-28",
            },
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.data["results"], [
            {
                "month": "2026-01",
                "income": "200.00",
                "expenses": "125.00",
                "net_income": "75.00",
            },
            {
                "month": "2026-02",
                "income": "0.00",
                "expenses": "0.00",
                "net_income": "0.00",
            },
        ])

    def test_invalid_period_rejected(self):
        invalid_periods = [
            {
                "date_from": "2026-02-01",
                "date_to": "2026-01-01",
            },
            {
                "date_from": "invalid",
                "date_to": "2026-01-31",
            },
            {
                "date_from": "2024-01-01",
                "date_to": "2026-01-01",
            },
        ]

        for period in invalid_periods:
            with self.subTest(period=period):
                response = self.client.get(
                    reverse("reports:dashboard"),
                    period,
                )
                self.assertEqual(response.status_code, 400)

    def test_progress_reports_use_existing_calculations(self):
        budgets = self.client.get(
            reverse("reports:budgets"),
            self.period,
        )
        self.assertEqual(budgets.status_code, 200)
        self.assertEqual(budgets.data["count"], 1)
        self.assertEqual(
            budgets.data["results"][0]["spent"],
            "125.00",
        )
        self.assertEqual(
            budgets.data["results"][0]["usage_percentage"],
            "50.00",
        )

        savings = self.client.get(reverse("reports:savings"))
        self.assertEqual(savings.status_code, 200)
        self.assertEqual(savings.data["count"], 1)
        self.assertEqual(
            savings.data["results"][0]["saved_amount"],
            "100.00",
        )

    def test_other_user_sees_no_private_data(self):
        self.client.force_authenticate(user=self.other_user)

        dashboard = self.client.get(
            reverse("reports:dashboard"),
            self.period,
        )
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(
            dashboard.data["period_summary"]["income"],
            "0.00",
        )
        self.assertEqual(
            dashboard.data["current_balances"]["current_balance"],
            "0.00",
        )

        for name in ("categories", "budgets", "savings"):
            response = self.client.get(
                reverse(f"reports:{name}"),
                self.period,
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["results"], [])

        export = self.client.get(
            reverse("reports:export"),
            self.period,
        )
        self.assertEqual(export.status_code, 200)

        rows = list(csv.reader(io.StringIO(
            export.content.decode("utf-8-sig")
        )))
        self.assertEqual(len(rows), 1)  # Header only.

    def test_csv_export_preserves_history_and_neutralizes_formula(self):
        response = self.client.get(
            reverse("reports:export"),
            self.period,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])

        rows = list(csv.DictReader(io.StringIO(
            response.content.decode("utf-8-sig")
        )))

        self.assertEqual(len(rows), 3)
        self.assertEqual(
            {row["Type"] for row in rows},
            {"INCOME", "EXPENSE", "TRANSFER"},
        )

        expense_row = next(
            row for row in rows
            if row["ID"] == str(self.expense.pk)
        )

        self.assertEqual(expense_row["Description"], "'=1+1")