from rest_framework import filters, serializers, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated

from .models import Budget
from .permissions import IsBudgetOwner
from .serializers import BudgetSerializer


class BudgetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class BudgetFilterSerializer(serializers.Serializer):
    category = serializers.IntegerField(
        min_value=1,
        required=False,
    )

    on_date = serializers.DateField(required=False)


class BudgetViewSet(viewsets.ModelViewSet):
    serializer_class = BudgetSerializer
    permission_classes = [IsAuthenticated, IsBudgetOwner]
    pagination_class = BudgetPagination

    filter_backends = [
        filters.SearchFilter,
        filters.OrderingFilter,
    ]

    search_fields = ["category__name"]
    ordering_fields = ["amount", "start_date", "end_date"]
    ordering = ["-start_date", "-id"]

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Budget.objects.none()

        queryset = (
            Budget.objects
            .filter(user=self.request.user)
            .select_related("category")
        )

        if self.action == "list":
            serializer = BudgetFilterSerializer(
                data=self.request.query_params
            )
            serializer.is_valid(raise_exception=True)
            values = serializer.validated_data

            if "category" in values:
                queryset = queryset.filter(
                    category_id=values["category"]
                )

            if "on_date" in values:
                queryset = queryset.filter(
                    start_date__lte=values["on_date"],
                    end_date__gte=values["on_date"],
                )

        return queryset