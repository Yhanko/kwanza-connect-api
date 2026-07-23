from django.urls import path
from .controllers.users import (
    AdminUsersView, AdminUserDetailsView, AdminUserKYCView, AdminUserStatusView,
    AdminUserSanctionView, AdminReportListView, AdminReportActionView, AdminUserDeleteView
)
from .controllers.offers import AdminOffersView, AdminOfferActionView
from .controllers.dashboard import AdminDashboardStatsView, AdminAuditLogsView
from .controllers.health import AdminSystemHealthView
from .controllers.auth import AdminLoginView, AdminRegisterView
from .controllers.currencies import AdminCurrenciesView, AdminSeedCurrenciesView

urlpatterns = [
    # Auth
    path('auth/login/', AdminLoginView.as_view(), name='admin-login'),
    path('auth/register/', AdminRegisterView.as_view(), name='admin-register'),
    
    # Dashboard
    path('dashboard-stats/', AdminDashboardStatsView.as_view(), name='admin-dashboard-stats'),
    path('health/', AdminSystemHealthView.as_view(), name='admin-health'),
    path('audit-logs/', AdminAuditLogsView.as_view(), name='admin-audit-logs'),
    
    # Users
    path('users/', AdminUsersView.as_view(), name='admin-users-list'),
    path('users/<uuid:user_id>/', AdminUserDetailsView.as_view(), name='admin-user-details'),
    path('users/<uuid:user_id>/kyc/', AdminUserKYCView.as_view(), name='admin-user-kyc'),
    path('users/<uuid:user_id>/status/', AdminUserStatusView.as_view(), name='admin-user-status'),
    path('users/<uuid:user_id>/sanction/', AdminUserSanctionView.as_view(), name='admin-user-sanction'),
    path('users/<uuid:user_id>/delete/', AdminUserDeleteView.as_view(), name='admin-user-delete'),
    
    # Moderation
    path('reports/', AdminReportListView.as_view(), name='admin-reports-list'),
    path('reports/<uuid:report_id>/action/', AdminReportActionView.as_view(), name='admin-report-action'),

    
    # Offers
    path('offers/', AdminOffersView.as_view(), name='admin-offers-list'),
    path('offers/<uuid:offer_id>/action/', AdminOfferActionView.as_view(), name='admin-offer-action'),
    
    # Currencies
    path('currencies/', AdminCurrenciesView.as_view(), name='admin-currencies-list'),
    path('currencies/seed/', AdminSeedCurrenciesView.as_view(), name='admin-currencies-seed'),
]
