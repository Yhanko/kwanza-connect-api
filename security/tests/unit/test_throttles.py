import pytest
from unittest.mock import Mock, patch
from rest_framework.test import APIRequestFactory
from security.throttles import (
    get_client_ip, ReliableAnonRateThrottle, 
    KYCTieredUserRateThrottle, AuthBruteForceThrottle
)
from rest_framework.exceptions import Throttled
from app.exceptions import handle_global_errors

def test_get_client_ip_with_x_forwarded_for():
    """Testa a extração segura do IP através de proxy reverso."""
    factory = APIRequestFactory()
    request = factory.get('/', HTTP_X_FORWARDED_FOR='197.234.50.12, 10.0.0.1')
    assert get_client_ip(request) == '197.234.50.12'

def test_get_client_ip_with_remote_addr():
    """Testa a extração padrão do IP remoto."""
    factory = APIRequestFactory()
    request = factory.get('/', REMOTE_ADDR='192.168.1.100')
    assert get_client_ip(request) == '192.168.1.100'

def test_reliable_anon_rate_throttle_unauthenticated():
    """Testa se o throttle anónimo gera chave de cache baseada no IP."""
    factory = APIRequestFactory()
    request = factory.get('/', REMOTE_ADDR='200.10.10.1')
    request.user = Mock(is_authenticated=False)
    
    throttle = ReliableAnonRateThrottle()
    key = throttle.get_cache_key(request, view=None)
    assert key is not None
    assert 'anon' in key
    assert '200.10.10.1' in key

def test_reliable_anon_rate_throttle_skips_authenticated():
    """Testa se o throttle anónimo não afeta utilizadores autenticados."""
    factory = APIRequestFactory()
    request = factory.get('/')
    request.user = Mock(is_authenticated=True)
    
    throttle = ReliableAnonRateThrottle()
    assert throttle.get_cache_key(request, view=None) is None

def test_kyc_tiered_user_rate_throttle_admin():
    """Testa se administradores recebem escopo de alta capacidade."""
    factory = APIRequestFactory()
    request = factory.get('/')
    request.user = Mock(is_authenticated=True, is_staff=True, is_superuser=False, is_verified=True, pk='user-admin-1')
    
    throttle = KYCTieredUserRateThrottle()
    key = throttle.get_cache_key(request, view=None)
    assert throttle.scope == 'user_admin'
    assert 'user-admin-1' in key

def test_kyc_tiered_user_rate_throttle_verified_user():
    """Testa se utilizadores verificados (KYC aprovado) recebem taxa expandida."""
    factory = APIRequestFactory()
    request = factory.get('/')
    request.user = Mock(is_authenticated=True, is_staff=False, is_superuser=False, is_verified=True, pk='user-ver-2')
    
    throttle = KYCTieredUserRateThrottle()
    key = throttle.get_cache_key(request, view=None)
    assert throttle.scope == 'user_verified'
    assert 'user-ver-2' in key

def test_kyc_tiered_user_rate_throttle_unverified_user():
    """Testa se utilizadores não verificados recebem limite estrito."""
    factory = APIRequestFactory()
    request = factory.get('/')
    request.user = Mock(is_authenticated=True, is_staff=False, is_superuser=False, is_verified=False, pk='user-unver-3')
    
    throttle = KYCTieredUserRateThrottle()
    key = throttle.get_cache_key(request, view=None)
    assert throttle.scope == 'user_unverified'
    assert 'user-unver-3' in key

def test_auth_brute_force_throttle():
    """Testa se o throttle de autenticação combina IP e e-mail no ident."""
    factory = APIRequestFactory()
    request = factory.post('/api/auth/login/', data={'email': 'ALVO@kwanza.ao'}, format='json')
    request.META['REMOTE_ADDR'] = '197.234.1.1'
    request.data = {'email': 'alvo@kwanza.ao'}
    
    throttle = AuthBruteForceThrottle()
    key = throttle.get_cache_key(request, view=None)
    assert key is not None
    assert 'auth_login' in key
    assert '197.234.1.1_alvo@kwanza.ao' in key

@patch('app.audit_service.audit_log')
def test_handle_throttled_exception_generates_retry_after_and_audit(mock_audit):
    """Testa se exceção Throttled (429) retorna cabeçalho Retry-After e grava auditoria."""
    exc = Throttled(wait=42)
    factory = APIRequestFactory()
    request = factory.get('/api/offers/')
    context = {'request': request, 'view': 'OfferListCreateView'}
    
    response = handle_global_errors(exc, context)
    
    assert response.status_code == 429
    assert response.headers.get('Retry-After') == '42'
    assert response.data['success'] is False
    assert response.data['error_code'] == 'RATE_LIMIT_EXCEEDED'
    assert response.data['retry_after_seconds'] == 42
    assert '42 segundo(s)' in response.data['message']
    
    # Verifica se a auditoria de incidente de segurança foi disparada
    mock_audit.assert_called_once()
    audit_kwargs = mock_audit.call_args[1]
    assert audit_kwargs['action'] == 'RATE_LIMIT_EXCEEDED'
    assert audit_kwargs['severity'] == 'WARNING'
    assert audit_kwargs['status'] == 'BLOCKED'
