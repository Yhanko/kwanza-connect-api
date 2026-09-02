from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from rest_framework.permissions import AllowAny
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from rest_framework_simplejwt.views import TokenRefreshView
from app.health import health_check

class ThrottledTokenRefreshView(TokenRefreshView):
    throttle_scope = 'token_refresh'

urlpatterns = [
    # ── Redirecionamento da Raiz para a Documentação ───────────────────
    path('', RedirectView.as_view(url='/api/docs/', permanent=False), name='root_redirect'),

    # ── Health Check (Docker / Load Balancer) ───────────────────────────
    path('api/health/',         health_check,                  name='health_check'),

    # ── Admin ──────────────────────────────────────────────────────────
    path('admin/', admin.site.urls),

    # ── OpenAPI / Documentação ─────────────────────────────────────────
    path(
        'api/schema/',
        SpectacularAPIView.as_view(
            permission_classes=[AllowAny],
            throttle_classes=[],
            authentication_classes=[],
        ),
        name='schema'
    ),
    path(
        'api/docs/',
        SpectacularSwaggerView.as_view(
            url_name='schema',
            permission_classes=[AllowAny],
            throttle_classes=[],
            authentication_classes=[],
        ),
        name='swagger-ui'
    ),
    path(
        'api/redoc/',
        SpectacularRedocView.as_view(
            url_name='schema',
            permission_classes=[AllowAny],
            throttle_classes=[],
            authentication_classes=[],
        ),
        name='redoc'
    ),

    # ── JWT (RENOVAÇÃO DE TOKENS) ───────────────────────────────────────
    # Endpoint para renovação de acesso: O cliente envia um 'refresh_token' válido e recebe um novo 'access_token' (e um novo refresh token rodado).
    path('api/auth/token/refresh/', ThrottledTokenRefreshView.as_view(), name='token_refresh'),

    # ── Módulos ────────────────────────────────────────────────────────
    path('api/auth/',          include('users.routes.urls')),
    path('api/offers/',        include('offers.routes.urls')),
    path('api/chat/',          include('chat.routes.urls')),
    path('api/notifications/', include('notifications.routes.urls')),
    path('api/rates/',         include('rates.routes.urls')),
    path('api/transactions/',  include('transactions.routes.urls')),
    path('api/audit/',         include('audit.infra.urls')),
    path('api/admin/',         include('admin_api.urls')),
    path('api/',               include('security.urls')),
]

# Servir media em desenvolvimento
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
