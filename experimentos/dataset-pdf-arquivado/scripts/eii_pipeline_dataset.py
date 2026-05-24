
"""
EII - Pipeline: Validação + Golden Dataset + SQLite
Funciona SEM qdrant-client instalado

Uso:
    python eii_pipeline_sqlite.py --input data/dataset_templates.json
"""

import json
import random
import argparse
import sqlite3
from datetime import datetime
from pathlib import Path
from collections import Counter
from typing import List, Dict, Any


# ============================================================
# FASE 1: VALIDAR AMOSTRA DE 50 CASOS
# ============================================================

class EIIValidador:
    """Valida qualidade de amostra do dataset."""

    CRITERIOS = {
        "question_completa": "A pergunta descreve claramente o problema?",
        "ground_truth_acionavel": "O ground truth tem passos claros de correção?",
        "xml_valido": "O XML snippet e plausivel (mesmo que errado)?",
        "categoria_correta": "A categoria faz sentido para o codigo de rejeicao?",
        "complexidade_adequada": "A complexidade reflete a dificuldade real?",
        "contexto_realista": "A empresa/funcionario mencionado e realista?",
    }

    def __init__(self, dataset: List[Dict]):
        self.dataset = dataset
        self.amostra = []

    def selecionar_amostra(self, n: int = 50, seed: int = 42) -> List[Dict]:
        """Seleciona amostra estratificada por categoria."""
        random.seed(seed)

        por_categoria = {}
        for caso in self.dataset:
            cat = caso.get("categoria", "outros")
            por_categoria.setdefault(cat, []).append(caso)

        amostra = []
        for cat, casos in por_categoria.items():
            n_cat = max(1, int(n * len(casos) / len(self.dataset)))
            amostra.extend(random.sample(casos, min(n_cat, len(casos))))

        if len(amostra) < n:
            restante = [c for c in self.dataset if c not in amostra]
            amostra.extend(random.sample(restante, min(n - len(amostra), len(restante))))

        self.amostra = amostra[:n]
        return self.amostra

    def gerar_relatorio_validacao(self, output_path: str = "data/validacao_amostra.json"):
        """Gera relatorio de validacao para revisao manual."""
        relatorio = {
            "meta": {
                "data_validacao": datetime.now().isoformat(),
                "total_amostra": len(self.amostra),
                "criterios": self.CRITERIOS,
                "instrucoes": "Revise cada caso e marque True/False para cada criterio. Casos com < 4 True devem ser corrigidos.",
            },
            "casos": [],
        }

        for i, caso in enumerate(self.amostra, 1):
            relatorio["casos"].append({
                "id": i,
                "rejection_code": caso.get("rejection_code"),
                "categoria": caso.get("categoria"),
                "complexidade": caso.get("complexidade"),
                "question": caso.get("question"),
                "ground_truth": caso.get("ground_truth"),
                "xml_snippet": caso.get("xml_snippet"),
                "avaliacao": {
                    "question_completa": None,
                    "ground_truth_acionavel": None,
                    "xml_valido": None,
                    "categoria_correta": None,
                    "complexidade_adequada": None,
                    "contexto_realista": None,
                },
                "notas": "",
            })

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(relatorio, f, indent=2, ensure_ascii=False)

        print(f"[Validador] Relatorio gerado: {output_path}")
        return relatorio

    def calcular_metricas_automaticas(self) -> Dict:
        """Calcula metricas automaticas."""
        metricas = {
            "total": len(self.dataset),
            "avg_question_length": sum(len(c.get("question", "")) for c in self.dataset) / len(self.dataset),
            "avg_gt_length": sum(len(c.get("ground_truth", "")) for c in self.dataset) / len(self.dataset),
            "com_xml": sum(1 for c in self.dataset if c.get("xml_snippet")),
            "com_contexto": sum(1 for c in self.dataset if c.get("contexto_empresa")),
            "categorias": dict(Counter(c.get("categoria") for c in self.dataset)),
            "complexidades": dict(Counter(c.get("complexidade") for c in self.dataset)),
        }
        return metricas


# ============================================================
# FASE 2: SELECIONAR GOLDEN DATASET 300
# ============================================================

