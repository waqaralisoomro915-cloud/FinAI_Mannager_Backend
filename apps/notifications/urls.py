from rest_framework.routers import DefaultRouter

from .views import NotificationViewSet


router = DefaultRouter()

router.register(
    "",
    NotificationViewSet,
    basename="notification",
)

urlpatterns = router.urls