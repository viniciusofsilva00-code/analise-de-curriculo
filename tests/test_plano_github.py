"""Plano Claude via GitHub: site (API do GitHub simulada) e script da Action."""
import json
import re
from pathlib import Path

import pytest

from conftest import FIXTURE, RAIZ, REFERENCIA_PASTA

SITE = RAIZ / "docs" / "index.html"
REPO = "usuario/triagem-cv-dados"


class GitHubFalso:
    """Simula o pedaço da API do GitHub que o site usa."""

    def __init__(self, privado=True, falhas_blob=0):
        self.privado = privado
        self.falhas_blob = falhas_blob  # quantos POST de blob respondem 500 antes de aceitar
        self.blobs = {}
        self.arvores = {}
        self.commits = 0
        self.arquivos = {}
        self.label = False
        self.issues = []
        self.comentarios = []  # comentários do usuário (ajuste)
        self.polls = 0

    def __call__(self, route):
        req = route.request
        if req.method == "OPTIONS":
            return route.fulfill(status=204, headers={"access-control-allow-origin": "*", "access-control-allow-headers": "*", "access-control-allow-methods": "*"})
        assert req.headers.get("authorization") == "Bearer github_pat_teste"
        url = re.sub(r"\?.*$", "", req.url).replace("https://api.github.com", "")
        corpo = json.loads(req.post_data) if req.post_data else None
        j = lambda d, st=200: route.fulfill(status=st, content_type="application/json", body=json.dumps(d), headers={"access-control-allow-origin": "*"})
        if url == f"/repos/{REPO}":
            return j({"private": self.privado, "default_branch": "main", "permissions": {"push": True}})
        if url == f"/repos/{REPO}/labels" and req.method == "GET":
            return j([{"name": "triagem"}] if self.label else [{"name": "bug"}])
        if url == f"/repos/{REPO}/labels" and req.method == "POST":
            self.label = True
            return j({"name": "triagem"}, 201)
        if url == f"/repos/{REPO}/git/blobs" and req.method == "POST":
            if self.falhas_blob:
                self.falhas_blob -= 1
                return j({"message": "Server Error"}, 500)
            sha = f"blob{len(self.blobs)}"
            self.blobs[sha] = corpo["content"]
            return j({"sha": sha}, 201)
        if url == f"/repos/{REPO}/git/ref/heads/main":
            return j({"object": {"sha": f"commit{self.commits}"}})
        if re.fullmatch(rf"/repos/{REPO}/git/commits/commit\d+", url):
            return j({"tree": {"sha": "arvore-base"}})
        if url == f"/repos/{REPO}/git/trees" and req.method == "POST":
            sha = f"arvore{len(self.arvores)}"
            self.arvores[sha] = corpo["tree"]
            return j({"sha": sha}, 201)
        if url == f"/repos/{REPO}/git/commits" and req.method == "POST":
            self.ultimo_commit = corpo["tree"]
            return j({"sha": "novo"}, 201)
        if url == f"/repos/{REPO}/git/refs/heads/main" and req.method == "PATCH":
            self.commits += 1
            for item in self.arvores[self.ultimo_commit]:
                self.arquivos[item["path"]] = self.blobs[item["sha"]]
            return j({"object": {"sha": corpo["sha"]}})
        if url == f"/repos/{REPO}/issues" and req.method == "POST":
            self.issues.append(corpo)
            return j({"number": 7}, 201)
        if url == f"/repos/{REPO}/issues/7/comments" and req.method == "POST":
            self.comentarios.append(corpo["body"])
            return j({"id": 1}, 201)
        if url == f"/repos/{REPO}/issues/7/comments":
            self.polls += 1
            if self.comentarios:
                return j([{"body": "<!-- triagem: pronto -->\nTriagem pronta."}])
            if self.polls < 3:
                return j([{"body": "<!-- triagem: recebido -->\nRecebi."}] if self.polls == 2 else [])
            return j([{"body": "<!-- triagem: recebido -->"}, {"body": "<!-- triagem: perguntas -->\nPosso pontuar com esta matriz?\n| C1 | O | 10 |"}])
        if re.match(rf"/repos/{REPO}/contents/resultados/[^/]+/processo\.json$", url):
            assert "raw" in req.headers.get("accept", "")
            return route.fulfill(status=200, body=FIXTURE.read_text(encoding="utf-8"), headers={"access-control-allow-origin": "*"})
        return j({"message": f"inesperado {req.method} {url}"}, 500)


