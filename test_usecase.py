import sys
import os
import django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")
django.setup()

import uuid
from offers.services.use_cases import ExpressInterestUseCase
from offers.infra.repositories import DjangoOfferRepository
from rest_framework.exceptions import ValidationError, NotFound

repo = DjangoOfferRepository()
use_case = ExpressInterestUseCase(repo)

# Offer ID from user
offer_id = uuid.UUID('b74fb9c8-8c66-4dde-88b1-c356cb328bc8')

# Random user ID to simulate "outro usuário logado"
user_id = uuid.uuid4()

try:
    use_case.execute(user_id=user_id, offer_id=offer_id, message="Test message")
    print("SUCCESS")
except ValidationError as e:
    print("VALIDATION ERROR:", e.detail)
except NotFound as e:
    print("NOT FOUND ERROR:", e.detail)
except Exception as e:
    print("UNEXPECTED ERROR:", str(e))
