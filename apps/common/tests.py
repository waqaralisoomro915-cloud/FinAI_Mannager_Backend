from django.test import SimpleTestCase
from django.urls import reverse

from rest_framework import serializers, status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.test import APIClient, APIRequestFactory

from .pagination import StandardPagination


class HealthCheckTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("common:health")

    def test_health_is_public(self):
        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            response.json(),
            {
                "status": "ok",
                "service": "FinAI Manager API",
            },
        )
        self.assertEqual(
            response["Cache-Control"],
            "no-store",
        )

    def test_health_ignores_invalid_authentication_header(self):
        response = self.client.get(
            self.url,
            HTTP_AUTHORIZATION="Bearer invalid-token",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

    def test_health_rejects_post(self):
        response = self.client.post(
            self.url,
            {},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )


# This view is only used by tests. It has no public URL.
class PaginationItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()


class PaginationProbeView(ListAPIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = []
    serializer_class = PaginationItemSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        return [{"id": number} for number in range(1, 151)]


class PaginationTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = PaginationProbeView.as_view()

    def test_next_page_continues_without_repeating_records(self):
        first_response = self.view(
            self.factory.get("/pagination-probe/")
        )

        self.assertEqual(
            first_response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(first_response.data["count"], 150)
        self.assertEqual(
            [item["id"] for item in first_response.data["results"]],
            list(range(1, 21)),
        )
        self.assertIsNone(first_response.data["previous"])
        self.assertIsNotNone(first_response.data["next"])

        second_response = self.view(
            self.factory.get(first_response.data["next"])
        )

        self.assertEqual(
            [item["id"] for item in second_response.data["results"]],
            list(range(21, 41)),
        )
        self.assertIsNotNone(second_response.data["previous"])

    def test_requested_page_size_is_capped(self):
        response = self.view(
            self.factory.get(
                "/pagination-probe/",
                {"page_size": 10000},
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(response.data["count"], 150)
        self.assertEqual(len(response.data["results"]), 100)
        self.assertIsNotNone(response.data["next"])