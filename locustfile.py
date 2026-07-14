from locust import HttpUser, task, between
import uuid

class KwanzaConnectLoadTest(HttpUser):
    # Tempo de espera entre cada tarefa (entre 1 e 3 segundos)
    wait_time = between(1, 3)

    @task(3)
    def test_get_public_profile(self):
        """
        Simula utilizadores a consultar perfis públicos.
        Substitua este UUID por um ID válido de um utilizador existente na sua base de dados,
        ou deixe que a API retorne 404 (o teste contará a carga na mesma).
        """
        # Exemplo de UUID (idealmente deve ser de um utilizador ativo)
        sample_user_id = "00000000-0000-0000-0000-000000000000"
        self.client.get(f"/api/users/profile/{sample_user_id}/", name="/api/users/profile/[id]")

    @task(1)
    def test_login_attempt(self):
        """
        Simula tentativas de login.
        """
        self.client.post("/api/auth/login/", json={
            "email": f"fake_{uuid.uuid4().hex[:5]}@example.com",
            "password": "Password123!"
        }, name="/api/auth/login/")

    @task(2)
    def test_register_attempt(self):
        """
        Simula tentativas de registo de utilizadores.
        """
        self.client.post("/api/auth/register/", json={
            "full_name": "Carga Teste",
            "email": f"loadtest_{uuid.uuid4().hex[:6]}@example.com",
            "password": "Password123!",
            "password_confirm": "Password123!",
            "phone": "+244 922 000 000"
        }, name="/api/auth/register/")
