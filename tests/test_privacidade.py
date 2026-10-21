"""Privacidade: o painel do caso de referência (porta 1) não expõe contato nem dado pessoal sensível."""
import re

import pytest

from conftest import REFERENCIA_PASTA, resultado_referencia


@pytest.fixture(scope="module")
def painel_ref():
    pasta = resultado_referencia()
    if pasta is None:
        pytest.skip("caso de referência ainda não rodado nesta cópia (exemplos/ fica fora do git): rode /analise-de-curriculo na pasta de referência com --saida exemplos/referencia/_resultado")
    return (pasta / "painel.html").read_text(encoding="utf-8")


def test_sem_email_nem_telefone(painel_ref):
    assert not re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", painel_ref), "e-mail no painel"
    assert not re.search(r"\(?\b\d{2}\)?\s?9\d{4}-\d{4}\b", painel_ref), "telefone no painel"


def test_sem_pcd_nem_deficiencia(painel_ref):
    assert not re.search(r"\bPcD\b", painel_ref, re.I)
    assert "deficiência" not in painel_ref.lower() and "deficiencia" not in painel_ref.lower()


def test_nenhum_contato_real_dos_curriculos(painel_ref, tmp_path):
    from extrair_texto import main as extrair

    extrair([str(REFERENCIA_PASTA), "--saida", str(tmp_path)])
    contatos = set()
    for txt in (tmp_path / "textos").glob("*.txt"):
        t = txt.read_text(encoding="utf-8")
        contatos |= set(re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", t))
        contatos |= set(re.findall(r"\(\d{2}\) \d{4,5}-\d{4}", t))
        contatos |= set(re.findall(r"linkedin\.com/in/\w+", t))
    assert contatos, "a extração deveria achar os contatos dos currículos"
    vazados = [c for c in contatos if c in painel_ref]
    assert vazados == []


def test_sem_motivo_pessoal_de_lacuna(painel_ref):
    assert "cuidados de familiar" not in painel_ref.lower()
