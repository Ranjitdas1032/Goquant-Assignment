# engine/serializers.py
from rest_framework import serializers

class OrderSerializer(serializers.Serializer):
    symbol = serializers.CharField()
    order_type = serializers.ChoiceField(choices=["market","limit","ioc","fok"])
    side = serializers.ChoiceField(choices=["buy","sell"])
    quantity = serializers.DecimalField(max_digits=30, decimal_places=10)
    price = serializers.DecimalField(max_digits=30, decimal_places=10, required=False)

    def validate(self, data):
        if data["order_type"] != "market" and "price" not in data:
            raise serializers.ValidationError("price required for non-market orders")
        return data
