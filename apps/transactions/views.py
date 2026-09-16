from django.db.models import Q

from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Transaction
from .permissions import IsTransactionOwner
from .serializers import (
    TransactionCreateSerializer,
    TransactionFilterSerializer,
    TransactionSerializer,
    VoidTransactionSerializer,
)
from .services import void_transaction


class TransactionPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class TransactionViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated, IsTransactionOwner]
    pagination_class = TransactionPagination

    filter_backends = [
        filters.SearchFilter,
        filters.OrderingFilter,
    ]

    search_fields = ["description"]
    ordering_fields = ["amount", "transaction_date", "created_at"]
    ordering = ["-transaction_date", "-id"]

    def get_serializer_class(self):
        if self.action == "create":
            return TransactionCreateSerializer

        if self.action == "void":
            return VoidTransactionSerializer

        return TransactionSerializer

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Transaction.objects.none()

        queryset = (
            Transaction.objects
            .filter(user=self.request.user)
            .select_related("wallet", "destination_wallet", "category")
        )

        if self.action != "list":
            return queryset

        serializer = TransactionFilterSerializer(
            data=self.request.query_params
        )
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data

        if "wallet" in values:
            queryset = queryset.filter(
                Q(wallet_id=values["wallet"])
                | Q(destination_wallet_id=values["wallet"])
            )

        if "category" in values:
            queryset = queryset.filter(category_id=values["category"])

        if "transaction_type" in values:
            queryset = queryset.filter(
                transaction_type=values["transaction_type"]
            )

        if "is_void" in values:
            queryset = queryset.filter(is_void=values["is_void"])

        if "date_from" in values:
            queryset = queryset.filter(
                transaction_date__gte=values["date_from"]
            )

        if "date_to" in values:
            queryset = queryset.filter(
                transaction_date__lte=values["date_to"]
            )

        return queryset

    @action(detail=True, methods=["post"])
    def void(self, request, pk=None):
        entry = self.get_object()

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        entry = void_transaction(
            user=request.user,
            transaction_id=entry.pk,
            reason=serializer.validated_data["reason"],
        )

        return Response(
            TransactionSerializer(entry).data,
            status=status.HTTP_200_OK,
        )