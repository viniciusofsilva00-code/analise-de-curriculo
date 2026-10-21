"""App (porta 2): build, modo de teste local e fluxo completo com o `sample` simulado."""
import json
import re

import pytest

from conftest import APP, FIXTURE, RAIZ, REFERENCIA_PASTA, resultado_referencia
from validar import validar

ESQUELETO = '<!doctype html><html><head><meta charset=utf8><meta name=viewport content="width=device-width,initial-scale=1"></head><body>{}</body></html>'


@pytest.fixture(scope="module", autouse=True)
def build():
    import subprocess
    import sys

    subprocess.run([sys.executable, str(RAIZ / "scripts" / "build_app.py")], check=True, capture_output=True)


@pytest.fixture
def app_publicado(tmp_path):
    """O app como a publicação o serve: envolvido num esqueleto HTML."""
    arq = tmp_path / "app.html"
    arq.write_text(ESQUELETO.format(APP.read_text(encoding="utf-8")), encoding="utf-8")
    return arq


def test_build_embute_regras_e_template():
    html = APP.read_text(encoding="utf-8")
    assert html.lstrip().startswith("<title>")
    fora_js = re.sub(r"<script\b[^>]*>.*?</script>", "", html, flags=re.S)
    for tag in ("<!doctype", "<html", "<head>", "<body"):
        assert tag not in fora_js.lower()
    regras = (RAIZ / "core" / "regras-avaliacao.md").read_text(encoding="utf-8")
    m = re.search(r"const REGRAS = (\".*?\");\n", html)
    assert json.loads(m.group(1).replace("<\\/", "</")) == regras
    for src in re.findall(r'<script src="([^"]+)"', html):
        assert src.startswith("https://cdnjs.cloudflare.com/") and re.search(r"/\d+\.\d+\.\d+/", src)


def test_modo_de_teste_local_abre_processo_da_porta_1(pagina, app_publicado):
    pasta = resultado_referencia() or None
    origem = (pasta / "processo.json") if pasta else FIXTURE
    page = pagina.page
    page.goto(app_publicado.as_uri())
    assert "Modo de teste local" in page.inner_text("#modo")
    assert page.is_hidden("#btn-avaliar")
    assert page.is_hidden("#run") and page.is_hidden("#afirm-box")  # [hidden] vence o display:flex
    page.set_input_files("#in-imp", str(origem))
    page.wait_for_selector("#rank-body tr")
    proc = json.loads(origem.read_text(encoding="utf-8"))
    for cid in proc["top3"]:
        assert page.is_visible(f"#tab-{cid}")
    assert page.is_hidden("#app")
    assert pagina.erros == []


def test_app_arquivo_cru_tambem_abre(pagina):
    """Abrir o .html direto (sem esqueleto) funciona em modo de teste."""
    page = pagina.page
    page.goto(APP.as_uri())
    assert "Modo de teste local" in page.inner_text("#modo")
    page.fill("#imp-txt", FIXTURE.read_text(encoding="utf-8"))
    page.click("#btn-imp-colar")
    page.wait_for_selector("#tab-juliana")
    assert pagina.erros == []


def test_app_400px_sem_rolagem(pagina_400, app_publicado):
    page = pagina_400.page
    page.goto(app_publicado.as_uri())
    w = page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
    assert w[0] <= w[1]
    assert pagina_400.erros == []


MOCK = """
window.__chamadas = [];
window.__respostas = %s;
window.claude = { use: async (nome) => {
  if (nome === "sample") {
    const f = async (input, opts) => { throw {code: "invalid_request", message: "use json"}; };
    f.json = async (prompt, opts) => {
      window.__chamadas.push({prompt, opts: {modelTier: opts.modelTier, temSignal: !!opts.signal}});
      if (opts.onText) opts.onText({text: "{", delta: "{"});
      const r = window.__respostas.shift();
      if (r && r.__erro) throw r.__erro;
      return JSON.parse(JSON.stringify(r));
    };
    return f;
  }
  return null;  // downloads indisponível: cai no campo de copiar
}};
"""


def _respostas_do_fixture():
    """Converte o processo de referência (porta 1) nas respostas que o Claude daria ao app."""
    pasta = resultado_referencia()
    proc = json.loads(((pasta / "processo.json") if pasta else FIXTURE).read_text(encoding="utf-8"))
    cands = []
    for c in proc["candidatos"]:
        if c["status"] == "nao_avaliado":
            continue
        r = {k: v for k, v in c.items() if k not in ("id", "ordemRecencia")}
        r["recenciaMeses"] = c.get("ordemRecencia", 9) * 3
        r["proximidade"] = 3
        cands.append(r)
    triagem = {"criterios": proc["criterios"], "candidatos": cands}
    perguntas = {"comuns": proc["perguntas"]["comuns"], "porCandidato": proc["perguntas"]["porCandidato"]}
    return proc, triagem, perguntas


