from django.urls import path
from .views import SubmitOrder, Snapshot

urlpatterns = [
    path("orders/", SubmitOrder.as_view(), name="submit-order"),
    path("snapshot/", Snapshot.as_view(), name="snapshot"),
]
