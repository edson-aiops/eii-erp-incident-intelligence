"""
EII PDF Parser - Manual de Orientacao do eSocial S-1.3
Extrai casos de rejeicao, exemplos hipoteticos e regras de validacao

Dependencias:
    pip install PyMuPDF pandas

Uso:
    python eii_pdf_parser.py --pdf "/caminho/manual_s-1-3.pdf" --output "casos_extraidos.json"
"""

import fitz  # PyMuPDF
import re
import json
import argparse
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
from datetime import datetime


@dataclass
class CasoRejeicao:
    """Caso extraido do manual oficial."""
    codigo: str
    descricao: str
    acao_sugerida: str
    eventos_afetados: List[str]
    categoria: str
    complexidade: str
    fonte: str
    pagina: int
    xml_tag: Optional[str] = None
    exemplo_xml: Optional[str] = None

    def to_dict(self) -> Dict:
        return asdict(self)


class EIIManualParser:
    """
    Parser do Manual de Orientacao do eSocial.
    Extrai rejeicoes, exemplos e regras de validacao.
    """

    # Padroes regex para extracao
    PADROES = {
        "codigo_rejeicao": re.compile(
            r'(?:Rejeicao|Codigo|Erro)\s*[:\-]?\s*(\d{3,4})',
            re.IGNORECASE
        ),
        "descricao_rejeicao": re.compile(
            r'(?:Descricao|Mensagem|Texto)\s*[:\-]?\s*(.+?)(?=
\s*(?:Acao|Correcao|Solucao)|\Z)',
            re.IGNORECASE | re.DOTALL
        ),
        "acao_sugerida": re.compile(
            r'(?:Acao\s*Sugerida|Correcao|Solucao|Como\s*corrigir)\s*[:\-]?\s*(.+?)(?=
\s*(?:Rejeicao|Codigo|Evento)|\Z)',
            re.IGNORECASE | re.DOTALL
        ),
        "evento_tipo": re.compile(
            r'S[-\s]?(\d{4})',
            re.IGNORECASE
        ),
        "xml_tag": re.compile(
            r'<(\w+)>',
        ),
        "exemplo_bloco": re.compile(
            r'(?:Exemplo|Exemplo\s*XML|XML\s*de\s*Exemplo)[:\-]?\s*(.+?)(?=
\s*(?:Rejeicao|Codigo|Nota)|\Z)',
            re.IGNORECASE | re.DOTALL
        ),
    }

    CATEGORIAS = {
        "identificacao": ["cnpj", "cei", "caepf", "ideempregador", "identificacao"],
        "remuneracao": ["remun", "salario", "rubrica", "vlrremun", "remuneracao"],
        "admissao": ["admis", "contrat", "vinculo", "dtadm", "matricula"],
        "desligamento": ["deslig", "demiss", "rescis", "afast", "dtterm"],
        "afastamento": ["afast", "licenc", "atestado", "dtiniafast"],
        "folha": ["folha", "periodo", "competencia", "apuracao"],
        "beneficios": ["benef", "previdenci", "aposent", "penSAO"],
        "fgts": ["fgts", "guia", "recolhimento"],
    }

    def __init__(self, pdf_path: str):
        self.pdf_path = Path(pdf_path)
        self.doc = None
        self.casos: List[CasoRejeicao] = []

    def __enter__(self):
        self.doc = fitz.open(self.pdf_path)
        print(f"[Parser] PDF aberto: {self.pdf_path.name}")
        print(f"[Parser] Paginas: {len(self.doc)}")
        return self

    def __exit__(self, *args):
        if self.doc:
            self.doc.close()
            print(f"[Parser] PDF fechado. Casos extraidos: {len(self.casos)}")

    def _classificar_categoria(self, texto: str) -> str:
        """Classifica caso em categoria baseado em keywords."""
        texto_lower = texto.lower()
        for categoria, keywords in self.CATEGORIAS.items():
            if any(kw in texto_lower for kw in keywords):
                return categoria
        return "outros"

    def _classificar_complexidade(self, texto: str) -> str:
        """Estima complexidade baseado em indicadores."""
        texto_lower = texto.lower()

        # Indicadores de complexidade
        critica = ["multi", "vinculo", "sobrepos", "pro-rata", "calculo", "formula"]
        alta = ["validar", "consultar", "confirmar", "verificar em", "cruzamento"]

        if any(c in texto_lower for c in critica):
            return "critical"
        elif any(h in texto_lower for h in alta):
            return "high"
        elif len(texto) > 500:  # Descricao longa = provavelmente complexo
            return "medium"
        else:
            return "low"

    def _extrair_eventos(self, texto: str) -> List[str]:
        """Extrai tipos de evento mencionados."""
        matches = self.PADROES["evento_tipo"].findall(texto)
        return [f"S-{m}" for m in matches] if matches else ["S-GERAL"]

    def _extrair_xml_tag(self, texto: str) -> Optional[str]:
        """Extrai tag XML mencionada."""
        matches = self.PADROES["xml_tag"].findall(texto)
        # Retorna a tag mais mencionada ou a primeira
        if matches:
            from collections import Counter
            return Counter(matches).most_common(1)[0][0]
        return None

    def parse_pagina(self, page_num: int) -> List[CasoRejeicao]:
        """Parse de uma pagina especifica."""
        page = self.doc[page_num]
        texto = page.get_text()

        casos_pagina = []

        # Estrategia 1: Procurar blocos de rejeicao
        # Padrao comum no manual: codigo + descricao + acao
        blocos = re.split(r'
\s*(?=\d{3,4}\s*[-–])', texto)

        for bloco in blocos:
            codigo_match = self.PADROES["codigo_rejeicao"].search(bloco)
            if not codigo_match:
                continue

            codigo = codigo_match.group(1)

            # Extrair descricao (texto ate proxima secao)
            descricao_match = self.PADROES["descricao_rejeicao"].search(bloco)
            descricao = descricao_match.group(1).strip() if descricao_match else ""

            # Extrair acao sugerida
            acao_match = self.PADROES["acao_sugerida"].search(bloco)
            acao = acao_match.group(1).strip() if acao_match else ""

            # Se nao achou acao no bloco, procurar nas proximas linhas
            if not acao and len(bloco) > 200:
                # Heuristica: ultimas 3-5 frases = acao
                frases = bloco.split(".")
                if len(frases) > 3:
                    acao = ". ".join(frases[-3:]).strip()

            # Extrair exemplo XML se houver
            exemplo_match = self.PADROES["exemplo_bloco"].search(bloco)
            exemplo_xml = exemplo_match.group(1).strip() if exemplo_match else None

            caso = CasoRejeicao(
                codigo=codigo,
                descricao=descricao[:500],  # Limitar tamanho
                acao_sugerida=acao[:500],
                eventos_afetados=self._extrair_eventos(bloco),
                categoria=self._classificar_categoria(bloco),
                complexidade=self._classificar_complexidade(bloco),
                fonte=f"Manual eSocial S-1.3, pagina {page_num + 1}",
                pagina=page_num + 1,
                xml_tag=self._extrair_xml_tag(bloco),
                exemplo_xml=exemplo_xml,
            )

            casos_pagina.append(caso)

        return casos_pagina

    def parse_all(self, paginas: Optional[List[int]] = None) -> List[CasoRejeicao]:
        """
        Parse de todo o PDF ou paginas especificas.

        Args:
            paginas: Lista de paginas para parse (None = todas)
        """
        if paginas is None:
            paginas = range(len(self.doc))

        for i, page_num in enumerate(paginas):
            if i % 50 == 0:
                print(f"[Parser] Processando pagina {page_num + 1}/{len(self.doc)}...")

            casos_pagina = self.parse_pagina(page_num)
            self.casos.extend(casos_pagina)

        # Deduplicacao por codigo + descricao
        seen = set()
        unicos = []
        for caso in self.casos:
            key = f"{caso.codigo}_{hash(caso.descricao[:100])}"
            if key not in seen:
                seen.add(key)
                unicos.append(caso)

        self.casos = unicos
        print(f"[Parser] Total casos unicos: {len(self.casos)}")

        return self.casos

    def exportar_json(self, output_path: str):
        """Exporta casos para JSON."""
        data = {
            "meta": {
                "fonte": "Manual de Orientacao do eSocial S-1.3",
                "data_extracao": datetime.now().isoformat(),
                "total_casos": len(self.casos),
                "parser_version": "1.0",
            },
            "casos": [c.to_dict() for c in self.casos],
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"[Parser] Exportado: {output_path}")

    def exportar_csv(self, output_path: str):
        """Exporta casos para CSV (abre no Excel)."""
        import csv

        if not self.casos:
            print("[Parser] Nenhum caso para exportar")
            return

        fieldnames = list(self.casos[0].to_dict().keys())

        with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for caso in self.casos:
                row = caso.to_dict()
                # Converter listas para string para CSV
                row["eventos_afetados"] = "; ".join(row["eventos_afetados"])
                writer.writerow(row)

        print(f"[Parser] Exportado CSV: {output_path}")

    def resumo_estatistico(self) -> Dict:
        """Retorna estatisticas dos casos extraidos."""
        from collections import Counter

        categorias = Counter(c.categoria for c in self.casos)
        complexidades = Counter(c.complexidade for c in self.casos)
        eventos = Counter()
        for c in self.casos:
            for e in c.eventos_afetados:
                eventos[e] += 1

        return {
            "total_casos": len(self.casos),
            "por_categoria": dict(categorias.most_common(10)),
            "por_complexidade": dict(complexidades),
            "por_evento": dict(eventos.most_common(10)),
            "com_xml_tag": sum(1 for c in self.casos if c.xml_tag),
            "com_exemplo_xml": sum(1 for c in self.casos if c.exemplo_xml),
        }


# ============================================================
# SCRIPT PRINCIPAL
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Parser do Manual de Orientacao eSocial")
    parser.add_argument("--pdf", required=True, help="Caminho do PDF do manual")
    parser.add_argument("--output", default="casos_extraidos.json", help="Arquivo de saida JSON")
    parser.add_argument("--csv", default="casos_extraidos.csv", help="Arquivo de saida CSV")
    parser.add_argument("--paginas", nargs="+", type=int, help="Paginas especificas (opcional)")
    parser.add_argument("--resumo", action="store_true", help="Mostrar resumo estatistico")

    args = parser.parse_args()

    with EIIManualParser(args.pdf) as parser:
        # Parse
        parser.parse_all(paginas=args.paginas)

        # Exportar
        parser.exportar_json(args.output)
        parser.exportar_csv(args.csv)

        # Resumo
        if args.resumo:
            stats = parser.resumo_estatistico()
            print("\n" + "="*60)
            print("RESUMO ESTATISTICO")
            print("="*60)
            print(json.dumps(stats, indent=2, ensure_ascii=False))
            print("="*60)


if __name__ == "__main__":
    main()
