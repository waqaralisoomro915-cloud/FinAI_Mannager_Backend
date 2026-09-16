"""
URL configuration for Config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path,include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('apps.accounts.urls')),
    path('api/v1/', include('apps.wallets.urls')),
    path("api/v1/wallets/", include("apps.wallets.urls")),
    path("api/v1/categories/", include("apps.categories.urls")),
    path("api/v1/transactions/", include("apps.transactions.urls")),
    path("api/v1/budgets/", include("apps.budgets.urls")),
    path("api/v1/savings/", include("apps.savings.urls")),
    path("api/v1/reports/", include("apps.reports.urls")),
    path("api/v1/notifications/", include("apps.notifications.urls")),
    path("api/v1/ai-assistance/", include("apps.ai_assistance.urls")),

]
