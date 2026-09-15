from django.urls import path
from . import views
urlpatterns = [
    path('common/',views.common,name='common'),
]