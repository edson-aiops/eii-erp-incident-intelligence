
# ============================================================
# EII - Script Autocriador + Gerador de Massa
# Cria o arquivo Python automaticamente e executa
# Cole no PowerShell e aperte Enter
# ============================================================

# 1. Configurar encoding
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# 2. Verificar chave Groq
if (-not $env:GROQ_API_KEY) {
    Write-Host "[ERRO] GROQ_API_KEY nao configurada" -ForegroundColor Red
    Write-Host "Configure: $env:GROQ_API_KEY = 'sua-chave'" -ForegroundColor Yellow
    exit 1
}

# 3. Verificar casos base
if (-not (Test-Path "data/casos_manual.json")) {
    Write-Host "[ERRO] data/casos_manual.json nao encontrado" -ForegroundColor Red
    Write-Host "Rode o parser primeiro: .\eii_setup_automatico.ps1" -ForegroundColor Yellow
    exit 1
}

# 4. Instalar groq se necessario
Write-Host "[EII] Verificando groq..." -ForegroundColor Green
try {
    python -c "import groq" 2>$null
    Write-Host "[EII] groq OK" -ForegroundColor Green
} catch {
    Write-Host "[EII] Instalando groq..." -ForegroundColor Yellow
    pip install groq
}

# 5. CRIAR o arquivo gerador automaticamente
$geradorPath = "eii_gerador_massa.py"
Write-Host "[EII] Criando $geradorPath..." -ForegroundColor Green

$geradorCode = @"
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
    def __init__(self, api_key=None, model='llama-3.3-70b-versatile'):
        self.api_key = api_key or os.getenv('GROQ_API_KEY')
        if not self.api_key:
            raise ValueError('GROQ_API_KEY nao configurado')
        self.client = Groq(api_key=self.api_key)
        self.model = model
        self.total_gerados = 0
        self.total_erros = 0

    def _criar_prompt(self, caso_base, n_variacoes):
        return f\"\"\"Voce e especialista em eSocial.

Gere EXATAMENTE {n_variacoes} casos REAIS e DIFERENTES.

REGRA OFICIAL:
- Codigo: {caso_base['codigo']}
- Descricao: {caso_base['descricao']}
- Categoria: {caso_base['categoria']}
- Eventos: {', '.join(caso_base['eventos_afetados'])}

INSTRUCOES:
1. Descricao UNICA por caso
2. Varie empresas, setores, valores
3. Inclua XML snippet com erro
4. Ground truth completo
5. Mesmo codigo: {caso_base['codigo']}

FORMATO JSON (apenas array):
[
  {{
    'question': 'descricao do problema',
    'xml_snippet': '<tag>valor</tag>',
    'ground_truth': 'passos correcao',
    'contexto_empresa': 'empresa ficticia'
  }},
  ...
]

