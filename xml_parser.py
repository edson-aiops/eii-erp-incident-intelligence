"""
EII — XML Parser (eSocial + EFD-Reinf)
Parses government rejection responses from eSocial and EFD-Reinf webservices.
eSocial:   retornoEnvioLoteEventos, retornoEvento, retornoProcessamentoEvento
EFD-Reinf: retornoLoteEventos, retornoEvt* (R-1000..R-9001)
"""

import xml.etree.ElementTree as ET
import re
from dataclasses import dataclass, field
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# PII scrubbing — CPF, CNPJ, NIS/PIS, nmTrab
# Order matters: CNPJ (14 digits) before CPF/NIS (11 digits);
#                XML-tag patterns before bare-digit patterns.
# ─────────────────────────────────────────────────────────────────────────────

_RE_CNPJ_FMT = re.compile(r'\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b')
_RE_CNPJ_RAW = re.compile(r'\b\d{14}\b')
_RE_NIS_FMT  = re.compile(r'\b\d{3}\.\d{5}\.\d{2}-\d{1}\b')
_RE_NIS_XML  = re.compile(r'(<nisTrabalh>)(\d{11})(</nisTrabalh>)', re.IGNORECASE)
_RE_NM_TRAB  = re.compile(r'(<nmTrab>)[^<]+(</nmTrab>)', re.IGNORECASE)
_RE_CPF_FMT  = re.compile(r'\b\d{3}\.\d{3}\.\d{3}-\d{2}\b')
_RE_CPF_RAW  = re.compile(r'\b\d{11}\b')

# EFD-Reinf PII — XML tags específicas (CNPJ/CPF dentro de tags de negócio)
_RE_CNPJ_CONTRI  = re.compile(r'(<cnpjContri>)(\d{14})(</cnpjContri>)', re.IGNORECASE)
_RE_CNPJ_PREST   = re.compile(r'(<cnpjPrestador>)(\d{14})(</cnpjPrestador>)', re.IGNORECASE)
_RE_CNPJ_TOMAD   = re.compile(r'(<cnpjTomador>)(\d{14})(</cnpjTomador>)', re.IGNORECASE)
_RE_CPF_PROD     = re.compile(r'(<cpfProdRural>)(\d{11})(</cpfProdRural>)', re.IGNORECASE)


def scrub_pii(text: str) -> str:
    """Mask CPF, CNPJ, NIS/PIS and worker name before LLM prompts and persistence."""
    if not text:
        return text

    def _mask(m: re.Match, label: str, keep: int) -> str:
        digits = re.sub(r'\D', '', m.group())
        return f'[{label}/****{digits[-keep:]}]'

    text = _RE_CNPJ_FMT.sub(lambda m: _mask(m, 'CNPJ', 2), text)
    text = _RE_CNPJ_RAW.sub(lambda m: _mask(m, 'CNPJ', 2), text)
    text = _RE_NIS_FMT.sub( lambda m: _mask(m, 'NIS',  1), text)
    # NIS/PIS inside <nisTrabalh> XML tag (11 digits, no punctuation)
    text = _RE_NIS_XML.sub(
        lambda m: f"{m.group(1)}[NIS/****{m.group(2)[-1:]}]{m.group(3)}", text
    )
    # Worker name inside <nmTrab> XML tag
    text = _RE_NM_TRAB.sub(lambda m: f"{m.group(1)}[NOME_SUPRIMIDO]{m.group(2)}", text)
    text = _RE_CPF_FMT.sub( lambda m: _mask(m, 'CPF',  2), text)
    # CPF without formatting: \b\d{11}\b (also catches bare NIS not in XML tags)
    text = _RE_CPF_RAW.sub( lambda m: _mask(m, 'CPF',  2), text)
    # EFD-Reinf specific XML tags
    text = _RE_CNPJ_CONTRI.sub(lambda m: f"{m.group(1)}[CNPJ/****{m.group(2)[-2:]}]{m.group(3)}", text)
    text = _RE_CNPJ_PREST.sub( lambda m: f"{m.group(1)}[CNPJ/****{m.group(2)[-2:]}]{m.group(3)}", text)
    text = _RE_CNPJ_TOMAD.sub( lambda m: f"{m.group(1)}[CNPJ/****{m.group(2)[-2:]}]{m.group(3)}", text)
    text = _RE_CPF_PROD.sub(   lambda m: f"{m.group(1)}[CPF/****{m.group(2)[-2:]}]{m.group(3)}", text)
    return text


