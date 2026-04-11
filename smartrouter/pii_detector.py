"""
Detector Leve de PII para Roteamento LGPD
Identifica CPF, NIS, Email, Telefone sem modificar o conteúdo original.
"""

import re
import logging

logger = logging.getLogger(__name__)

# Padrões brasileiros comuns (sem modificar, só detectar)
PII_PATTERNS = [
    r'\b\d{3}\.\d{3}\.\d{3}-\d{2}\b',           # CPF formatado
    r'\b\d{11}\b',                                # NIS / CPF raw (11 dígitos)
    r'\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b',      # CNPJ
    r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', # Email
    r'\(?\d{2}\)?\s?\d{4,5}-?\d{4}',             # Telefone
    r'\b\d{5}-\d{3}\b',                           # CEP
]

COMPILED_PATTERNS = [re.compile(p) for p in PII_PATTERNS]

def contains_pii(text: str, threshold: float = 0.0) -> bool:
    """
    Verifica se o texto contém PII.
    threshold: % mínima de caracteres sensíveis para flagrar (0.0 = qualquer match)
    """
    if not text or len(text) < 5:
        return False
    
    text_str = str(text)
    
    # Busca rápida
    for pattern in COMPILED_PATTERNS:
        if pattern.search(text_str):
            logger.debug(f"PII detectado: {pattern.pattern}")
            return True
    
    # Heurística adicional: muitos dígitos consecutivos (possível ID sensível)
    digit_ratio = sum(c.isdigit() for c in text_str) / len(text_str)
    if digit_ratio > 0.6 and len(text_str) > 20:
        logger.debug(f"Alta densidade numérica detectada ({digit_ratio:.1%})")
        return True
    
    return False

def get_pii_summary(text: str) -> dict:
    """Retorna resumo dos tipos de PII encontrados"""
    found = []
    for pattern in COMPILED_PATTERNS:
        matches = pattern.findall(str(text))
        if matches:
            found.append({"pattern": pattern.pattern, "count": len(matches)})
    return {"has_pii": len(found) > 0, "types": found}