class EIIGoldenSelector:
    """Seleciona 300 casos mais representativos."""

    def __init__(self, dataset: List[Dict]):
        self.dataset = dataset

    def selecionar_golden(self, n: int = 300) -> List[Dict]:
        """Seleciona golden dataset balanceado."""
        originais = [c for c in self.dataset if c.get("tipo") == "original_manual"]
        variacoes = [c for c in self.dataset if c.get("tipo") != "original_manual"]
        complexos = [c for c in self.dataset if c.get("complexidade") in ["high", "critical"]]

        golden = []

        # 1. Originais (40%)
        n_originais = min(len(originais), int(n * 0.40))
        originais_sorted = sorted(originais, key=lambda x: len(x.get("ground_truth", "")), reverse=True)
        golden.extend(originais_sorted[:n_originais])

        # 2. Variacoes diversas (35%)
        n_variacoes = int(n * 0.35)
        codigos_vistos = set()
        variacoes_diversas = []
        for c in variacoes:
            rc = c.get("rejection_code", "")
            if rc not in codigos_vistos:
                codigos_vistos.add(rc)
                variacoes_diversas.append(c)

        if len(variacoes_diversas) < n_variacoes:
            restante = [c for c in variacoes if c not in variacoes_diversas]
            variacoes_diversas.extend(random.sample(restante, min(n_variacoes - len(variacoes_diversas), len(restante))))

        golden.extend(variacoes_diversas[:n_variacoes])

        # 3. Edge cases (25%)
        n_complexos = n - len(golden)
        complexos_nao_selecionados = [c for c in complexos if c not in golden]
        if complexos_nao_selecionados:
            golden.extend(random.sample(complexos_nao_selecionados, min(n_complexos, len(complexos_nao_selecionados))))

        # Completar
        if len(golden) < n:
            restante = [c for c in self.dataset if c not in golden]
            golden.extend(random.sample(restante, min(n - len(golden), len(restante))))

        return golden[:n]

    def exportar_golden(self, golden: List[Dict], output_path: str = "data/golden_dataset_300.json"):
        """Exporta golden dataset formatado para RAGAS."""
        ragas_format = []
        for caso in golden:
            ragas_format.append({
                "question": caso.get("question", ""),
                "answer": "",
                "contexts": [caso.get("ground_truth", "")],
                "ground_truth": caso.get("ground_truth", ""),
                "rejection_code": caso.get("rejection_code", ""),
                "event_type": caso.get("event_type", ""),
                "categoria": caso.get("categoria", ""),
                "complexidade": caso.get("complexidade", ""),
                "tipo": caso.get("tipo", ""),
            })

        output = {
            "meta": {
                "total": len(golden),
                "data_criacao": datetime.now().isoformat(),
                "formato": "RAGAS-compatible",
            },
            "casos": ragas_format,
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        print(f"[Golden] Dataset exportado: {output_path}")
        return output


# ============================================================
# FASE 3: INTEGRAR AO SQLITE
# ============================================================

class EIISQLiteIntegrator:
    """Integra dataset ao SQLite local."""

    def __init__(self, db_path: str = "data/eii_kb.sqlite"):
        self.db_path = db_path

    def criar_tabela(self):
        """Cria tabela knowledge_base."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_base (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT,
                ground_truth TEXT,
                rejection_code TEXT,
                event_type TEXT,
                categoria TEXT,
                complexidade TEXT,
                xml_snippet TEXT,
                tipo TEXT,
                contexto_empresa TEXT,
                created_at TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS golden_dataset (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT,
                ground_truth TEXT,
                rejection_code TEXT,
                event_type TEXT,
                categoria TEXT,
                complexidade TEXT,
                tipo TEXT,
                created_at TEXT
            )
        """)

        conn.commit()
        conn.close()
        print(f"[SQLite] Tabelas criadas: {self.db_path}")

    def inserir_dataset(self, dataset: List[Dict]):
        """Insere dataset completo."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        for caso in dataset:
            cursor.execute("""
                INSERT INTO knowledge_base 
                (question, ground_truth, rejection_code, event_type, categoria, complexidade, xml_snippet, tipo, contexto_empresa, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                caso.get("question", ""),
                caso.get("ground_truth", ""),
                caso.get("rejection_code", ""),
                caso.get("event_type", ""),
                caso.get("categoria", ""),
                caso.get("complexidade", ""),
                caso.get("xml_snippet", ""),
                caso.get("tipo", ""),
                caso.get("contexto_empresa", ""),
                datetime.now().isoformat(),
            ))

        conn.commit()
        conn.close()
        print(f"[SQLite] Dataset inserido: {len(dataset)} registros")

    def inserir_golden(self, golden: List[Dict]):
        """Insere golden dataset."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        for caso in golden:
            cursor.execute("""
                INSERT INTO golden_dataset 
                (question, ground_truth, rejection_code, event_type, categoria, complexidade, tipo, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                caso.get("question", ""),
                caso.get("ground_truth", ""),
                caso.get("rejection_code", ""),
                caso.get("event_type", ""),
                caso.get("categoria", ""),
                caso.get("complexidade", ""),
                caso.get("tipo", ""),
                datetime.now().isoformat(),
            ))

        conn.commit()
        conn.close()
        print(f"[SQLite] Golden inserido: {len(golden)} registros")

    def resumo(self):
        """Mostra resumo do banco."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM knowledge_base")
        total_kb = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM golden_dataset")
        total_golden = cursor.fetchone()[0]

        cursor.execute("SELECT categoria, COUNT(*) FROM knowledge_base GROUP BY categoria")
        cats = cursor.fetchall()

        conn.close()

        print(f"\n[SQLite] RESUMO DO BANCO")
        print(f"  Knowledge Base: {total_kb} registros")
        print(f"  Golden Dataset: {total_golden} registros")
        print(f"  Por categoria:")
        for cat, n in cats:
            print(f"    {cat}: {n}")


# ============================================================
# PIPELINE PRINCIPAL
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Pipeline EII: Validacao + Golden + SQLite")
    parser.add_argument("--input", default="data/dataset_templates.json", help="Dataset completo")
    parser.add_argument("--skip-validacao", action="store_true", help="Pular validacao")
    args = parser.parse_args()

    print("="*60)
    print("EII PIPELINE: Validacao + Golden Dataset + SQLite")
    print("="*60)

    # 1. Carregar
    print(f"\n[1/4] Carregando dataset: {args.input}")
    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    dataset = data["casos"]
    print(f"[1/4] Dataset: {len(dataset)} casos")

    # 2. Validacao
    if not args.skip_validacao:
        print(f"\n[2/4] FASE 1: Validacao")
        validador = EIIValidador(dataset)
        amostra = validador.selecionar_amostra(n=50)
        relatorio = validador.gerar_relatorio_validacao("data/validacao_amostra.json")
        metricas = validador.calcular_metricas_automaticas()

        print(f"[2/4] Amostra: 50 casos")
        print(f"[2/4] Metricas:")
        print(f"  - Media pergunta: {metricas['avg_question_length']:.0f} chars")
        print(f"  - Media GT: {metricas['avg_gt_length']:.0f} chars")
        print(f"  - Com XML: {metricas['com_xml']}")
        print(f"  - Com contexto: {metricas['com_contexto']}")
    else:
        print(f"\n[2/4] Validacao pulada")

    # 3. Golden
    print(f"\n[3/4] FASE 2: Golden Dataset 300")
    selector = EIIGoldenSelector(dataset)
    golden = selector.selecionar_golden(n=300)
    selector.exportar_golden(golden, "data/golden_dataset_300.json")

    cats_golden = Counter(c.get("categoria") for c in golden)
    tipos_golden = Counter(c.get("tipo") for c in golden)
    print(f"[3/4] Golden: {len(golden)} casos")
    print(f"  - Originais: {tipos_golden.get('original_manual', 0)}")
    print(f"  - Variacoes: {tipos_golden.get('variacao_template', 0)}")
    print(f"  - Categorias: {dict(cats_golden)}")

    # 4. SQLite
    print(f"\n[4/4] FASE 3: SQLite")
    integrator = EIISQLiteIntegrator("data/eii_kb.sqlite")
    integrator.criar_tabela()
    integrator.inserir_dataset(dataset)
    integrator.inserir_golden(golden)
    integrator.resumo()

    print("\n" + "="*60)
    print("PIPELINE CONCLUIDO")
    print("="*60)
    print("Arquivos:")
    print("  - data/validacao_amostra.json (revise manualmente)")
    print("  - data/golden_dataset_300.json (pronto para RAGAS)")
    print("  - data/eii_kb.sqlite (KB local)")
    print("="*60)


if __name__ == "__main__":
    main()
