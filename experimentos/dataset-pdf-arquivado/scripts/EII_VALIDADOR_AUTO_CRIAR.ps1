
# ============================================================
# EII - Criar Validador e Executar Automaticamente
# Cria o arquivo Python diretamente via PowerShell
# ============================================================

Write-Host "[EII] Criando validador automaticamente..." -ForegroundColor Green

$codigoValidador = @"
import json
import re
import argparse
from datetime import datetime
from collections import Counter, defaultdict

class EIIValidadorAutomatico:
    PESOS = {
        "completude_question": 20,
        "acionabilidade_gt": 25,
        "plausibilidade_xml": 15,
        "consistencia_categoria": 15,
        "adequacao_complexidade": 10,
        "realismo_contexto": 15,
    }

    CODIGOS_POR_CATEGORIA = {
        "identificacao": ["201", "202", "203", "273", "274", "275", "276", "277", "278", "279"],
        "remuneracao": ["501", "502", "503", "504", "505", "506", "507", "508", "509", "510"],
        "admissao": ["701", "702", "703", "704", "705", "706", "707", "708", "709", "710", "781"],
        "desligamento": ["731", "732", "733", "734", "735", "736", "737", "738", "739", "740"],
        "afastamento": ["721", "722", "723", "724", "725", "726", "727", "728", "729", "730"],
        "folha": ["601", "602", "603", "604", "605", "606", "607", "608", "609", "610"],
        "beneficios": ["801", "802", "803", "804", "805", "806", "807", "808", "809", "810"],
        "fgts": ["901", "902", "903", "904", "905", "906", "907", "908", "909", "910"],
    }

    TAGS_ESPERADAS = {
        "identificacao": ["ideEmpregador", "tpInsc", "nrInsc", "ideTransmissor", "ideEstab"],
        "remuneracao": ["vlrRemun", "itensRemun", "codRubr", "vrRubr", "tpRubr", "ideADC"],
        "admissao": ["matricula", "dtAdm", "tpRegTrab", "tpRegPrev", "cadIni", "dtExercicio"],
        "desligamento": ["dtDeslig", "mtvDeslig", "dtProjFimAPI", "indPagtoAPI", "dtTerm"],
        "afastamento": ["dtIniAfast", "dtTermAfast", "codMotAfast", "iniAfastamento"],
        "folha": ["perApur", "indGuia", "nrReciboAnt", "ideEvento"],
        "beneficios": ["cpfBenef", "nmBenefic", "dtNascto", "ideBenef"],
        "fgts": ["tpLancto", "nrDoc", "dtVenc", "ideEstabLotto"],
    }

    def __init__(self, dataset):
        self.dataset = dataset
        self.resultados = []
        self.stats = defaultdict(list)

    def _score_completude_question(self, caso):
        q = caso.get("question", "")
        score = 0
        notas = []
        if len(q) > 30: score += 5
        else: notas.append("pergunta muito curta")
        if re.search(r'\d{3,4}', q): score += 5
        else: notas.append("sem codigo de rejeicao")
        if any(x in q.lower() for x in ['empresa', 'funcionario', 'trabalhador']): score += 5
        else: notas.append("sem contexto")
        if '<' in q or 'tag' in q.lower() or 'campo' in q.lower(): score += 5
        else: notas.append("sem referencia tecnica")
        return score, "; ".join(notas) if notas else "OK"

    def _score_acionabilidade_gt(self, caso):
        gt = caso.get("ground_truth", "")
        score = 0
        notas = []
        if len(gt) > 50: score += 5
        else: notas.append("GT muito curto")
        if re.search(r'(\d+[\.\)]\s|\-\s|\*\s)', gt): score += 10
        else: notas.append("sem passos numerados")
        if any(x in gt.lower() for x in ['verificar', 'corrigir', 'ajustar', 'alterar']): score += 5
        else: notas.append("sem verbo de acao")
        if any(x in gt for x in ['Exemplo:', 'exemplo', 'correto:']): score += 5
        else: notas.append("sem exemplo")
        return score, "; ".join(notas) if notas else "OK"

    def _score_plausibilidade_xml(self, caso):
        xml = caso.get("xml_snippet", "")
        score = 0
        notas = []
        if not xml: return 0, "sem xml_snippet"
        tags = re.findall(r'<(\w+)>', xml)
        if tags: score += 5
        else: notas.append("sem tags XML")
        if re.search(r'<\w+>.*?</\w+>', xml): score += 5
        else: notas.append("tags nao fecham")
        cat = caso.get("categoria", "outros")
        tags_esperadas = self.TAGS_ESPERADAS.get(cat, [])
        if tags and any(t in tags_esperadas for t in tags): score += 5
        else: notas.append("tag inesperada")
        valores = re.findall(r'<\w+>(.*?)</\w+>', xml)
        if valores and not all(v in ['', 'VALOR_ERRADO', 'ERRO'] for v in valores): score += 5
        else: notas.append("valor generico")
        return score, "; ".join(notas) if notas else "OK"

    def _score_consistencia_categoria(self, caso):
        cat = caso.get("categoria", "outros")
        codigo = caso.get("rejection_code", "")
        score = 0
        notas = []
        codigos_esperados = self.CODIGOS_POR_CATEGORIA.get(cat, [])
        if codigo in codigos_esperados: score += 10
        elif cat == "outros": score += 5
        else: notas.append("codigo " + codigo + " inesperado para " + cat)
        evento = caso.get("event_type", "")
        eventos_esperados = {
            "identificacao": ["S-2200", "S-2300", "S-1000", "S-1005"],
            "remuneracao": ["S-1200", "S-1202", "S-1207", "S-1210"],
            "admissao": ["S-2200", "S-2300"],
            "desligamento": ["S-2299", "S-2399"],
            "afastamento": ["S-2230", "S-2231"],
            "folha": ["S-1200", "S-1298"],
            "beneficios": ["S-2400", "S-2410"],
            "fgts": ["S-5001", "S-5002"],
        }
        if evento in eventos_esperados.get(cat, []) or evento == "S-GERAL": score += 5
        else: notas.append("evento " + evento + " atipico")
        return score, "; ".join(notas) if notas else "OK"

    def _score_adequacao_complexidade(self, caso):
        comp = caso.get("complexidade", "medium")
        gt = caso.get("ground_truth", "")
        score = 0
        notas = []
        if comp in ["high", "critical"]:
            if len(gt) > 200: score += 10
            else: notas.append("alta complexidade, GT curto")
        elif comp == "medium":
            if 100 < len(gt) < 300: score += 10
            else: notas.append("media complexidade, GT fora da faixa")
        else:
            if len(gt) < 150: score += 10
            else: notas.append("baixa complexidade, GT longo")
        if comp == "critical":
            if len(re.findall(r'\d+[\.\)]', gt)) >= 3: score += 5
            else: notas.append("critical precisa 3+ passos")
        return score, "; ".join(notas) if notas else "OK"

    def _score_realismo_contexto(self, caso):
        score = 0
        notas = []
        if caso.get("contexto_empresa"): score += 5
        else: notas.append("sem contexto_empresa")
        empresa = caso.get("contexto_empresa", "")
        if empresa and not any(x in empresa for x in ["Empresa", "Teste", "Exemplo"]): score += 5
        else: notas.append("nome generico")
        q = caso.get("question", "")
        if any(x in q for x in ['Ltda', 'S.A.', 'ME']) or any(x in q for x in ['Silva', 'Santos']): score += 5
        else: notas.append("sem referencia realista")
        return score, "; ".join(notas) if notas else "OK"

    def avaliar_caso(self, caso):
        scores = {}
        notas = {}
        scores["completude_question"], notas["completude_question"] = self._score_completude_question(caso)
        scores["acionabilidade_gt"], notas["acionabilidade_gt"] = self._score_acionabilidade_gt(caso)
        scores["plausibilidade_xml"], notas["plausibilidade_xml"] = self._score_plausibilidade_xml(caso)
        scores["consistencia_categoria"], notas["consistencia_categoria"] = self._score_consistencia_categoria(caso)
        scores["adequacao_complexidade"], notas["adequacao_complexidade"] = self._score_adequacao_complexidade(caso)
        scores["realismo_contexto"], notas["realismo_contexto"] = self._score_realismo_contexto(caso)

        score_total = sum(scores[k] * self.PESOS[k] // 20 for k in scores)

        if score_total >= 80: qualidade = "EXCELENTE"
        elif score_total >= 60: qualidade = "BOM"
        elif score_total >= 40: qualidade = "REGULAR"
        else: qualidade = "RUIM"

        flags = [k for k, v in notas.items() if v != "OK"]

        return {
            "rejection_code": caso.get("rejection_code"),
            "categoria": caso.get("categoria"),
            "complexidade": caso.get("complexidade"),
            "tipo": caso.get("tipo"),
            "score_total": score_total,
            "qualidade": qualidade,
            "scores_detalhados": scores,
            "notas": {k: v for k, v in notas.items() if v != "OK"},
            "flags": flags,
            "precisa_correcao": score_total < 60 or len(flags) >= 3,
        }

    def avaliar_todos(self):
        print(f"[Validador] Avaliando {len(self.dataset)} casos...")
        for i, caso in enumerate(self.dataset):
            if (i + 1) % 500 == 0: print(f"[Validador] {i+1}/{len(self.dataset)}...")
            resultado = self.avaliar_caso(caso)
            self.resultados.append(resultado)
            self.stats["qualidade"].append(resultado["qualidade"])
            self.stats["categoria"].append(resultado["categoria"])
            self.stats["score"].append(resultado["score_total"])
        print(f"[Validador] Avaliacao concluida")
        return self.resultados

    def gerar_relatorio_completo(self, output_path="data/validacao_completa.json"):
        scores = self.stats["score"]
        qualidades = Counter(self.stats["qualidade"])

        relatorio = {
            "meta": {
                "data_validacao": datetime.now().isoformat(),
                "total_casos": len(self.dataset),
                "score_medio": round(sum(scores) / len(scores), 1),
                "score_min": min(scores),
                "score_max": max(scores),
                "percentil_25": sorted(scores)[len(scores)//4],
                "percentil_75": sorted(scores)[3*len(scores)//4],
            },
            "distribuicao_qualidade": dict(qualidades),
            "distribuicao_score": {
                "excelente_80_100": sum(1 for s in scores if s >= 80),
                "bom_60_79": sum(1 for s in scores if 60 <= s < 80),
                "regular_40_59": sum(1 for s in scores if 40 <= s < 60),
                "ruim_0_39": sum(1 for s in scores if s < 40),
            },
            "casos_com_problemas": [],
            "melhores_casos": [],
            "piores_casos": [],
            "por_categoria": {},
        }

        problemas = [r for r in self.resultados if r["precisa_correcao"]]
        relatorio["casos_com_problemas"] = problemas[:50]
        relatorio["total_problemas"] = len(problemas)

        sorted_results = sorted(self.resultados, key=lambda x: x["score_total"], reverse=True)
        relatorio["melhores_casos"] = sorted_results[:20]
        relatorio["piores_casos"] = sorted_results[-20:]

        for cat in set(self.stats["categoria"]):
            cat_scores = [r["score_total"] for r in self.resultados if r["categoria"] == cat]
            relatorio["por_categoria"][cat] = {
                "total": len(cat_scores),
                "score_medio": round(sum(cat_scores) / len(cat_scores), 1),
                "excelentes": sum(1 for s in cat_scores if s >= 80),
            }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(relatorio, f, indent=2, ensure_ascii=False)
        print(f"[Validador] Relatorio: {output_path}")
        return relatorio

    def gerar_csv_revisao(self, output_path="data/casos_para_revisao.csv"):
        import csv
        problemas = [r for r in self.resultados if r["precisa_correcao"]]
        with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=["rejection_code", "categoria", "score_total", "qualidade", "flags", "notas", "acao_sugerida"])
            writer.writeheader()
            for r in problemas:
                writer.writerow({
                    "rejection_code": r["rejection_code"],
                    "categoria": r["categoria"],
                    "score_total": r["score_total"],
                    "qualidade": r["qualidade"],
                    "flags": "; ".join(r["flags"]),
                    "notas": "; ".join(r["notas"].values()) if r["notas"] else "",
                    "acao_sugerida": "Revisar question/GT/XML",
                })
        print(f"[Validador] CSV revisao: {output_path} ({len(problemas)} casos)")

    def print_resumo(self):
        scores = self.stats["score"]
        qualidades = Counter(self.stats["qualidade"])
        print("\n" + "="*60)
        print("VALIDACAO AUTOMATICA - RESUMO")
        print("="*60)
        print(f"Total casos: {len(self.dataset)}")
        print(f"Score medio: {sum(scores)/len(scores):.1f}/100")
        print(f"Score min/max: {min(scores)}/{max(scores)}")
        print(f"\nDistribuicao qualidade:")
        for q, n in qualidades.most_common():
            print(f"  {q}: {n} ({n/len(self.dataset)*100:.1f}%)")
        problemas = sum(1 for r in self.resultados if r["precisa_correcao"])
        print(f"\nCasos com problemas: {problemas} ({problemas/len(self.dataset)*100:.1f}%)")
        print(f"Casos EXCELENTES: {qualidades.get('EXCELENTE', 0)}")
        print("="*60)


def main():
    parser = argparse.ArgumentParser(description="Validador automatico EII")
    parser.add_argument("--input", default="data/dataset_templates.json", help="Dataset completo")
    parser.add_argument("--output", default="data/validacao_completa.json", help="Relatorio JSON")
    parser.add_argument("--csv", default="data/casos_para_revisao.csv", help="CSV para revisao")
    args = parser.parse_args()

    print("="*60)
    print("EII - VALIDADOR AUTOMATICO DE DATASET")
    print("="*60)

    print(f"\n[1/3] Carregando: {args.input}")
    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)
    dataset = data["casos"]
    print(f"[1/3] Dataset: {len(dataset)} casos")

    print(f"\n[2/3] Avaliando qualidade...")
    validador = EIIValidadorAutomatico(dataset)
    validador.avaliar_todos()
    validador.print_resumo()

    print(f"\n[3/3] Gerando relatorios...")
    validador.gerar_relatorio_completo(args.output)
    validador.gerar_csv_revisao(args.csv)

    print("\n" + "="*60)
    print("VALIDACAO CONCLUIDA")
    print("="*60)
    print("Arquivos:")
    print(f"  - {args.output} (relatorio completo)")
    print(f"  - {args.csv} (casos para revisao manual)")
    print("="*60)


if __name__ == "__main__":
    main()
"@

Set-Content -Path "eii_validador_auto.py" -Value $codigoValidador -Encoding UTF8
Write-Host "[EII] Validador criado: eii_validador_auto.py" -ForegroundColor Green

# Verificar dataset
if (-not (Test-Path "data/dataset_templates.json")) {
    Write-Host "[ERRO] data/dataset_templates.json nao encontrado" -ForegroundColor Red
    exit 1
}

# Executar
Write-Host "[EII] Executando validacao..." -ForegroundColor Green
python eii_validador_auto.py --input data/dataset_templates.json

Write-Host "[EII] Concluido!" -ForegroundColor Green
