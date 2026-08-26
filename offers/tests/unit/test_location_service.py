from unittest.mock import patch, Mock
import requests
from app.services.location_service import LocationService

def test_reverse_geocode_success():
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'address': {
            'city': 'Luanda',
            'state': 'Luanda'
        }
    }
    with patch('requests.get', return_value=mock_response):
        res = LocationService.reverse_geocode(-8.838333, 13.234444, timeout=5)
        assert res == 'Luanda'

def test_reverse_geocode_city_and_state():
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'address': {
            'town': 'Viana',
            'state': 'Luanda'
        }
    }
    with patch('requests.get', return_value=mock_response):
        res = LocationService.reverse_geocode(-8.91, 13.37, timeout=5)
        assert res == 'Viana - Luanda'

def test_reverse_geocode_timeout_returns_none():
    with patch('requests.get', side_effect=requests.Timeout("Connection timed out")):
        res = LocationService.reverse_geocode(-8.838333, 13.234444, timeout=1)
        assert res is None

def test_reverse_geocode_error_returns_none():
    with patch('requests.get', side_effect=requests.RequestException("Network error")):
        res = LocationService.reverse_geocode(-8.838333, 13.234444, timeout=1)
        assert res is None
