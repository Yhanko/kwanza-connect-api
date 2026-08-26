"""
Serviço de geolocalização e geocodificação reversa.
"""
import logging
from typing import Optional
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

class LocationService:
    @staticmethod
    def reverse_geocode(latitude: float, longitude: float, timeout: Optional[int] = None) -> Optional[str]:
        """
        Converte coordenadas latitude e longitude num nome legível de localização (Cidade/Município/Província).
        Trata excepções e timeouts graciosamente sem bloquear a aplicação.
        """
        if latitude is None or longitude is None:
            return None

        effective_timeout = timeout or getattr(settings, 'GEOLOCATION_TIMEOUT', 15)
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={latitude}&lon={longitude}&zoom=14&addressdetails=1"
        headers = {
            'User-Agent': 'KwanzaConnectAPI/1.0 (contact@kwanzaconnect.ao)'
        }

        try:
            response = requests.get(url, headers=headers, timeout=effective_timeout)
            if response.status_code == 200:
                data = response.json()
                address = data.get('address', {})
                
                city = (
                    address.get('city') or
                    address.get('town') or
                    address.get('municipality') or
                    address.get('suburb') or
                    address.get('county') or
                    address.get('state')
                )
                
                state = address.get('state') or address.get('region') or ''
                
                if city and state and city.lower() != state.lower():
                    return f"{city} - {state}"
                elif city:
                    return city
                elif state:
                    return state

        except requests.Timeout:
            logger.warning("LocationService: Timeout ao capturar localização para lat=%s, lon=%s (timeout=%ss)", latitude, longitude, effective_timeout)
        except requests.RequestException as exc:
            logger.warning("LocationService: Erro HTTP ao capturar localização: %s", exc)
        except Exception as exc:
            logger.warning("LocationService: Erro inesperado ao geocodificar coordenadas (%s, %s): %s", latitude, longitude, exc)

        return None
