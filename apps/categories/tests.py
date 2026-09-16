from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from .models import Category


User = get_user_model()


class CategoryAPITests(APITestCase):
    client: APIClient


    def setUp(self):
        self.user = User.objects.create_user(
            email="waqar@example.com",
            password="Testing!Category2026",
        )
        self.other_user = User.objects.create_user(
            email="other@example.com",
            password="Testing!Category2026",
        )

        self.category = Category.objects.create(
            user=self.user,
            name="Food",
            category_type=Category.CategoryType.EXPENSE,
        )
        self.other_category = Category.objects.create(
            user=self.other_user,
            name="Salary",
            category_type=Category.CategoryType.INCOME,
        )

        self.client.force_authenticate(user=self.user)

        self.list_url = reverse("category-list")
        self.detail_url = reverse(
            "category-detail",
            args=[self.category.pk],
        )

    def test_authentication_required(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(self.list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_creation_assigns_authenticated_owner(self):
        response = self.client.post(
            self.list_url,
            {
                "name": "Transport",
                "category_type": "EXPENSE",
                "user": self.other_user.pk,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        category = Category.objects.get(pk=response.data["id"])
        self.assertEqual(category.user_id, self.user.pk)

    def test_case_insensitive_duplicate_rejected(self):
        response = self.client.post(
            self.list_url,
            {
                "name": " food ",
                "category_type": "EXPENSE",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_different_users_can_have_same_category(self):
        self.client.force_authenticate(user=self.other_user)

        response = self.client.post(
            self.list_url,
            {
                "name": "Food",
                "category_type": "EXPENSE",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_list_contains_only_own_categories(self):
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item["id"] for item in response.data["results"]],
            [self.category.pk],
        )

    def test_other_users_category_is_inaccessible(self):
        detail_url = reverse(
            "category-detail",
            args=[self.other_category.pk],
        )
        archive_url = reverse(
            "category-archive",
            args=[self.other_category.pk],
        )

        responses = [
            self.client.get(detail_url),
            self.client.patch(
                detail_url,
                {"name": "Changed"},
                format="json",
            ),
            self.client.post(archive_url),
        ]

        for response in responses:
            self.assertEqual(
                response.status_code,
                status.HTTP_404_NOT_FOUND,
            )

    def test_category_type_cannot_change(self):
        response = self.client.patch(
            self.detail_url,
            {"category_type": "INCOME"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.category.refresh_from_db()
        self.assertEqual(self.category.category_type, "EXPENSE")

    def test_archive_and_restore(self):
        for action_name, expected_active in [
            ("category-archive", False),
            ("category-restore", True),
        ]:
            response = self.client.post(
                reverse(action_name, args=[self.category.pk])
            )

            self.assertEqual(response.status_code, status.HTTP_200_OK)

            self.category.refresh_from_db()
            self.assertEqual(self.category.is_active, expected_active)

    def test_delete_not_allowed(self):
        response = self.client.delete(self.detail_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )