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
    assert html.startswith("<!doctype html>")
    assert (RAIZ / "docs" / ".nojekyll").exists()
    page = pagina.page
    page.goto(site.as_uri())
    assert page.evaluate("document.compatMode") == "CSS1Compat"  # sem modo quirks
    assert "fora do claude.ai" in page.inner_text("#modo")
    assert page.is_visible("#btn-avaliar")
    page.fill("#imp-txt", FIXTURE.read_text(encoding="utf-8"))
    page.click("#btn-imp-colar")
    page.wait_for_selector("#tab-juliana")
    assert pagina.erros == []


def test_conexao_ia_so_no_site(pagina):
    """A seção de API (Claude/GPT/Gemini) existe só no site; a chave não persiste sem 'Lembrar'."""
    assert 'id="sec-conexao"' not in APP.read_text(encoding="utf-8") and "ConexaoIA = {" not in APP.read_text(encoding="utf-8")
    site = RAIZ / "docs" / "index.html"
    page = pagina.page
    page.goto(site.as_uri())
    opcoes = page.eval_on_selector_all("#ia-provedor option", "os => os.map(o => o.value)")
    assert opcoes == ["", "plano", "anthropic", "openai", "google", "cloudflare"]
    assert page.is_hidden("#ia-conta-box")
    page.select_option("#ia-provedor", "anthropic")
    assert page.input_value("#ia-modelo") == "claude-opus-5-5"
    page.fill("#ia-chave", "sk-ant-teste-123")
    assert "selecionado" in page.inner_text("#ia-status")
    assert page.evaluate("ConexaoIA.get()") == {"provedor": "anthropic", "modelo": "claude-opus-5-5", "temChave": True}
    guardado = page.evaluate("localStorage.getItem('analise-curriculos-conexao-ia-v1')")
    assert "sk-ant-teste-123" not in guardado  # sem "Lembrar", a chave não vai para o armazenamento
    page.check("#ia-lembrar")
    assert "sk-ant-teste-123" in page.evaluate("localStorage.getItem('analise-curriculos-conexao-ia-v1')")
    page.click("#ia-esquecer")
    assert "sk-ant-teste-123" not in page.evaluate("localStorage.getItem('analise-curriculos-conexao-ia-v1')")
    page.select_option("#ia-provedor", "google")
    assert page.input_value("#ia-modelo") == ""
    # Cloudflare: URL do Worker (ponte) + chave de acesso do Worker
    page.select_option("#ia-provedor", "cloudflare")
    assert page.is_visible("#ia-conta-box") and page.inner_text("#ia-chave-rotulo") == "Chave de acesso do Worker (CHAVE_ACESSO)"
    page.fill("#ia-modelo", "@cf/modelo-teste")
    page.fill("#ia-conta", "sem-https.exemplo")
    page.fill("#ia-chave", "token-cf")
    assert "https://" in page.inner_text("#ia-status")
    page.fill("#ia-conta", "https://ponte.exemplo.workers.dev/")
    page.fill("#ia-chave", "token-cf")
    assert "selecionado" in page.inner_text("#ia-status")
    assert page.evaluate("ConexaoIA.get()") == {"provedor": "cloudflare", "modelo": "@cf/modelo-teste", "temChave": True, "conta": "https://ponte.exemplo.workers.dev/"}
    # a chave nunca entra no processo.json exportado
    page.fill("#ia-chave", "chave-secreta-xyz")
    page.fill("#imp-txt", FIXTURE.read_text(encoding="utf-8"))
    page.click("#btn-imp-colar")
    page.wait_for_selector("#tab-juliana")
    page.click("#btn-export")
    assert "chave-secreta-xyz" not in page.input_value("#io-out")
    assert pagina.erros == []


