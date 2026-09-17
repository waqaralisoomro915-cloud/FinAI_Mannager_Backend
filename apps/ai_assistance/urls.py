from django.urls import path

from .views import SpendingInsightView


app_name = "ai_assistance"

urlpatterns = [
    path("",SpendingInsightView.as_view(),name="spending-insights",),
]