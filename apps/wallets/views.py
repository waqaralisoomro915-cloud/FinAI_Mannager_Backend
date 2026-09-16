from rest_framework import filters, mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Wallet
from .permissions import IsWalletOwner
from .serializers import WalletSerializer


class WalletPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class WalletViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = WalletSerializer
    permission_classes = [IsAuthenticated, IsWalletOwner]
    pagination_class = WalletPagination

    filter_backends = [
        filters.SearchFilter,
        filters.OrderingFilter,
    ]

    search_fields = ["name"]
    ordering_fields = ["name", "created_at", "opening_balance"]
    ordering = ["-created_at", "-id"]

    def get_queryset(self):
        user = self.request.user

        if not user.is_authenticated:
            return Wallet.objects.none()

        queryset = Wallet.objects.filter(user=user)

        # Filters apply only to the list endpoint.
        if self.action == "list":
            is_active = self.request.query_params.get("is_active")
            wallet_type = self.request.query_params.get("wallet_type")

            if is_active is not None:
                is_active = is_active.lower()

                if is_active not in ("true", "false"):
                    raise serializers.ValidationError({
                        "is_active": "Use true or false."
                    })

                queryset = queryset.filter(
                    is_active=(is_active == "true")
                )

            if wallet_type is not None:
                if wallet_type not in Wallet.WalletType.values:
                    raise serializers.ValidationError({
                        "wallet_type": "Use CASH, BANK, or MOBILE."
                    })

                queryset = queryset.filter(wallet_type=wallet_type)

        return queryset

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        wallet = self.get_object()
        wallet.is_active = False
        wallet.save(update_fields=["is_active", "updated_at"])

        return Response(self.get_serializer(wallet).data)

    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        wallet = self.get_object()
        wallet.is_active = True
        wallet.save(update_fields=["is_active", "updated_at"])

        return Response(self.get_serializer(wallet).data)