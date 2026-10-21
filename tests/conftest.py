import json
import os
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
SCRIPTS = RAIZ / "skill" / "analise-de-curriculo" / "scripts"
sys.path.insert(0, str(SCRIPTS))
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(RAIZ / ".venv" / "ms-playwright"))

FIXTURE = RAIZ / "tests" / "fixture-processo.json"
REFERENCIA_PASTA = Path(os.path.expanduser("~/Documentos/IA NA PRATICA/AULA 3/Análise de Currículos"))
REFERENCIA_RESULTADO = RAIZ / "exemplos" / "referencia" / "_resultado"
APP = RAIZ / "app" / "analise-curriculos-app.html"
CACHE_CDN = RAIZ / ".venv" / "cdn-cache"


def carregar_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture
def proc():
    return carregar_fixture()


def resultado_referencia() -> Path | None:
    """Pasta do resultado do caso de referência (porta 1), se já foi gerado."""
    if not REFERENCIA_RESULTADO.is_dir():
        return None
    pastas = sorted(p for p in REFERENCIA_RESULTADO.iterdir() if (p / "processo.json").is_file())
    return pastas[-1] if pastas else None


# ------------------------------------------------------------------ Playwright

@pytest.fixture(scope="session")
def browser():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def _cdn(route):
    """Serve os scripts do cdnjs a partir de um cache local (baixado uma vez); sem rede, um stub vazio."""
    url = route.request.url
    nome = url.split("/ajax/libs/")[-1].replace("/", "_")
    arq = CACHE_CDN / nome
    if not arq.exists():
        try:
            import urllib.request

            CACHE_CDN.mkdir(parents=True, exist_ok=True)
            arq.write_bytes(urllib.request.urlopen(url, timeout=20).read())
        except Exception:  # noqa: BLE001
            return route.fulfill(status=200, body="/* sem rede: stub */", content_type="application/javascript")
    route.fulfill(status=200, body=arq.read_bytes(), content_type="application/javascript")


class Pagina:
    def __init__(self, page):
        self.page = page
        self.erros = []
        page.on("console", lambda m: m.type == "error" and self.erros.append(m.text))
        page.on("pageerror", lambda e: self.erros.append(str(e)))
        page.route("**/fonts.googleapis.com/**", lambda r: r.fulfill(status=200, body="", content_type="text/css"))
        page.route("**/fonts.gstatic.com/**", lambda r: r.fulfill(status=200, body=b"", content_type="font/woff2"))
        page.route("**/cdnjs.cloudflare.com/**", _cdn)


@pytest.fixture
def pagina(browser):
    ctx = browser.new_context(viewport={"width": 1200, "height": 900})
    pg = ctx.new_page()
    w = Pagina(pg)
    yield w
    ctx.close()


@pytest.fixture
def pagina_400(browser):
    ctx = browser.new_context(viewport={"width": 400, "height": 800})
    pg = ctx.new_page()
    w = Pagina(pg)
    yield w
    ctx.close()


@pytest.fixture
def painel_fixture(tmp_path, proc):
    from gerar_painel import montar_html

    arq = tmp_path / "painel.html"
    arq.write_text(montar_html(proc), encoding="utf-8")
    return arq
