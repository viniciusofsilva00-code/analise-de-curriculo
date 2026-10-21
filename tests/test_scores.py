"""Score da triagem: gabarito do fixture e equivalência Python × JavaScript (implementação única no template)."""
import random

import pytest

from _comum import ranking_processo

PESOS = {"C1": 10, "C2": 15, "C3": 10, "C4": 20, "C5": 15, "C6": 5, "C7": 4, "C8": 4, "C9": 4, "C10": 3, "C11": 2, "C12": 8}
GABARITO = [("juliana", 82.0), ("anderson", 69.6), ("gabriel", 64.8), ("fernanda", 62.6), ("camila", 59.8)]


def test_pesos_do_fixture(proc):
    assert {c["id"]: c["peso"] for c in proc["criterios"]} == PESOS


def test_ranking_gabarito_python(proc):
    rk = ranking_processo(proc)
    assert [(x["id"], round(x["score"], 1)) for x in rk] == GABARITO
    assert proc["top3"] == ["juliana", "anderson", "gabriel"]


def _js_ranking(page, proc, pesos):
    return page.evaluate(
        """([p, pesos]) => PainelSelecao.calc.ranking(p.candidatos.filter(c=>c.status==="aprovado"), p.criterios, pesos)""",
        [proc, pesos],
    )


def test_python_e_javascript_dao_o_mesmo_resultado(pagina, painel_fixture, proc):
    pg = pagina.page
    pg.goto(painel_fixture.as_uri())
    js = _js_ranking(pg, proc, None)
    assert [(x["id"], round(x["score"], 1)) for x in js] == GABARITO
    rnd = random.Random(42)
    for _ in range(25):
        pesos = {k: rnd.choice([0, 1, 2, 3, 5, 8, 10, 15, 20, 30]) for k in PESOS}
        if not any(pesos.values()):
            continue
        py = ranking_processo(proc, pesos)
        js = _js_ranking(pg, proc, pesos)
        assert [x["id"] for x in py] == [x["id"] for x in js], pesos
        for a, b in zip(py, js):
            assert a["score"] == pytest.approx(b["score"], abs=1e-9)
            assert a["obr"] == b["obr"]
    assert pagina.erros == []
