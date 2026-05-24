"""
EII - Pipeline de Extracao e Geracao de Casos
Passo a passo do PDF oficial ate dataset final
"""

# ============================================================
# PASSO 1: Extrair do PDF oficial
# ============================================================

# Baixe o manual primeiro:
# wget https://www.gov.br/esocial/pt-br/documentacao-tecnica/manuais/mos-s-1-3-consolidada-ate-a-no-s-1-3-03-2025.pdf

# Rode o parser:
# python eii_pdf_parser.py --pdf "mos-s-1-3-consolidada.pdf" --output "casos_manual.json" --resumo

# Output esperado:
# [Parser] PDF aberto: mos-s-1-3-consolidada.pdf
# [Parser] Paginas: 900+
# [Parser] Processando pagina 1/900...
# [Parser] Processando pagina 51/900...
# ...
# [Parser] Total casos unicos: 450
# [Parser] Exportado: casos_manual.json
# [Parser] Exportado CSV: casos_manual.csv

# ============================================================
# PASSO 2: Gerar variacoes com Groq (bulk)
# ============================================================

import json
from groq import Groq
import os

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def gerar_variacoes_caso(caso_base: dict, n_variacoes: int = 5) -> list:
    """
    Gera N variacoes realistas de um caso base usando Groq.

    Input: caso extraido do manual
    Output: lista de casos variados (empresas diferentes, valores diferentes)
    """

    prompt = f"""Voce e um especialista em eSocial. 

Baseado nesta rejeicao oficial do Manual do eSocial:

CODIGO: {caso_base['codigo']}
DESCRICAO: {caso_base['descricao']}
ACAO SUGERIDA: {caso_base['acao_sugerida']}
EVENTOS AFETADOS: {', '.join(caso_base['eventos_afetados'])}
CATEGORIA: {caso_base['categoria']}

Gere EXATAMENTE {n_variacoes} casos REAIS e DIFERENTES que causariam esta MESMA rejeicao.

Regras:
1. Cada caso deve ter descricao UNICA (nao copie a original)
2. Varie: empresas de diferentes portes, setores, valores
3. Inclua XML snippet com o erro especifico
4. Forneca ground truth completo de correcao
5. Mantenha o mesmo codigo de rejeicao

Formato de saida (JSON):
[
  {{
    "question": "como o usuario descreveria o problema",
    "xml_snippet": "<tag>valor_errado</tag>",
    "ground_truth": "passos detalhados para corrigir",
    "contexto_empresa": "empresa ficticia, setor, porte"
  }},
  ...
]

Responda APENAS com o JSON valido."""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=2000,
        )

        content = response.choices[0].message.content

        # Extrair JSON da resposta
        import re
        json_match = re.search(r'\[.*\]', content, re.DOTALL)
        if json_match:
            variacoes = json.loads(json_match.group())

            # Adicionar metadados
            for v in variacoes:
                v["rejection_code"] = caso_base["codigo"]
                v["event_type"] = caso_base["eventos_afetados"][0] if caso_base["eventos_afetados"] else "S-GERAL"
                v["categoria"] = caso_base["categoria"]
                v["complexidade"] = caso_base["complexidade"]
                v["fonte"] = f"Gerado a partir de: {caso_base['fonte']}"
                v["original_caso_id"] = caso_base.get("codigo", "")

            return variacoes

    except Exception as e:
        print(f"Erro ao gerar variacoes para {caso_base['codigo']}: {e}")
        return []

    return []


def pipeline_geracao_bulk(casos_base: list, variacoes_por_caso: int = 5) -> list:
    """
    Gera dataset bulk a partir dos casos extraidos do manual.

    Args:
        casos_base: Lista de casos do parser PDF
        variacoes_por_caso: Quantas variacoes gerar por caso

    Returns:
        Dataset completo (casos originais + variacoes)
    """
    dataset_final = []

    # Adicionar casos originais
    for caso in casos_base:
        dataset_final.append({
            "question": caso["descricao"],
            "rejection_code": caso["codigo"],
            "event_type": caso["eventos_afetados"][0] if caso["eventos_afetados"] else "S-GERAL",
            "ground_truth": caso["acao_sugerida"],
            "categoria": caso["categoria"],
            "complexidade": caso["complexidade"],
            "fonte": caso["fonte"],
            "tipo": "original_manual",
        })

    # Gerar variacoes (com rate limiting)
    import time

    for i, caso in enumerate(casos_base):
        print(f"Gerando variacoes {i+1}/{len(casos_base)}: {caso['codigo']}")

        variacoes = gerar_variacoes_caso(caso, n_variacoes=variacoes_por_caso)

        for v in variacoes:
            v["tipo"] = "variacao_sintetica"
            dataset_final.append(v)

        # Rate limit: esperar entre chamadas
        if i < len(casos_base) - 1:
            time.sleep(2)

    return dataset_final


# ============================================================
# PASSO 3: Curadoria e validacao
# ============================================================

def curadoria_dataset(dataset: list) -> list:
    """
    Filtra e valida dataset gerado.

    Regras:
    - Remover duplicatas (mesmo rejection_code + question similar)
    - Validar codigos de rejeicao conhecidos
    - Garantir ground_truth nao vazio
    - Balancear por categoria
    """
    from difflib import SequenceMatcher

    def similar(a, b):
        return SequenceMatcher(None, a, b).ratio() > 0.85

    # Remover duplicatas
    unicos = []
    for caso in dataset:
        if not any(similar(caso["question"], u["question"]) for u in unicos):
            unicos.append(caso)

    # Validar
    validos = []
    for caso in unicos:
        if (caso.get("ground_truth") and 
            len(caso["ground_truth"]) > 20 and
            caso["rejection_code"].isdigit()):
            validos.append(caso)

    print(f"Curadoria: {len(dataset)} -> {len(unicos)} unicos -> {len(validos)} validos")

    return validos


# ============================================================
# PIPELINE COMPLETO
# ============================================================

if __name__ == "__main__":
    # 1. Carregar casos do manual
    with open("casos_manual.json", "r", encoding="utf-8") as f:
        casos_manual = json.load(f)["casos"]

    print(f"Casos do manual: {len(casos_manual)}")

    # 2. Gerar variacoes (meta: 500 casos finais)
    # Se temos 100 casos do manual, geramos 4 variacoes cada = 500
    n_variacoes = max(1, (500 // len(casos_manual)) - 1)

    dataset_bulk = pipeline_geracao_bulk(casos_manual, variacoes_por_caso=n_variacoes)

    # 3. Curadoria
    dataset_final = curadoria_dataset(dataset_bulk)

    # 4. Exportar
    with open("eii_dataset_500.json", "w", encoding="utf-8") as f:
        json.dump(dataset_final, f, indent=2, ensure_ascii=False)

    print(f"\nDataset final: {len(dataset_final)} casos")
    print("Salvo em: eii_dataset_500.json")

    # 5. Estatisticas
    from collections import Counter
    cats = Counter(c["categoria"] for c in dataset_final)
    comps = Counter(c["complexidade"] for c in dataset_final)

    print("\nPor categoria:")
    for cat, count in cats.most_common():
        print(f"  {cat}: {count}")

    print("\nPor complexidade:")
    for comp, count in comps.most_common():
        print(f"  {comp}: {count}")
