from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework.test import APIClient, APITestCase

from ..categories.models import Category
from ..transactions.models import Transaction
from ..wallets.models import Wallet

from .models import Budget


User = get_user_model()


class BudgetAPITests(APITestCase):
    client: APIClient

    def setUp(self):
        self.user = User.objects.create_user(
            email="waqar@example.com",
            password="Testing!Budget2026",
        )
        self.other_user = User.objects.create_user(
            email="other@example.com",
            password="Testing!Budget2026",
        )

        self.category = Category.objects.create(
            user=self.user,
            name="Food",
            category_type="EXPENSE",
        )
        self.income_category = Category.objects.create(
            user=self.user,
            name="Salary",
            category_type="INCOME",
        )
        self.foreign_category = Category.objects.create(
            user=self.other_user,
            name="Private Food",
            category_type="EXPENSE",
        )

        self.wallet = Wallet.objects.create(
            user=self.user,
            name="Cash",
            opening_balance=Decimal("10000.00"),
        )

        self.budget = Budget.objects.create(
            user=self.user,
            category=self.category,
            amount=Decimal("1000.00"),
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 30),
        )

        self.client.force_authenticate(user=self.user)

        self.list_url = reverse("budget-list")
        self.detail_url = reverse(
            "budget-detail",
            args=[self.budget.pk],
        )

    def payload(self, **overrides):
        data = {
            "category": self.category.pk,
            "amount": "1500.00",
            "start_date": "2026-10-01",
            "end_date": "2026-10-31",
        }
        data.update(overrides)
        return data

    def test_authentication_required(self):
        self.client.force_authenticate(user=None)

        self.assertEqual(
            self.client.get(self.list_url).status_code,
            401,
        )

    def test_create_assigns_owner(self):
        response = self.client.post(
            self.list_url,
            self.payload(user=self.other_user.pk),
            format="json",
        )

        self.assertEqual(response.status_code, 201)

        budget = Budget.objects.get(pk=response.data["id"])
        self.assertEqual(budget.user_id, self.user.pk)

    def test_overlap_rejected(self):
        response = self.client.post(
            self.list_url,
            self.payload(
                start_date="2026-09-30",
                end_date="2026-10-10",
            ),
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_invalid_dates_and_amount_rejected(self):
        invalid_payloads = [
            self.payload(amount="0.00"),
            self.payload(amount="-1.00"),
            self.payload(
                start_date="2026-10-31",
                end_date="2026-10-01",
            ),
        ]

        for data in invalid_payloads:
            with self.subTest(data=data):
                response = self.client.post(
                    self.list_url,
                    data,
                    format="json",
                )
                self.assertEqual(response.status_code, 400)

    def test_income_and_foreign_categories_rejected(self):
        for category in (
            self.income_category,
            self.foreign_category,
        ):
            with self.subTest(category=category.pk):
                response = self.client.post(
                    self.list_url,
                    self.payload(category=category.pk),
                    format="json",
                )
                self.assertEqual(response.status_code, 400)

    def test_archived_category_rejected_on_create(self):
        self.category.is_active = False
        self.category.save()

        response = self.client.post(
            self.list_url,
            self.payload(),
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_update_rechecks_overlap(self):
        october = Budget.objects.create(
            user=self.user,
            category=self.category,
            amount=Decimal("1000.00"),
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 31),
        )

        response = self.client.patch(
            reverse("budget-detail", args=[october.pk]),
            {"start_date": "2026-09-20"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_amount_update_allowed(self):
        response = self.client.patch(
            self.detail_url,
            {"amount": "2000.00"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.budget.refresh_from_db()
        self.assertEqual(self.budget.amount, Decimal("2000.00"))

    def test_spending_excludes_void_and_outside_period(self):
        for amount, entry_date, is_void in [
            ("1200.00", date(2026, 9, 10), False),
            ("500.00", date(2026, 9, 12), True),
            ("700.00", date(2026, 10, 1), False),
        ]:
            Transaction.objects.create(
                user=self.user,
                wallet=self.wallet,
                category=self.category,
                transaction_type="EXPENSE",
                amount=Decimal(amount),
                transaction_date=entry_date,
                is_void=is_void,
            )

        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["spent"], "1200.00")
        self.assertEqual(response.data["remaining"], "-200.00")
        self.assertEqual(response.data["usage_percentage"], "120.00")
        self.assertTrue(response.data["is_exceeded"])

    def test_other_user_cannot_access_budget(self):
        self.client.force_authenticate(user=self.other_user)

        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"], [])

        responses = [
            self.client.get(self.detail_url),
            self.client.patch(
                self.detail_url,
                {"amount": "5.00"},
                format="json",
            ),
            self.client.delete(self.detail_url),
        ]

        for response in responses:
            self.assertEqual(response.status_code, 404)

    def test_owner_can_delete_budget(self):
        response = self.client.delete(self.detail_url)

        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            Budget.objects.filter(pk=self.budget.pk).exists()
        )
        self.assertTrue(
            Category.objects.filter(pk=self.category.pk).exists()
        )