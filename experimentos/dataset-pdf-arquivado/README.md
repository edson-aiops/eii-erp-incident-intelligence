# Experimento Arquivado: Extração de Dataset via PDF

**Data do experimento:** 19-20/05/2026  
**Data do arquivamento:** 20/05/2026  
**Responsável:** Agentes IA (Claude, Qwen) + Edson Oliveira

---

## O que foi tentado

Extrair um dataset de casos de rejeição do eSocial a partir do **Manual de Orientação do eSocial S-1.3** (PDF oficial do governo), usando scripts de parsing automático com PyMuPDF e geração de variações via templates e LLM (Groq).

Pipeline executado:
1. `eii_pdf_parser_auto.py` / `eii_pdf_parser.py` → extraíram 428 "casos" do PDF
2. `eii_gerador_templates.py` / `eii_gerador_variacoes.py` → geraram 2.568 variações sintéticas
3. `eii_gerador_final.py` → adicionou casos complexos high/critical
4. `eii_pipeline_dataset.py` → validou amostra e criou golden dataset (300 casos)

---

## Por que foi arquivado

**O manual de orientação S-1.3 é a fonte ERRADA.**

- Ele é um **manual técnico de referência**, não um catálogo de erros/rejeições.
- Não possui estrutura "código de erro → descrição do problema → ação corretiva".
- Os "códigos" extraídos (1000, 101, 105, 301, 501, 721, etc.) são **códigos de categoria de trabalhador** e identificadores de eventos (S-1000, S-2200), não códigos de rejeição.
- O campo `acao_sugerida` ficava **duplicado do contexto** em 100% dos casos (bug de design no parser: a mesma variável `texto_contexto` era copiada para ambos os campos).
- 346 casos (81%) tinham descrição inútil (< 5 caracteres) porque o parser capturava apenas a primeira linha do PDF.
- O dataset final continha 346 casos com `question` vazia (14% lixo estrutural).
- O golden dataset de 300 casos tinha 120 casos inúteis (40%).

**Resultado:** o dataset gerado não representa casos reais de rejeição do eSocial e não serve para treinar o agente EII.

---

## Lição aprendida

> **Validar a ADEQUAÇÃO da fonte de dados antes de extrair em escala.**

Um documento oficial não é automaticamente uma fonte de treinamento válida. É necessário confirmar que ele contém a estrutura semântica esperada (erro → causa → solução) antes de investir tempo em parsers e geradores.

---

## Fonte correta para o futuro

Para extrair códigos de rejeição reais do eSocial, a fonte adequada é:

- **Tabela de Regras de Validação do eSocial** (Anexo II dos leiautes)
- **Mensagens de retorno do Ambiente Nacional** (códigos de erro RS_*, VR_*, etc.)
- **Base de incidentes reais** (como os 93 casos curados manualmente em `knowledge_base.py`)

---

## Status

**Arquivado, não deletado.**  
Os scripts e dados permanecem nesta pasta para referência histórica e análise de erros. Não devem ser usados em produção nem mergeados de volta para a aplicação principal.

---

## Estrutura do arquivamento

```
experimentos/dataset-pdf-arquivado/
├── README.md              <- este arquivo
├── scripts/               <- scripts do experimento
│   ├── eii_pdf_parser.py
│   ├── eii_pdf_parser_auto.py
│   ├── eii_gerador_templates.py
│   ├── eii_gerador_variacoes.py
│   ├── eii_gerador_final.py
│   ├── eii_gerador_massa_fix.py
│   ├── gerador_v2.py
│   ├── eii_pipeline_dataset.py
│   ├── eii_validador_auto.py
│   ├── eii_setup_automatico.ps1
│   ├── EII_GERADOR_AUTO.ps1
│   └── EII_VALIDADOR_AUTO_CRIAR.ps1
└── dados/                 <- datasets gerados
    ├── casos_manual.json
    ├── dataset_templates.json
    ├── dataset_final.json
    ├── golden_dataset_300.json
    ├── eii_kb.sqlite
    ├── validacao_amostra.json
    ├── lote1.json
    └── teste.json
```
