"""
End-to-end automated test against HF Space: EdsonPO/eii-incident-intelligence
Protocol: POST /call/analyze_xml  →  GET /call/analyze_xml/{event_id}  (SSE)
Pure requests — no gradio_client.
"""

import os
import re
import sys
import time
import json
import requests

# Force UTF-8 output on Windows (avoids CP1252 UnicodeEncodeError)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE_URL = "https://edsonpo-eii-incident-intelligence.hf.space"
SUBMIT_URL = f"{BASE_URL}/call/analyze_xml"
TIMEOUT_SUBMIT = 30
TIMEOUT_STREAM = 120          # total wall-clock limit per test

HF_TOKEN = os.environ.get("HF_TOKEN")
HEADERS = {"Content-Type": "application/json"}
if HF_TOKEN:
    HEADERS["Authorization"] = f"Bearer {HF_TOKEN}"

# ---------------------------------------------------------------------------
# Fixtures inline
# ---------------------------------------------------------------------------
XML_S1200 = """\
<?xml version="1.0" encoding="UTF-8"?>
<eSocial xmlns="http://www.esocial.gov.br/schema/evt/evtRemun/v04_00_00">
  <evtRemun Id="ID1200000000000000000000000000000000000001">
    <ideEvento>
      <indRetif>3</indRetif>
      <nrRec>1.2.202403.0000001</nrRec>
      <tpAmb>1</tpAmb>
    </ideEvento>
    <ideEmpregador>
      <tpInsc>1</tpInsc>
      <nrInsc>12345678000195</nrInsc>
    </ideEmpregador>
    <retornoEvento>
      <evento Id="ID1200000000000000000000000000000000000001">
        <retornoProcessamento>
          <cdResposta>401</cdResposta>
          <descResposta>Rejeitado</descResposta>
          <ocorrencias>
            <ocorrencia>
              <tipo>E</tipo>
              <codigo>MA105</codigo>
              <descricao>Valor do campo [indRetif] invalido. Primeira transmissao deve ser original (indRetif=1).</descricao>
              <localizacaoErro>//evtRemun/ideEvento/indRetif</localizacaoErro>
            </ocorrencia>
          </ocorrencias>
        </retornoProcessamento>
      </evento>
    </retornoEvento>
  </evtRemun>
</eSocial>"""

XML_S2200 = """\
<?xml version="1.0" encoding="UTF-8"?>
<eSocial xmlns="http://www.esocial.gov.br/schema/evt/evtAdmissao/v03_00_00">
  <evtAdmissao Id="ID2200000000000000000000000000000000000001">
    <ideEvento>
      <indRetif>2</indRetif>
      <nrRec>1.2.202403.0000002</nrRec>
      <tpAmb>1</tpAmb>
    </ideEvento>
    <ideEmpregador>
      <tpInsc>1</tpInsc>
      <nrInsc>12345678000195</nrInsc>
    </ideEmpregador>
    <retornoEvento>
      <evento Id="ID2200000000000000000000000000000000000001">
        <retornoProcessamento>
          <cdResposta>401</cdResposta>
          <descResposta>Rejeitado</descResposta>
          <ocorrencias>
            <ocorrencia>
              <tipo>E</tipo>
              <codigo>E312</codigo>
              <descricao>Vinculo empregaticio nao encontrado. O trabalhador nao possui vinculo ativo para retificacao.</descricao>
              <localizacaoErro>//evtAdmissao/ideVinculo</localizacaoErro>
            </ocorrencia>
          </ocorrencias>
        </retornoProcessamento>
      </evento>
    </retornoEvento>
  </evtAdmissao>
</eSocial>"""

XML_INVALID = """\
<?xml version="1.0" encoding="UTF-8"?>
<eSocial xmlns="http://www.esocial.gov.br/schema/evt/evtRemun/v04_00_00">
  <evtRemun Id="ID_MALFORMED">
    <ideEvento>
      <indRetif>1</indRetif>
      <tpAmb>1
    </ideEvento>
  <!-- fechamento ausente propositalmente
"""