def _preparar(page, gh):
    page.route("https://api.github.com/**", gh)
    page.goto(SITE.as_uri())
    page.click("#usar-plano-github")
    assert page.input_value("#ia-provedor") == "plano" and page.is_hidden("#ia-modelo-box")
    page.fill("#ia-conta", REPO)
    page.fill("#ia-chave", "github_pat_teste")
    assert "selecionado" in page.inner_text("#ia-status")
    page.evaluate("ConexaoIA.plano.intervalo = 30")
    page.fill("#v-cargo", "Analista de Recursos Humanos")
    page.set_input_files("#in-arqs", sorted(str(p) for p in REFERENCIA_PASTA.glob("*.pdf"))[:4])
    page.wait_for_function("AppAnalise.W.arquivos.length===4 && AppAnalise.W.arquivos.every(a=>!a.lendo)", timeout=60000)
    assert "Avaliar pelo meu plano" in page.inner_text("#btn-avaliar")


def test_plano_via_github_fluxo_completo(pagina):
    gh = GitHubFalso()
    page = pagina.page
    _preparar(page, gh)
    page.click("#btn-avaliar")
    page.wait_for_selector("#plano-resp", timeout=20000)  # o Claude pediu ok da matriz
    assert "Posso pontuar com esta matriz" in page.inner_text("#resultado")
    # enviou os 4 arquivos + vaga.md para entrada/<id>/, num repositório privado, com o marcador no pedido
    caminhos = sorted(gh.arquivos)
    pid = caminhos[0].split("/")[1]
    assert re.fullmatch(r"\d{14}-[a-z0-9]{4}", pid)
    assert len(caminhos) == 5 and f"entrada/{pid}/vaga.md" in caminhos
    assert gh.commits == 1  # tudo num commit só
    import base64
    vaga = base64.b64decode(gh.arquivos[f"entrada/{pid}/vaga.md"]).decode()
    assert "Analista de Recursos Humanos" in vaga and "00_anuncio_vaga_analista_rh.pdf" in vaga
    assert gh.label and gh.issues[0]["labels"] == ["triagem"] and f"<!-- triagem-id: {pid} -->" in gh.issues[0]["body"]
    # responde a pergunta -> comentário "ajuste:" -> pronto -> painel abre aqui
    page.fill("#plano-resp", "pode pontuar com esta matriz")
    page.click("#plano-enviar-resp")
    page.wait_for_selector("#painel-root #rank-body tr", timeout=20000)
    assert gh.comentarios == ["ajuste: pode pontuar com esta matriz"]
    assert page.evaluate("PainelSelecao.atual().exportar().top3") == json.loads(FIXTURE.read_text())["top3"]
    assert "github_pat_teste" not in json.dumps(page.evaluate("PainelSelecao.atual().exportar()"))
    assert pagina.erros == []


def test_plano_tenta_de_novo_quando_github_da_500(pagina):
    gh = GitHubFalso(falhas_blob=1)  # o erro "GitHub 500" que aparecia no meio do envio
    page = pagina.page
    _preparar(page, gh)
    page.click("#btn-avaliar")
    page.wait_for_selector("#plano-resp", timeout=20000)
    assert len(gh.arquivos) == 5 and gh.commits == 1 and len(gh.issues) == 1
    assert [e for e in pagina.erros if "status of 500" not in e] == []  # só o 500 simulado, registrado pelo navegador


