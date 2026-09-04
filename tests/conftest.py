import sys
import os

# Adiciona a raiz do projeto ao sys.path para os testes encontrarem os módulos
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app():
    """FastAPI app do eii_api (A3.5)."""
    import eii_api
    return eii_api.app


@pytest.fixture
def client(app):
    """TestClient para o eii_api (A3.5)."""
    return TestClient(app)
