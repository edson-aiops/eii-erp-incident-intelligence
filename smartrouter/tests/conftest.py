"""Fixtures compartilhadas da suite do SmartRouter."""
import pytest

_DUMMY_KEYS = (
    "GROQ_API_KEY",
    "GOOGLE_AI_API_KEY",
    "ANTHROPIC_API_KEY",
    "CEREBRAS_API_KEY",
    "MISTRAL_API_KEY",
    "OLLAMA_API_KEY",
    "OPENAI_API_KEY",
)


@pytest.fixture(autouse=True)
def _dummy_provider_keys(monkeypatch):
    """Torna a suite deterministica e independente do ambiente.

    O check de disponibilidade do router (router.py) le os.environ:
    sem chave, o provedor 'some' e o roteamento cai em emergency
    fallback para Groq, quebrando os asserts de roteamento ideal.

    Injetar dummies via monkeypatch tambem impede que os testes
    usem acidentalmente chaves REAIS do ambiente local — nenhum
    teste desta suite deve tocar a rede.
    """
    for key in _DUMMY_KEYS:
        monkeypatch.setenv(key, "test-dummy")
