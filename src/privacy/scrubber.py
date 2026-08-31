"""Scrubber de PII obrigatório e não-configurável do EII.

O scrubbing é executado antes de qualquer chamada a LLM remoto. O mapa de
tokens (`token_map`) fica apenas em memória e no escopo do request, garantindo
que o operador remoto não possa reidentificar o titular.

Esta solução é pseudonimização com mapa local, não anonimização plena.
"""

from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
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

    # Mapeamento de tag -> prefixo de token. Tags dentro de <endereco>
    # compartilham o mesmo token (bloco inteiro).
    TAG_PREFIXES: ClassVar[dict[str, str]] = {
        "cpfTrab": "CPF",
        "cpfBenef": "CPF",
        "cpfResp": "CPF",
        "nmTrab": "NOME",
        "nmSoc": "NOME",
        "nmMae": "NOME",
        "nmPai": "NOME",
        "nisTrab": "NIS",
        "dtNascto": "DATA_NASC",
        "logradouro": "ENDERECO",
        "nrLogradouro": "ENDERECO",
        "cep": "ENDERECO",
        "matricula": "MATR",
        "nrCtps": "DOC",
        "nrRic": "DOC",
        "nrRg": "DOC",
        "nrCnh": "DOC",
        "vrRubr": "VALOR",
        "vrBcCp": "VALOR",
    }

    # Rede de segurança: padrões que, se restarem no payload final,
    # forçam is_safe_for_remote=False. Usam negative lookbehind/ahead de
    # dígitos para não disparar em janelas de 11 dígitos dentro de sequências
    # maiores, como CNPJ de 14 dígitos ou Id do evento eSocial.
    _CPF_PATTERN = re.compile(r"(?<!\d)\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?!\d)")
    _PIS_PATTERN = re.compile(r"(?<!\d)\d{3}\.?\d{5}\.?\d{2}-?\d(?!\d)")

    def scrub(self, xml_content: str, event_type: str) -> ScrubResult:
        """Pseudonimiza PII presente em `xml_content`.

        Args:
            xml_content: string XML do evento eSocial.
            event_type: tipo do evento (ex.: "S-1200").

        Returns:
            ScrubResult com payload limpo, mapa de tokens, campos tratados e
            indicação se pode ser enviado a um LLM remoto.
        """
        token_map: dict[str, str] = {}
        fields_scrubbed: list[str] = []

        # Fail-closed: evento não mapeado
        if event_type not in self.SUPPORTED_EVENTS:
            return ScrubResult(
                scrubbed_payload=xml_content,
                token_map=token_map,
                fields_scrubbed=fields_scrubbed,
                is_safe_for_remote=False,
            )

        # Fail-closed: XML malformado
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError:
            return ScrubResult(
                scrubbed_payload=xml_content,
                token_map=token_map,
                fields_scrubbed=fields_scrubbed,
                is_safe_for_remote=False,
            )

        counters: dict[str, int] = {}

        # Endereço é tratado como bloco: todas as tags relevantes dentro de um
        # mesmo <endereco> compartilham o token.
        endereco_tokens: dict[int, str] = {}

        # 1ª passada: substituição por campo.
        for elem in root.iter():
            tag = self._strip_namespace(elem.tag)
            path = self._element_path(elem)

            if tag in self.TAG_PREFIXES:
                prefix = self.TAG_PREFIXES[tag]

                if prefix == "ENDERECO":
                    # Localiza o ancestral <endereco> mais próximo.
                    endereco_elem = self._find_ancestor_endereco(elem)
                    if endereco_elem is not None:
                        eid = id(endereco_elem)
                        if eid not in endereco_tokens:
                            endereco_tokens[eid] = self._next_token(
                                prefix, counters, token_map, "ENDERECO_BLOCO"
                            )
                        token = endereco_tokens[eid]
                    else:
                        token = self._next_token(
                            prefix, counters, token_map, elem.text or ""
                        )
                    token_map[token] = elem.text or ""
                    elem.text = token
                    fields_scrubbed.append(path)

                elif prefix == "VALOR":
                    token = self._value_token(elem.text or "0")
                    token_map[token] = elem.text or ""
                    elem.text = token
                    fields_scrubbed.append(path)

                else:
                    value = elem.text or ""
                    token = self._next_token(prefix, counters, token_map, value)
                    token_map[token] = value
                    elem.text = token
                    fields_scrubbed.append(path)

        # 2ª passada: rede de segurança por regex no payload final.
        scrubbed_payload = ET.tostring(root, encoding="unicode")
        is_safe_for_remote = not (
            self._CPF_PATTERN.search(scrubbed_payload)
            or self._PIS_PATTERN.search(scrubbed_payload)
        )

        return ScrubResult(
            scrubbed_payload=scrubbed_payload,
            token_map=token_map,
            fields_scrubbed=fields_scrubbed,
            is_safe_for_remote=is_safe_for_remote,
        )

    def restore(self, text: str, token_map: dict[str, str]) -> str:
        """Reverte tokens para os valores reais em `text`.

        Deve ser chamada apenas após a resposta do LLM voltar, dentro do mesmo
        request e com o mesmo `token_map`.
        """
        if not token_map:
            return text

        # Ordena tokens por tamanho decrescente para evitar substituições
        # parciais (ex.: CPF_001 dentro de CPF_0010).
        for token in sorted(token_map, key=len, reverse=True):
            text = re.sub(re.escape(token), token_map[token], text)
        return text

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_namespace(tag: str) -> str:
        """Remove namespace da tag, se houver."""
        if "}" in tag:
            return tag.split("}", 1)[1]
        return tag

    @staticmethod
    def _element_path(elem: ET.Element) -> str:
        """Monta um caminho legível para o elemento."""
        parts = []
        current: ET.Element | None = elem
        while current is not None:
            tag = PIIScrubber._strip_namespace(current.tag)
            parts.append(tag)
            # ElementTree não expõe parent diretamente; usamos busca inversa.
            current = next(
                (p for p in current.iter() if current in list(p)), None
            )
        return "/".join(reversed(parts))

    @staticmethod
    def _find_ancestor_endereco(elem: ET.Element) -> ET.Element | None:
        """Encontra o ancestral <endereco> de `elem`, se existir.

        Como ElementTree padrão não guarda referência ao pai, fazemos uma
        busca simples olhando todos os elementos <endereco> do documento e
        verificando se `elem` está entre seus descendentes.
        """
        # Procura o documento via raiz: sobe até o topo.
        root = elem
        while True:
            try:
                parent = next((p for p in root.iter() if elem in list(p)), None)
            except TypeError:
                parent = None
            if parent is None:
                break
            root = parent

        for candidate in root.iter():
            tag = PIIScrubber._strip_namespace(candidate.tag)
            if tag == "endereco":
                if elem in list(candidate.iter()):
                    # Verifica se elem é descendente direto/indireto.
                    for child in candidate.iter():
                        if child is elem:
                            return candidate
        return None

    @staticmethod
    def _next_token(
        prefix: str,
        counters: dict[str, int],
        token_map: dict[str, str],
        value: str,
    ) -> str:
        """Gera um novo token sequencial para `prefix`."""
        counters[prefix] = counters.get(prefix, 0) + 1
        token = f"{prefix}_{counters[prefix]:03d}"
        # Garante unicidade em caso de colisão extremamente improvável.
        while token in token_map:
            counters[prefix] += 1
            token = f"{prefix}_{counters[prefix]:03d}"
        return token

    @staticmethod
    def _value_token(raw_value: str) -> str:
        """Converte valor monetário em token de faixa preservando formato.

        Exemplo: 1543.27 -> VALOR_FAIXA_1000_2000
        """
        try:
            value = float(raw_value)
        except ValueError:
            value = 0.0

        if value < 0:
            value = 0.0

        # Faixas em reais (R$). Os limites superiores são abertos.
        bounds = [0, 1000, 2000, 5000, 10000]

        lower = 0
        upper = None
        for i, bound in enumerate(bounds):
            if value < bound:
                upper = bound
                break
            lower = bound

        if upper is None:
            upper = int(math.ceil(value / 10000.0) * 10000)
            if upper == lower:
                upper += 10000

        return f"VALOR_FAIXA_{lower}_{upper}"