Apenas JSON valido.\"\"\"

    def _parse_resposta(self, content, caso_base):
        import re
        json_match = re.search(r'\[.*\]', content, re.DOTALL)
        if json_match:
            try:
                variacoes = json.loads(json_match.group())
                for v in variacoes:
                    v['rejection_code'] = caso_base['codigo']
                    v['event_type'] = caso_base['eventos_afetados'][0] if caso_base['eventos_afetados'] else 'S-GERAL'
                    v['categoria'] = caso_base['categoria']
                    v['complexidade'] = caso_base['complexidade']
                    v['fonte'] = f\"Gerado via Groq de: {caso_base['fonte']}\"
                    v['caso_base_id'] = caso_base.get('codigo', '')
                    v['tipo'] = 'variacao_sintetica'
                    v['gerado_em'] = datetime.now().isoformat()
                return variacoes
            except:
                pass
        return []

    def gerar_variacoes(self, caso_base, n_variacoes=5):
        prompt = self._criar_prompt(caso_base, n_variacoes)
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{'role': 'user', 'content': prompt}],
                temperature=0.8,
                max_tokens=4000,
            )
            content = response.choices[0].message.content
            variacoes = self._parse_resposta(content, caso_base)
            self.total_gerados += len(variacoes)
            return variacoes
        except Exception as e:
            self.total_erros += 1
            print(f\"  [ERRO] {caso_base['codigo']}: {str(e)[:80]}\")
            return []

    def processar_lote(self, casos_base, n_variacoes=5, max_workers=3, delay=2.0):
        dataset_final = []

        # Adicionar originais
        for caso in casos_base:
            dataset_final.append({
                'question': caso['descricao'],
                'rejection_code': caso['codigo'],
                'event_type': caso['eventos_afetados'][0] if caso['eventos_afetados'] else 'S-GERAL',
                'ground_truth': caso['acao_sugerida'],
                'categoria': caso['categoria'],
                'complexidade': caso['complexidade'],
                'xml_tag': caso.get('xml_tag'),
                'fonte': caso['fonte'],
                'tipo': 'original_manual',
                'pagina': caso.get('pagina'),
            })

        print(f\"[Gerador] Originais: {len(dataset_final)}\")
        print(f\"[Gerador] Meta: {len(casos_base) * n_variacoes} variacoes\")
        print(f\"[Gerador] Workers: {max_workers} | Delay: {delay}s\")
        print(f\"[Gerador] Estimativa: ~{(len(casos_base) * n_variacoes * delay) / 60:.0f} min\n\")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for i, caso in enumerate(casos_base):
                future = executor.submit(self.gerar_variacoes, caso, n_variacoes)
                futures[future] = (i, caso['codigo'])
                time.sleep(delay)

            for future in as_completed(futures):
                i, codigo = futures[future]
                try:
                    variacoes = future.result(timeout=60)
                    dataset_final.extend(variacoes)
                    if (i + 1) % 10 == 0:
                        print(f\"[Gerador] {i+1}/{len(casos_base)} | Gerados: {self.total_gerados} | Erros: {self.total_erros}\")
                except Exception as e:
                    print(f\"  [ERRO] Futuro {codigo}: {e}\")

        return dataset_final

    def curadoria(self, dataset):
        from difflib import SequenceMatcher
        def similar(a, b):
            return SequenceMatcher(None, a, b).ratio() > 0.85

        unicos = []
        seen = set()
        for caso in dataset:
            key = f\"{caso.get('rejection_code', '')}_{caso.get('question', '')[:60]}\"
            if key not in seen:
                seen.add(key)
                unicos.append(caso)

        validos = []
        for caso in unicos:
            gt = caso.get('ground_truth', '')
            q = caso.get('question', '')
            rc = caso.get('rejection_code', '')
            if gt and len(gt) > 20 and q and len(q) > 10 and rc and rc.isdigit():
                validos.append(caso)

        print(f\"[Curadoria] {len(dataset)} -> {len(unicos)} unicos -> {len(validos)} validos\")
        return validos


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default='data/casos_manual.json')
    parser.add_argument('--output', default='data/dataset_bulk.json')
    parser.add_argument('--variacoes', type=int, default=5)
    parser.add_argument('--workers', type=int, default=3)
    parser.add_argument('--delay', type=float, default=2.0)
    parser.add_argument('--max-casos', type=int, default=None)
    args = parser.parse_args()

    api_key = os.getenv('GROQ_API_KEY')
    if not api_key:
        print('[ERRO] GROQ_API_KEY nao configurado')
        exit(1)

    print(f'[Main] Carregando: {args.input}')
    with open(args.input, 'r', encoding='utf-8') as f:
        data = json.load(f)

    casos_base = data['casos']
    if args.max_casos:
        casos_base = casos_base[:args.max_casos]
        print(f'[Main] Limitado a {args.max_casos} casos')

    print(f'[Main] Casos base: {len(casos_base)}')

    gerador = EIIGeradorMassa(api_key=api_key)
    inicio = time.time()
    dataset = gerador.processar_lote(casos_base, args.variacoes, args.workers, args.delay)
    dataset_final = gerador.curadoria(dataset)

    output_data = {
        'meta': {
            'fonte': 'EII Dataset Bulk',
            'data_geracao': datetime.now().isoformat(),
            'casos_base': len(casos_base),
            'variacoes_por_caso': args.variacoes,
            'total_gerado': gerador.total_gerados,
            'total_erros': gerador.total_erros,
            'total_final': len(dataset_final),
            'tempo_minutos': round((time.time() - inicio) / 60, 1),
        },
        'casos': dataset_final,
    }

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    cats = Counter(c['categoria'] for c in dataset_final)
    comps = Counter(c['complexidade'] for c in dataset_final)
    tipos = Counter(c.get('tipo', 'unknown') for c in dataset_final)

    print('\n' + '='*60)
    print('DATASET BULK - RESUMO FINAL')
    print('='*60)
    print(f'Total: {len(dataset_final)}')
    print(f'  Originais: {tipos.get(\"original_manual\", 0)}')
    print(f'  Sinteticas: {tipos.get(\"variacao_sintetica\", 0)}')
    print('\nPor categoria:')
    for cat, n in cats.most_common():
        print(f'  {cat}: {n}')
    print('\nPor complexidade:')
    for comp, n in comps.most_common():
        print(f'  {comp}: {n}')
    print(f'\nTempo: {output_data[\"meta\"][\"tempo_minutos\"]:.1f} min')
    print(f'Arquivo: {args.output}')
    print(f'Tamanho: {os.path.getsize(args.output) / 1024:.1f} KB')
    print('='*60)


if __name__ == '__main__':
    main()
"@

Set-Content -Path $geradorPath -Value $geradorCode -Encoding UTF8
Write-Host "[EII] Gerador criado: $geradorPath" -ForegroundColor Green

# 6. Perguntar quantas variações
Write-Host "`n[EII] Escolha o modo:" -ForegroundColor Cyan
Write-Host "  1. TESTE RAPIDO - 10 casos, 3 variações (~5 min)" -ForegroundColor Yellow
Write-Host "  2. PADRAO - 428 casos, 5 variações (~50 min, ~2.140 casos)" -ForegroundColor Green
Write-Host "  3. MAXIMO - 428 casos, 10 variações (~100 min, ~4.280 casos)" -ForegroundColor Magenta
Write-Host "  4. CUSTOM - voce define" -ForegroundColor White

$escolha = Read-Host "Digite 1, 2, 3 ou 4"

switch ($escolha) {
    "1" {
        Write-Host "[EII] Modo TESTE RAPIDO" -ForegroundColor Yellow
        python $geradorPath --max-casos 10 --variacoes 3 --output data/teste.json
    }
    "2" {
        Write-Host "[EII] Modo PADRAO" -ForegroundColor Green
        python $geradorPath --input data/casos_manual.json --output data/dataset_bulk.json --variacoes 5
    }
    "3" {
        Write-Host "[EII] Modo MAXIMO" -ForegroundColor Magenta
        python $geradorPath --input data/casos_manual.json --output data/dataset_maximo.json --variacoes 10
    }
    "4" {
        $maxCasos = Read-Host "Quantos casos base? (max 428)"
        $variacoes = Read-Host "Quantas variacoes por caso?"
        $outputName = Read-Host "Nome do arquivo de saida (ex: dataset_custom.json)"
        python $geradorPath --max-casos $maxCasos --variacoes $variacoes --output "data/$outputName"
    }
    default {
        Write-Host "[EII] Opcao invalida. Rodando modo TESTE..." -ForegroundColor Yellow
        python $geradorPath --max-casos 5 --variacoes 2 --output data/teste.json
    }
}

Write-Host "`n[EII] Concluido!" -ForegroundColor Green
