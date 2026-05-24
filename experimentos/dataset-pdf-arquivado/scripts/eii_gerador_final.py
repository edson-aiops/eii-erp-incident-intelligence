
"""
EII - Gerador Final: High/Critical + Afastamento/Folha
Gera 200+ casos complexos e 100+ casos de categorias sub-representadas
Integra ao dataset existente de 2568 casos

Uso:
    python eii_gerador_final.py --input data/dataset_templates.json --output data/dataset_final.json

Output: Dataset final ~3000 casos balanceado
"""

import json
import random
import argparse
from datetime import datetime
from collections import Counter
from typing import List, Dict


# ============================================================
# BANCO DE DADOS PARA CASOS COMPLEXOS
# ============================================================

EMPRESAS_COMPLEXAS = [
    {"nome": "Multinacional Brasil Holdings S.A.", "porte": "grande", "setor": "industria", "filiais": 5},
    {"nome": "Grupo Economico Alpha Ltda", "porte": "grande", "setor": "holding", "empresas": 12},
    {"nome": "Construtora Mega Obra S.A.", "porte": "grande", "setor": "construcao", "obras": 45},
    {"nome": "Hospital Rede Saude SS", "porte": "grande", "setor": "saude", "unidades": 8},
    {"nome": "Transportadora Nacional S.A.", "porte": "grande", "setor": "transporte", "frota": 2000},
]

FUNCIONARIOS_COMPLEXOS = [
    {"nome": "Joao Silva", "cargo": "Diretor", "salario": 25000.00, "admissao": "2015-03-10", "vinculos": 2},
    {"nome": "Maria Santos", "cargo": "Gerente", "salario": 18000.00, "admissao": "2018-07-22", "vinculos": 1},
    {"nome": "Pedro Oliveira", "cargo": "Especialista", "salario": 12000.00, "admissao": "2020-01-15", "vinculos": 3},
    {"nome": "Ana Costa", "cargo": "Analista Senior", "salario": 9500.00, "admissao": "2019-11-05", "vinculos": 1},
    {"nome": "Carlos Lima", "cargo": "Coordenador", "salario": 14000.00, "admissao": "2017-04-18", "vinculos": 2},
]


# ============================================================
# GERADORES DE CASOS COMPLEXOS (HIGH/CRITICAL)
# ============================================================

def gerar_pro_rata(n: int = 50) -> List[Dict]:
    """Gera casos de pro-rata (high complexity)."""
    casos = []

    for i in range(n):
        emp = random.choice(EMPRESAS_COMPLEXAS)
        func = random.choice(FUNCIONARIOS_COMPLEXOS)

        # Variacoes de pro-rata
        cenarios = [
            {
                "desc": f"Funcionario {func['nome']} teve aumento salarial no meio do mes. Antes: R$ {func['salario']*0.8:.2f}, Depois: R$ {func['salario']:.2f}. Como calcular pro-rata no S-1200?",
                "gt": f"1. Calcular dias no salario antigo: R$ {func['salario']*0.8:.2f} / 30 * dias_antigos\n2. Calcular dias no salario novo: R$ {func['salario']:.2f} / 30 * dias_novos\n3. Somar: valor_antigo + valor_novo = total_remuneracao\n4. Informar no S-1200 com ideADC para alteracao salarial\n5. Validar se vlrRemun = soma das rubricas",
                "codigo": "501",
            },
            {
                "desc": f"Promocao de {func['nome']} em {random.choice(['15', '20', '25'])} do mes. S-1200 rejeitado: valor nao corresponde ao esperado.",
                "gt": f"1. Verificar data da alteracao no S-2205 ou S-2306\n2. Calcular pro-rata: salario_antigo * (dias_antes/30) + salario_novo * (dias_depois/30)\n3. Arredondar para 2 casas decimais\n4. Usar ponto como separador decimal\n5. Transmitir S-1200 apenas apos S-2205 estar processado",
                "codigo": "501",
            },
            {
                "desc": f"{func['nome']} trabalhou 15 dias como {func['cargo']} e 15 dias como estagiario (mudanca de cargo). Como informar remuneracao?",
                "gt": f"1. Gerar dois S-1200 separados ou usar ideADC\n2. Primeira metade: cargo original, salario proporcional\n3. Segunda metade: novo cargo, salario proporcional\n4. Verificar se CBO foi alterado no S-2206\n5. Validar soma das rubricas = vlrRemun total",
                "codigo": "502",
            },
        ]

        cenario = random.choice(cenarios)

        casos.append({
            "question": cenario["desc"],
            "rejection_code": cenario["codigo"],
            "event_type": "S-1200",
            "ground_truth": cenario["gt"],
            "xml_snippet": f"<vlrRemun>VALOR_PRO-RATA</vlrRemun><ideADC><dtAltSal>2025-01-{random.choice(['15','20','25'])}</dtAltSal></ideADC>",
            "categoria": "remuneracao",
            "complexidade": "high",
            "contexto_empresa": emp["nome"],
            "tipo": "variacao_complexa",
        })

    return casos


