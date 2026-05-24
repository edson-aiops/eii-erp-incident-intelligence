
"""
EII - Gerador de Variações por Templates
Gera milhares de casos sintéticos a partir dos 428 casos base
Sem LLM, sem rate limit, sem custo

Uso:
    python eii_gerador_templates.py --input data/casos_manual.json --output data/dataset_templates.json --variacoes 5

Tempo estimado: 5 minutos para 2000+ casos
"""

import json
import random
import argparse
from datetime import datetime
from pathlib import Path
from collections import Counter
from typing import List, Dict, Any


# ============================================================
# BANCO DE DADOS PARA VARIAÇÕES REALISTAS
# ============================================================

EMPRESAS_FICTICIAS = [
    {"nome": "Indústria São Paulo Ltda", "porte": "grande", "setor": "indústria", "cnpj_base": "12345678"},
    {"nome": "Comércio Rio Preto S.A.", "porte": "médio", "setor": "comércio", "cnpj_base": "87654321"},
    {"nome": "Tech Solutions ME", "porte": "pequeno", "setor": "tecnologia", "cnpj_base": "11223344"},
    {"nome": "Construtora Horizonte Ltda", "porte": "grande", "setor": "construção", "cnpj_base": "55667788"},
    {"nome": "Clínica Bem Estar SS", "porte": "pequeno", "setor": "saúde", "cnpj_base": "99887766"},
    {"nome": "Transporte Rápido S.A.", "porte": "médio", "setor": "transporte", "cnpj_base": "44332211"},
    {"nome": "Educação Futuro ME", "porte": "pequeno", "setor": "educação", "cnpj_base": "66778899"},
    {"nome": "Agropecuária Verde Ltda", "porte": "grande", "setor": "agronegócio", "cnpj_base": "33445566"},
]

NOMES_FUNCIONARIOS = [
    "João Silva", "Maria Santos", "Pedro Oliveira", "Ana Costa", "Carlos Lima",
    "Fernanda Souza", "Roberto Almeida", "Juliana Pereira", "Marcos Rodrigues", "Patrícia Gomes",
    "Lucas Fernandes", "Amanda Ribeiro", "Bruno Martins", "Camila Dias", "Diego Carvalho",
]

MATRICULAS = ["001", "002", "123", "456", "789", "1000", "2025", "9999", "0001", "5555"]

CARGOS = [
    "Analista de RH", "Assistente Administrativo", "Gerente de TI", "Operador de Máquinas",
    "Vendedor", "Enfermeiro", "Motorista", "Professor", "Engenheiro", "Contador",
]

VALORES_SALARIO = ["1500.00", "2500.50", "3500.00", "4800.75", "5200.00", "6800.25", "8500.00", "12000.00"]

DATAS = ["2025-01-15", "2025-02-01", "2025-03-10", "2024-12-20", "2025-04-05"]

CNPJS_ERRADOS = [
    "12.345.678/0001-90",      # com formatação
    "12345678000190",          # sem formatação mas inválido
    "1234567",                  # curto
    "123456789012345",          # longo
    "ABCDEFGH",                 # letras
    "00000000",                 # zeros
    "11111111",                 # repetido
    "",                         # vazio
]

DATAS_ERRADAS = [
    "15/01/2025",               # formato BR
    "2025-1-5",                 # sem zero
    "2025-13-01",               # mês inválido
    "2025-01-32",               # dia inválido
    "01-15-2025",               # formato US
    "2025/01/15",               # barras
]

VALORES_ERRADOS = [
    "1.500,00",                 # formato BR
    "1500",                     # sem centavos
    "1500.5",                   # um decimal
    "1500.000",                 # três decimais
    "mil e quinhentos",         # por extenso
    "-1500.00",                 # negativo
]

