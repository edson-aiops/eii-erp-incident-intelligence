
import json
import os
import time
import argparse
from datetime import datetime
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from groq import Groq
except ImportError:
    print("[ERRO] groq nao instalado. Rode: pip install groq")
    exit(1)


class EIIGeradorMassa:
    def __init__(self, api_key=None, model="llama-3.3-70b-versatile"):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY nao configurado")
        self.client = Groq(api_key=self.api_key)
        self.model = model
        self.total_gerados = 0
        self.total_erros = 0

    def _criar_prompt(self, caso_base, n_variacoes):
        codigo = caso_base["codigo"]
        descricao = caso_base["descricao"]
        categoria = caso_base["categoria"]
        eventos = ", ".join(caso_base["eventos_afetados"])

        lines = []
        lines.append("Voce e especialista em eSocial.")
        lines.append("")
        lines.append("Gere EXATAMENTE " + str(n_variacoes) + " casos REAIS e DIFERENTES.")
        lines.append("")
        lines.append("REGRA OFICIAL:")
        lines.append("- Codigo: " + codigo)
        lines.append("- Descricao: " + descricao)
        lines.append("- Categoria: " + categoria)
        lines.append("- Eventos: " + eventos)
        lines.append("")
        lines.append("INSTRUCOES:")
        lines.append("1. Descricao UNICA por caso")
        lines.append("2. Varie empresas, setores, valores")
        lines.append("3. Inclua XML snippet com erro")
        lines.append("4. Ground truth completo")
        lines.append("5. Mesmo codigo: " + codigo)
        lines.append("")
        lines.append("FORMATO JSON (apenas array):")
        lines.append("[")
        lines.append('  {"question": "descricao", "xml_snippet": "<tag>valor</tag>", "ground_truth": "passos", "contexto_empresa": "empresa"},')
        lines.append("  ...")
        lines.append("]")
        lines.append("")
        lines.append("Apenas JSON valido.")

        return "\n".join(lines)

    def _parse_resposta(self, content, caso_base):
        import re
        json_match = re.search(r'\[.*\]', content, re.DOTALL)
        if json_match:
            try:
                variacoes = json.loads(json_match.group())
                for v in variacoes:
                    v["rejection_code"] = caso_base["codigo"]
                    v["event_type"] = caso_base["eventos_afetados"][0] if caso_base["eventos_afetados"] else "S-GERAL"
                    v["categoria"] = caso_base["categoria"]
                    v["complexidade"] = caso_base["complexidade"]
                    v["fonte"] = "Gerado via Groq"
                    v["caso_base_id"] = caso_base.get("codigo", "")
                    v["tipo"] = "variacao_sintetica"
                    v["gerado_em"] = datetime.now().isoformat()
                return variacoes
            except:
                pass
        return []

    def gerar_variacoes(self, caso_base, n_variacoes=5):
        prompt = self._criar_prompt(caso_base, n_variacoes)
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8,
                max_tokens=4000,
            )
            content = response.choices[0].message.content
            variacoes = self._parse_resposta(content, caso_base)
            self.total_gerados += len(variacoes)
            return variacoes
        except Exception as e:
            self.total_erros += 1
            print("  [ERRO] " + caso_base["codigo"] + ": " + str(e)[:80])
            return []

    def processar_lote(self, casos_base, n_variacoes=5, max_workers=3, delay=2.0):
        dataset_final = []

        for caso in casos_base:
            dataset_final.append({
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

        print("[Gerador] Originais: " + str(len(dataset_final)))
        print("[Gerador] Meta: " + str(len(casos_base) * n_variacoes) + " variacoes")
        print("[Gerador] Workers: " + str(max_workers) + " | Delay: " + str(delay) + "s")
        print("[Gerador] Estimativa: ~" + str(int((len(casos_base) * n_variacoes * delay) / 60)) + " min\n")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for i, caso in enumerate(casos_base):
                future = executor.submit(self.gerar_variacoes, caso, n_variacoes)
                futures[future] = (i, caso["codigo"])
                time.sleep(delay)

            for future in as_completed(futures):
                i, codigo = futures[future]
                try:
                    variacoes = future.result(timeout=60)
                    dataset_final.extend(variacoes)
                    if (i + 1) % 10 == 0:
                        print("[Gerador] " + str(i+1) + "/" + str(len(casos_base)) + " | Gerados: " + str(self.total_gerados) + " | Erros: " + str(self.total_erros))
                except Exception as e:
                    print("  [ERRO] Futuro " + codigo + ": " + str(e))

        return dataset_final

    def curadoria(self, dataset):
        from difflib import SequenceMatcher
        def similar(a, b):
            return SequenceMatcher(None, a, b).ratio() > 0.85

        unicos = []
        seen = set()
        for caso in dataset:
            key = caso.get("rejection_code", "") + "_" + caso.get("question", "")[:60]
            if key not in seen:
                seen.add(key)
                unicos.append(caso)

        validos = []
        for caso in unicos:
            gt = caso.get("ground_truth", "")
            q = caso.get("question", "")
            rc = caso.get("rejection_code", "")
            if gt and len(gt) > 20 and q and len(q) > 10 and rc and rc.isdigit():
                validos.append(caso)

        print("[Curadoria] " + str(len(dataset)) + " -> " + str(len(unicos)) + " unicos -> " + str(len(validos)) + " validos")
        return validos


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/casos_manual.json")
    parser.add_argument("--output", default="data/dataset_bulk.json")
    parser.add_argument("--variacoes", type=int, default=5)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--delay", type=float, default=2.0)
    parser.add_argument("--max-casos", type=int, default=None)
    args = parser.parse_args()

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("[ERRO] GROQ_API_KEY nao configurado")
        exit(1)

    print("[Main] Carregando: " + args.input)
    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    casos_base = data["casos"]
    if args.max_casos:
        casos_base = casos_base[:args.max_casos]
        print("[Main] Limitado a " + str(args.max_casos) + " casos")

    print("[Main] Casos base: " + str(len(casos_base)))

    gerador = EIIGeradorMassa(api_key=api_key)
    inicio = time.time()
    dataset = gerador.processar_lote(casos_base, args.variacoes, args.workers, args.delay)
    dataset_final = gerador.curadoria(dataset)

    output_data = {
        "meta": {
            "fonte": "EII Dataset Bulk",
            "data_geracao": datetime.now().isoformat(),
            "casos_base": len(casos_base),
            "variacoes_por_caso": args.variacoes,
            "total_gerado": gerador.total_gerados,
            "total_erros": gerador.total_erros,
            "total_final": len(dataset_final),
            "tempo_minutos": round((time.time() - inicio) / 60, 1),
        },
        "casos": dataset_final,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    cats = Counter(c["categoria"] for c in dataset_final)
    comps = Counter(c["complexidade"] for c in dataset_final)
    tipos = Counter(c.get("tipo", "unknown") for c in dataset_final)

    print("\n" + "="*60)
    print("DATASET BULK - RESUMO FINAL")
    print("="*60)
    print("Total: " + str(len(dataset_final)))
    print("  Originais: " + str(tipos.get("original_manual", 0)))
    print("  Sinteticas: " + str(tipos.get("variacao_sintetica", 0)))
    print("\nPor categoria:")
    for cat, n in cats.most_common():
        print("  " + cat + ": " + str(n))
    print("\nPor complexidade:")
    for comp, n in comps.most_common():
        print("  " + comp + ": " + str(n))
    print("\nTempo: " + str(output_data["meta"]["tempo_minutos"]) + " min")
    print("Arquivo: " + args.output)
    print("Tamanho: " + str(round(os.path.getsize(args.output) / 1024, 1)) + " KB")
    print("="*60)


if __name__ == "__main__":
    main()
