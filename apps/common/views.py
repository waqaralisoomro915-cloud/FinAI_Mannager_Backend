from rest_framework.permissions import AllowAny
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthCheckView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = []
    renderer_classes = [JSONRenderer]

    def get(self, request):
        return Response(
            {
                "status": "ok",
                "service": "FinAI Manager API",
            },
            headers={"Cache-Control": "no-store"},
        )