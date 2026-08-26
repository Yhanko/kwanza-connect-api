# KwanzaConnect API — Plataforma de Câmbio P2P

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-4.2+-092E20?logo=django&logoColor=white)](https://www.djangoproject.com/)
[![Clean Architecture](https://img.shields.io/badge/Architecture-Clean--Architecture-blue)](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)

## 📝 Sobre o Software
A **KwanzaConnect API** é uma solução robusta para facilitar a troca de moedas entre indivíduos (Peer-to-Peer). A plataforma permite que utilizadores publiquem propostas de câmbio, encontrem parceiros de negócio em tempo real, negociem via chat integrado e acompanhem as taxas de câmbio mundiais atualizadas.

**Propósito:** Democratizar o acesso ao câmbio, permitindo que as pessoas negociem valores de forma direta, segura e transparente, sem a necessidade de intermediários bancários complexos para pequenas operações.

---

## 👤 Criador
Este projeto foi idealizado e desenvolvido por **Romeu Cajamba**.

---

## 🛠️ Tecnologias Utilizadas
- **Linguagem & Framework Base:** Python 3.14+ & Django 4.2+
- **APIs RESTful:** Django REST Framework (DRF)
- **Real-Time (Chat & Notificações):** Django Channels (WebSockets) com Redis Layer
- **Media Storage (Imagens e Documentos KYC):** Integração com **Cloudinary** API
- **Email Service:** Mock Terminal (Dev) / SMTP (Prod)
- **Base de Dados:** PostgreSQL (Persistência Principal)
- **Cache & Message Broker:** Redis
- **Tarefas Assíncronas (Background Jobs):** Celery & Celery Beat (Atualização de taxas de câmbio, cancelamento/expiração de transações/ofertas)
- **Documentação Interativa da API:** DRF Spectacular (OpenAPI 3 / Swagger)
- **Segurança:** SimpleJWT (JSON Web Tokens), Hashes Avançados via Argon2 & API Key Auth
- **Infraestrutura/Ambiente:** Docker & Docker Compose

---

## 🏛️ Arquitetura e Organização
O projeto foi totalmente refatorado seguindo os princípios de **Clean Architecture**, **SOLID** e **Clean Code**. Esta abordagem desacopla a lógica de negócio do framework (Django), facilitando a manutenção e a testabilidade, criando um fluxo unidirecional das regras da empresa.

### Estrutura de Pastas (por Módulo)
Cada módulo central (`users`, `offers`, `chat`, `notifications`, `rates`, `transactions`, `admin_api`, `security`, `audit`) segue o estrito padrão de portas e adaptadores:

1. **`domain/` (Coração do Sistema)**:
   - `entities.py`: Classes Python puras (POPOs - *Plain Old Python Objects*) que detêm o estado real livre do ORM do Django.
   - `interfaces.py`: Contratos abstratos (ABCs) para Repositórios e Interfaces de Serviços, os quais a infraestrutura implementará.
2. **`services/` (Casos de Uso)**:
   - `use_cases.py`: Orquestram a lógica da aplicação operando totalmente isolada, ligada apenas por Injeção de Dependências.
3. **`infra/` (Detalhes Técnicos)**:
   - `repositories.py`: Implementações dos contratos (Bases de Dados, Querysets e acoplamento ao ORM do Django).
   - `serializers.py`: Validação e transformação de dados que viajam para o exterior (DRF Validation).
   - `email_service.py` ou serviços externos como `Cloudinary`.
4. **`controllers/` (Interface de Entrada)**:
   - `views.py` / `urls.py`: Pontos de entrada baseados em DRF `APIView` ou `ViewSet` que recebem HTTP Requests, validam Serializers e Injetam as dependências para o Caso de Uso.
5. **`tests/` (Garantia de Qualidade)**:
   - `unit/`: Testes utilizando fixtures e Mocking.
   - `e2e/`: End-to-end tests integrados usando Banco de Dados the teste.

---

## 🧪 Testes e Qualidade
A API conta com uma suíte de testes automatizados construída sobre `pytest` e `pytest-django`, além de suporte para testes de carga com `Locust`.

### 1️⃣ Testes Automatizados (pytest)
```bash
# 1. Ativar o ambiente virtual (Windows)
.\venv\Scripts\activate

# 2. Executar a suíte completa com output verboso
pytest -v

# Apenas os testes unitários de um módulo (ex: users)
pytest users/tests/unit/ -v

# Apenas os testes end-to-end (e2e - Integração global total com o DB real/teste)
pytest offers/tests/e2e/ -v
```

### 2️⃣ Testes de Carga e Performance (Locust)
O projeto inclui o ficheiro `locustfile.py` para simular acessos concorrentes aos endpoints da API (autenticação, registo, perfis públicos).

```bash
# 1. Instalar o Locust (caso ainda não esteja instalado no ambiente virtual)
pip install locust

# 2. Iniciar a interface Web do Locust (Host padrão da API: http://localhost:8000)
locust -f locustfile.py --host=http://localhost:8000
# Ou simplesmente (estando na raiz do projeto):
locust

# 3. Aceder ao painel interativo no navegador:
# http://localhost:8089

# (Opcional) Executar testes em modo headless (sem interface gráfica):
locust -f locustfile.py --headless -u 10 -r 2 --run-time 1m --host=http://localhost:8000
```

### 3️⃣ Utilitários (Diagrama ERD & Superuser)
```bash
# Gerar diagrama de entidade-relacionamento (ERD)
venv\Scripts\python.exe manage.py graph_models -a -o erd.png
venv\Scripts\python.exe manage.py graph_models -a > erd.dot

# Criar Superusuário
venv\Scripts\python.exe manage.py createsuperuser
```

Super user: `romeucajamba07`
Email: `romeucajamba@gmail.com`
---

## ⚖️ Regras de Negócio Importantes
1. **Verificação (KYC):** Somente contas aprovadas pelo admin possuem acesso ao P2P para Publicar Ofertas ou Enviar Propostas (`is_verified` // `verification_status="approved"`).
2. **Geração the Usernames:** Identificadores únicos (`@username`) gerados automaticamente a partir do formulário de submissão do Nome Completo mitigando homónimos.
3. **Restrições de Sanção & Bloqueio:** Os admins podem `suspender temporariamente` ou `bloquear definitivamente` membros baseados no _Reporting System_.
4. **Ciclo P2P (Ofertas & Transacções):** Ofertas (`Ativa`, `Pausada`, `Expirada`, `Encerrada`). Interesses transitam de `pending` a `accepted` gerando `Transacções` via Chat Socket Rooms.
5. **Taxas e Câmbios:** Cotações globais integradas de provedores abertos auto atualizados periodicamente através de *Celery Beat*. 
6. **Real-Time WebSockets:** Chat point-to-point (P2P) assíncrono para agilizar transação fiduciária com notificação em painel (Push e DB).

---

## ⚙️ Variáveis de Ambiente Necessárias (o `env`)
Sempre crie um ficheiro **`.env`** na raiz. Os parâmetros essenciais incluem:
```ini
DEBUG=True
SECRET_KEY=sua-secret-key-secreta-do-django
FRONTEND_URL=http://localhost:5173

# BD Connection URI
DATABASE_URL=postgres://user:pass@host:port/dbname

# Broker (Websockets e Async Tasks)
REDIS_URL=redis://127.0.0.1:6379/1

# CLOUDINARY (Media Storage Hoster)
CLOUDINARY_CLOUD_NAME=nome_cloud
CLOUDINARY_API_KEY=0000000
CLOUDINARY_API_SECRET=xxxxxxxxxxxxxxxxxxxxx
```

---

## 🚀 Como Iniciar / Executar o Projeto Localmente

### Pré-requisitos Nativos
- **Python 3.10+** instalado
- Instâncias de **PostgreSQL** e **Redis** operando localmente no host.
- *Virtualenv* para a conteinerização das bibliotecas Python.

### 1️⃣ Inicialização do Core
Abra os terminais necessários e siga as etapas para uma instância **Dev Nativa**. (Windows / Unix)

```bash
# Iniciar repositório no virtual environment (Linux/Mac)
python -m venv venv
source venv/bin/activate
# ou Windows: .\venv\Scripts\activate

# Instalar pacotes de terceiros (DRF, Celery, psycopg2, Cloudinary...)
pip install -r requirements.txt

# Aplicar estruturas do domínio no Database ORM e rodar Scripts de Migração de Dados
python manage.py makemigrations
python manage.py migrate

# Criar Superusuário nativo para ter passe livre na App Administrativa (`/admin/` Django nativo & Painel React)
python manage.py createsuperuser

# Subir a API Django Rest (Host porting => 127.0.0.1:8000)
python manage.py runserver
```

### 2️⃣ Inicialização the Filas e Sockets Asíncronos (Celery Workers)
Para que o envio de emails em background, websockets push notification e os algoritmos que dão purge em DB log persistam atempadamente. *(Executar em 2 terminais separados e ter o serviço the servidor Redis activo no background na porta standard 6379).*

```bash
# TERMINAL 2: Iniciar o Worker Unit (Linux/Mac)
celery -A app worker -l info 
# IMPORTANTE: Se usar WINDOWS utilize o parametro --pool=solo!
celery -A app worker -l info --pool=solo

# TERMINAL 3: Agendador the Tasks 
celery -A app beat -l info
```

---

## 📖 Swagger e Exploração the Routas REST
Assim que todos os servidores locais estiverem _up_, consulte visualmente os Endpoints criados navegando para:
- **`http://localhost:8000/api/schema/swagger-ui/`** (Swagger Completo UI)

---
## 📜 Licença 
Este software backend e as suas respectivas bases core, são de modelo e propriedade fechados e pertecem apenas a **Romeu Cajamba**.