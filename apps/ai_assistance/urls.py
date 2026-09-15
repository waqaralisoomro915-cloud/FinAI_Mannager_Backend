from django.urls import path
from . import views
urlpatterns = [
    path('ai-assistance/',views.ai_assistance,name='ai_assistance'),
]