def gerar_multi_vinculo(n: int = 50) -> List[Dict]:
    """Gera casos de multi-vinculo (critical complexity)."""
    casos = []

    for i in range(n):
        emp = random.choice(EMPRESAS_COMPLEXAS)
        func = random.choice(FUNCIONARIOS_COMPLEXOS)

        cenarios = [
            {
                "desc": f"{func['nome']} tem {func['vinculos']} vinculos ativos (CLT + estatutario). Rejeicao 781: sobreposicao de periodos.",
                "gt": f"1. Verificar se os vinculos sao compativeis (art. 5º da CLT permite acumulo em casos especificos)\n2. Se acumulo permitido: informar CPF em ambos, mas matriculas diferentes\n3. Verificar se horarios nao conflitam (descanso minimo 11h entre jornadas)\n4. Se vinculo secundario: informar como trabalho intermitente ou parcial\n5. Validar se soma das remuneracoes nao excede teto previdenciario",
                "codigo": "781",
            },
            {
                "desc": f"Funcionario demitido da {emp['nome']} em 2024, readmitido em 2025. S-2200 rejeitado: CPF ja possui vinculo ativo.",
                "gt": f"1. Verificar se S-2299 (desligamento) do vinculo anterior foi transmitido e processado\n2. Se desligamento nao processado: regularizar primeiro\n3. Se readmissao em menos de 90 dias: reativar vinculo anterior (nao criar novo)\n4. Se apos 90 dias: novo vinculo, mas data de admissao deve ser D+1 do desligamento\n5. Verificar se nao ha outro vinculo ativo para o mesmo CPF na mesma empresa",
                "codigo": "781",
            },
            {
                "desc": f"Trabalhador com vinculo em {emp['nome']} e vinculo em empresa do mesmo grupo economico. Rejeicao: CNPJ do mesmo grupo.",
                "gt": f"1. Verificar se empresas pertencem ao mesmo grupo economico (CNPJ raiz igual)\n2. Se grupo economico: informar CNPJ do estabelecimento especifico, nao da matriz\n3. Verificar se trabalhador nao excede limite de 8h diarias somando ambos vinculos\n4. Se trabalho temporario: usar S-2300 em vez de S-2200\n5. Validar se INSS esta sendo recolhido corretamente em ambos vinculos",
                "codigo": "782",
            },
        ]

        cenario = random.choice(cenarios)

        casos.append({
            "question": cenario["desc"],
            "rejection_code": cenario["codigo"],
            "event_type": "S-2200",
            "ground_truth": cenario["gt"],
            "xml_snippet": f"<cpfTrab>{random.choice(['12345678901','98765432109'])}</cpfTrab><matricula>{random.choice(['001','002','003'])}</matricula>",
            "categoria": "admissao",
            "complexidade": "critical",
            "contexto_empresa": emp["nome"],
            "tipo": "variacao_complexa",
        })

    return casos


