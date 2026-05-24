import fitz
import json
import argparse
from datetime import datetime
from collections import Counter

def extrair_casos_do_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    casos = []
    print(f"[Parser] PDF: {pdf_path} | Paginas: {len(doc)}")

    for page_num in range(len(doc)):
        if page_num % 100 == 0:
            print(f"[Parser] Pagina {page_num + 1}/{len(doc)}...")

        page = doc[page_num]
        texto = page.get_text()
        linhas = texto.split('\n')

        i = 0
        while i < len(linhas):
            linha = linhas[i].strip()

            if linha and linha[0].isdigit():
                partes = linha.split(None, 1)
                if partes and partes[0].isdigit():
                    codigo = partes[0]
                    if 3 <= len(codigo) <= 4 and codigo.isdigit():
                        descricao = partes[1] if len(partes) > 1 else ""

                        contexto = []
                        j = i + 1
                        while j < len(linhas):
                            prox = linhas[j].strip()
                            if not prox:
                                j += 1
                                continue
                            if prox[0].isdigit() and prox.split(None, 1)[0].isdigit():
                                break
                            if any(prox.startswith(x) for x in ['NOTA', 'OBS', 'Exemplo', 'Tabela', 'Figura']):
                                break
                            contexto.append(prox)
                            if len(contexto) > 20:
                                break
                            j += 1

                        texto_contexto = ' '.join(contexto)

                        import re
                        eventos = re.findall(r'S[-\s]?(\d{4})', texto_contexto)
                        eventos = [f"S-{e}" for e in eventos] if eventos else ["S-GERAL"]

                        texto_lower = (descricao + ' ' + texto_contexto).lower()
                        categoria = "outros"
                        if any(x in texto_lower for x in ['cnpj', 'cei', 'caepf', 'identif']):
                            categoria = "identificacao"
                        elif any(x in texto_lower for x in ['remun', 'salario', 'rubric', 'vlr']):
                            categoria = "remuneracao"
                        elif any(x in texto_lower for x in ['admis', 'contrat', 'vinculo', 'dtadm']):
                            categoria = "admissao"
                        elif any(x in texto_lower for x in ['deslig', 'demiss', 'rescis', 'afast']):
                            categoria = "desligamento"
                        elif any(x in texto_lower for x in ['afast', 'licenc', 'atestado']):
                            categoria = "afastamento"
                        elif any(x in texto_lower for x in ['folha', 'periodo', 'competenc']):
                            categoria = "folha"
                        elif any(x in texto_lower for x in ['benef', 'previdenc', 'aposent']):
                            categoria = "beneficios"
                        elif any(x in texto_lower for x in ['fgts', 'guia', 'recolh']):
                            categoria = "fgts"

                        if any(x in texto_lower for x in ['multi', 'sobrepos', 'pro-rata', 'calculo']):
                            complexidade = "critical"
                        elif any(x in texto_lower for x in ['validar', 'consultar', 'confirmar', 'cruzamento']):
                            complexidade = "high"
                        elif len(texto_contexto) > 300:
                            complexidade = "medium"
                        else:
                            complexidade = "low"

                        tags = re.findall(r'<(\w+)>', texto_contexto)
                        xml_tag = tags[0] if tags else None

                        caso = {
                            "codigo": codigo,
                            "descricao": descricao[:300],
                            "contexto": texto_contexto[:500],
                            "acao_sugerida": texto_contexto[:500],
                            "eventos_afetados": eventos[:3],
                            "categoria": categoria,
                            "complexidade": complexidade,
                            "xml_tag": xml_tag,
                            "fonte": f"Manual eSocial S-1.3, pagina {page_num + 1}",
                            "pagina": page_num + 1,
                        }
                        casos.append(caso)
                        i = j
                        continue
            i += 1

    doc.close()

    unicos = []
    seen = set()
    for caso in casos:
        key = f"{caso['codigo']}_{caso['descricao'][:50]}"
        if key not in seen:
            seen.add(key)
            unicos.append(caso)

    print(f"[Parser] Brutos: {len(casos)} | Unicos: {len(unicos)}")
    return unicos

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--output", default="casos_manual.json")
    parser.add_argument("--resumo", action="store_true")
    args = parser.parse_args()

    casos = extrair_casos_do_pdf(args.pdf)

    output = {
        "meta": {
            "fonte": "Manual eSocial S-1.3",
            "data_extracao": datetime.now().isoformat(),
            "total_casos": len(casos),
            "parser": "auto v1.0",
        },
        "casos": casos,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"[Parser] Salvo: {args.output} ({len(casos)} casos)")

    if args.resumo:
        cats = Counter(c["categoria"] for c in casos)
        comps = Counter(c["complexidade"] for c in casos)
        print("\n" + "="*50)
        print("RESUMO")
        print("="*50)
        print(f"Total: {len(casos)}")
        print("\nPor categoria:")
        for cat, n in cats.most_common():
            print(f"  {cat}: {n}")
        print("\nPor complexidade:")
        for comp, n in comps.most_common():
            print(f"  {comp}: {n}")
        print("="*50)

if __name__ == "__main__":
    main()
