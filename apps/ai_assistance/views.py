from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import SpendingInsightRequestSerializer
from .services import generate_spending_insights
from .throttles import SpendingInsightThrottle


class SpendingInsightView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [SpendingInsightThrottle]

    def post(self, request):
        serializer = SpendingInsightRequestSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        result = generate_spending_insights(
            user=request.user,
            start=data["date_from"],
            end=data["date_to"],
        )

        return Response(result)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(
            request,
            response,
            *args,
            **kwargs,
        )
        response["Cache-Control"] = "private, no-store"
        return response