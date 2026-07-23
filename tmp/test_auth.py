import os
import django
import uuid

# Configurar ambiente Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from users.infra.repositories import DjangoUserRepository
from users.services.use_cases import RegisterUserUseCase, LoginUseCase
from audit.infra.repositories import DjangoAuditRepository
from users.infra.email_service import TerminalEmailService

import pytest

@pytest.mark.django_db
def test_flow():
    repo = DjangoUserRepository()
    audit_repo = DjangoAuditRepository()
    email_service = TerminalEmailService()
    
    email = f"test_{uuid.uuid4().hex[:6]}@example.com"
    password = "Password123!"
    full_name = "Test User"
    
    print(f"--- Testando Registo para {email} ---")
    try:
        register_use_case = RegisterUserUseCase(repo, audit_repo, email_service)
        result = register_use_case.execute(email=email, password=password, full_name=full_name)
        print(f"Registo OK: {result}")
        
        print("\n--- Testando Login ---")
        login_use_case = LoginUseCase(repo, audit_repo)
        tokens = login_use_case.execute(email=email, password=password)
        print(f"Login OK: Tokens recebidos")
        assert tokens is not None
    except Exception as e:
        print(f"ERRO: {str(e)}")
        import traceback
        traceback.print_exc()
        assert False, f"Fluxo falhou: {e}"

if __name__ == "__main__":
    test_flow()
