from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import OrderSerializer
from .engine import BOOK

class SubmitOrder(APIView):
    authentication_classes = []
    permission_classes = []
    def post(self, request):
        s = OrderSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        order_id = BOOK.submit(s.validated_data)
        return Response({"order_id": order_id}, status=status.HTTP_201_CREATED)

class Snapshot(APIView):
    authentication_classes = []
    permission_classes = []
    def get(self, request):
        data = {
            "bbo": BOOK._bbo(),
            "l2": BOOK._l2_snapshot(),
        }
        return Response(data, status=200)
