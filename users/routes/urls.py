from django.urls import path
from ..controllers.views import (
    RegisterView, LoginView, LogoutView,
    VerifyEmailView, ForgotPasswordView, ResetPasswordView,
    MeView, ChangePasswordView, PublicProfileView,
    KYCSubmitView, KYCStatusView, UserLocationsView,
    ReportUserView,
    TwoFactorSetupView, TwoFactorEnableView,
    TwoFactorDisableView, TwoFactorVerifyLoginView,
)

urlpatterns = [
    # Autenticação
    path('register/',                RegisterView.as_view(),       name='auth-register'),
    path('login/',                   LoginView.as_view(),          name='auth-login'),
    path('logout/',                  LogoutView.as_view(),         name='auth-logout'),
    path('verify-email/<str:token>/', VerifyEmailView.as_view(),   name='auth-verify-email'),
    path('forgot-password/',         ForgotPasswordView.as_view(), name='auth-forgot-password'),
    path('reset-password/',          ResetPasswordView.as_view(),  name='auth-reset-password'),

    # Autenticação de 2 Fatores (2FA / TOTP)
    path('2fa/setup/',               TwoFactorSetupView.as_view(),        name='auth-2fa-setup'),
    path('2fa/enable/',              TwoFactorEnableView.as_view(),       name='auth-2fa-enable'),
    path('2fa/disable/',             TwoFactorDisableView.as_view(),      name='auth-2fa-disable'),
    path('2fa/verify/',              TwoFactorVerifyLoginView.as_view(),  name='auth-2fa-verify'),

    # Perfil
    path('me/',                      MeView.as_view(),             name='user-me'),
    path('me/change-password/',      ChangePasswordView.as_view(), name='user-change-password'),
    path('users/<str:user_id>/',     PublicProfileView.as_view(),  name='user-public-profile'),

    # KYC
    path('kyc/submit/',              KYCSubmitView.as_view(),      name='kyc-submit'),
    path('kyc/status/',              KYCStatusView.as_view(),      name='kyc-status'),
    
    # Locais
    path('locations/',               UserLocationsView.as_view(),  name='user-locations'),
    
    # Moderação
    path('report/',                  ReportUserView.as_view(),     name='user-report'),
]