# ---------------------------------------------------------------------------
# Gradio SSE caller
# ---------------------------------------------------------------------------

def call_analyze_xml(xml: str) -> tuple[list, float]:
    """
    Submit XML to analyze_xml and collect the SSE response.
    Returns (data_array, elapsed_seconds).
    Raises on HTTP errors or timeout.
    """
    t0 = time.time()

    # Step 1 — submit job
    r1 = requests.post(
        SUBMIT_URL,
        headers=HEADERS,
        json={"data": [xml]},
        timeout=TIMEOUT_SUBMIT,
    )
    r1.raise_for_status()
    event_id = r1.json()["event_id"]

    # Step 2 — stream result (SSE)
    stream_url = f"{SUBMIT_URL}/{event_id}"
    with requests.get(stream_url, headers=HEADERS, stream=True,
                      timeout=TIMEOUT_STREAM) as r2:
        r2.raise_for_status()
        last_data: list | None = None
        for raw_line in r2.iter_lines(decode_unicode=True):
            if not raw_line:
                continue
            if raw_line.startswith("data:"):
                payload = raw_line[5:].strip()
                last_data = json.loads(payload)
            # "event: complete" signals the final message was already sent

    elapsed = time.time() - t0
    if last_data is None:
        raise ValueError("SSE stream ended without a data line")
    return last_data, elapsed


# ---------------------------------------------------------------------------
# Markdown parsers
# ---------------------------------------------------------------------------
INCIDENT_ID_RE = re.compile(r"\bINC-\d{8}-\d{6}\b")
SEVERIDADE_RE  = re.compile(r"\*\*Severidade\*\*\s*\|\s*[^\|]*\*\*([A-ZÁÉÍÓÚÇ]+)\*\*")
CONFIANCA_RE   = re.compile(r"\*\*Confiança IA\*\*\s*\|\s*[^\|]*?(ALTA|MÉDIA|BAIXA)")
FONTE_RE       = re.compile(r"\*\*Fonte do diagnóstico\*\*\s*\|\s*`([A-Z_]+)`")


def parse_fields(arr: list) -> dict:
    """Extract structured fields from the Gradio response array."""
    md: str = arr[0] if arr else ""

    # incident_id — prefer arr[2] (plain text), fall back to heading
    inc_id = (arr[2].strip() if len(arr) > 2 and arr[2] else None)
    if not inc_id:
        m = INCIDENT_ID_RE.search(md)
        inc_id = m.group(0) if m else None

    # Detect PARSE_ERROR via heading emoji ❌
    is_parse_error = md.startswith("## ❌") or "Erro ao interpretar o XML" in md[:120]
    if is_parse_error:
        return {
            "incident_id": inc_id,       # may be None
            "severidade": None,
            "confianca": None,
            "fonte": "PARSE_ERROR",
            "passos_resolucao": [],
        }

    # severidade
    m = SEVERIDADE_RE.search(md)
    severidade = m.group(1) if m else None

    # confiança
    m = CONFIANCA_RE.search(md)
    confianca = m.group(1) if m else None

    # fonte
    m = FONTE_RE.search(md)
    fonte = m.group(1) if m else None

    # passos_resolucao — numbered lines under the "Passos" section
    passos: list[str] = []
    in_passos = False
    for line in md.splitlines():
        if re.search(r"Passos de Resolução", line):
            in_passos = True
            continue
        if in_passos:
            if line.startswith("#"):   # next section
                break
            stripped = line.strip()
            if re.match(r"^\d+\.", stripped):
                passos.append(stripped)

    return {
        "incident_id": inc_id,
        "severidade": severidade,
        "confianca": confianca,
        "fonte": fonte,
        "passos_resolucao": passos,
    }


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------
VALID_SEVERIDADES = {"CRÍTICO", "ALTO", "MÉDIO", "BAIXO"}
VALID_CONFIANÇAS  = {"ALTA", "MÉDIA", "BAIXA"}
VALID_FONTES      = {"KB_MATCH", "LLM_FALLBACK", "PARSE_ERROR"}


