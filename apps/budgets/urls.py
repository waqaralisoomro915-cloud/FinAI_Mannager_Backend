from django.urls import path
from . import views
urlpatterns = [
    path('budgets/',views.budget,name='budgets'),
]