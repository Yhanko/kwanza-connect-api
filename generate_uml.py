import urllib.request
import json
import ssl

context = ssl._create_unverified_context()

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
    payload = json.dumps(data).encode('utf-8')
    req = urllib.request.Request(
        "https://kroki.io/",
        data=payload,
        headers={
            'Content-Type': 'application/json',
            'Accept': 'image/png',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    )
    
    print("Atualizando imagem...")
    with urllib.request.urlopen(req, context=context) as resp:
        with open(r"c:\pfc\yhanko\kwanzaConnect-project\kwanzaConnect-API\diagrama_uso.png", "wb") as f:
            f.write(resp.read())
            
    print("Imagem atualizada com sucesso sem o actor Sistema!")
except Exception as e:
    print("Erro durante a execucao:", e)
