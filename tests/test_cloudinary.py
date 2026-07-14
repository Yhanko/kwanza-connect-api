import os
import django
import sys

# Configurar Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

import cloudinary.uploader
from app.services.cloudinary_storage import CloudinaryStorageService

def test_cloudinary():
    print("Iniciando teste do Cloudinary...")
    storage = CloudinaryStorageService()
    
    # Criar um pequeno buffer de imagem fake (1x1 pixel branco)
    # Mas para simplificar vamos apenas enviar uma string como se fosse um arquivo de texto
    # ou usar um link de imagem online
    
    test_content = b"KwanzaConnect Test File"
    try:
        url = storage.upload(test_content, "test-file", folder="tests")
        print(f"Sucesso! Ficheiro carregado em: {url}")
        assert url is not None
    except Exception as e:
        print(f"Erro no Cloudinary: {e}")
        assert False, f"Upload falhou: {e}"

if __name__ == "__main__":
    test_cloudinary()