TAGS_XML = {
    "identificacao": ["ideEmpregador", "tpInsc", "nrInsc", "ideTransmissor"],
    "remuneracao": ["vlrRemun", "itensRemun", "codRubr", "vrRubr", "tpRubr"],
    "admissao": ["matricula", "dtAdm", "tpRegTrab", "tpRegPrev", "cadIni"],
    "desligamento": ["dtDeslig", "mtvDeslig", "dtProjFimAPI", "indPagtoAPI"],
    "afastamento": ["dtIniAfast", "dtTermAfast", "codMotAfast"],
    "folha": ["perApur", "indGuia", "nrReciboAnt"],
    "beneficios": ["cpfBenef", "nmBenefic", "dtNascto"],
    "fgts": ["tpLancto", "nrDoc", "dtVenc"],
}


# ============================================================
# FUNÇÕES DE GERAÇÃO POR CATEGORIA
# ============================================================

def gerar_variacoes_identificacao(caso_base: Dict, n: int) -> List[Dict]:
    """Gera variações de erros de identificação (CNPJ, CEI, etc.)."""
    variacoes = []

    for i in range(n):
        emp = random.choice(EMPRESAS_FICTICIAS)
        cnpj_errado = random.choice(CNPJS_ERRADOS)
        tag = random.choice(TAGS_XML["identificacao"])

        # Variação 1: CNPJ com formatação
        if i % 4 == 0:
            desc = f"Empresa {emp['nome']} ({emp['porte']}, {emp['setor']}) tentou enviar CNPJ com pontos e traços: {cnpj_errado}"
            xml = f"<{tag}>{cnpj_errado}</{tag}>"
            gt = f"1. Remover toda formatação do CNPJ\n2. Usar apenas 8 dígitos do CNPJ base: {emp['cnpj_base']}\n3. Completar com 6 zeros: {emp['cnpj_base']}000000\n4. Validar no campo {tag}"

        # Variação 2: CNPJ curto
        elif i % 4 == 1:
            desc = f"{emp['nome']} informou CNPJ incompleto no evento"
            xml = f"<{tag}>{emp['cnpj_base'][:6]}</{tag}>"
            gt = f"1. Verificar CNPJ completo da empresa\n2. Informar 8 dígitos do CNPJ base: {emp['cnpj_base']}\n3. Completar com zeros: {emp['cnpj_base']}000000"

        # Variação 3: CNPJ com letras
        elif i % 4 == 2:
            desc = f"Erro de digitação no CNPJ da empresa {emp['nome']}"
            xml = f"<{tag}>{emp['cnpj_base'][:4]}ABCD</{tag}>"
            gt = f"1. Corrigir CNPJ - remover letras\n2. Usar apenas números: {emp['cnpj_base']}\n3. Total 14 dígitos: {emp['cnpj_base']}000000"

        # Variação 4: CNPJ de outra empresa
        else:
            outro_cnpj = random.choice([e for e in EMPRESAS_FICTICIAS if e['cnpj_base'] != emp['cnpj_base']])
            desc = f"CNPJ informado pertence a outra empresa ({outro_cnpj['nome']})"
            xml = f"<{tag}>{outro_cnpj['cnpj_base']}000000</{tag}>"
            gt = f"1. Verificar CNPJ correto da empresa atual\n2. Usar CNPJ base: {emp['cnpj_base']}\n3. Não usar CNPJ de {outro_cnpj['nome']}"

        variacoes.append({
            "question": desc,
            "rejection_code": caso_base["codigo"],
            "event_type": caso_base["eventos_afetados"][0] if caso_base["eventos_afetados"] else "S-2200",
            "ground_truth": gt,
            "xml_snippet": xml,
            "categoria": "identificacao",
            "complexidade": caso_base["complexidade"],
            "contexto_empresa": emp["nome"],
            "tipo": "variacao_template",
        })

    return variacoes


