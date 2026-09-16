from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework.test import APIClient, APITestCase

from apps.categories.models import Category
from apps.transactions.services import wallet_balance
from apps.wallets.models import Wallet

from .models import SavingsGoal
from .services import goal_saved, wallet_reserved


User = get_user_model()


class SavingsAPITests(APITestCase):
    client: APIClient

    def setUp(self):
        self.user = User.objects.create_user(
            email="waqar@example.com",
            password="Testing!Savings2026",
        )

        self.other_user = User.objects.create_user(
            email="other@example.com",
            password="Testing!Savings2026",
        )

        self.wallet = Wallet.objects.create(
            user=self.user,
            name="Cash",
            opening_balance=Decimal("1000.00"),
        )

        self.foreign_wallet = Wallet.objects.create(
            user=self.other_user,
            name="Private Wallet",
        )

        self.goal = SavingsGoal.objects.create(
            user=self.user,
            wallet=self.wallet,
            name="Laptop",
            target_amount=Decimal("5000.00"),
        )

        self.expense_category = Category.objects.create(
            user=self.user,
            name="Food",
            category_type="EXPENSE",
        )

        self.income_category = Category.objects.create(
            user=self.user,
            name="Salary",
            category_type="INCOME",
        )

        self.client.force_authenticate(user=self.user)

        self.list_url = reverse("savings-goal-list")

        self.detail_url = reverse(
            "savings-goal-detail",
            args=[self.goal.pk],
        )

        self.entries_url = reverse(
            "savings-goal-entries",
            args=[self.goal.pk],
        )

    def entry(self, amount, kind="CONTRIBUTION"):
        return self.client.post(
            self.entries_url,
            {
                "entry_type": kind,
                "amount": amount,
                "note": "Test entry",
            },
            format="json",
        )

    def test_creation_returns_wallet_id(self):
        response = self.client.post(
            self.list_url,
            {
                "wallet": self.wallet.pk,
                "name": "Emergency Fund",
                "target_amount": "2000.00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["wallet"], self.wallet.pk)
        self.assertEqual(response.data["saved_amount"], "0.00")

        goal = SavingsGoal.objects.get(pk=response.data["id"])
        self.assertEqual(goal.user_id, self.user.pk)

    def test_foreign_wallet_rejected(self):
        response = self.client.post(
            self.list_url,
            {
                "wallet": self.foreign_wallet.pk,
                "name": "Invalid Goal",
                "target_amount": "100.00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400, response.data)

    def test_contribution_reserves_without_changing_balance(self):
        response = self.entry("300.00")

        self.assertEqual(response.status_code, 201, response.data)

        self.assertEqual(
            goal_saved(self.goal),
            Decimal("300.00"),
        )
        self.assertEqual(
            wallet_reserved(self.wallet),
            Decimal("300.00"),
        )
        self.assertEqual(
            wallet_balance(self.wallet),
            Decimal("1000.00"),
        )

    def test_cannot_reserve_more_than_available(self):
        first = self.entry("700.00")
        self.assertEqual(first.status_code, 201, first.data)

        second = self.entry("301.00")
        self.assertEqual(second.status_code, 400, second.data)

        self.assertEqual(
            goal_saved(self.goal),
            Decimal("700.00"),
        )
        self.assertEqual(self.goal.contributions.count(), 1)

    def test_withdrawal_releases_reservation(self):
        contribution = self.entry("300.00")
        self.assertEqual(
            contribution.status_code, 201, contribution.data
        )

        withdrawal = self.entry("100.00", "WITHDRAWAL")
        self.assertEqual(
            withdrawal.status_code, 201, withdrawal.data
        )

        self.assertEqual(
            goal_saved(self.goal),
            Decimal("200.00"),
        )

        excessive = self.entry("201.00", "WITHDRAWAL")
        self.assertEqual(excessive.status_code, 400, excessive.data)

        self.assertEqual(
            goal_saved(self.goal),
            Decimal("200.00"),
        )

    def test_expense_cannot_spend_reserved_money(self):
        contribution = self.entry("800.00")
        self.assertEqual(
            contribution.status_code, 201, contribution.data
        )

        response = self.client.post(
            reverse("transaction-list"),
            {
                "wallet": self.wallet.pk,
                "category": self.expense_category.pk,
                "transaction_type": "EXPENSE",
                "amount": "201.00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(
            wallet_balance(self.wallet),
            Decimal("1000.00"),
        )

    def test_void_cannot_remove_money_covering_savings(self):
        income = self.client.post(
            reverse("transaction-list"),
            {
                "wallet": self.wallet.pk,
                "category": self.income_category.pk,
                "transaction_type": "INCOME",
                "amount": "500.00",
            },
            format="json",
        )

        self.assertEqual(income.status_code, 201, income.data)

        contribution = self.entry("1400.00")
        self.assertEqual(
            contribution.status_code, 201, contribution.data
        )

        response = self.client.post(
            reverse(
                "transaction-void",
                args=[income.data["id"]],
            ),
            {"reason": "Incorrect income"},
            format="json",
        )

        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(
            wallet_balance(self.wallet),
            Decimal("1500.00"),
        )

    def test_archive_requires_zero_reserved(self):
        contribution = self.entry("100.00")
        self.assertEqual(
            contribution.status_code, 201, contribution.data
        )

        archive_url = reverse(
            "savings-goal-archive",
            args=[self.goal.pk],
        )

        response = self.client.post(archive_url)
        self.assertEqual(response.status_code, 400, response.data)

        withdrawal = self.entry("100.00", "WITHDRAWAL")
        self.assertEqual(
            withdrawal.status_code, 201, withdrawal.data
        )

        response = self.client.post(archive_url)
        self.assertEqual(response.status_code, 200, response.data)

        self.goal.refresh_from_db()
        self.assertFalse(self.goal.is_active)

    def test_other_user_cannot_access_goal_or_contribute(self):
        self.client.force_authenticate(user=self.other_user)

        detail = self.client.get(self.detail_url)
        self.assertEqual(detail.status_code, 404, detail.data)

        contribution = self.entry("100.00")
        self.assertEqual(
            contribution.status_code, 404, contribution.data
        )

        self.assertEqual(self.goal.contributions.count(), 0)

    def test_wallet_cannot_be_changed(self):
        another_wallet = Wallet.objects.create(
            user=self.user,
            name="Bank",
        )

        response = self.client.patch(
            self.detail_url,
            {"wallet": another_wallet.pk},
            format="json",
        )

        self.assertEqual(response.status_code, 400, response.data)

        self.goal.refresh_from_db()
        self.assertEqual(self.goal.wallet_id, self.wallet.pk)

    def test_wallet_api_shows_savings_balances(self):
        contribution = self.entry("300.00")
        self.assertEqual(
            contribution.status_code, 201, contribution.data
        )

        wallet_url = reverse(
            "wallet-detail",
            args=[self.wallet.pk],
        )

        response = self.client.get(wallet_url)

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            response.data["current_balance"], "1000.00"
        )
        self.assertEqual(
            response.data["reserved_balance"], "300.00"
        )
        self.assertEqual(
            response.data["available_balance"], "700.00"
        )

        withdrawal = self.entry("100.00", "WITHDRAWAL")
        self.assertEqual(
            withdrawal.status_code, 201, withdrawal.data
        )

        response = self.client.get(wallet_url)

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            response.data["current_balance"], "1000.00"
        )
        self.assertEqual(
            response.data["reserved_balance"], "200.00"
        )
        self.assertEqual(
            response.data["available_balance"], "800.00"
        )