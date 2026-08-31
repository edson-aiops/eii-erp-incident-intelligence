"""Scrubber de PII obrigatório e não-configurável do EII — revisão v2 (A23).

O scrubbing é executado antes de qualquer chamada a LLM remoto. O mapa de
tokens (`token_map`) fica apenas em memória e no escopo do request, garantindo
que o operador remoto não possa reidentificar o titular.

Esta solução é pseudonimização com mapa local, não anonimização plena.
"""

from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class ScrubResult:
    """Resultado de uma operação de scrubbing."""

    scrubbed_payload: str          # o que PODE sair pela rede
    token_map: dict[str, str]      # token -> valor real. NUNCA serializar.
    fields_scrubbed: list[str]     # caminhos de campo tratados (para auditoria)
    is_safe_for_remote: bool       # False => proibido chamar LLM remoto


class PIIScrubber:
    """Remove/replace dados pessoais de XMLs eSocial antes do envio a LLMs.

    O scrubber é puro em relação a disco e rede: não escreve, não loga e não
    persiste. O `token_map` é criado a cada chamada de `scrub()` e vive apenas
    em memória.
    """

    LAYOUT_VERSION: ClassVar[str] = "S-1.3"

    # Eventos eSocial suportados. Novos eventos devem ser mapeados
    # explicitamente; tipos fora desta lista ativam fail-closed.
    SUPPORTED_EVENTS: ClassVar[frozenset[str]] = frozenset({
        "S-1200", "S-1202", "S-1207", "S-1210", "S-1250", "S-1260",
        "S-1270", "S-1280", "S-1298", "S-1299", "S-1300", "S-2190",
        "S-2200", "S-2205", "S-2206", "S-2210", "S-2220", "S-2221",
        "S-2230", "S-2231", "S-2240", "S-2241", "S-2245", "S-2250",
        "S-2260", "S-2298", "S-2299", "S-2300", "S-2306", "S-2399",
        "S-2400", "S-2405", "S-2410", "S-2418", "S-2420", "S-3000",
    })

    # Blocos de titular: dentro deles, todo nó folha é tratado por padrão,
    # exceto os explicitamente na allowlist (TITULAR_ALLOWLIST).
    TITULAR_BLOCKS: ClassVar[frozenset[str]] = frozenset({
        "trabalhador", "dependente", "endereco", "documentos", "contato",
        "infoDeficiencia", "aposentadoria", "trabEstrangeiro",
        "filiacaoSindical",
    })

    # Allowlist dentro de blocos de titular (campos preservados).
    TITULAR_ALLOWLIST: ClassVar[frozenset[str]] = frozenset({
        "codMunic", "uf", "tpLograd", "undSalFixo", "orgaoEmissor",
        "ufCtps", "ufCnh", "categoriaCnh", "dtExped", "dtValid", "dtPriHab",
    })

    # Tags fora de blocos de titular que são preservadas por definição.
    PRESERVE_TAGS: ClassVar[frozenset[str]] = frozenset({
        "tpInsc", "tpAmb", "indRetif", "codCateg", "CBOCargo", "CBOFunc",
        "tpRegTrab", "tpRegPrev", "tpAdmissao", "indAdmissao",
        "cnpjSindCategProf", "cnpjEmpregador", "cnpjTransf", "cnpjSucessora",
        "dtAdm", "dtDeslig", "dtOpcFGTS", "cdResposta", "codigo",
        "nrRecibo", "nrRec", "nrRecArqBase", "nrRecInfPrelim",
        "nrProtocolo", "hash",
    })

    # Mapeamento tag -> prefixo de token (classe TOKENIZAR).
    # Manter compatibilidade com nomes usados na v1 (logradouro/nrLogradouro)
    # e na v2 (dscLograd/nrLograd).
    TAG_PREFIXES: ClassVar[dict[str, str]] = {
        # identificadores diretos
        "cpfTrab": "CPF", "cpfBenef": "CPF", "cpfResp": "CPF", "cpfDep": "CPF",
        "nmTrab": "NOME", "nmSoc": "NOME", "nmDep": "NOME",
        "nmMae": "NOME", "nmPai": "NOME",
        "nisTrab": "NIS",
        "dtNascto": "DATA_NASC",
        "matricula": "MATR",
        "nrCtps": "DOC",
        "nrRic": "DOC", "nrRg": "DOC", "nrRne": "DOC", "nrOc": "DOC",
        "nrRegCnh": "DOC", "nrCnh": "DOC",  # nrCnh = v1
        "nrProcJud": "PROC", "nrProcTrab": "PROC",
        "cnpjSindTrab": "CNPJ_SIND",
        "fonePrinc": "FONE", "foneAlternat": "FONE",
        "emailPrinc": "EMAIL", "emailAlternat": "EMAIL",
        # endereço
        "dscLograd": "ENDERECO", "logradouro": "ENDERECO",
        "nrLograd": "ENDERECO", "nrLogradouro": "ENDERECO",
        "complemento": "ENDERECO", "bairro": "ENDERECO",
        # texto livre
        "observacao": "TEXTO_LIVRE",
        "dscSalVar": "TEXTO_LIVRE",
    }

    # Mapeamento tag -> domínio válido (classe CLASSIFICAR).
    CLASSIFY_DOMAINS: ClassVar[dict[str, frozenset[str]]] = {
        "racaCor": frozenset({"1", "2", "3", "4", "5", "6"}),
        "sexo": frozenset({"M", "F"}),
        "estCiv": frozenset({"1", "2", "3", "4", "5"}),
        "grauInstr": frozenset({f"{i:02d}" for i in range(1, 13)}),
        "defFisica": frozenset({"S", "N"}),
        "defVisual": frozenset({"S", "N"}),
        "defAuditiva": frozenset({"S", "N"}),
        "defMental": frozenset({"S", "N"}),
        "defIntelectual": frozenset({"S", "N"}),
        "reabReadap": frozenset({"S", "N"}),
        "infoCota": frozenset({"S", "N"}),
        "incTrab": frozenset({"S", "N"}),
        "trabAposent": frozenset({"S", "N"}),
        "tpDep": frozenset({f"{i:02d}" for i in range(1, 100)}),
        "classTrabEstrang": frozenset({str(i) for i in range(1, 11)}),
        "casadoBr": frozenset({"S", "N"}),
        "filhosBr": frozenset({"S", "N"}),
        "depIRRF": frozenset({"S", "N"}),
        "depSF": frozenset({"S", "N"}),
        "paisNascto": frozenset(),   # tratado por exceção de país
        "paisNac": frozenset(),
        "paisResid": frozenset(),
        "paisResidExt": frozenset(),
    }

    # Tags que recebem GENERALIZAR (valores contínuos).
    GENERALIZE_TAGS: ClassVar[frozenset[str]] = frozenset({
        "vrRubr", "vrBcCp", "vrSalFx", "vrDedDep", "vrCpSeg", "cep",
    })

    # Rede de segurança: regexes refinadas de CPF/PIS.
    _CPF_PATTERN = re.compile(r"(?<!\d)\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?!\d)")
    _PIS_PATTERN = re.compile(r"(?<!\d)\d{3}\.?\d{5}\.?\d{2}-?\d(?!\d)")

    # Camada 3 — isenção de run de dígitos.
    RUN_EXEMPTIONS: ClassVar[frozenset[str]] = frozenset({
        "Id", "nrInsc", "cnpjSindCategProf", "cnpjEmpregador", "cnpjTransf",
        "cnpjSucessora", "nrRecibo", "nrRec", "nrRecArqBase",
        "nrRecInfPrelim", "nrProtocolo", "hash",
    })

    # Nós de texto livre de retorno (camada 1 da rede de segurança).
    FREE_TEXT_RETURN_TAGS: ClassVar[frozenset[str]] = frozenset({
        "descResposta", "descricao", "motivo",
    })

    def scrub(self, xml_content: str, event_type: str) -> ScrubResult:
        """Pseudonimiza PII presente em `xml_content`."""
        token_map: dict[str, str] = {}
        fields_scrubbed: list[str] = []

        # Fail-closed: evento não mapeado
        if event_type not in self.SUPPORTED_EVENTS:
            return self._fail_closed(xml_content)

        # Fail-closed: XML malformado
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError:
            return self._fail_closed(xml_content)

        # Mapa de parent para navegação.
        parent_map: dict[ET.Element, ET.Element] = {
            child: parent for parent in root.iter() for child in parent
        }

        counters: dict[str, int] = {}
        # (prefixo, valor) -> token — garante mesma token para mesmo valor.
        value_tokens: dict[tuple[str, str], str] = {}
        # id(bloco endereco) -> token
        endereco_tokens: dict[int, str] = {}
        # CPF do empregador -> token CPF_EMPR_NN
        employer_cpf_tokens: dict[str, str] = {}
        # id(pai do CTPS) -> série
        ctps_series: dict[int, str] = {}

        # Passada 0: coletar série da CTPS.
        for elem in root.iter():
            tag = self._strip_namespace(elem.tag)
            if tag == "serieCtps":
                parent = parent_map.get(elem)
                if parent is not None:
                    ctps_series[id(parent)] = elem.text or ""

        # Processar Id do evento.
        for elem in root.iter():
            if "Id" in elem.attrib:
                new_id, ok = self._scrub_id(
                    elem.attrib["Id"], employer_cpf_tokens, counters, token_map
                )
                if not ok:
                    return self._fail_closed(xml_content)
                if new_id != elem.attrib["Id"]:
                    elem.attrib["Id"] = new_id
                    fields_scrubbed.append(f"{self._strip_namespace(elem.tag)}@Id")
                break

        # Passada principal: substituição por campo.
        for elem in root.iter():
            tag = self._strip_namespace(elem.tag)
            path = self._element_path(elem, parent_map)

            # serieCtps é tratada junto com nrCtps.
            if tag == "serieCtps":
                continue

            # nrInsc do empregador: regra condicional a tpInsc.
            if tag == "nrInsc" and self._is_ide_empregador_nr_insc(elem, parent_map):
                tp_insc = self._find_tp_insc(elem, parent_map)
                new_value, ok = self._scrub_employer_nr_insc(
                    elem.text or "", tp_insc, employer_cpf_tokens, counters, token_map
                )
                if not ok:
                    return self._fail_closed(xml_content)
                if new_value != (elem.text or ""):
                    elem.text = new_value
                    fields_scrubbed.append(path)
                continue

            in_titular = self._is_inside_titular_block(elem, parent_map)
            treatment = self._get_treatment(tag, in_titular)

            if treatment == "PRESERVE":
                continue

            if treatment == "TOKENIZE":
                self._tokenize_field(
                    elem, tag, path, parent_map, ctps_series,
                    endereco_tokens, value_tokens, counters, token_map,
                    fields_scrubbed,
                )
                continue

            if treatment == "CLASSIFY":
                token = self._classify_token(tag, elem.text or "", counters, token_map)
                if token is not None:
                    elem.text = token
                    fields_scrubbed.append(path)
                continue

            if treatment == "GENERALIZE":
                if tag == "cep":
                    token = self._cep_token(elem.text or "", counters, token_map)
                else:
                    token = self._value_token(elem.text or "")
                if token is not None:
                    elem.text = token
                    fields_scrubbed.append(path)
                continue

            # Default da allowlist dentro de bloco de titular.
            if in_titular and tag not in self.TITULAR_ALLOWLIST:
                token = self._get_token_for_value(
                    "CAMPO_TITULAR", elem.text or "", value_tokens, counters, token_map
                )
                if token is not None:
                    elem.text = token
                    fields_scrubbed.append(path)
                continue

        # Camada 1 da rede de segurança: eco de valores em texto livre de retorno.
        self._scrub_free_text(root, token_map)

        # Montar payload.
        scrubbed_payload = ET.tostring(root, encoding="unicode")

        # Camadas 2 e 3 da rede de segurança.
        is_safe_for_remote = self._security_check(root, parent_map)

        return ScrubResult(
            scrubbed_payload=scrubbed_payload,
            token_map=token_map,
            fields_scrubbed=fields_scrubbed,
            is_safe_for_remote=is_safe_for_remote,
        )

    def restore(self, text: str, token_map: dict[str, str]) -> str:
        """Reverte tokens para os valores reais em `text`."""
        if not token_map:
            return text
        for token in sorted(token_map, key=len, reverse=True):
            text = re.sub(re.escape(token), token_map[token], text)
        return text

    # ------------------------------------------------------------------
    # Helpers de classificação / tokenização
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_namespace(tag: str) -> str:
        if "}" in tag:
            return tag.split("}", 1)[1]
        return tag

    def _element_path(self, elem: ET.Element, parent_map: dict[ET.Element, ET.Element]) -> str:
        """Monta caminho legível do elemento."""
        parts = []
        current: ET.Element | None = elem
        while current is not None:
            parts.append(self._strip_namespace(current.tag))
            current = parent_map.get(current)
        return "/".join(reversed(parts))

    def _is_inside_titular_block(
        self, elem: ET.Element, parent_map: dict[ET.Element, ET.Element]
    ) -> bool:
        current: ET.Element | None = elem
        while current is not None:
            if self._strip_namespace(current.tag) in self.TITULAR_BLOCKS:
                return True
            current = parent_map.get(current)
        return False

    def _is_ide_empregador_nr_insc(
        self, elem: ET.Element, parent_map: dict[ET.Element, ET.Element]
    ) -> bool:
        parent = parent_map.get(elem)
        return parent is not None and self._strip_namespace(parent.tag) == "ideEmpregador"

    def _find_tp_insc(
        self, elem: ET.Element, parent_map: dict[ET.Element, ET.Element]
    ) -> str | None:
        parent = parent_map.get(elem)
        if parent is None:
            return None
        for child in parent:
            if self._strip_namespace(child.tag) == "tpInsc":
                return child.text
        return None

    def _get_treatment(self, tag: str, in_titular: bool) -> str | None:
        """Retorna 'PRESERVE', 'TOKENIZE', 'CLASSIFY', 'GENERALIZE' ou None."""
        if tag in self.TAG_PREFIXES:
            return "TOKENIZE"
        if tag in self.CLASSIFY_DOMAINS:
            return "CLASSIFY"
        if tag in self.GENERALIZE_TAGS:
            return "GENERALIZE"
        if tag in self.PRESERVE_TAGS:
            return "PRESERVE"
        if not in_titular:
            return "PRESERVE"
        return None

    def _get_token_for_value(
        self,
        prefix: str,
        value: str,
        value_tokens: dict[tuple[str, str], str],
        counters: dict[str, int],
        token_map: dict[str, str],
    ) -> str | None:
        value = value.strip()
        if value == "":
            return None
        key = (prefix, value)
        if key in value_tokens:
            return value_tokens[key]
        counters[prefix] = counters.get(prefix, 0) + 1
        token = f"{prefix}_{counters[prefix]:03d}"
        while token in token_map:
            counters[prefix] += 1
            token = f"{prefix}_{counters[prefix]:03d}"
        value_tokens[key] = token
        token_map[token] = value
        return token

    def _classify_token(
        self,
        tag: str,
        value: str,
        counters: dict[str, int],
        token_map: dict[str, str],
    ) -> str | None:
        value = value.strip()
        if value == "":
            return None

        # Exceção de país: prefixo unificado para qualquer campo de país.
        # Validação é de FORMATO (3 dígitos), não contra tabela de países.
        if tag in ("paisNascto", "paisNac", "paisResid", "paisResidExt"):
            prefix = "PAIS"
            if value == "105":
                suffix = "BRASIL"
            elif value.isdigit() and len(value) == 3:
                suffix = "ESTRANGEIRO"
            else:
                suffix = "FORA_DOMINIO"
        else:
            prefix = self._to_snake_upper(tag)
            domain = self.CLASSIFY_DOMAINS.get(tag, frozenset())
            if value in domain:
                suffix = "VALIDO"
            else:
                suffix = "FORA_DOMINIO"

        counters[prefix] = counters.get(prefix, 0) + 1
        token = f"{prefix}_{suffix}_{counters[prefix]:03d}"
        while token in token_map:
            counters[prefix] += 1
            token = f"{prefix}_{suffix}_{counters[prefix]:03d}"
        token_map[token] = value
        return token

    @staticmethod
    def _to_snake_upper(tag: str) -> str:
        """Converte camelCase para SNAKE_UPPER."""
        result = []
        for i, ch in enumerate(tag):
            if ch.isupper() and i > 0:
                result.append("_")
            result.append(ch.upper())
        return "".join(result)

    def _cep_token(
        self,
        value: str,
        counters: dict[str, int],
        token_map: dict[str, str],
    ) -> str | None:
        value = value.strip()
        if value == "":
            return None
        prefix = "CEP"
        if re.fullmatch(r"\d{8}", value):
            suffix = "VALIDO"
        else:
            suffix = "FORA_FORMATO"
        counters[prefix] = counters.get(prefix, 0) + 1
        token = f"{prefix}_{suffix}_{counters[prefix]:03d}"
        while token in token_map:
            counters[prefix] += 1
            token = f"{prefix}_{suffix}_{counters[prefix]:03d}"
        token_map[token] = value
        return token

    def _value_token(self, raw_value: str) -> str:
        """Converte valor monetário em token de faixa."""
        try:
            value = float(raw_value)
        except ValueError:
            value = 0.0
        if value < 0:
            value = 0.0
        bounds = [0, 1000, 2000, 5000, 10000]
        lower = 0
        upper = None
        for bound in bounds:
            if value < bound:
                upper = bound
                break
            lower = bound
        if upper is None:
            upper = int(math.ceil(value / 10000.0) * 10000)
            if upper == lower:
                upper += 10000
        return f"VALOR_FAIXA_{lower}_{upper}"

    # ------------------------------------------------------------------
    # Tratamentos especiais
    # ------------------------------------------------------------------

    def _tokenize_field(
        self,
        elem: ET.Element,
        tag: str,
        path: str,
        parent_map: dict[ET.Element, ET.Element],
        ctps_series: dict[int, str],
        endereco_tokens: dict[int, str],
        value_tokens: dict[tuple[str, str], str],
        counters: dict[str, int],
        token_map: dict[str, str],
        fields_scrubbed: list[str],
    ) -> None:
        text = (elem.text or "").strip()
        if text == "":
            return

        # Endereço: bloco compartilha token.
        if tag in ("dscLograd", "logradouro", "nrLograd", "nrLogradouro",
                   "complemento", "bairro"):
            block = self._find_ancestor_in_set(elem, {"endereco"}, parent_map)
            if block is not None:
                eid = id(block)
                if eid not in endereco_tokens:
                    endereco_tokens[eid] = self._get_token_for_value(
                        "ENDERECO", "ENDERECO_BLOCO", value_tokens, counters, token_map
                    )
                token = endereco_tokens[eid]
            else:
                token = self._get_token_for_value(
                    "ENDERECO", elem.text or "", value_tokens, counters, token_map
                )
            elem.text = token
            fields_scrubbed.append(path)
            return

        # CTPS: número + série formam identificador.
        if tag == "nrCtps":
            parent = parent_map.get(elem)
            series = ctps_series.get(id(parent), "").strip() if parent is not None else ""
            value = text + (f"|{series}" if series else "")
            token = self._get_token_for_value(
                "DOC", value, value_tokens, counters, token_map
            )
            elem.text = token
            fields_scrubbed.append(path)
            if parent is not None:
                for child in parent:
                    if self._strip_namespace(child.tag) == "serieCtps":
                        child.text = token
                        fields_scrubbed.append(self._element_path(child, parent_map))
            return

        # Tokenização padrão.
        prefix = self.TAG_PREFIXES[tag]
        token = self._get_token_for_value(
            prefix, text, value_tokens, counters, token_map
        )
        elem.text = token
        fields_scrubbed.append(path)

    def _find_ancestor_in_set(
        self,
        elem: ET.Element,
        tags: set[str],
        parent_map: dict[ET.Element, ET.Element],
    ) -> ET.Element | None:
        current: ET.Element | None = elem
        while current is not None:
            if self._strip_namespace(current.tag) in tags:
                return current
            current = parent_map.get(current)
        return None

    # ------------------------------------------------------------------
    # Id e nrInsc do empregador
    # ------------------------------------------------------------------

    def _scrub_id(
        self,
        id_value: str,
        employer_cpf_tokens: dict[str, str],
        counters: dict[str, int],
        token_map: dict[str, str],
    ) -> tuple[str, bool]:
        if not id_value.startswith("ID") or len(id_value) != 36:
            return id_value, False

        prefix = id_value[:2]
        tp_insc = id_value[2:3]
        nr_insc = id_value[3:17]
        timestamp = id_value[17:31]
        seq = id_value[31:36]

        if tp_insc not in "1234":
            return id_value, False
        if not (nr_insc.isdigit() and timestamp.isdigit() and seq.isdigit()):
            return id_value, False

        if tp_insc == "1":
            return id_value, True

        if tp_insc in ("2", "3"):
            cpf_part = nr_insc[:11]
            suffix = nr_insc[11:]
            token = self._get_employer_cpf_token(
                cpf_part, employer_cpf_tokens, counters, token_map
            )
            new_nr = token + suffix
            return prefix + tp_insc + new_nr + timestamp + seq, True

        # tpInsc == 4 (CNO) — preservado.
        return id_value, True

    def _scrub_employer_nr_insc(
        self,
        value: str,
        tp_insc: str | None,
        employer_cpf_tokens: dict[str, str],
        counters: dict[str, int],
        token_map: dict[str, str],
    ) -> tuple[str, bool]:
        if tp_insc is None:
            return value, False
        if tp_insc == "1":
            return value, True
        if tp_insc in ("2", "3"):
            if not value.isdigit() or len(value) < 11:
                return value, False
            cpf_part = value[:11]
            suffix = value[11:]
            token = self._get_employer_cpf_token(
                cpf_part, employer_cpf_tokens, counters, token_map
            )
            return token + suffix, True
        if tp_insc == "4":
            return value, True
        return value, False

    def _get_employer_cpf_token(
        self,
        cpf: str,
        employer_cpf_tokens: dict[str, str],
        counters: dict[str, int],
        token_map: dict[str, str],
    ) -> str:
        if cpf in employer_cpf_tokens:
            return employer_cpf_tokens[cpf]
        counters["CPF_EMPR"] = counters.get("CPF_EMPR", 0) + 1
        # sequencial de 2 dígitos; estourar ⇒ fail-closed é tratado pelo chamador.
        if counters["CPF_EMPR"] > 99:
            raise _TooManyEmployersError()
        token = f"CPF_EMPR_{counters['CPF_EMPR']:02d}"
        employer_cpf_tokens[cpf] = token
        token_map[token] = cpf
        return token

    # ------------------------------------------------------------------
    # Rede de segurança v2
    # ------------------------------------------------------------------

    def _scrub_free_text(self, root: ET.Element, token_map: dict[str, str]) -> None:
        """Camada 1: substituir valores reais (cru e formatado) por tokens
        em nós de texto livre de retorno."""
        if not token_map:
            return

        # Preparar versões formatadas dos valores.
        replacements: dict[str, str] = {}
        for token, value in token_map.items():
            replacements[value] = token
            fmt = self._format_value(value)
            if fmt:
                replacements[fmt] = token

        for elem in root.iter():
            tag = self._strip_namespace(elem.tag)
            if tag in self.FREE_TEXT_RETURN_TAGS and elem.text:
                new_text = elem.text
                # Ordenar por tamanho decrescente para evitar substituições parciais.
                for old in sorted(replacements, key=len, reverse=True):
                    new_text = new_text.replace(old, replacements[old])
                elem.text = new_text

    @staticmethod
    def _format_value(value: str) -> str | None:
        """Retorna versão formatada de CPF/PIS, se aplicável."""
        if len(value) == 11 and value.isdigit():
            return f"{value[:3]}.{value[3:6]}.{value[6:9]}-{value[9:11]}"
        if len(value) == 12 and value.isdigit():
            return f"{value[:3]}.{value[3:8]}.{value[8:10]}-{value[10:11]}"
        return None

    def _security_check(
        self,
        root: ET.Element,
        parent_map: dict[ET.Element, ET.Element],
    ) -> bool:
        payload = ET.tostring(root, encoding="unicode")

        # Camada 2 — regex CPF/PIS.
        if self._CPF_PATTERN.search(payload) or self._PIS_PATTERN.search(payload):
            return False

        # Camada 3 — run de dígitos >= 11.
        for elem in root.iter():
            tag = self._strip_namespace(elem.tag)

            # Atributo Id é isento por validação estrutural própria.
            if "Id" in elem.attrib:
                continue

            # nrInsc isento apenas quando tpInsc=1.
            if tag == "nrInsc":
                if self._is_ide_empregador_nr_insc(elem, parent_map):
                    tp_insc = self._find_tp_insc(elem, parent_map)
                    if tp_insc == "1":
                        continue
                # Outros contextos de nrInsc (lotação etc.) — isenção nominal.
                # A lista de isenção cobre a tag genericamente abaixo.

            if tag in self.RUN_EXEMPTIONS:
                continue

            if elem.text and self._has_long_digit_run(elem.text):
                return False

            for attr_name, attr_value in elem.attrib.items():
                if attr_name in self.RUN_EXEMPTIONS:
                    continue
                if self._has_long_digit_run(attr_value):
                    return False

        return True

    @staticmethod
    def _has_long_digit_run(text: str) -> bool:
        normalized = re.sub(r"[.\-/\s]", "", text)
        current = 0
        for ch in normalized:
            if ch.isdigit():
                current += 1
                if current >= 11:
                    return True
            else:
                current = 0
        return False

    # ------------------------------------------------------------------
    # Utilitários
    # ------------------------------------------------------------------

    @staticmethod
    def _fail_closed(xml_content: str) -> ScrubResult:
        return ScrubResult(
            scrubbed_payload=xml_content,
            token_map={},
            fields_scrubbed=[],
            is_safe_for_remote=False,
        )


class _TooManyEmployersError(Exception):
    """Sinaliza que o limite de 99 CPFs de empregador distintos foi estourado."""