def gerar_variacoes_remuneracao(caso_base: Dict, n: int) -> List[Dict]:
    """Gera variações de erros de remuneração."""
    variacoes = []

    for i in range(n):
        emp = random.choice(EMPRESAS_FICTICIAS)
        func = random.choice(NOMES_FUNCIONARIOS)
        salario = random.choice(VALORES_SALARIO)
        valor_errado = random.choice(VALORES_ERRADOS)
        tag = random.choice(TAGS_XML["remuneracao"])

        if i % 3 == 0:
            desc = f"Funcionário {func} da {emp['nome']} com salário informado no formato errado: {valor_errado}"
            xml = f"<{tag}>{valor_errado}</{tag}>"
            gt = f"1. Converter para formato correto: ponto decimal, 2 casas\n2. Valor correto: {salario}\n3. Exemplo: <{tag}>{salario}</{tag}>"

        elif i % 3 == 1:
            desc = f"Soma das rubricas não bate com total de remuneração no S-1200 da {emp['nome']}"
            xml = f"<vlrRemun>{salario}</vlrRemun><itensRemun><vrRubr>{valor_errado}</vrRubr></itensRemun>"
            gt = f"1. Somar todas as rubricas individualmente\n2. Comparar com vlrRemun total\n3. Ajustar para: {salario}\n4. Verificar pro-rata se mudança salarial no mês"

        else:
            desc = f"Valor negativo informado para remuneração de {func}"
            xml = f"<{tag}>-{salario}</{tag}>"
            gt = f"1. Remover sinal negativo\n2. Valor deve ser positivo: {salario}\n3. Verificar se não houve estorno indevido"

        variacoes.append({
            "question": desc,
            "rejection_code": caso_base["codigo"],
            "event_type": caso_base["eventos_afetados"][0] if caso_base["eventos_afetados"] else "S-1200",
            "ground_truth": gt,
            "xml_snippet": xml,
            "categoria": "remuneracao",
            "complexidade": caso_base["complexidade"],
            "contexto_empresa": emp["nome"],
            "tipo": "variacao_template",
        })

    return variacoes


def gerar_variacoes_admissao(caso_base: Dict, n: int) -> List[Dict]:
    """Gera variações de erros de admissão."""
    variacoes = []

    for i in range(n):
        emp = random.choice(EMPRESAS_FICTICIAS)
        func = random.choice(NOMES_FUNCIONARIOS)
        matricula = random.choice(MATRICULAS)
        data = random.choice(DATAS)
        data_errada = random.choice(DATAS_ERRADAS)

        if i % 3 == 0:
            desc = f"Data de admissão de {func} no formato brasileiro: {data_errada}"
            xml = f"<dtAdm>{data_errada}</dtAdm>"
            gt = f"1. Converter para formato AAAA-MM-DD\n2. Data correta: {data}\n3. Exemplo: <dtAdm>{data}</dtAdm>"

        elif i % 3 == 1:
            desc = f"Matrícula {matricula} já existe para outro funcionário na {emp['nome']}"
            xml = f"<matricula>{matricula}</matricula>"
            gt = f"1. Verificar se matrícula já está em uso\n2. Gerar nova matrícula única\n3. Sugestão: usar número sequencial maior que último cadastrado"

        else:
            desc = f"Admissão de {func} com data posterior ao início das atividades da empresa"
            xml = f"<dtAdm>2026-01-01</dtAdm>"
            gt = f"1. Verificar data de início de atividades da empresa\n2. Data de admissão deve ser igual ou posterior\n3. Data correta: {data}"

        variacoes.append({
            "question": desc,
            "rejection_code": caso_base["codigo"],
            "event_type": caso_base["eventos_afetados"][0] if caso_base["eventos_afetados"] else "S-2200",
            "ground_truth": gt,
            "xml_snippet": xml,
            "categoria": "admissao",
            "complexidade": caso_base["complexidade"],
            "contexto_empresa": emp["nome"],
            "tipo": "variacao_template",
        })

    return variacoes


def gerar_variacoes_genericas(caso_base: Dict, n: int) -> List[Dict]:
    """Gera variações genéricas para categorias menos comuns."""
    variacoes = []
    categoria = caso_base.get("categoria", "outros")

    for i in range(n):
        emp = random.choice(EMPRESAS_FICTICIAS)
        func = random.choice(NOMES_FUNCIONARIOS)

        desc = f"Erro {caso_base['codigo']} na {emp['nome']}: {caso_base['descricao']} - funcionário {func}"
        gt = caso_base.get("acao_sugerida", "Verificar manual eSocial")

        if categoria in TAGS_XML:
            tag = random.choice(TAGS_XML[categoria])
            xml = f"<{tag}>VALOR_ERRADO_{i}</{tag}>"
        else:
            xml = f"<tag>ERRO_{caso_base['codigo']}</tag>"

        variacoes.append({
            "question": desc,
            "rejection_code": caso_base["codigo"],
            "event_type": caso_base["eventos_afetados"][0] if caso_base["eventos_afetados"] else "S-GERAL",
            "ground_truth": gt,
            "xml_snippet": xml,
            "categoria": categoria,
            "complexidade": caso_base["complexidade"],
            "contexto_empresa": emp["nome"],
            "tipo": "variacao_template",
        })

    return variacoes


