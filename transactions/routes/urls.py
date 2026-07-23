from django.urls import path
from ..controllers.views import TransactionListView, TransactionConfirmView, TransactionReviewView, TransactionDetailView, ReviewListView, TopLocationsMetricsView, TopPaymentMethodsMetricsView

urlpatterns = [
    # Transações
    path('',                          TransactionListView.as_view(),    name='transaction-list'),
    path('confirm/',                  TransactionConfirmView.as_view(), name='transaction-confirm'),
    path('reviews/<str:user_id>/',    ReviewListView.as_view(),         name='user-reviews'),
    path('<str:transaction_id>/',     TransactionDetailView.as_view(),  name='transaction-detail'),
    path('<str:transaction_id>/review/', TransactionReviewView.as_view(), name='transaction-review'),
    
    # Métricas
    path('metrics/top-locations/',    TopLocationsMetricsView.as_view(), name='top-locations'),
    path('metrics/top-payment-methods/', TopPaymentMethodsMetricsView.as_view(), name='top-payment-methods'),
]
