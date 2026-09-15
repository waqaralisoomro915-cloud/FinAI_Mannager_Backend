from django.urls import path
from . import views
urlpatterns = [
    path('savings/',views.savings,name='savings'),
]