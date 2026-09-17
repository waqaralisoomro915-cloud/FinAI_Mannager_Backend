import json

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import httpx

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from openai import APITimeoutError
from rest_framework.test import APIClient, APITestCase

from ..categories.models import Category
from ..transactions.models import Transaction
from ..wallets.models import Wallet


User = get_user_model()


@override_settings(
    OPENAI_API_KEY="test-key-not-real",
    OPENAI_MODEL="gpt-4.1-mini",
)
class SpendingInsightTests(APITestCase):
    client: APIClient

    def setUp(self):
        cache.clear()

        self.user = User.objects.create_user(
            email="waqar@example.com",
            password="Testing!Insights2026",
        )
        self.other_user = User.objects.create_user(
            email="other@example.com",
            password="Testing!Insights2026",
        )

        self.wallet = Wallet.objects.create(
            user=self.user,
            name="Private Wallet Name",
            opening_balance=Decimal("1000.00"),
        )
        self.category = Category.objects.create(
            user=self.user,
            name="Food",
            category_type="EXPENSE",
        )

        self.today = timezone.localdate()

        Transaction.objects.create(
            user=self.user,
            wallet=self.wallet,
            category=self.category,
            transaction_type="EXPENSE",
            amount=Decimal("80.00"),
            description="Private transaction description",
            transaction_date=self.today,
        )

        self.client.force_authenticate(user=self.user)

        self.url = reverse("ai_assistance:spending-insights")
        self.payload = {
            "date_from": self.today.isoformat(),
            "date_to": self.today.isoformat(),
        }

        self.patcher = patch("apps.ai_assistance.services.OpenAI")
        self.openai_class = self.patcher.start()
        self.addCleanup(self.patcher.stop)

        self.provider = (
            self.openai_class.return_value.__enter__.return_value
        )
        self.provider.responses.create.return_value.status = "completed"
        self.provider.responses.create.return_value.output_text = (
            "You recorded PKR 80.00 in food expenses."
        )

    def test_authentication_required(self):
        self.client.force_authenticate(user=None)

        response = self.client.post(
            self.url, self.payload, format="json"
        )

        self.assertEqual(response.status_code, 401)
        self.openai_class.assert_not_called()

    def test_success_returns_summary_and_insights(self):
        response = self.client.post(
            self.url, self.payload, format="json"
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["source"], "openai")
        self.assertEqual(
            response.data["summary"]["period_summary"]["expenses"],
            "80.00",
        )
        self.assertIn("PKR 80.00", response.data["insights"])

        kwargs = self.provider.responses.create.call_args.kwargs
        self.assertFalse(kwargs["store"])
        self.assertNotIn("tools", kwargs)

    def test_payload_excludes_identity_and_transaction_description(self):
        response = self.client.post(
            self.url, self.payload, format="json"
        )
        self.assertEqual(response.status_code, 200)

        sent = self.provider.responses.create.call_args.kwargs["input"]

        self.assertNotIn(self.user.email, sent)
        self.assertNotIn("Private Wallet Name", sent)
        self.assertNotIn("Private transaction description", sent)

    def test_other_users_data_is_excluded(self):
        wallet = Wallet.objects.create(
            user=self.other_user,
            name="Other Wallet",
            opening_balance=Decimal("10000.00"),
        )
        category = Category.objects.create(
            user=self.other_user,
            name="Other User Secret Category",
            category_type="EXPENSE",
        )
        Transaction.objects.create(
            user=self.other_user,
            wallet=wallet,
            category=category,
            transaction_type="EXPENSE",
            amount=Decimal("750.00"),
            transaction_date=self.today,
        )

        response = self.client.post(
            self.url,
            {**self.payload, "user": self.other_user.pk},
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        sent = self.provider.responses.create.call_args.kwargs["input"]
        data = json.loads(sent)

        self.assertEqual(
            data["period_summary"]["expenses"],
            "80.00",
        )
        self.assertNotIn("Other User Secret Category", sent)

    def test_invalid_or_future_dates_rejected(self):
        tomorrow = self.today + timedelta(days=1)

        for payload in (
            {
                "date_from": tomorrow.isoformat(),
                "date_to": self.today.isoformat(),
            },
            {
                "date_from": self.today.isoformat(),
                "date_to": tomorrow.isoformat(),
            },
        ):
            with self.subTest(payload=payload):
                response = self.client.post(
                    self.url, payload, format="json"
                )
                self.assertEqual(response.status_code, 400)

        self.openai_class.assert_not_called()

    def test_missing_key_returns_service_unavailable(self):
        with override_settings(OPENAI_API_KEY=""):
            response = self.client.post(
                self.url, self.payload, format="json"
            )

        self.assertEqual(response.status_code, 503)
        self.openai_class.assert_not_called()

    def test_timeout_and_incomplete_response_handled(self):
        self.provider.responses.create.side_effect = APITimeoutError(
            request=httpx.Request(
                "POST",
                "https://api.openai.com/v1/responses",
            )
        )

        response = self.client.post(
            self.url, self.payload, format="json"
        )
        self.assertEqual(response.status_code, 503)

        self.provider.responses.create.side_effect = None
        self.provider.responses.create.return_value.status = "incomplete"

        response = self.client.post(
            self.url, self.payload, format="json"
        )
        self.assertEqual(response.status_code, 502)

    def test_empty_period_does_not_call_ai(self):
        yesterday = self.today - timedelta(days=1)

        response = self.client.post(
            self.url,
            {
                "date_from": yesterday.isoformat(),
                "date_to": yesterday.isoformat(),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["source"], "application")
        self.openai_class.assert_not_called()