"""Painel com Playwright (Chromium): comportamento aprovado do painel de entrevistas."""
import json

from _comum import ranking_processo


def _abrir(w, arq):
    w.page.goto(arq.as_uri())
    w.page.wait_for_selector("#rank-body tr")
    return w.page


def _ordem(page):
    return page.eval_on_selector_all("#rank-body tr[data-rank]", "trs => trs.map(t => t.dataset.rank)")


def test_mudar_peso_recalcula_ranking(pagina, painel_fixture, proc):
    page = _abrir(pagina, painel_fixture)
    assert _ordem(page) == ["juliana", "anderson", "gabriel", "fernanda", "camila"]
    assert page.inner_text('[data-score="juliana"]') == "82,0"
    page.fill("#peso-C4", "0")
    page.fill("#peso-C5", "40")
    pesos = {c["id"]: c["peso"] for c in proc["criterios"]} | {"C4": 0, "C5": 40}
    esperado = [x["id"] for x in ranking_processo(proc, pesos)]
    assert _ordem(page) == esperado
    assert esperado != ["juliana", "anderson", "gabriel", "fernanda", "camila"]
    assert page.is_visible("#top-mudou")  # avisa que o Top 3 mudaria
    assert pagina.erros == []


def test_nao_confirmado_em_obrigatorio_bloqueia(pagina, painel_fixture):
    page = _abrir(pagina, painel_fixture)
    page.click("#tab-juliana")
    assert page.inner_text('[data-block="juliana"]') == ""
    page.click('label:has(#juliana-A1-N)')  # A1 está ligado a C4 (obrigatório)
    bloco = page.inner_text('[data-block="juliana"]')
    assert "bloqueado" in bloco.lower() and "A1" in bloco and "C4" in bloco
    assert page.inner_text('[data-fin="juliana"]') == "Bloq."
    # item desejável não bloqueia
    page.click('label:has(#juliana-A1-C)')
    page.click('label:has(#juliana-A7-N)')  # A7 -> C7 (desejável)
    assert page.inner_text('[data-block="juliana"]') == ""
    page.click('label:has(#juliana-A1-N)')
    page.click("#tab-comp")
    assert "Bloqueado" in page.inner_text("#cmp-body")
    assert pagina.erros == []


def _preencher(page, cid, nota_b=4, status_a="C"):
    page.click(f"#tab-{cid}")
    for inp in page.query_selector_all(f'input[data-a^="{cid}|"][value="{status_a}"]'):
        page.click(f'label:has(#{inp.get_attribute("id")})')
    for inp in page.query_selector_all(f'input[data-b^="{cid}|"][value="{nota_b}"]'):
        page.click(f'label:has(#{inp.get_attribute("id")})')


def test_recomendacao_so_com_tudo_preenchido(pagina, painel_fixture):
    page = _abrir(pagina, painel_fixture)
    page.click("#tab-comp")
    assert page.is_visible("#reco-pendente") and not page.query_selector("#reco-final")
    _preencher(page, "juliana", 5)
    _preencher(page, "anderson", 3)
    _preencher(page, "gabriel", 4)
    # tira uma resposta: continua pendente
    page.click("#tab-gabriel")
    page.click('[data-clear-b="gabriel|B3"]')
    page.click("#tab-comp")
    assert page.is_visible("#reco-pendente") and "Faltam 1" in page.inner_text("#reco-pendente")
    page.click("#tab-gabriel")
    page.click('label:has(#gabriel-B3-4)')
    page.click("#tab-comp")
    reco = page.inner_text("#reco-final")
    assert "Recomendação: Juliana Ferreira Costa" in reco
    assert not page.query_selector("#reco-pendente")
    assert pagina.erros == []


def test_recomendacao_usa_anotacoes(pagina, painel_fixture):
    page = _abrir(pagina, painel_fixture)
    for cid in ("juliana", "anderson", "gabriel"):
        _preencher(page, cid, 4)
    page.click("#tab-juliana")
    page.fill("#juliana-A1-n", "Conduziu as entrevistas com roteiro STAR")
    page.click("#tab-comp")
    assert "Conduziu as entrevistas com roteiro STAR" in page.inner_text("#reco")
    assert pagina.erros == []


def _estado(page):
    s = page.evaluate("PainelSelecao.atual().getState()")
    s.pop("salvoEm", None)
    return s


def test_exportar_e_importar_devolve_o_mesmo_estado(pagina, painel_fixture):
    page = _abrir(pagina, painel_fixture)
    page.fill("#peso-C12", "12")
    _preencher(page, "juliana", 5)
    page.click("#tab-anderson")
    page.click('label:has(#anderson-A2-P)')
    page.fill("#anderson-A2-n", "Volume de 15 vagas/mês; sem roteiro formal")
    page.click('label:has(#anderson-B1-2)')
    page.click("#tab-comp")
    page.fill("#fase-a", "50")
    page.select_option("#dec-cand", "juliana")
    page.fill("#dec-texto", "Melhor validação e aderência.")
    page.wait_for_timeout(400)
    antes = _estado(page)

    page.click("#btn-export")
    exportado = page.input_value("#io-out")  # sem capability downloads: mostra o JSON para copiar
    dados = json.loads(exportado)
    assert dados["schemaVersion"] == "1.0" and dados["respostas"]["decisao"]["cand"] == "juliana"

    # limpar com confirmação dentro da página
    page.click("#btn-reset")
    page.click("#rs-yes")
    assert _estado(page) != antes
    assert _estado(page)["decisao"]["cand"] == ""

    page.click("#btn-import")
    page.fill("#io-in", exportado)
    page.click("#io-apply")
    page.wait_for_selector("#iozone .alertbox.ok")
    assert _estado(page) == antes
    page.click("#tab-anderson")
    assert page.input_value("#anderson-A2-n") == "Volume de 15 vagas/mês; sem roteiro formal"
    assert page.is_checked("#anderson-A2-P")
    assert pagina.erros == []


def test_limpar_pede_confirmacao_na_pagina(pagina, painel_fixture):
    page = _abrir(pagina, painel_fixture)
    _preencher(page, "juliana", 5)
    page.click("#btn-reset")
    page.click("#rs-no")  # cancelar mantém tudo
    assert _estado(page)["resp"]["juliana"]["B"]["B1"]["s"] == 5
    assert pagina.erros == []


def test_sem_erros_no_console_em_todas_as_abas(pagina, painel_fixture):
    page = _abrir(pagina, painel_fixture)
    for aba in ("juliana", "anderson", "gabriel", "comp", "geral"):
        page.click(f"#tab-{aba}")
    page.click("#btn-report")  # relatório cai no campo de copiar quando não há downloads
    assert "<!doctype html>" in page.input_value("#io-out")
    assert pagina.erros == []


def test_400px_sem_rolagem_horizontal(pagina_400, painel_fixture):
    page = _abrir(pagina_400, painel_fixture)
    for aba in ("geral", "juliana", "anderson", "gabriel", "comp"):
        page.click(f"#tab-{aba}")
        page.evaluate("document.querySelectorAll('details').forEach(d=>d.open=true)")
        largura = page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
        assert largura[0] <= largura[1], f"aba {aba}: rolagem horizontal {largura}"
    assert pagina_400.erros == []


def test_template_vazio_nao_quebra(pagina):
    from _comum import achar_core

    pagina.page.goto((achar_core() / "painel-template.html").as_uri())
    assert "template vazio" in pagina.page.inner_text("body")
    assert pagina.erros == []