def _resposta_provedor(provedor, dados):
    """Monta a resposta HTTP que cada provedor daria, com `dados` (dict) como texto JSON."""
    texto = json.dumps(dados, ensure_ascii=False)
    if provedor == "anthropic":
        partes = [texto[i:i + 4000] for i in range(0, len(texto), 4000)]
        evs = [{"type": "message_start", "message": {}}, {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}]
        evs += [{"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": p}} for p in partes]
        evs += [{"type": "message_delta", "delta": {"stop_reason": "end_turn"}}, {"type": "message_stop"}]
        corpo = "".join(f"event: {e['type']}\ndata: {json.dumps(e, ensure_ascii=False)}\n\n" for e in evs)
        return {"status": 200, "content_type": "text/event-stream", "body": corpo}
    if provedor == "openai":
        corpo = {"choices": [{"finish_reason": "stop", "message": {"content": "```json\n" + texto + "\n```"}}]}
    elif provedor == "google":
        corpo = {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": texto}]}}]}
    else:
        corpo = {"texto": texto}
    return {"status": 200, "content_type": "application/json", "body": json.dumps(corpo, ensure_ascii=False)}


URLS = {"anthropic": "https://api.anthropic.com/v1/messages", "openai": "https://api.openai.com/v1/chat/completions",
        "google": "https://generativelanguage.googleapis.com/**", "cloudflare": "https://ponte.exemplo.workers.dev/**"}
MODELOS = {"anthropic": None, "openai": "modelo-gpt-teste", "google": "modelo-gemini-teste", "cloudflare": "@cf/modelo-teste"}


@pytest.mark.parametrize("provedor", ["anthropic", "openai", "google", "cloudflare"])
def test_site_avalia_pela_api(pagina, provedor):
    proc_ref, triagem, perguntas = _respostas_do_fixture()
    page = pagina.page
    pedidos = []

    def resposta_para(prompt):
        if "<curriculos>" in prompt:  # triagem: devolve só os currículos deste lote
            cands = [c for c in triagem["candidatos"] if f'arquivo="{c["arquivo"]}"' in prompt]
            return {"criterios": triagem["criterios"], "candidatos": cands}
        return perguntas

    def responder(route):
        req = route.request
        if req.method == "OPTIONS":
            return route.fulfill(status=204, headers={"access-control-allow-origin": "*", "access-control-allow-headers": "*"})
        corpo = json.loads(req.post_data or "{}")
        pedidos.append({"headers": req.headers, "body": corpo})
        texto = corpo.get("prompt") or (corpo.get("messages") or [{}])[0].get("content") or corpo["contents"][0]["parts"][0]["text"]
        r = _resposta_provedor(provedor, resposta_para(texto))
        route.fulfill(status=r["status"], content_type=r["content_type"], body=r["body"], headers={"access-control-allow-origin": "*"})

    page.route(URLS[provedor], responder)
    page.goto((RAIZ / "docs" / "index.html").as_uri())
    page.fill("#v-cargo", "Analista de Recursos Humanos")
    pdfs = sorted(str(p) for p in REFERENCIA_PASTA.glob("*.pdf"))
    page.set_input_files("#in-arqs", pdfs)
    page.wait_for_function("AppAnalise.W.arquivos.length===11 && AppAnalise.W.arquivos.every(a=>!a.lendo)", timeout=60000)
    if page.evaluate("AppAnalise.W.arquivos.filter(a=>a.legivel).length") == 0:
        pytest.skip("sem rede para baixar o pdf.js do cdnjs nesta máquina")

    page.click("#btn-avaliar")  # sem chave: pede para completar a seção 0, sem chamar nada
    assert "Complete a seção 0" in page.inner_text("#msg") and pedidos == []

    page.select_option("#ia-provedor", provedor)
    if MODELOS[provedor]:
        page.fill("#ia-modelo", MODELOS[provedor])
    if provedor == "cloudflare":
        page.fill("#ia-conta", "https://ponte.exemplo.workers.dev/")
    page.fill("#ia-chave", "chave-teste-123")
    page.click("#btn-avaliar")
    if provedor == "cloudflare":  # 4 currículos por lote no Workers AI: um clique por lote
        for lote in (2, 3):
            page.wait_for_function(f"AppAnalise.W.loteAtual==={lote-1} && !document.querySelector('#acoes').hidden", timeout=20000)
            assert f"({lote} de 3)" in page.inner_text("#btn-avaliar")
            page.click("#btn-avaliar")
    page.wait_for_function("AppAnalise.W.etapa==='perguntas'", timeout=20000)
    page.click("#btn-avaliar")
    page.wait_for_selector("#painel-root #rank-body tr", timeout=20000)

    h = pedidos[0]["headers"]
    if provedor == "anthropic":
        assert h["x-api-key"] == "chave-teste-123" and h["anthropic-version"] == "2023-06-01"
        assert h["anthropic-dangerous-direct-browser-access"] == "true"
        assert pedidos[0]["body"]["model"] == "claude-opus-5-5" and pedidos[0]["body"]["stream"] is True
    elif provedor == "google":
        assert h["x-goog-api-key"] == "chave-teste-123"
    else:
        assert h["authorization"] == "Bearer chave-teste-123"
    regras = (RAIZ / "core" / "regras-avaliacao.md").read_text(encoding="utf-8")
    assert regras in json.dumps(pedidos[0]["body"], ensure_ascii=False).encode().decode("unicode_escape") or "Regras de avaliação" in json.dumps(pedidos[0]["body"], ensure_ascii=False)
    gerado = page.evaluate("PainelSelecao.atual().exportar()")
    assert gerado["top3"] == proc_ref["top3"]
    assert "chave-teste-123" not in json.dumps(gerado)
    erros, _ = validar(gerado)
    assert erros == [], erros
    assert pagina.erros == []


def test_lotes_cloudflare(pagina):
    page = pagina.page
    page.goto((RAIZ / "docs" / "index.html").as_uri())
    page.select_option("#ia-provedor", "cloudflare")
    n = page.evaluate("""() => {
      AppAnalise.W.arquivos = Array.from({length: 10}, (_, i) => ({id: 'cv'+i, arquivo: 'cv'+i+'.pdf', texto: 'x'.repeat(1300), legivel: true, ehVaga: false}));
      return AppAnalise.montarLotes().map(l => l.length);
    }""")
    assert n == [4, 4, 2]
    assert pagina.erros == []


def test_site_chave_recusada(pagina):
    page = pagina.page
    page.route("https://api.anthropic.com/v1/messages", lambda r: r.fulfill(status=401, body='{"error":{"type":"authentication_error"}}', headers={"access-control-allow-origin": "*"}))
    page.goto((RAIZ / "docs" / "index.html").as_uri())
    page.fill("#v-cargo", "Analista")
    page.evaluate("""() => { AppAnalise.W.arquivos = [{id:'cv1', arquivo:'cv1.pdf', texto:'Analista de RH '.repeat(40), legivel:true, ehVaga:false}]; }""")
    page.fill("#v-req", "Obrigatório: 2 anos em RH")
    page.select_option("#ia-provedor", "anthropic")
    page.fill("#ia-chave", "sk-ant-errada")
    page.click("#btn-avaliar")
    page.wait_for_selector("#btn-repetir")
    assert "recusou a chave" in page.inner_text("#msg")
    assert page.is_visible("#btn-avaliar")
    # erro de rede/HTTP no console do navegador é esperado aqui (401); erros de script, não
    assert [e for e in pagina.erros if "401" not in e and "Failed to load resource" not in e] == []


def test_site_oferece_plano_claude(pagina):
    """No site, o caminho principal é o app no claude.ai (plano Claude, sem chave)."""
    assert "link-plano-claude" not in APP.read_text(encoding="utf-8")
    page = pagina.page
    page.goto((RAIZ / "docs" / "index.html").as_uri())
    link = page.locator("#link-plano-claude")
    assert link.is_visible()
    assert link.get_attribute("href").startswith("https://claude.ai/artifact/")
    assert link.get_attribute("target") == "_blank"
    assert pagina.erros == []
