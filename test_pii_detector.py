"""Teste o detector de PII"""
from smartrouter.pii_detector import contains_pii, detect_pii_types

xml = "<evtAdmissao><trabalhador><cpf>123.456.789-00</cpf></trabalhador></evtAdmissao>"

print("🔍 Testando detector de PII...")
print(f"XML: {xml}")
print(f"\nContém PII: {contains_pii(xml)}")
print(f"Tipos detectados: {detect_pii_types(xml)}")