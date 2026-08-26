"""
Tratamento global de erros — handleGlobalErrors.
Devolve respostas JSON padronizadas para todos os status codes e erros.
Nenhuma informação sensível (stack trace, query, modelo interno) é exposta.
"""
import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import PermissionDenied, ValidationError as DjangoValidationError
from django.http import Http404
import traceback

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  Mapa de mensagens por status code
# ─────────────────────────────────────────────
STATUS_MESSAGES = {
    400: 'Pedido inválido. Verifique os dados enviados.',
    401: 'Não autenticado. Faça login para continuar.',
    403: 'Acesso negado. Não tem permissão para realizar esta acção.',
    404: 'Recurso não encontrado.',
    405: 'Método HTTP não permitido neste endpoint.',
    408: 'Tempo limite da ligação excedido. Tente novamente.',
    409: 'Conflito. O recurso já existe ou há um conflito de dados.',
    410: 'Este recurso já não está disponível.',
    422: 'Dados não processáveis. Verifique os campos obrigatórios.',
    429: 'Demasiados pedidos. Aguarde e tente novamente.',
    500: 'Erro interno do servidor. A equipa foi notificada.',
    502: 'Serviço temporariamente indisponível.',
    503: 'Serviço em manutenção. Tente mais tarde.',
}


def _build_error_response(
    status_code: int,
    message: str = None,
    errors: dict | list | None = None,
    error_code: str = None,
) -> Response:
    """Constrói uma resposta de erro padronizada."""
    payload = {
        'success': False,
        'status':  status_code,
        'message': message or STATUS_MESSAGES.get(status_code, 'Erro desconhecido.'),
    }
    if error_code:
        payload['error_code'] = error_code
    if errors:
        payload['errors'] = errors
    return Response(payload, status=status_code)


def handle_global_errors(exc, context) -> Response:
    """
    Handler global de excepções para o Django REST Framework.
    Configurado em REST_FRAMEWORK['EXCEPTION_HANDLER'] no settings.py.
    """
    # Chama o handler padrão do DRF primeiro
    response = exception_handler(exc, context)

    # ── Excepções Django não capturadas pelo DRF ──────────────────────
    if response is None:
        if isinstance(exc, Http404):
            return _build_error_response(404)

        if isinstance(exc, PermissionDenied):
            return _build_error_response(403)

        if isinstance(exc, DjangoValidationError):
            errors = exc.message_dict if hasattr(exc, 'message_dict') else {'non_field_errors': exc.messages}
            return _build_error_response(400, errors=errors)

        # Formata o erro de forma limpa e compreensiva
        view_name = context.get('view', '?')
        tb = traceback.extract_tb(exc.__traceback__)
        last_call = tb[-1] if tb else None
        
        err_msg = f"\n\033[91m💥 [ERRO 500 - INTERNO] na view: {view_name}\033[0m"
        if last_call:
            file_name = last_call.filename.split('kwanzaConnect-API')[-1]
            err_msg += f"\n   📍 Local: {file_name} na linha {last_call.lineno} (função '{last_call.name}')"
        err_msg += f"\n   🚨 Motivo: {type(exc).__name__}: {str(exc)}\n"

        logger.error(err_msg)
        
        request = context.get('request')
        if request:
            from app.audit_service import audit_log
            audit_log(
                action='SYSTEM_ERROR_500',
                resource='system',
                metadata={'view': str(view_name), 'error': type(exc).__name__, 'details': str(exc)},
                request=request
            )
            
        return _build_error_response(500)

    # ── Respostas DRF — normalizar formato ───────────────────────────
    data    = response.data
    code    = response.status_code
    message = STATUS_MESSAGES.get(code, 'Erro na operação.')
    errors  = None

    # DRF devolve dicts com 'detail' ou com campos de erro
    if isinstance(data, dict):
        if 'detail' in data:
            # Extrai mensagem do DRF e usa como mensagem principal
            detail = str(data['detail'])
            # Mapeia códigos DRF para mensagens PT
            drf_code_map = {
                'not_authenticated':      'Não autenticado. Faça login para continuar.',
                'authentication_failed':  'Credenciais inválidas.',
                'token_not_valid':        'Token inválido ou expirado. Faça login novamente.',
                'user_not_found':         'Utilizador não encontrado.',
                'permission_denied':      'Acesso negado. Não tem permissão para realizar esta acção.',
                'not_found':              'Recurso não encontrado.',
                'method_not_allowed':     'Método não permitido neste endpoint.',
                # TRATAMENTO DE EXCEÇÃO DE RATE LIMIT: Intercepta o limite de Throttle do DRF (HTTP 429) e devolve mensagem personalizada em português.
                'throttled':              'Demasiados pedidos. Aguarde e tente novamente.',
            }
            error_code = getattr(data.get('detail'), 'code', None)
            if error_code and error_code in drf_code_map:
                message = drf_code_map[error_code]
            else:
                message = detail
        else:
            # Erros de validação campo a campo — sanitiza antes de expor
            errors = _sanitize_validation_errors(data)

    elif isinstance(data, list):
        errors = data

    # Log de erros 5xx para debugging interno (sem expor ao cliente)
    if code >= 500:
        logger.error('\n\033[91m💥 [ERRO DRF 5xx] na view: %s\033[0m\n   🚨 Motivo: %s\n', context.get('view', '?'), exc)
        request = context.get('request')
        if request:
            from app.audit_service import audit_log
            audit_log(
                action=f'SYSTEM_ERROR_{code}',
                resource='system',
                metadata={'view': str(context.get('view', '?')), 'error': type(exc).__name__, 'details': str(exc)},
                request=request
            )

    response.data = {
        'success': False,
        'status':  code,
        'message': message,
    }
    if errors:
        response.data['errors'] = errors

    return response


def _sanitize_validation_errors(data: dict) -> dict:
    """
    Converte erros de validação DRF para strings legíveis.
    Remove qualquer informação interna do modelo ou base de dados.
    """
    sanitized = {}
    for field, messages in data.items():
        if isinstance(messages, list):
            sanitized[field] = [str(m) for m in messages]
        elif isinstance(messages, dict):
            sanitized[field] = _sanitize_validation_errors(messages)
        else:
            sanitized[field] = str(messages)
    return sanitized


def success_response(data=None, message: str = 'Operação realizada com sucesso.', status_code: int = 200) -> Response:
    """Resposta de sucesso padronizada para usar nas views."""
    payload = {
        'success': True,
        'status':  status_code,
        'message': message,
    }
    if data is not None:
        payload['data'] = data
    return Response(payload, status=status_code)


def created_response(data=None, message: str = 'Criado com sucesso.') -> Response:
    return success_response(data=data, message=message, status_code=status.HTTP_201_CREATED)


def no_content_response(message: str = 'Removido com sucesso.') -> Response:
    return Response({'success': True, 'message': message}, status=status.HTTP_204_NO_CONTENT)
