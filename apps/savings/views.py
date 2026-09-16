from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import SavingsGoal
from .permissions import IsSavingsGoalOwner
from .serializers import (
    SavingsEntrySerializer,
    SavingsGoalReadSerializer,
    SavingsGoalSerializer,
)
from .services import record_savings_entry, set_goal_active


class SavingsPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class SavingsGoalViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated, IsSavingsGoalOwner]
    pagination_class = SavingsPagination

    filter_backends = [
        filters.SearchFilter,
        filters.OrderingFilter,
    ]

    search_fields = ["name"]
    ordering_fields = ["name", "target_amount", "created_at"]
    ordering = ["-created_at", "-id"]

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return SavingsGoal.objects.none()

        return (
            SavingsGoal.objects
            .filter(user=self.request.user)
            .select_related("wallet")
        )

    def get_serializer_class(self):
        if self.action == "entries":
            return SavingsEntrySerializer

        if self.action in ("create", "update", "partial_update"):
            return SavingsGoalSerializer

        return SavingsGoalReadSerializer

    @action(detail=True, methods=["get", "post"])
    def entries(self, request, pk=None):
        goal = self.get_object()

        if request.method == "GET":
            queryset = goal.contributions.all()
            page = self.paginate_queryset(queryset)

            serializer = SavingsEntrySerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = SavingsEntrySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        entry = record_savings_entry(
            user=request.user,
            goal_id=goal.pk,
            data=serializer.validated_data,
        )

        return Response(
            SavingsEntrySerializer(entry).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        goal = self.get_object()

        goal = set_goal_active(
            user=request.user,
            goal_id=goal.pk,
            active=False,
        )

        return Response(SavingsGoalReadSerializer(goal).data)

    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        goal = self.get_object()

        goal = set_goal_active(
            user=request.user,
            goal_id=goal.pk,
            active=True,
        )

        return Response(SavingsGoalReadSerializer(goal).data)