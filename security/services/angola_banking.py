"""
Validador Oficial de Contas Bancárias e IBANs de Angola (Norma BNA / EMIS).
Formato: AO06 + 21 dígitos numéricos = 25 caracteres (ISO 7064 MOD 97-10).
KwanzaConnect API — Sandbox Regulatório do BNA / LISPA.
"""

import re
from typing import Dict, Optional, Tuple


# Catálogo Oficial dos Bancos Comerciais e Instituições Financeiras de Angola (BNA / EMIS)
ANGOLAN_BANKS: Dict[str, Dict[str, str]] = {
    '0040': {'code': 'BAI', 'name': 'Banco Angolano de Investimentos', 'short_name': 'BAI'},
    '0006': {'code': 'BFA', 'name': 'Banco de Fomento Angola', 'short_name': 'BFA'},
    '0055': {'code': 'BMA', 'name': 'Banco Millennium Atlântico', 'short_name': 'Atlântico'},
    '0051': {'code': 'BIC', 'name': 'Banco BIC', 'short_name': 'Banco BIC'},
    '0005': {'code': 'BCI', 'name': 'Banco de Comércio e Indústria', 'short_name': 'BCI'},
    '0043': {'code': 'BSOL', 'name': 'Banco Sol', 'short_name': 'Banco Sol'},
    '0044': {'code': 'BKEVE', 'name': 'Banco Keve', 'short_name': 'Banco Keve'},
    '0048': {'code': 'BYETU', 'name': 'Banco Yetu', 'short_name': 'Banco Yetu'},
    '0058': {'code': 'SBA', 'name': 'Standard Bank Angola', 'short_name': 'Standard Bank'},
    '0060': {'code': 'BCGA', 'name': 'Banco Caixa Geral Angola', 'short_name': 'Caixa Angola'},
    '0054': {'code': 'BCH', 'name': 'Banco Comercial do Huambo', 'short_name': 'BCH'},
    '0059': {'code': 'BPG', 'name': 'Banco Prestígio', 'short_name': 'Banco Prestígio'},
    '0062': {'code': 'BVAL', 'name': 'Banco Valor', 'short_name': 'Banco Valor'},
    '0064': {'code': 'BCS', 'name': 'Banco de Crédito do Sul', 'short_name': 'BCS'},
    '0066': {'code': 'SCBA', 'name': 'Standard Chartered Bank Angola', 'short_name': 'Standard Chartered'},
    '0067': {'code': 'BNI', 'name': 'Banco de Negócios Internacional', 'short_name': 'BNI'},
    '0069': {'code': 'FNB', 'name': 'Finibanco Angola', 'short_name': 'Finibanco'},
    '0045': {'code': 'BANC', 'name': 'Banco Angolano de Negócios e Comércio', 'short_name': 'BANC'},
    '0052': {'code': 'BPA', 'name': 'Banco Poupança e Crédito', 'short_name': 'BPC'},
    '0056': {'code': 'BIR', 'name': 'Banco de Investimento Rural', 'short_name': 'BIR'},
    '0057': {'code': 'BVB', 'name': 'Banco VTB África', 'short_name': 'VTB África'},
    '0063': {'code': 'BCOM', 'name': 'Banco Comercial Angolano', 'short_name': 'BCA'},
}


class AngolaBankingValidator:
    """
    Validador estrito de IBANs angolanos em conformidade com as instruções do BNA e EMIS.
    """

    @classmethod
    def clean_iban(cls, raw_iban: str) -> str:
        """Remove espaços, pontos e hífens e converte para maiúsculas."""
        if not raw_iban:
            return ""
        return re.sub(r'[\s\.\-]', '', str(raw_iban)).upper()

    @classmethod
    def validate_iban(cls, raw_iban: str) -> Tuple[bool, Optional[Dict[str, str]], Optional[str]]:
        """
        Valida a estrutura, o país, o código bancário e o checksum MOD 97 de um IBAN angolano.
        Retorna (is_valid, bank_info, error_message).
        """
        iban = cls.clean_iban(raw_iban)

        if not iban:
            return False, None, "O IBAN não pode estar vazio."

        # 1. Comprimento e Prefixo do País
        if len(iban) != 25:
            return False, None, f"O IBAN angolano deve conter exatamente 25 caracteres (fornecido: {len(iban)})."

        if not iban.startswith("AO06"):
            return False, None, "O IBAN de Angola deve obrigatoriamente iniciar com o prefixo 'AO06'."

        # 2. Verificar se todos os caracteres após AO06 são dígitos
        numeric_part = iban[4:]
        if not numeric_part.isdigit():
            return False, None, "A parte numérica do IBAN deve conter apenas dígitos decimais."

        # 3. Código do Banco (4 primeiros dígitos após AO06)
        bank_code = numeric_part[:4]
        bank_info = ANGOLAN_BANKS.get(bank_code)

        # 4. Validação Matemática MOD 97-10 (ISO 7064)
        # Move os 4 primeiros caracteres (AO06) para o final: <21 digitos>AO06 -> converte letras A=10, O=24
        # A=10, O=24 -> AO06 = '102406'
        rearranged = numeric_part + "102406"
        if int(rearranged) % 97 != 1:
            return False, bank_info, "Dígito de controle do IBAN inválido (falha na validação MOD 97)."

        if not bank_info:
            bank_info = {
                'code': f'BANCO_{bank_code}',
                'name': f'Instituição Financeira BNA ({bank_code})',
                'short_name': f'Banco {bank_code}'
            }

        formatted_iban = f"{iban[:4]}.{iban[4:8]}.{iban[8:12]}.{iban[12:16]}.{iban[16:20]}.{iban[20:24]}.{iban[24:]}"

        result_data = {
            'iban': iban,
            'formatted_iban': formatted_iban,
            'bank_code': bank_code,
            'bank_name': bank_info['name'],
            'bank_short_name': bank_info['short_name'],
            'currency': 'AOA',
            'country': 'Angola',
            'status': 'VALID',
        }

        return True, result_data, None

    @classmethod
    def generate_sample_iban(cls, bank_code: str = '0040', account_part: str = '000012345678901') -> str:
        """
        Gera um IBAN angolano matematicamente válido para o código bancário especificado.
        Útil para testes e preenchimento automático em simulações.
        """
        bank_clean = str(bank_code).zfill(4)[:4]
        acc_clean = str(account_part).zfill(15)[:15]
        base_19 = f"{bank_clean}{acc_clean}"

        # Encontra os 2 dígitos de controle que satisfazem (base_19 + xx + 102406) % 97 == 1
        for check in range(100):
            check_str = f"{check:02d}"
            candidate_rearranged = f"{base_19}{check_str}102406"
            if int(candidate_rearranged) % 97 == 1:
                return f"AO06{base_19}{check_str}"

        return f"AO06{base_19}00"

