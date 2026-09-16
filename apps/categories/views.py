from django.db import IntegrityError, transaction

from rest_framework import filters, mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Category
from .permissions import IsCategoryOwner
from .serializers import CategorySerializer


class CategoryPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class CategoryViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated, IsCategoryOwner]
    pagination_class = CategoryPagination

    filter_backends = [
        filters.SearchFilter,
        filters.OrderingFilter,
    ]

    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name", "id"]

    def get_queryset(self):
        user = self.request.user

        if not user.is_authenticated:
            return Category.objects.none()

        queryset = Category.objects.filter(user=user)

        if self.action == "list":
            category_type = self.request.query_params.get(
                "category_type"
            )
            is_active = self.request.query_params.get("is_active")

            if category_type is not None:
                if category_type not in Category.CategoryType.values:
                    raise serializers.ValidationError({
                        "category_type": "Use INCOME or EXPENSE."
                    })

                queryset = queryset.filter(
                    category_type=category_type
                )

            if is_active is not None:
                is_active = is_active.lower()

                if is_active not in ("true", "false"):
                    raise serializers.ValidationError({
                        "is_active": "Use true or false."
                    })

                queryset = queryset.filter(
                    is_active=(is_active == "true")
                )

        return queryset

    def _save_category(self, serializer, **kwargs):
        # Also handles simultaneous requests for the same category.
        try:
            with transaction.atomic():
                serializer.save(**kwargs)
        except IntegrityError:
            raise serializers.ValidationError({
                "name": (
                    "Category could not be saved. "
                    "Check whether this name already exists for this type."
                )
            })

    def perform_create(self, serializer):
        self._save_category(
            serializer,
            user=self.request.user,
        )

    def perform_update(self, serializer):
        self._save_category(serializer)

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        category = self.get_object()
        category.is_active = False
        category.save(update_fields=["is_active", "updated_at"])

        return Response(self.get_serializer(category).data)

    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        category = self.get_object()
        category.is_active = True
        category.save(update_fields=["is_active", "updated_at"])

        return Response(self.get_serializer(category).data)