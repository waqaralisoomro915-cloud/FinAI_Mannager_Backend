from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (BudgetProgressReportView,CategorySpendingReportView,DashboardReportView,MonthlyTrendReportView,SavingsProgressReportView,TransactionCSVView,)
from .saved_views import (GeneratedReportViewSet,ReportScheduleViewSet,)
app_name = "reports"
router = DefaultRouter()
router.register("saved",GeneratedReportViewSet,basename="generated-report",)
router.register("schedules",ReportScheduleViewSet,basename="report-schedule",)
urlpatterns = [
    path("dashboard/",DashboardReportView.as_view(), name="dashboard",),
    path("categories/",CategorySpendingReportView.as_view(), name="categories",),
    path("monthly/", MonthlyTrendReportView.as_view(),name="monthly",),
    path("budgets/",BudgetProgressReportView.as_view(),name="budgets",),
    path("savings/",SavingsProgressReportView.as_view(),name="savings",),
    path("transactions/export/",TransactionCSVView.as_view(),name="export", ),
]
urlpatterns += router.urls