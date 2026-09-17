from django.utils import timezone

from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Notification
from .permissions import IsNotificationRecipient
from .serializers import (
    NotificationFilterSerializer,
    NotificationSerializer,
)


class NotificationPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class NotificationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = NotificationSerializer
    permission_classes = [
        IsAuthenticated,
        IsNotificationRecipient,
    ]
    pagination_class = NotificationPagination

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Notification.objects.none()

        queryset = Notification.objects.filter(
            recipient=self.request.user
        )

        if self.action == "list":
            serializer = NotificationFilterSerializer(
                data=self.request.query_params
            )
            serializer.is_valid(raise_exception=True)
            values = serializer.validated_data

            if "is_read" in values:
                queryset = queryset.filter(
                    read_at__isnull=not values["is_read"]
                )

            if "kind" in values:
                queryset = queryset.filter(kind=values["kind"])

        return queryset

    @action(
        detail=False,
        methods=["get"],
        url_path="unread-count",
    )
    def unread_count(self, request):
        count = self.get_queryset().filter(
            read_at__isnull=True
        ).count()

        return Response({"unread_count": count})

    @action(
        detail=True,
        methods=["post"],
        url_path="mark-read",
    )
    def mark_read(self, request, pk=None):
        notification = self.get_object()

        Notification.objects.filter(
            pk=notification.pk,
            recipient=request.user,
            read_at__isnull=True,
        ).update(read_at=timezone.now())

        notification.refresh_from_db()

        return Response(
            self.get_serializer(notification).data
        )

    @action(
        detail=False,
        methods=["post"],
        url_path="mark-all-read",
    )
    def mark_all_read(self, request):
        updated = self.get_queryset().filter(
            read_at__isnull=True
        ).update(read_at=timezone.now())

        return Response({"marked_read": updated})