def validate(fields: dict, is_parse_error_expected: bool) -> list[str]:
    """Return list of failure messages (empty = PASS)."""
    failures = []
    fonte = fields.get("fonte")

    # fonte always required
    if not fonte:
        failures.append("campo 'fonte' ausente")
    elif fonte not in VALID_FONTES:
        failures.append(f"fonte '{fonte}' inválida (esperado {VALID_FONTES})")

    actual_parse_error = (fonte == "PARSE_ERROR")

    if not actual_parse_error:
        # incident_id
        inc_id = fields.get("incident_id")
        if not inc_id:
            failures.append("campo 'incident_id' ausente")
        elif not INCIDENT_ID_RE.fullmatch(inc_id):
            failures.append(
                f"incident_id '{inc_id}' fora do formato INC-YYYYMMDD-HHMMSS"
            )

        # severidade
        sev = fields.get("severidade")
        if not sev:
            failures.append("campo 'severidade' ausente")
        elif sev not in VALID_SEVERIDADES:
            failures.append(f"severidade '{sev}' inválida (esperado {VALID_SEVERIDADES})")

        # confiança
        conf = fields.get("confianca")
        if not conf:
            failures.append("campo 'confianca' ausente")
        elif conf not in VALID_CONFIANÇAS:
            failures.append(
                f"confianca '{conf}' inválida (esperado {VALID_CONFIANÇAS})"
            )

        # passos_resolucao — lista não vazia
        passos = fields.get("passos_resolucao", [])
        if not isinstance(passos, list) or len(passos) == 0:
            failures.append("'passos_resolucao' deve ser lista não vazia")

    return failures


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------
TEST_CASES = [
    {
        "name": "XML_S1200",
        "xml": XML_S1200,
        "parse_error_expected": False,
        "description": "S-1200 rejeição MA105 (indRetif inválido)",
    },
    {
        "name": "XML_S2200",
        "xml": XML_S2200,
        "parse_error_expected": False,
        "description": "S-2200 rejeição E312 (vínculo não encontrado)",
    },
    {
        "name": "XML_INVALID",
        "xml": XML_INVALID,
        "parse_error_expected": True,
        "description": "XML malformado → PARSE_ERROR sem crash",
    },
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_tests() -> int:
    passed = 0
    total = len(TEST_CASES)

    print(f"\n{'='*62}")
    print("  EII End-to-End Tests — HF Space")
    print(f"  {BASE_URL}")
    print(f"{'='*62}\n")

    for tc in TEST_CASES:
        name = tc["name"]
        try:
            arr, elapsed = call_analyze_xml(tc["xml"])

            if elapsed >= TIMEOUT_STREAM:
                print(
                    f"[FAIL] {name} — tempo={elapsed:.1f}s excedeu "
                    f"{TIMEOUT_STREAM}s"
                )
                continue

            fields = parse_fields(arr)
            failures = validate(fields, tc["parse_error_expected"])

            if failures:
                detail = "; ".join(failures)
                print(f"[FAIL] {name} — {detail}")
            else:
                sev   = fields.get("severidade") or "—"
                conf  = fields.get("confianca")  or "—"
                fonte = fields.get("fonte")      or "—"
                print(
                    f"[PASS] {name} — severidade={sev}, confianca={conf}, "
                    f"fonte={fonte}, tempo={elapsed:.1f}s"
                )
                passed += 1

        except requests.exceptions.Timeout:
            print(f"[FAIL] {name} — timeout ({TIMEOUT_STREAM}s excedido)")
        except requests.exceptions.ConnectionError as exc:
            print(f"[FAIL] {name} — erro de conexão: {exc}")
        except Exception as exc:  # noqa: BLE001
            print(f"[FAIL] {name} — {type(exc).__name__}: {exc}")

    print(f"\n{'='*62}")
    print(f"  Resultado: {passed}/{total} testes passaram")
    print(f"{'='*62}\n")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(run_tests())
