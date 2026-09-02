import requests
import json
import os

uml_code = """@startuml
left to right direction
skinparam packageStyle rectangle
skinparam usecase {
    BackgroundColor #e1f5fe
    BorderColor #0288d1
}
skinparam actor {
    BackgroundColor white
}

actor "Utilizador\\nNão Verificado" as nao_verificado
actor "Utilizador\\nVerificado" as verificado

verificado --|> nao_verificado

rectangle "KwanzaConnect" {
  usecase "Registar e Entrar" as login
  usecase "Aceder ao Perfil" as perfil
  usecase "Alterar Senha" as senha
  usecase "Submeter Documentos (KYC)" as kyc
  
  usecase "Explorar Ofertas Disponíveis" as explorar
  usecase "Criar e Gerir Ofertas" as ofertas
  usecase "Expressar Interesse (Comprar)" as interesse
  usecase "Aceitar / Rejeitar Compradores" as aceitar
  usecase "Negociar no Chat (Privado)" as chat
  usecase "Marcar Transacao Concluida" as transacao
  usecase "Avaliar a Contraparte" as review
  usecase "Denunciar Perfis Suspeitos" as denunciar
}

nao_verificado --> login
nao_verificado --> perfil
nao_verificado --> senha
nao_verificado --> kyc

verificado --> explorar
verificado --> ofertas
verificado --> interesse
verificado --> aceitar
verificado --> chat
verificado --> transacao
verificado --> review
verificado --> denunciar

@enduml"""

data = {
    "diagram_source": uml_code,
    "diagram_type": "plantuml",
    "output_format": "png"
}

try:
    print("Atualizando imagem do diagrama UML...")
    resp = requests.post(
        "https://kroki.io/",
        json=data,
        headers={
            'Accept': 'image/png',
            'User-Agent': 'KwanzaConnect-UML-Generator/1.0'
        },
        timeout=30
    )
    resp.raise_for_status()
    output_path = os.path.join(os.path.dirname(__file__), "diagrama_uso.png")
    with open(output_path, "wb") as f:
        f.write(resp.content)
    print("Imagem atualizada com sucesso!")
except Exception as e:
    print("Erro durante a execucao:", e)

