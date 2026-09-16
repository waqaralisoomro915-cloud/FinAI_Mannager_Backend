import csv

from django.http import HttpResponse

from rest_framework import generics
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.budgets.models import Budget
from apps.budgets.serializers import BudgetSerializer
from apps.savings.models import SavingsGoal
from apps.savings.serializers import SavingsGoalReadSerializer

from .serializers import ReportPeriodSerializer
from .services import (
    category_spending,
    current_balances,
    money,
    monthly_trends,
    period_summary,
    period_transactions,
    safe_csv_text,
)


class PrivateReportMixin:
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(
            request,
            response,
            *args,
            **kwargs,
        )
        response["Cache-Control"] = "private, no-store"
        return response


class BasePeriodReportView(PrivateReportMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_period(self):
        serializer = ReportPeriodSerializer(
            data=self.request.query_params
        )
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        return data["date_from"], data["date_to"]

    def report_response(self, start, end, data):
        return Response({
            "currency": "PKR",
            "date_from": start.isoformat(),
            "date_to": end.isoformat(),
            **data,
        })


class DashboardReportView(BasePeriodReportView):
    def get(self, request):
        start, end = self.get_period()

        return self.report_response(
            start,
            end,
            {
                "period_summary": period_summary(
                    request.user,
                    start,
                    end,
                ),
                # Current balances are NOT limited to the period.
                "current_balances": current_balances(request.user),
            },
        )


class CategorySpendingReportView(BasePeriodReportView):
    def get(self, request):
        start, end = self.get_period()

        return self.report_response(
            start,
            end,
            {
                "results": category_spending(
                    request.user,
                    start,
                    end,
                ),
            },
        )


class MonthlyTrendReportView(BasePeriodReportView):
    def get(self, request):
        start, end = self.get_period()

        return self.report_response(
            start,
            end,
            {
                "results": monthly_trends(
                    request.user,
                    start,
                    end,
                ),
            },
        )


class TransactionCSVView(BasePeriodReportView):
    def get(self, request):
        start, end = self.get_period()

        queryset = (
            period_transactions(request.user, start, end)
            .select_related(
                "wallet",
                "destination_wallet",
                "category",
            )
            .order_by("transaction_date", "id")
        )

        filename = f"finai-transactions-{start}-{end}.csv"

        response = HttpResponse(
            content_type="text/csv; charset=utf-8"
        )
        response["Content-Disposition"] = (
            f'attachment; filename="{filename}"'
        )

        # Helps Excel recognize UTF-8 text.
        response.write("\ufeff")

        writer = csv.writer(response)
        writer.writerow([
            "ID",
            "Date",
            "Type",
            "Wallet",
            "Destination Wallet",
            "Category",
            "Amount",
            "Currency",
            "Description",
        ])

        for entry in queryset.iterator(chunk_size=500):
            writer.writerow([
                entry.pk,
                entry.transaction_date.isoformat(),
                entry.transaction_type,
                safe_csv_text(entry.wallet.name),
                safe_csv_text(
                    entry.destination_wallet.name
                    if entry.destination_wallet else ""
                ),
                safe_csv_text(
                    entry.category.name if entry.category else ""
                ),
                money(entry.amount),
                entry.wallet.currency,
                safe_csv_text(entry.description),
            ])

        return response


class ReportPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class BudgetProgressReportView(
    PrivateReportMixin,
    generics.ListAPIView,
):
    permission_classes = [IsAuthenticated]
    serializer_class = BudgetSerializer
    pagination_class = ReportPagination

    def get_queryset(self):
        serializer = ReportPeriodSerializer(
            data=self.request.query_params
        )
        serializer.is_valid(raise_exception=True)
        period = serializer.validated_data

        return (
            Budget.objects
            .filter(
                user=self.request.user,
                start_date__lte=period["date_to"],
                end_date__gte=period["date_from"],
            )
            .select_related("category")
            .order_by("-start_date", "-id")
        )


class SavingsProgressReportView(
    PrivateReportMixin,
    generics.ListAPIView,
):
    permission_classes = [IsAuthenticated]
    serializer_class = SavingsGoalReadSerializer
    pagination_class = ReportPagination

    def get_queryset(self):
        # Current progress, not historical progress for a date range.
        return (
            SavingsGoal.objects
            .filter(user=self.request.user)
            .select_related("wallet")
            .order_by("-created_at", "-id")
        )