# ============================================================
# GERADOR PRINCIPAL
# ============================================================

def gerar_dataset(casos_base: List[Dict], variacoes_por_caso: int = 5) -> List[Dict]:
    """Gera dataset completo com variações por templates."""
    dataset = []

    # Adicionar casos originais
    for caso in casos_base:
        dataset.append({
            "question": caso["descricao"],
            "rejection_code": caso["codigo"],
            "event_type": caso["eventos_afetados"][0] if caso["eventos_afetados"] else "S-GERAL",
            "ground_truth": caso["acao_sugerida"],
            "categoria": caso["categoria"],
            "complexidade": caso["complexidade"],
            "xml_tag": caso.get("xml_tag"),
            "fonte": caso["fonte"],
            "tipo": "original_manual",
            "pagina": caso.get("pagina"),
        })

    # Gerar variações por categoria
    geradores = {
        "identificacao": gerar_variacoes_identificacao,
        "remuneracao": gerar_variacoes_remuneracao,
        "admissao": gerar_variacoes_admissao,
    }

    for caso in casos_base:
        cat = caso.get("categoria", "outros")

        if cat in geradores:
            variacoes = geradores[cat](caso, variacoes_por_caso)
        else:
            variacoes = gerar_variacoes_genericas(caso, variacoes_por_caso)

        dataset.extend(variacoes)

    return dataset


def main():
    parser = argparse.ArgumentParser(description="Gerador de variações por templates")
    parser.add_argument("--input", default="data/casos_manual.json", help="JSON com casos base")
    parser.add_argument("--output", default="data/dataset_templates.json", help="JSON de saída")
    parser.add_argument("--variacoes", type=int, default=5, help="Variações por caso")
    parser.add_argument("--seed", type=int, default=42, help="Seed para reproducibilidade")
    args = parser.parse_args()

    random.seed(args.seed)

    # Carregar casos base
    print("[Gerador] Carregando casos base...")
    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    casos_base = data["casos"]
    print(f"[Gerador] Casos base: {len(casos_base)}")

    # Gerar dataset
    print(f"[Gerador] Gerando {args.variacoes} variações por caso...")
    inicio = datetime.now()
    dataset = gerar_dataset(casos_base, args.variacoes)
    tempo = (datetime.now() - inicio).total_seconds()

    # Estatísticas
    cats = Counter(c["categoria"] for c in dataset)
    tipos = Counter(c.get("tipo", "unknown") for c in dataset)

    # Salvar
    output = {
        "meta": {
            "fonte": "EII Dataset Templates",
            "data_geracao": datetime.now().isoformat(),
            "casos_base": len(casos_base),
            "variacoes_por_caso": args.variacoes,
            "total_casos": len(dataset),
            "tempo_segundos": round(tempo, 1),
            "seed": args.seed,
        },
        "casos": dataset,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # Resumo
    print("\n" + "="*60)
    print("DATASET TEMPLATES - RESUMO FINAL")
    print("="*60)
    print(f"Total casos: {len(dataset)}")
    print(f"  Originais: {tipos.get('original_manual', 0)}")
    print(f"  Variações: {tipos.get('variacao_template', 0)}")
    print(f"\nPor categoria:")
    for cat, n in cats.most_common():
        print(f"  {cat}: {n}")
    print(f"\nTempo: {tempo:.1f} segundos")
    print(f"Arquivo: {args.output}")
    print(f"Tamanho: {Path(args.output).stat().st_size / 1024:.1f} KB")
    print("="*60)


if __name__ == "__main__":
    main()