def test_fluxo_completo_com_sample_simulado(pagina, app_publicado, tmp_path):
    proc_ref, triagem, perguntas = _respostas_do_fixture()
    page = pagina.page
    respostas = [{"__erro": {"code": "invalid_json", "message": "x", "text": "nao era json"}}, triagem, perguntas]
    page.add_init_script(MOCK % json.dumps(respostas, ensure_ascii=False))
    page.goto(app_publicado.as_uri())
    page.wait_for_function("document.querySelector('#btn-avaliar').textContent==='Avaliar'")
    page.fill("#v-cargo", "Analista de Recursos Humanos")
    page.fill("#v-empresa", "Nexora")
    page.fill("#v-local", "São Paulo, SP")
    page.fill("#v-faixa", "R$ 3.800–5.200")
    pdfs = sorted(str(p) for p in REFERENCIA_PASTA.glob("*.pdf"))
    page.set_input_files("#in-arqs", pdfs)
    page.wait_for_function("AppAnalise.W.arquivos.length===11 && AppAnalise.W.arquivos.every(a=>!a.lendo)", timeout=60000)
    legiveis = page.evaluate("AppAnalise.W.arquivos.filter(a=>a.legivel).length")
    if legiveis == 0:
        pytest.skip("sem rede para baixar o pdf.js do cdnjs nesta máquina")

    # 1º clique: anúncio presente -> vai direto para a triagem; a resposta simulada vem fora do formato
    page.click("#btn-avaliar")
    page.wait_for_selector("#btn-repetir")
    assert "formato JSON" in page.inner_text("#msg")
    # "Tentar de novo" (clique do usuário) -> triagem ok
    page.click("#btn-repetir")
    page.wait_for_function("AppAnalise.W.etapa==='perguntas'")
    assert "Gerar perguntas" in page.inner_text("#btn-avaliar")
    page.click("#btn-avaliar")
    page.wait_for_selector("#painel-root #rank-body tr")

    chamadas = page.evaluate("window.__chamadas")
    assert len(chamadas) == 3  # uma por clique, nenhuma automática
    assert all(c["opts"]["modelTier"] == "complex" and c["opts"]["temSignal"] for c in chamadas)
    regras = (RAIZ / "core" / "regras-avaliacao.md").read_text(encoding="utf-8")
    assert regras in chamadas[1]["prompt"] and regras in chamadas[2]["prompt"]
    assert "REQUISITOS OBRIGATÓRIOS" in chamadas[1]["prompt"]
    assert all(len(c["prompt"].encode()) < 256 * 1024 for c in chamadas)

    gerado = page.evaluate("PainelSelecao.atual().exportar()")
    assert gerado["geradoPor"] == "app"
    assert gerado["top3"] == proc_ref["top3"]
    elim = sorted(c["nome"] for c in gerado["candidatos"] if c["status"] != "aprovado")
    assert elim == sorted(c["nome"] for c in proc_ref["candidatos"] if c["status"] != "aprovado")
    erros, _ = validar(gerado)
    assert erros == [], erros
    assert pagina.erros == []


def test_lotes_respeitam_limite(pagina, app_publicado):
    page = pagina.page
    page.goto(app_publicado.as_uri())
    n = page.evaluate("""() => {
      const W = AppAnalise.W;
      W.arquivos = Array.from({length: 30}, (_, i) => ({id: 'cv'+i, arquivo: 'cv'+i+'.pdf', texto: 'x'.repeat(20000), legivel: true, ehVaga: false}));
      const lotes = AppAnalise.montarLotes();
      const vaga = {titulo: 'X', cargo: 'X'};
      return lotes.map(l => new TextEncoder().encode(AppAnalise.montarPromptTriagem(vaga, null, l)).length);
    }""")
    assert len(n) >= 3 and all(b < 256 * 1024 for b in n)
    assert pagina.erros == []


def test_site_github_pages(pagina):
    """docs/index.html (GitHub Pages) é o mesmo app com esqueleto e abre em modo de teste."""
    site = RAIZ / "docs" / "index.html"
    html = site.read_text(encoding="utf-8")
    assert html.startswith("<!doctype html>") and APP.read_text(encoding="utf-8") in html
    assert (RAIZ / "docs" / ".nojekyll").exists()
    page = pagina.page
    page.goto(site.as_uri())
    assert page.evaluate("document.compatMode") == "CSS1Compat"  # sem modo quirks
    assert "Modo de teste local" in page.inner_text("#modo")
    page.fill("#imp-txt", FIXTURE.read_text(encoding="utf-8"))
    page.click("#btn-imp-colar")
    page.wait_for_selector("#tab-juliana")
    assert pagina.erros == []