def gerar_rescisao_complexa(n: int = 50) -> List[Dict]:
    """Gera casos de rescisao complexa (critical)."""
    casos = []

    for i in range(n):
        emp = random.choice(EMPRESAS_COMPLEXAS)
        func = random.choice(FUNCIONARIOS_COMPLEXOS)

        cenarios = [
            {
                "desc": f"Rescisao de {func['nome']} com acordo trabalhista. S-2299 rejeitado: verbas rescisorias nao conferem.",
                "gt": f"1. Calcular verbas rescisorias: saldo salario + 13o proporcional + ferias proporcionais + 1/3 ferias\n2. Se acordo: adicionar indenizacao de 20% do FGTS (art. 484-A CLT)\n3. Verificar se S-1200 do mes anterior foi transmitido\n4. Informar dtDeslig como ultimo dia trabalhado (nao dia do pagamento)\n5. Validar se mtvDeslig corresponde ao tipo de rescisao (acordo = 11)\n6. Verificar se S-5003 (FGTS rescisorio) sera transmitido separadamente",
                "codigo": "731",
            },
            {
                "desc": f"Funcionario {func['nome']} falecido. Como informar rescisao e pensao por morte no eSocial?",
                "gt": f"1. Transmitir S-2299 com mtvDeslig = 23 (falecimento)\n2. Informar dtDeslig = data do obito\n3. Calcular verbas: saldo salario + 13o + ferias + 1/3 (ate data do obito)\n4. Transmitir S-2410 (pensao por morte) para dependentes\n5. Verificar se S-1210 (pagamento) foi feito aos dependentes\n6. Se FGTS: dependentes tem direito a 100% (nao 40% como em rescisao normal)",
                "codigo": "732",
            },
            {
                "desc": f"Rescisao coletiva na {emp['nome']}: {random.choice([50,100,200])} funcionarios. Como processar em lote?",
                "gt": f"1. Verificar se houve comunicacao previa ao Ministerio do Trabalho (art. 486 CLT)\n2. Transmitir S-2299 individual para cada funcionario (nao aceita lote)\n3. Verificar se S-1200 do mes foi transmitido antes dos desligamentos\n4. Se rescisao coletiva: informar mtvDeslig = 10 (extincao contrato)\n5. Calcular indenizacao adicional de 3 meses (art. 486-A CLT) se aplicavel\n6. Validar se todos os S-2299 usam a mesma dtDeslig (ultimo dia do acordo)",
                "codigo": "733",
            },
        ]

        cenario = random.choice(cenarios)

        casos.append({
            "question": cenario["desc"],
            "rejection_code": cenario["codigo"],
            "event_type": "S-2299",
            "ground_truth": cenario["gt"],
            "xml_snippet": f"<mtvDeslig>{random.choice(['10','11','23'])}</mtvDeslig><dtDeslig>2025-{random.choice(['03','06','09'])}-{random.choice(['15','20','25'])}</dtDeslig>",
            "categoria": "desligamento",
            "complexidade": "critical",
            "contexto_empresa": emp["nome"],
            "tipo": "variacao_complexa",
        })

    return casos


