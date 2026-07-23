import sys
import os
import django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")
django.setup()

from offers.infra.serializers import OfferInterestCreateSerializer

data = {}
serializer = OfferInterestCreateSerializer(data=data)
is_valid = serializer.is_valid()
print("IS VALID:", is_valid)
if not is_valid:
    print("ERRORS:", serializer.errors)
