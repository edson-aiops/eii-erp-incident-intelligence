import re
from typing import Dict

# Padrões de PII (CPF, CNPJ, NIS, Nome)
PII_PATTERNS = {
    "CPF": r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b",
    "CNPJ": r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b",
    "NIS": r"\b\d{3}\.?\d{5}\.?\d{2}-?\d\b",
    "NOME": r"<nmTrab>([^<]+)</nmTrab>",
    "CPF_TRAB": r"<cpfTrab>([^<]+)</cpfTrab>"
}

REPLACEMENTS = {
    "CPF": "***.***.***-**",
    "CNPJ": "**.***.***/****-**",
    "NIS": "***.*****.**-#",
    "NOME": "<nmTrab>[REDACTED]</nmTrab>",
    "CPF_TRAB": "<cpfTrab>***.***.***-**</cpfTrab>"
}

def scrub_pii(xml: str) -> tuple[str, Dict[str, int]]:
    """
    Sanitiza dados sensíveis no XML antes do envio para cloud.
    Retorna: (xml_limpo, dict_com_contagem_de_PIIs_encontradas)
    """
    counts = {k: 0 for k in PII_PATTERNS}
    cleaned = xml
    
    for tipo, pattern in PII_PATTERNS.items():
        matches = re.findall(pattern, cleaned)
        counts[tipo] = len(matches)
        if matches:
            cleaned = re.sub(pattern, REPLACEMENTS[tipo], cleaned)
            
    return cleaned, counts