def gerar_afastamento_complexo(n: int = 50) -> List[Dict]:
    """Gera casos de afastamento (high)."""
    casos = []

    motivos = [
        ("01", "Acidente de trabalho"),
        ("03", "Doenca"),
        ("06", "Licenca maternidade"),
        ("15", "Auxilio doenca previdenciario"),
        ("18", "Licenca remunerada"),
    ]

    for i in range(n):
        emp = random.choice(EMPRESAS_COMPLEXAS)
        func = random.choice(FUNCIONARIOS_COMPLEXOS)
        cod_mot, desc_mot = random.choice(motivos)

        cenarios = [
            {
                "desc": f"{func['nome']} afastado por {desc_mot} em {random.choice(['10','15','20'])} do mes. S-2230 rejeitado: afastamento sobreposto.",
                "gt": f"1. Verificar se ja existe afastamento ativo para o mesmo CPF/matricula\n2. Se afastamento anterior nao encerrado: transmitir S-2230 com dtTermAfast antes de novo inicio\n3. Se afastamento por doenca: verificar se houve CAT (S-2210) se acidente de trabalho\n4. Para licenca maternidade: verificar se S-1200 do mes anterior foi transmitido\n5. Validar se codMotAfast = {cod_mot} corresponde ao tipo de afastamento\n6. Se auxilio-doenca previdenciario: informar nrBeneficio do INSS",
                "codigo": "721",
            },
            {
                "desc": f"Funcionario retornou de afastamento mas S-2230 nao foi encerrado. Rejeicao: afastamento sem termino.",
                "gt": f"1. Transmitir S-2230 com dtTermAfast = data do retorno ao trabalho\n2. Verificar se S-1200 do mes de retorno foi transmitido com remuneracao integral\n3. Se afastamento previdenciario: verificar se S-2410 (beneficio) foi encerrado\n4. Validar se dias de afastamento nao excedem prazo legal (ex: 180 dias para doenca)\n5. Se licenca maternidade: verificar se houve prorrogacao medica (ate 180 dias)\n6. Informar se houve alteracao de jornada apos retorno",
                "codigo": "722",
            },
        ]

        cenario = random.choice(cenarios)

        casos.append({
            "question": cenario["desc"],
            "rejection_code": cenario["codigo"],
            "event_type": "S-2230",
            "ground_truth": cenario["gt"],
            "xml_snippet": f"<codMotAfast>{cod_mot}</codMotAfast><dtIniAfast>2025-{random.choice(['01','02','03'])}-{random.choice(['10','15'])}</dtIniAfast>",
            "categoria": "afastamento",
            "complexidade": "high",
            "contexto_empresa": emp["nome"],
            "tipo": "variacao_complexa",
        })

    return casos


def gerar_folha_complexa(n: int = 50) -> List[Dict]:
    """Gera casos de folha complexa (high)."""
    casos = []

    for i in range(n):
        emp = random.choice(EMPRESAS_COMPLEXAS)
        func = random.choice(FUNCIONARIOS_COMPLEXOS)

        cenarios = [
            {
                "desc": f"{emp['nome']} com {emp.get('filiais', 3)} filiais. S-1299 fechamento da folha rejeitado: inconsistencia entre estabelecimentos.",
                "gt": f"1. Verificar se todos os S-1200 das filiais foram transmitidos\n2. Validar se soma dos vlrRemun de todas as filiais = total da empresa\n3. Verificar se CNPJ de cada filial esta correto (8 digitos base + filial)\n4. Se transferencia de funcionario entre filiais: verificar S-2206 (alteracao contratual)\n5. Validar se INSS, IRRF e FGTS foram recolhidos por filial separadamente\n6. Se folha consolidada: informar apenas CNPJ da matriz no S-1299",
                "codigo": "601",
            },
            {
                "desc": f"13o salario de {func['nome']} com admissao em {func['admissao']}. Como calcular proporcionalidade?",
                "gt": f"1. Calcular meses de trabalho no ano: de {func['admissao'][:4]}-01 ate 2025-12\n2. Se admissao apos 15 do mes: nao conta o mes de admissao\n3. 13o = (salario / 12) * meses trabalhados\n4. Se afastamento no ano: descontar meses sem remuneracao\n5. Informar no S-1200 de dezembro com rubrica especifica de 13o\n6. Validar se S-1210 (pagamento) corresponde ao valor calculado",
                "codigo": "602",
            },
            {
                "desc": f"Ferias de {func['nome']} com vendo de 1/3. S-1200 rejeitado: valor de ferias nao confere.",
                "gt": f"1. Calcular ferias: salario / 30 * dias de ferias (ex: 30 dias = 1 salario)\n2. Calcular 1/3: ferias * 1/3\n3. Se abono pecuniario: calcular proporcional aos dias vendidos (max 10 dias)\n4. Informar no S-1200 com ideADC tipo 'F' (ferias)\n5. Validar se dtIni e dtFim das ferias estao corretas\n6. Verificar se S-1210 foi transmitido com valor bruto (antes de descontos)",
                "codigo": "603",
            },
        ]

        cenario = random.choice(cenarios)

        casos.append({
            "question": cenario["desc"],
            "rejection_code": cenario["codigo"],
            "event_type": "S-1200",
            "ground_truth": cenario["gt"],
            "xml_snippet": f"<perApur>2025-{random.choice(['01','06','12'])}</perApur><indGuia>1</indGuia>",
            "categoria": "folha",
            "complexidade": "high",
            "contexto_empresa": emp["nome"],
            "tipo": "variacao_complexa",
        })

    return casos


