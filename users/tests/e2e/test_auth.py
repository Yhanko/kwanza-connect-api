from rest_framework import status
from rest_framework.test import APITestCase
from django.urls import reverse
from users.models import User

class TestAuthE2E(APITestCase):
    def test_user_registration_e2e(self):
        url = reverse('auth-register')
        data = {
            'email': 'newuser@example.com',
            'password': 'Password123!',
            'password_confirm': 'Password123!',
            'full_name': 'New User Test'
        }
        
        response = self.client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['data']['email'] == data['email']
        assert User.objects.filter(email=data['email']).exists()

    def test_user_login_e2e(self):
        # Setup: Create and verify user
        email = 'loginuser@example.com'
        password = 'Password123!'
        user = User.objects.create_user(email=email, password=password, full_name='Login User')
        user.is_active = True
        user.save()
        
        url = reverse('auth-login')
        data = {
            'email': email,
            'password': password
        }
        
        response = self.client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.data['data']
        assert 'refresh' in response.data['data']