def test_secao_como_avaliar_recolhe_depois_de_escolher(pagina):
    page = pagina.page
    page.route("https://api.github.com/**", GitHubFalso())
    page.goto(SITE.as_uri())
    assert page.is_visible("#conexao-corpo") and page.is_hidden("#conexao-resumo")
    page.click("#usar-plano-github")
    page.fill("#ia-conta", REPO)
    page.fill("#ia-chave", "github_pat_teste")
    assert page.is_visible("#conexao-corpo")  # não fecha no meio da digitação
    page.check("#ia-lembrar")  # clicar dentro da seção não recolhe
    assert page.is_visible("#conexao-corpo")
    page.click("#v-cargo")  # sair da seção recolhe
    page.wait_for_selector("#conexao-resumo", state="visible")
    assert page.is_hidden("#conexao-corpo")
    assert REPO in page.inner_text("#conexao-escolha")
    assert page.is_visible("#plano-listar")  # "ver meus processos" continua à mão
    page.click("#conexao-trocar")
    assert page.is_visible("#conexao-corpo") and page.is_hidden("#conexao-resumo")
    # com a chave lembrada, a página já abre recolhida
    page.reload()
    assert page.is_hidden("#conexao-corpo") and page.is_visible("#conexao-resumo")
    assert pagina.erros == []


def test_plano_recusa_repositorio_publico(pagina):
    gh = GitHubFalso(privado=False)
    page = pagina.page
    _preparar(page, gh)
    page.click("#btn-avaliar")
    page.wait_for_function("document.querySelector('#msg').innerText.includes('público')", timeout=10000)
    assert gh.arquivos == {} and gh.issues == []  # nada saiu do navegador
    assert pagina.erros == []


def test_acao_preparar(tmp_path):
    from importlib import util
    spec = util.spec_from_file_location("acao", RAIZ / "scripts" / "acao_preparar.py")
    acao = util.module_from_spec(spec)
    spec.loader.exec_module(acao)
    (tmp_path / "entrada" / "20261026101500-ab12").mkdir(parents=True)
    (tmp_path / "entrada" / "20261026101500-ab12" / "vaga.md").write_text("x")
    ev = tmp_path / "ev.json"
    ev.write_text(json.dumps({"issue": {"number": 3, "body": "<!-- triagem-id: 20261026101500-ab12 -->\noi"}}))
    coms = tmp_path / "c.json"
    coms.write_text(json.dumps([
        {"body": "<!-- triagem: perguntas -->\nPosso?", "user": {"type": "Bot"}},
        {"body": "ajuste: pode pontuar", "user": {"type": "User"}},
        {"body": "comentário solto", "user": {"type": "User"}},
    ]))
    assert acao.main(["--evento", str(ev), "--comentarios", str(coms), "--raiz", str(tmp_path)]) == 0
    assert (tmp_path / "work" / "ajustes.md").read_text() == "- pode pontuar"
    # marcador ausente ou id malformado (tentativa de caminho) é recusado
    ev.write_text(json.dumps({"issue": {"number": 3, "body": "<!-- triagem-id: ../../etc -->"}}))
    assert acao.main(["--evento", str(ev), "--comentarios", str(coms), "--raiz", str(tmp_path)]) == 2


def test_workflow_do_repositorio_de_dados():
    wf = (RAIZ / "dados-template" / ".github" / "workflows" / "triagem.yml").read_text(encoding="utf-8")
    assert "claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}" in wf  # plano, não API
    assert "anthropic_api_key" not in wf
    assert ".private" in wf  # recusa rodar em repositório público
    for marca in ("recebido", "perguntas", "pronto", "falhou"):
        assert f"<!-- triagem: {marca} -->" in wf
    assert "git add \"$DESTINO\"" in wf  # só o resultado entra no commit
