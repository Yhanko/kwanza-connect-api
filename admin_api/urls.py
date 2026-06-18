from django.urls import path
from .controllers.users import AdminUsersView, AdminUserDetailsView, AdminUserKYCView, AdminUserStatusView
from .controllers.offers import AdminOffersView, AdminOfferActionView
from .controllers.dashboard import AdminDashboardStatsView, AdminAuditLogsView
from .controllers.auth import AdminLoginView, AdminRegisterView
from .controllers.currencies import AdminCurrenciesView, AdminSeedCurrenciesView

urlpatterns = [
    # Auth
    path('auth/login/', AdminLoginView.as_view(), name='admin-login'),
    path('auth/register/', AdminRegisterView.as_view(), name='admin-register'),
    
    # Dashboard
    path('dashboard-stats/', AdminDashboardStatsView.as_view(), name='admin-dashboard-stats'),
    path('audit-logs/', AdminAuditLogsView.as_view(), name='admin-audit-logs'),
    
    # Users
    path('users/', AdminUsersView.as_view(), name='admin-users-list'),
    path('users/<uuid:user_id>/', AdminUserDetailsView.as_view(), name='admin-user-details'),
    path('users/<uuid:user_id>/kyc/', AdminUserKYCView.as_view(), name='admin-user-kyc'),
    path('users/<uuid:user_id>/status/', AdminUserStatusView.as_view(), name='admin-user-status'),
    
    # Offers
    path('offers/', AdminOffersView.as_view(), name='admin-offers-list'),
    path('offers/<uuid:offer_id>/action/', AdminOfferActionView.as_view(), name='admin-offer-action'),
    
    # Currencies
    path('currencies/', AdminCurrenciesView.as_view(), name='admin-currencies-list'),
    path('currencies/seed/', AdminSeedCurrenciesView.as_view(), name='admin-currencies-seed'),
]
