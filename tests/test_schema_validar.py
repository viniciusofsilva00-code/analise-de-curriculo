"""Schema do processo.json e regras checáveis do validar.py."""
import copy
import json

from conftest import FIXTURE, REFERENCIA_PASTA
from validar import erros_schema, validar


def test_schema_aceita_processo_completo(proc):
    assert erros_schema(proc) == []
    erros, _ = validar(proc)
    assert erros == []


def test_schema_rejeita_nota_sem_trecho(proc):
    p = copy.deepcopy(proc)
    del p["candidatos"][0]["notas"]["C1"]["trecho"]
    assert any("trecho" in e for e in erros_schema(p))


def test_schema_rejeita_trecho_vazio(proc):
    p = copy.deepcopy(proc)
    p["candidatos"][0]["notas"]["C2"]["trecho"] = "   "
    assert erros_schema(p)


def test_schema_rejeita_nota_fora_de_0_a_5(proc):
    for valor in (6, -1, 3.5):
        p = copy.deepcopy(proc)
        p["candidatos"][1]["notas"]["C3"]["nota"] = valor
        assert erros_schema(p), f"nota {valor} deveria ser rejeitada"


def test_regra_declarado_no_maximo_3(proc):
    p = copy.deepcopy(proc)
    n = p["candidatos"][0]["notas"]["C8"]
    assert n["natureza"] == "declarado"
    n["nota"] = 4
    erros, _ = validar(p)
    assert any("máximo é 3" in e for e in erros)


def test_regra_top3_vem_do_ranking(proc):
    p = copy.deepcopy(proc)
    p["top3"] = ["juliana", "gabriel", "anderson"]
    erros, _ = validar(p)
    assert any("difere do ranking" in e for e in erros)


def test_regra_eliminado_registra_requisito(proc):
    p = copy.deepcopy(proc)
    marcos = next(c for c in p["candidatos"] if c["id"] == "marcos")
    marcos["requisitosFaltantes"] = []
    erros, _ = validar(p)
    assert any("requisito que faltou" in e for e in erros)


def test_regra_privacidade_bloqueia_contato_e_dado_sensivel(proc):
    for texto in ("fulana.teste@exemplo.com", "(11) 91234-5678", "Candidato PcD", "deficiência auditiva"):
        p = copy.deepcopy(proc)
        p["candidatos"][0]["fortes"][0]["texto"] = texto
        erros, _ = validar(p)
        assert any("privacidade" in e for e in erros), texto


def test_regra_afirmativa_libera_criterio_afirmativo(proc):
    p = copy.deepcopy(proc)
    p["vaga"]["afirmativa"] = "Vaga afirmativa para pessoas com deficiência"
    erros, _ = validar(p)
    assert not any("privacidade" in e for e in erros)


def test_regra_cidade_so_com_presenca(proc):
    p = copy.deepcopy(proc)
    p["vaga"]["exigePresenca"] = False
    erros, _ = validar(p)
    assert any("cidade só entra" in e for e in erros)


def test_regra_quantidade_de_perguntas(proc):
    p = copy.deepcopy(proc)
    p["perguntas"]["porCandidato"]["gabriel"]["A"] = p["perguntas"]["porCandidato"]["gabriel"]["A"][:5]
    p["perguntas"]["comuns"] = p["perguntas"]["comuns"][:5]
    erros, _ = validar(p)
    assert any("Bloco A tem 5" in e for e in erros)
    assert any("6 perguntas comuns" in e for e in erros)


def test_trecho_literal_confere_com_curriculo(tmp_path):
    """Com a extração, um trecho inventado é recusado e um literal passa."""
    from extrair_texto import main as extrair

    assert extrair([str(REFERENCIA_PASTA), "--saida", str(tmp_path)]) == 0
    p = json.loads(FIXTURE.read_text(encoding="utf-8"))
    ju = next(c for c in p["candidatos"] if c["id"] == "juliana")
    # isola um candidato com trechos conhecidos
    p["candidatos"] = [ju]
    p["top3"] = ["juliana"]
    p["perguntas"]["porCandidato"] = {"juliana": p["perguntas"]["porCandidato"]["juliana"]}
    ju["notas"] = {k: {"nota": 0, "trecho": "Sem menção", "natureza": "ausente"} for k in ju["notas"]}
    ju["notas"]["C1"] = {"nota": 5, "trecho": "Bacharelado em Psicologia … Universidade Mackenzie — São Paulo — 2018", "natureza": "escrito"}
    ju["notas"]["C4"] = {"nota": 4, "trecho": "Coordenação de 40+ processos seletivos/ano (analista a gerência)", "natureza": "escrito"}
    ju["fortes"] = [{"texto": "x", "trecho": "Implantação de pesquisa de clima com 87% de adesão"}] * 3
    ju["riscos"] = [{"texto": "y", "trecho": "Analista de RH Sênior"}] * 2
    for q in p["perguntas"]["porCandidato"]["juliana"]["A"]:
        q["trecho"] = "Apoio em treinamentos e aplicação de LNT"
    erros, _ = validar(p, tmp_path / "extracao.json")
    assert [e for e in erros if "trecho" in e] == []
    ju["notas"]["C4"]["trecho"] = "Conduziu 200 entrevistas por competências"
    erros, _ = validar(p, tmp_path / "extracao.json")
    assert any("C4" in e and "não encontrado literalmente" in e for e in erros)
