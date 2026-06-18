from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    # ── Admin ──────────────────────────────────────────────────────────
    path('admin/', admin.site.urls),

    # ── OpenAPI / Documentação ─────────────────────────────────────────
    path('api/schema/',         SpectacularAPIView.as_view(),  name='schema'),
    path('api/docs/',           SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/',          SpectacularRedocView.as_view(url_name='schema'),   name='redoc'),

    # ── JWT ────────────────────────────────────────────────────────────
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # ── Módulos ────────────────────────────────────────────────────────
    path('api/auth/',          include('users.routes.urls')),
    path('api/offers/',        include('offers.routes.urls')),
    path('api/chat/',          include('chat.routes.urls')),
    path('api/notifications/', include('notifications.routes.urls')),
    path('api/rates/',         include('rates.routes.urls')),
    path('api/transactions/',  include('transactions.routes.urls')),
    path('api/audit/',         include('audit.infra.urls')),
    path('api/admin/',         include('admin_api.urls')),
]

# Servir media em desenvolvimento
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