# ============================================================
# GERADOR PRINCIPAL
# ============================================================

def gerar_casos_complexos() -> List[Dict]:
    """Gera todos os casos complexos."""
    print("[Gerador] Gerando casos complexos...")

    casos = []
    casos.extend(gerar_pro_rata(50))
    casos.extend(gerar_multi_vinculo(50))
    casos.extend(gerar_rescisao_complexa(50))
    casos.extend(gerar_afastamento_complexo(50))
    casos.extend(gerar_folha_complexa(50))

    print(f"[Gerador] {len(casos)} casos complexos gerados")
    return casos


def integrar_dataset(dataset_base: List[Dict], casos_complexos: List[Dict]) -> List[Dict]:
    """Integra casos complexos ao dataset base."""
    dataset_final = dataset_base + casos_complexos

    # Deduplicacao simples
    unicos = []
    seen = set()
    for caso in dataset_final:
        key = f"{caso.get('rejection_code', '')}_{caso.get('question', '')[:60]}"
        if key not in seen:
            seen.add(key)
            unicos.append(caso)

    return unicos


def main():
    parser = argparse.ArgumentParser(description="Gerador final de casos complexos")
    parser.add_argument("--input", default="data/dataset_templates.json", help="Dataset base")
    parser.add_argument("--output", default="data/dataset_final.json", help="Dataset final")
    args = parser.parse_args()

    print("="*60)
    print("EII - GERADOR FINAL: Casos Complexos + Integracao")
    print("="*60)

    # 1. Carregar dataset base
    print(f"\n[1/3] Carregando dataset base: {args.input}")
    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    dataset_base = data["casos"]
    print(f"[1/3] Dataset base: {len(dataset_base)} casos")

    # 2. Gerar casos complexos
    print(f"\n[2/3] Gerando casos complexos...")
    casos_complexos = gerar_casos_complexos()

    # 3. Integrar
    print(f"\n[3/3] Integrando datasets...")
    dataset_final = integrar_dataset(dataset_base, casos_complexos)

    # Estatisticas
    cats = Counter(c.get("categoria") for c in dataset_final)
    comps = Counter(c.get("complexidade") for c in dataset_final)
    tipos = Counter(c.get("tipo") for c in dataset_final)

    # Salvar
    output = {
        "meta": {
            "fonte": "EII Dataset Final",
            "data_geracao": datetime.now().isoformat(),
            "casos_base": len(dataset_base),
            "casos_complexos": len(casos_complexos),
            "total_final": len(dataset_final),
        },
        "casos": dataset_final,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # Resumo
    print("\n" + "="*60)
    print("DATASET FINAL - RESUMO")
    print("="*60)
    print(f"Total: {len(dataset_final)}")
    print(f"  Base: {len(dataset_base)}")
    print(f"  Complexos: {len(casos_complexos)}")
    print(f"\nPor categoria:")
    for cat, n in cats.most_common():
        print(f"  {cat}: {n}")
    print(f"\nPor complexidade:")
    for comp, n in comps.most_common():
        print(f"  {comp}: {n}")
    print(f"\nArquivo: {args.output}")
    print(f"Tamanho: {len(dataset_final)} casos")
    print("="*60)


if __name__ == "__main__":
    main()