def _scrub_parsed(p: "ParsedXML") -> "ParsedXML":
    p.nr_inscricao = scrub_pii(p.nr_inscricao)
    for oc in p.ocorrencias:
        oc.descricao   = scrub_pii(oc.descricao)
        oc.localizacao = scrub_pii(oc.localizacao)
    return p


@dataclass
class Ocorrencia:
    tipo: str        # ERROR, AVISO, INFO
    codigo: str
    descricao: str
    localizacao: str = ""


@dataclass
class ParsedXML:
    raw_xml: str
    formato: str = "desconhecido"         # lote | evento | retorno_processamento | efdreinf_lote | efdreinf_evento | efdreinf_generico
    sistema: str = "esocial"              # esocial | efdreinf
    cd_resposta: str = ""
    desc_resposta: str = ""
    tipo_evento: str = ""                 # S-1200, S-2200, R-1000, R-2010, etc.
    nr_recibo: str = ""
    nr_inscricao: str = ""               # CNPJ/CPF do empregador/contribuinte
    competencia: str = ""
    ocorrencias: list = field(default_factory=list)
    evento_ids: list = field(default_factory=list)
    erro: str = ""                        # parsing error if any

    @property
    def is_rejected(self) -> bool:
        return self.cd_resposta not in ("201", "100", "")

    @property
    def error_codes(self) -> list:
        return [o.codigo for o in self.ocorrencias if o.tipo in ("ERROR", "ERRO", "E")]

    @property
    def summary(self) -> str:
        codes = ", ".join(self.error_codes) if self.error_codes else self.cd_resposta
        return (
            f"Evento: {self.tipo_evento or '—'} | "
            f"Resp: {self.cd_resposta} | "
            f"Erros: {codes or '—'} | "
            f"Ocorrências: {len(self.ocorrencias)}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Namespace helpers
# ─────────────────────────────────────────────────────────────────────────────

NS = {
    "e": "http://www.esocial.gov.br/schema/lote/eventos/envio/retorno/v1_1_1",
    "ep": "http://www.esocial.gov.br/schema/lote/eventos/envio/retorno/processamento/v1_1_1",
}

# Strip namespace from tag
def _tag(element) -> str:
    return re.sub(r"\{[^}]+\}", "", element.tag)

def _find(root, *tags):
    """Breadth-first search ignoring namespaces."""
    queue = [root]
    for tag in tags:
        found = []
        for node in queue:
            for child in node:
                if _tag(child) == tag:
                    found.append(child)
        if not found:
            return None
        queue = found
    return queue[0] if queue else None

def _findall(root, tag):
    """Find all elements with tag, ignoring namespaces, recursively."""
    result = []
    for child in root.iter():
        if _tag(child) == tag:
            result.append(child)
    return result

def _text(root, tag) -> str:
    el = next((c for c in root.iter() if _tag(c) == tag), None)
    return (el.text or "").strip() if el is not None else ""


# ─────────────────────────────────────────────────────────────────────────────
# Event type detection
# ─────────────────────────────────────────────────────────────────────────────

ESOCIAL_EVENTS = [
    "S-1000","S-1005","S-1010","S-1020","S-1030","S-1035","S-1040","S-1050",
    "S-1060","S-1070","S-1080","S-1200","S-1202","S-1207","S-1210","S-1250",
    "S-1260","S-1270","S-1280","S-1295","S-1299","S-2100","S-2105","S-2200",
    "S-2205","S-2206","S-2210","S-2220","S-2221","S-2230","S-2231","S-2240",
    "S-2241","S-2245","S-2250","S-2260","S-2298","S-2299","S-2300","S-2306",
    "S-2399","S-2400","S-2405","S-2410","S-2416","S-2418","S-2420","S-2500",
    "S-2501","S-3000","S-5001","S-5002","S-5003","S-5011","S-5012","S-5013",
    "S-5501","S-5502","S-5503","S-5511","S-5512","S-5513",
]

# EFD-Reinf events (KB074-KB093)
EFDREINF_EVENTS = [
    "R-1000","R-1070",
    "R-2010","R-2020","R-2030","R-2040","R-2050","R-2055","R-2060","R-2070",
    "R-2098","R-2099",
    "R-4010","R-4020","R-4040","R-4080","R-4099",
    "R-9000","R-9001","R-9005","R-9011","R-9013","R-9015",
]

# Mapa evento EFD-Reinf → tag XML do elemento raiz do evento
_EFDREINF_EVT_TAGS = {
    "R-1000": "evtInfoContribuinte",
    "R-1070": "evtTabLig",
    "R-2010": "evtServTom",
    "R-2020": "evtServPrest",
    "R-2030": "evtAssocDespRec",
    "R-2040": "evtAssocDespDep",
    "R-2050": "evtComProd",
    "R-2055": "evtAqProd",
    "R-2060": "evtCPRB",
    "R-2070": "evtPgtos",
    "R-2098": "evtReabreEvtsPer",
    "R-2099": "evtFechaEvtsPer",
    "R-4010": "evtRetPF",
    "R-4020": "evtRetPJ",
    "R-4040": "evtRetNI",
    "R-4080": "evtRetPJ",   # cessão mão de obra
    "R-4099": "evtFechamento",
    "R-9000": "evtExclusao",
    "R-9001": "evtAdvertencia",
}


# Mapa nome do evento (extraído do namespace) → código eSocial.
# Nomes extraídos do padrão oficial de namespaces do eSocial:
#   http://www.esocial.gov.br/schema/evt/<evtNome>/v_S_01_03_00
# A versão (v_*) é ignorada — o mapeamento funciona em qualquer versão do leiaute.
_ESOCIAL_NS_EVENTS: dict[str, str] = {
    "evtInfoEmpregador": "S-1000",
    "evtTabEstab": "S-1005",
    "evtTabRubrica": "S-1010",
    "evtTabLotacao": "S-1020",
    "evtTabCargo": "S-1030",
    "evtTabCarreira": "S-1035",
    "evtTabFuncao": "S-1040",
    "evtTabHorTur": "S-1050",
    "evtTabAmbiente": "S-1060",
    "evtTabProcesso": "S-1070",
    "evtTabOperPort": "S-1080",
    "evtRemun": "S-1200",
    "evtRmnRPPS": "S-1202",
    "evtBenPrRP": "S-1207",
    "evtPgtos": "S-1210",
    "evtAqProd": "S-1250",
    "evtComProd": "S-1260",
    "evtContratAvNP": "S-1270",
    "evtInfoComplPer": "S-1280",
    "evtTotConting": "S-1295",
    "evtFechaEvPer": "S-1299",
    "evtCadInicial": "S-2100",
    "evtAltCadastral": "S-2105",
    "evtAdmissao": "S-2200",
    "evtAltContratual": "S-2205",
    "evtCE": "S-2206",
    "evtCAT": "S-2210",
    "evtMonit": "S-2220",
    "evtToxic": "S-2221",
    "evtAfastTemp": "S-2230",
    "evtCessao": "S-2231",
    "evtExpRisco": "S-2240",
    "evtInsApo": "S-2241",
    "evtTreiCap": "S-2245",
    "evtAvPrevio": "S-2250",
    "evtConvInterm": "S-2260",
    "evtReintegr": "S-2298",
    "evtDeslig": "S-2299",
    "evtTSVInicio": "S-2300",
    "evtTSVAltContr": "S-2306",
    "evtTSVTermino": "S-2399",
    "evtCdBenefIn": "S-2400",
    "evtCdBenefAlt": "S-2405",
    "evtCdBenIn": "S-2410",
    "evtCdBenAlt": "S-2416",
    "evtReativBen": "S-2418",
    "evtCdBenTerm": "S-2420",
    # Rótulos de família para eventos que compartilham o mesmo nome de namespace
    # (não há desambiguação simples no XML de envio — o namespace é idêntico)
    "evtExclusao": "S-2500/S-2501/S-3000",
    "evtBasesTrab": "S-5001",
    "evtIrrf": "S-5002",
    "evtBasesFGTS": "S-5003",
    "evtCS": "S-5011",
    "evtIrrfBenef": "S-5012",
    "evtFGTS": "S-5013",
    "evtTribProcTrab": "S-5501/S-5502/S-5503",
    "evtAgNoc": "S-5511/S-5512/S-5513",
}


def _detect_event_type(xml_str: str, root: ET.Element) -> str:
    # 0. eSocial: extrai evento do namespace do schema (mais confiável que busca textual)
    #    Namespace: http://www.esocial.gov.br/schema/evt/<evtNome>/v_S_01_03_00
    ns = ""
    if root.tag.startswith("{"):
        ns = root.tag[1:].split("}")[0]
    else:
        # Fallback: procura xmlns no XML bruto
        m = re.search(r'xmlns="([^"]+)"', xml_str)
        if m:
            ns = m.group(1)
    if ns:
        # Extrai o segmento após "/evt/" e antes da versão (v_*)
        parts = ns.split("/")
        for i, part in enumerate(parts):
            if part == "evt" and i + 1 < len(parts):
                evt_name = parts[i + 1]
                # Remove sufixo de versão se colado (ex: evtAdmissao/v02_05_00)
                evt_name = evt_name.split("/")[0]
                if evt_name in _ESOCIAL_NS_EVENTS:
                    return _ESOCIAL_NS_EVENTS[evt_name]
                break

    # 1. EFD-Reinf: procura tags de evento específicas (evtServTom, evtCPRB, etc.)
    for evt, tag in _EFDREINF_EVT_TAGS.items():
        if tag in xml_str:
            return evt

    # 2. eSocial: procura eventos S-XXXX no XML
    for evt in ESOCIAL_EVENTS:
        tag_search = evt.replace("-", "")  # S1200, S2200 etc
        if evt in xml_str or tag_search in xml_str:
            return evt

    # 3. tpEvento element
    tp = _text(root, "tpEvento")
    if tp:
        return tp

    # 4. Id attribute pattern evtS1200... ou R-1000 no id
    all_ids = re.findall(r'[Ii]d="([^"]+)"', xml_str)
    for id_val in all_ids:
        for evt in EFDREINF_EVENTS:
            if evt.replace("-", "").lower() in id_val.lower():
                return evt
        for evt in ESOCIAL_EVENTS:
            if evt.replace("-", "").lower() in id_val.lower():
                return evt

    return ""


# ─────────────────────────────────────────────────────────────────────────────
# Ocorrencia extraction
# ─────────────────────────────────────────────────────────────────────────────

_TIPO_EFDREINF = {"1": "ERROR", "2": "AVISO", "3": "INFO"}


def _extract_ocorrencias(root: ET.Element) -> list:
    result = []
    for oc in _findall(root, "ocorrencia"):
        tipo     = _text(oc, "tipo") or _text(oc, "tpOcorr") or "ERROR"
        # EFD-Reinf usa "1"/"2"/"3" em vez de "ERROR"/"AVISO"/"INFO"
        tipo     = _TIPO_EFDREINF.get(tipo, tipo)
        codigo   = _text(oc, "codigo") or _text(oc, "cdOcorr") or ""
        descricao = _text(oc, "descricao") or _text(oc, "dscOcorr") or ""
        loc      = (_text(oc, "localizacaoErro") or _text(oc, "localizacao")
                    or _text(oc, "locOcorr") or "")
        if codigo or descricao:
            result.append(Ocorrencia(tipo=tipo, codigo=codigo,
                                     descricao=descricao, localizacao=loc))
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Main parser
# ─────────────────────────────────────────────────────────────────────────────

def parse_esocial_xml(xml_content: str) -> ParsedXML:
    result = ParsedXML(raw_xml=xml_content)

    # Clean BOM and encoding declaration issues
    xml_clean = xml_content.strip()
    if xml_clean.startswith("\ufeff"):
        xml_clean = xml_clean[1:]

    try:
        root = ET.fromstring(xml_clean)
    except ET.ParseError as e:
        result.erro = f"XML inválido: {e}"
        return result

    result.tipo_evento = _detect_event_type(xml_clean, root)

    # ── Formato 1: retornoEnvioLoteEventos ───────────────────────────────
    lote_ret = next((c for c in root.iter() if _tag(c) == "retornoEnvioLoteEventos"), None)
    if lote_ret is not None:
        result.formato = "lote"
        result.nr_inscricao = _text(lote_ret, "nrInsc")
        status = next((c for c in lote_ret.iter() if _tag(c) == "status"), None)
        if status is not None:
            result.cd_resposta  = _text(status, "cdResposta")
            result.desc_resposta = _text(status, "descResposta")
        result.ocorrencias = _extract_ocorrencias(lote_ret)

        # Individual event returns inside the lot
        for ret_evt in _findall(lote_ret, "retornoEvento"):
            evt_id = ret_evt.get("id", "")
            if evt_id:
                result.evento_ids.append(evt_id)
            cd = _text(ret_evt, "cdResposta")
            if cd and cd != result.cd_resposta:
                result.cd_resposta = cd
                result.desc_resposta = _text(ret_evt, "descResposta")
            result.ocorrencias += _extract_ocorrencias(ret_evt)
            if not result.nr_recibo:
                result.nr_recibo = _text(ret_evt, "nrRec")
        return _scrub_parsed(result)

    # ── Formato 2: retornoProcessamentoEvento ────────────────────────────
    proc_ret = next((c for c in root.iter()
                     if _tag(c) == "retornoProcessamentoEvento"), None)
    if proc_ret:
        result.formato = "processamento"
        result.cd_resposta   = _text(proc_ret, "cdResposta")
        result.desc_resposta = _text(proc_ret, "descResposta")
        result.nr_recibo     = _text(proc_ret, "nrRec")
        result.ocorrencias   = _extract_ocorrencias(proc_ret)
        result.nr_inscricao  = _text(root, "nrInsc")
        return _scrub_parsed(result)

    # ── Formato 3: retornoEvento simples ─────────────────────────────────
    ret_evt = next((c for c in root.iter() if _tag(c) == "retornoEvento"), None)
    if ret_evt:
        result.formato = "evento"
        result.cd_resposta   = _text(ret_evt, "cdResposta")
        result.desc_resposta = _text(ret_evt, "descResposta")
        result.nr_recibo     = _text(ret_evt, "nrRec")
        result.ocorrencias   = _extract_ocorrencias(ret_evt)
        result.nr_inscricao  = _text(root, "nrInsc")
        return _scrub_parsed(result)

    # ── Formato 4: Qualquer XML com ocorrencias ───────────────────────────
    result.formato = "generico"
    result.cd_resposta   = _text(root, "cdResposta")
    result.desc_resposta = _text(root, "descResposta")
    result.nr_recibo     = _text(root, "nrRec")
    result.nr_inscricao  = _text(root, "nrInsc")
    result.competencia   = _text(root, "indApuracao") or _text(root, "perApur")
    result.ocorrencias   = _extract_ocorrencias(root)
    return _scrub_parsed(result)


# ─────────────────────────────────────────────────────────────────────────────
# EFD-Reinf parser
# ─────────────────────────────────────────────────────────────────────────────

def _is_efdreinf_xml(xml_str: str, root: ET.Element) -> bool:
    """Retorna True se o XML é EFD-Reinf (namespace ou tag raiz Reinf)."""
    root_tag = _tag(root).lower()
    if root_tag == "reinf":
        return True
    if "reinf.esocial.gov.br" in xml_str:
        return True
    # evento R-* detectado
    for tag in _EFDREINF_EVT_TAGS.values():
        if tag in xml_str:
            return True
    return False


def parse_efdreinf_xml(xml_content: str) -> ParsedXML:
    """Parser dedicado para XMLs EFD-Reinf (retornoLoteEventos, retornoEvt*)."""
    result = ParsedXML(raw_xml=xml_content, sistema="efdreinf")

    xml_clean = xml_content.strip()
    if xml_clean.startswith("\ufeff"):
        xml_clean = xml_clean[1:]

    try:
        root = ET.fromstring(xml_clean)
    except ET.ParseError as e:
        result.erro = f"XML inválido: {e}"
        return result

    result.tipo_evento = _detect_event_type(xml_clean, root)

    # ── Formato 1: retornoLoteEventos (EFD-Reinf) ────────────────────────────
    lote = next((c for c in root.iter() if _tag(c) == "retornoLoteEventos"), None)
    if lote is not None and len(lote) > 0:
        result.formato = "efdreinf_lote"
        result.nr_inscricao = (_text(lote, "nrInsc") or _text(root, "nrInsc"))
        # EFD-Reinf usa cdRetorno/descRetorno OU cdResposta/descResposta
        status = next((c for c in lote.iter() if _tag(c) == "status"), None)
        if status is not None:
            result.cd_resposta  = (_text(status, "cdRetorno")
                                   or _text(status, "cdResposta") or "")
            result.desc_resposta = (_text(status, "descRetorno")
                                    or _text(status, "descResposta") or "")
            result.nr_recibo = _text(status, "nrRec")
        result.ocorrencias = _extract_ocorrencias(lote)

        # Eventos individuais dentro do lote
        for evt_node in _findall(lote, "evento"):
            evt_id = evt_node.get("id", "")
            if evt_id:
                result.evento_ids.append(evt_id)
            # retornoEvento aninhado
            ret = next((c for c in evt_node.iter()
                        if _tag(c).startswith("retornoEvt")), None)
            if ret is not None:
                ide = next((c for c in ret.iter() if _tag(c) == "ideStatus"), None)
                if ide is not None:
                    cd = (_text(ide, "cdRetorno") or _text(ide, "cdResposta"))
                    if cd and not result.cd_resposta:
                        result.cd_resposta = cd
                        result.desc_resposta = (_text(ide, "descRetorno")
                                                or _text(ide, "descResposta"))
                    result.ocorrencias += _extract_ocorrencias(ide)
                if not result.nr_recibo:
                    result.nr_recibo = _text(ret, "nrRec")
        return _scrub_parsed(result)

    # ── Formato 2: retornoEvt* direto (R-1000, R-2010, etc.) ─────────────────
    ret_evt = next((c for c in root.iter()
                    if _tag(c).startswith("retornoEvt")), None)
    if ret_evt:
        result.formato = "efdreinf_evento"
        ide = next((c for c in ret_evt.iter() if _tag(c) == "ideStatus"), None)
        if ide:
            result.cd_resposta  = (_text(ide, "cdRetorno")
                                   or _text(ide, "cdResposta") or "")
            result.desc_resposta = (_text(ide, "descRetorno")
                                    or _text(ide, "descResposta") or "")
            result.ocorrencias = _extract_ocorrencias(ide)
        result.nr_recibo    = _text(ret_evt, "nrRec")
        result.nr_inscricao = _text(root, "nrInsc")
        result.competencia  = _text(root, "perApur")
        return _scrub_parsed(result)

    # ── Formato 3: genérico com campos EFD-Reinf ─────────────────────────────
    result.formato = "efdreinf_generico"
    result.cd_resposta   = (_text(root, "cdRetorno")
                            or _text(root, "cdResposta") or "")
    result.desc_resposta = (_text(root, "descRetorno")
                            or _text(root, "descResposta") or "")
    result.nr_recibo     = _text(root, "nrRec")
    result.nr_inscricao  = _text(root, "nrInsc")
    result.competencia   = _text(root, "perApur")
    result.ocorrencias   = _extract_ocorrencias(root)
    return _scrub_parsed(result)


# ─────────────────────────────────────────────────────────────────────────────
# Entrada unificada — detecta automaticamente eSocial vs EFD-Reinf
# ─────────────────────────────────────────────────────────────────────────────

def parse_xml_auto(xml_content: str) -> ParsedXML:
    """
    Parser unificado: detecta automaticamente se o XML é eSocial ou EFD-Reinf
    e delega para o parser correto.
    """
    xml_clean = xml_content.strip().lstrip("\ufeff")
    try:
        root = ET.fromstring(xml_clean)
    except ET.ParseError:
        # Tenta eSocial como fallback (vai capturar o erro lá também)
        return parse_esocial_xml(xml_content)

    if _is_efdreinf_xml(xml_clean, root):
        return parse_efdreinf_xml(xml_content)
    return parse_esocial_xml(xml_content)


# ─────────────────────────────────────────────────────────────────────────────
# Sample XML generators for testing / examples
# ─────────────────────────────────────────────────────────────────────────────

SAMPLE_XMLS = {
    "S-1200 / E428 — indRetif ausente": """<?xml version="1.0" encoding="UTF-8"?>
<eSocial xmlns="http://www.esocial.gov.br/schema/lote/eventos/envio/retorno/v1_1_1">
  <retornoEnvioLoteEventos>
    <ideEmpregador>
      <tpInsc>1</tpInsc>
      <nrInsc>12345678000195</nrInsc>
    </ideEmpregador>
    <ideTransmissor>
      <tpInsc>1</tpInsc>
      <nrInsc>98765432000110</nrInsc>
    </ideTransmissor>
    <status>
      <cdResposta>401</cdResposta>
      <descResposta>Lote recebido com erros de validação</descResposta>
    </status>
    <retornoLoteEventos>
      <retornoEventos>
        <retornoEvento id="ID_S1200_001">
          <evento id="ID_S1200_001">
            <eSocial>
              <evtRemun>
                <ideEvento>
                  <indRetif>1</indRetif>
                  <perApur>2024-01</perApur>
                  <tpAmb>1</tpAmb>
                </ideEvento>
              </evtRemun>
            </eSocial>
          </evento>
          <retornoEvento>
            <cdResposta>401</cdResposta>
            <descResposta>Evento rejeitado</descResposta>
            <nrRec></nrRec>
            <ocorrencias>
              <ocorrencia>
                <tipo>ERROR</tipo>
                <codigo>E428</codigo>
                <descricao>Campo [indRetif] deve ser igual a 2 quando informado [nrRecEvt] de evento anterior.</descricao>
                <localizacaoErro>evtRemun/ideEvento/indRetif</localizacaoErro>
              </ocorrencia>
            </ocorrencias>
          </retornoEvento>
        </retornoEvento>
      </retornoEventos>
    </retornoLoteEventos>
  </retornoEnvioLoteEventos>
</eSocial>""",

    "S-2200 / E469 — CNPJ inválido": """<?xml version="1.0" encoding="UTF-8"?>
<eSocial xmlns="http://www.esocial.gov.br/schema/lote/eventos/envio/retorno/v1_1_1">
  <retornoEnvioLoteEventos>
    <ideEmpregador>
      <nrInsc>12345678000195</nrInsc>
    </ideEmpregador>
    <status>
      <cdResposta>401</cdResposta>
      <descResposta>Lote rejeitado</descResposta>
    </status>
    <retornoLoteEventos>
      <retornoEventos>
        <retornoEvento id="ID_S2200_001">
          <retornoEvento>
            <cdResposta>401</cdResposta>
            <descResposta>Evento rejeitado</descResposta>
            <ocorrencias>
              <ocorrencia>
                <tipo>ERROR</tipo>
                <codigo>E469</codigo>
                <descricao>O CNPJ do estabelecimento informado não consta na base de dados da RFB ou está com situação cadastral diferente de ativa.</descricao>
                <localizacaoErro>evtAdmissao/ideEmpregador/nrInsc</localizacaoErro>
              </ocorrencia>
            </ocorrencias>
          </retornoEvento>
        </retornoEvento>
      </retornoEventos>
    </retornoLoteEventos>
  </retornoEnvioLoteEventos>
</eSocial>""",

    "S-1000 / E214 — Certificado digital expirado": """<?xml version="1.0" encoding="UTF-8"?>
<eSocial>
  <retornoEnvioLoteEventos>
    <ideEmpregador>
      <nrInsc>11222333000181</nrInsc>
    </ideEmpregador>
    <status>
      <cdResposta>402</cdResposta>
      <descResposta>Assinatura digital inválida ou certificado expirado</descResposta>
    </status>
    <retornoLoteEventos>
      <retornoEventos>
        <retornoEvento id="ID_S1000_CERT">
          <retornoEvento>
            <cdResposta>402</cdResposta>
            <descResposta>Rejeição por certificado</descResposta>
            <ocorrencias>
              <ocorrencia>
                <tipo>ERROR</tipo>
                <codigo>E214</codigo>
                <descricao>Certificado digital utilizado para assinatura do XML está expirado ou revogado pela ICP-Brasil.</descricao>
                <localizacaoErro>Signature/KeyInfo/X509Data</localizacaoErro>
              </ocorrencia>
            </ocorrencias>
          </retornoEvento>
        </retornoEvento>
      </retornoEventos>
    </retornoLoteEventos>
  </retornoEnvioLoteEventos>
</eSocial>""",

    "S-2299 / E312 — Vínculo não encontrado": """<?xml version="1.0" encoding="UTF-8"?>
<eSocial>
  <retornoProcessamentoEvento>
    <cdResposta>401</cdResposta>
    <descResposta>Evento rejeitado por inconsistência de dados</descResposta>
    <nrRec></nrRec>
    <ocorrencias>
      <ocorrencia>
        <tipo>ERROR</tipo>
        <codigo>E312</codigo>
        <descricao>Não existe vínculo empregatício ativo no eSocial para o CPF e CNPJ informados. Verifique se o evento S-2200 foi enviado e processado.</descricao>
        <localizacaoErro>evtDeslig/ideVinculo/cpfTrab</localizacaoErro>
      </ocorrencia>
    </ocorrencias>
  </retornoProcessamentoEvento>
</eSocial>""",

    "S-2230 / E500 — Timeout lote grande": """<?xml version="1.0" encoding="UTF-8"?>
<eSocial>
  <retornoEnvioLoteEventos>
    <ideEmpregador>
      <nrInsc>55666777000144</nrInsc>
    </ideEmpregador>
    <status>
      <cdResposta>500</cdResposta>
      <descResposta>Erro interno no processamento do lote. Número de eventos excede o limite permitido por transmissão.</descResposta>
    </status>
    <retornoLoteEventos>
      <retornoEventos>
        <retornoEvento id="ID_LOTE_GRANDE">
          <retornoEvento>
            <cdResposta>500</cdResposta>
            <descResposta>Timeout</descResposta>
            <ocorrencias>
              <ocorrencia>
                <tipo>ERROR</tipo>
                <codigo>E500</codigo>
                <descricao>Timeout na transmissão. O lote contém mais de 50 eventos. Reduza o volume e retransmita em lotes menores.</descricao>
                <localizacaoErro>retornoEnvioLoteEventos</localizacaoErro>
              </ocorrencia>
            </ocorrencias>
          </retornoEvento>
        </retornoEvento>
      </retornoEventos>
    </retornoLoteEventos>
  </retornoEnvioLoteEventos>
</eSocial>""",

    # ── EFD-Reinf samples ──────────────────────────────────────────────────────

    "R-1000 / ERF001 — CNPJ contribuinte não cadastrado": """<?xml version="1.0" encoding="UTF-8"?>
<Reinf xmlns="http://www.reinf.esocial.gov.br/schema/loteEventosAssincrono/v2_01_01">
  <retornoLoteEventos>
    <ideEmpregador>
      <tpInsc>1</tpInsc>
      <nrInsc>12345678000195</nrInsc>
    </ideEmpregador>
    <status>
      <cdRetorno>1</cdRetorno>
      <descRetorno>Lote recebido com erros</descRetorno>
    </status>
    <retornoEventos>
      <evento id="Evt001">
        <retornoEvento>
          <Reinf>
            <retornoEvtInfoContribuinte>
              <ideStatus>
                <cdRetorno>1</cdRetorno>
                <descRetorno>Evento rejeitado</descRetorno>
                <ocorrencias>
                  <ocorrencia>
                    <tipo>1</tipo>
                    <codigo>ERF001</codigo>
                    <descricao>CNPJ do contribuinte não cadastrado ou divergente na RFB. Verifique a situação cadastral antes de transmitir o R-1000.</descricao>
                    <localizacao>evtInfoContribuinte/ideContri/nrInsc</localizacao>
                  </ocorrencia>
                </ocorrencias>
              </ideStatus>
            </retornoEvtInfoContribuinte>
          </Reinf>
        </retornoEvento>
      </evento>
    </retornoEventos>
  </retornoLoteEventos>
</Reinf>""",

    "R-2010 / ERF010 — Retenção CSLL/COFINS/PIS divergente": """<?xml version="1.0" encoding="UTF-8"?>
<Reinf xmlns="http://www.reinf.esocial.gov.br/schema/loteEventosAssincrono/v2_01_01">
  <retornoLoteEventos>
    <ideEmpregador>
      <tpInsc>1</tpInsc>
      <nrInsc>12345678000195</nrInsc>
    </ideEmpregador>
    <status>
      <cdRetorno>1</cdRetorno>
      <descRetorno>Lote com erros de validação</descRetorno>
    </status>
    <retornoEventos>
      <evento id="Evt001">
        <retornoEvento>
          <Reinf>
            <retornoEvtServTom>
              <ideStatus>
                <cdRetorno>1</cdRetorno>
                <descRetorno>Evento R-2010 rejeitado</descRetorno>
                <ocorrencias>
                  <ocorrencia>
                    <tipo>1</tipo>
                    <codigo>ERF010</codigo>
                    <descricao>Valor de retenção de CSLL/COFINS/PIS diverge do percentual legal (4,65%) sobre o valor bruto da nota fiscal informada.</descricao>
                    <localizacao>evtServTom/ideServTom/vlrCsll</localizacao>
                  </ocorrencia>
                </ocorrencias>
              </ideStatus>
            </retornoEvtServTom>
          </Reinf>
        </retornoEvento>
      </evento>
    </retornoEventos>
  </retornoLoteEventos>
</Reinf>""",

    "R-2060 / ERF021 — CNAE inválido para CPRB/Desoneração": """<?xml version="1.0" encoding="UTF-8"?>
<Reinf xmlns="http://www.reinf.esocial.gov.br/schema/loteEventosAssincrono/v2_01_01">
  <retornoLoteEventos>
    <ideEmpregador>
      <tpInsc>1</tpInsc>
      <nrInsc>98765432000110</nrInsc>
    </ideEmpregador>
    <status>
      <cdRetorno>1</cdRetorno>
      <descRetorno>Lote rejeitado</descRetorno>
    </status>
    <retornoEventos>
      <evento id="Evt001">
        <retornoEvento>
          <Reinf>
            <retornoEvtCPRB>
              <ideStatus>
                <cdRetorno>1</cdRetorno>
                <descRetorno>Evento R-2060 rejeitado</descRetorno>
                <ocorrencias>
                  <ocorrencia>
                    <tipo>1</tipo>
                    <codigo>ERF021</codigo>
                    <descricao>CNAE informado não consta na lista de atividades beneficiadas pela desoneração da folha (Lei 12.546/2011 e alterações). Verifique se a empresa é optante pela CPRB no período informado.</descricao>
                    <localizacao>evtCPRB/ideEstab/cnae</localizacao>
                  </ocorrencia>
                </ocorrencias>
              </ideStatus>
            </retornoEvtCPRB>
          </Reinf>
        </retornoEvento>
      </evento>
    </retornoEventos>
  </retornoLoteEventos>
</Reinf>""",
}



# ─────────────────────────────────────────────────────────────────────────────
# Compatibilidade: alias para código legado que usa 'parse_xml'
# parse_xml_auto é a entrada recomendada para novo código
# ─────────────────────────────────────────────────────────────────────────────
parse_xml = parse_xml_auto