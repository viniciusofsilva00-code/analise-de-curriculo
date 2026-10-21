"""Funções comuns aos scripts da skill.

O cálculo de score tem UMA implementação de referência: PainelSelecao.calc, em JavaScript,
dentro de core/painel-template.html. As funções abaixo espelham a mesma fórmula só para o
resumo no terminal e para a validação; tests/test_scores.py compara os dois resultados.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

AQUI = Path(__file__).resolve().parent


def achar_core() -> Path:
    """Localiza a pasta core/ (regras, schema e template) a partir da skill."""
    candidatos = [AQUI.parent / "core"] + [p / "core" for p in AQUI.parents]
    for c in candidatos:
        if (c / "processo.schema.json").is_file() and (c / "painel-template.html").is_file():
            return c
    raise FileNotFoundError("pasta core/ não encontrada (esperada em skill/analise-de-curriculo/core ou na raiz do projeto)")


def carregar(caminho: str | Path) -> dict:
    return json.loads(Path(caminho).read_text(encoding="utf-8"))


def gravar(caminho: str | Path, dados: dict) -> None:
    Path(caminho).write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- score (espelho do JS)

def triagem(notas: dict, criterios: list, pesos: dict | None = None) -> float:
    soma = tot = 0.0
    for c in criterios:
        p = float((pesos or {}).get(c["id"], c["peso"]) or 0)
        n = float(notas.get(c["id"], {}).get("nota", 0) or 0)
        tot += p
        soma += (n / 5) * p
    return soma / tot * 100 if tot else 0.0


def obrig_pts(notas: dict, criterios: list) -> int:
    return sum(int(notas.get(c["id"], {}).get("nota", 0) or 0) for c in criterios if c["tipo"] == "O")


def ranking(candidatos: list, criterios: list, pesos: dict | None = None) -> list[dict]:
    rk = [
        {"id": c["id"], "score": triagem(c.get("notas", {}), criterios, pesos),
         "obr": obrig_pts(c.get("notas", {}), criterios), "rec": int(c.get("ordemRecencia") or 999)}
        for c in candidatos
    ]
    # score desc, obrigatórios desc, ordemRecencia asc — mesma ordem do JS
    rk.sort(key=lambda x: (-x["score"], -x["obr"], x["rec"]))
    return rk


def fmt(v: float) -> str:
    return f"{v:.1f}".replace(".", ",")


def avisos_ranking(rk: list[dict], nomes: dict) -> list[str]:
    out = []
    if len(rk) >= 4:
        a, b = rk[2], rk[3]
        if a["score"] - b["score"] < 3:
            out.append(f"Margem do 3º ({nomes[a['id']]}, {fmt(a['score'])}) para o 4º ({nomes[b['id']]}, {fmt(b['score'])}) "
                       f"é de {fmt(a['score'] - b['score'])} ponto(s), menor que 3.")
        if a["obr"] == b["obr"]:
            out.append(f"3º ({nomes[a['id']]}) e 4º ({nomes[b['id']]}) empatam na soma dos obrigatórios ({a['obr']}).")
    if len(rk) < 3:
        out.append(f"Só {len(rk)} candidato(s) passaram no filtro. A lista não foi completada com quem não atende.")
    return out


def ranking_processo(proc: dict, pesos: dict | None = None) -> list[dict]:
    aprov = [c for c in proc["candidatos"] if c["status"] == "aprovado"]
    return ranking(aprov, proc["criterios"], pesos)


# ---------------------------------------------------------------- privacidade (LGPD)

RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
RE_FONE = re.compile(r"\(?\b\d{2}\)?\s?9\d{4}-?\d{4}\b|\(\d{2}\)\s?\d{4}-\d{4}\b|\+55\s?\d{2}")
RE_CPF = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")
RE_LINK = re.compile(r"linkedin\.com/in/|github\.com/|instagram\.com/", re.I)

# Termos que nunca podem aparecer (exceto vaga afirmativa, para os marcados com True)
TERMOS_PROIBIDOS = [
    (re.compile(r"\bPcD\b", re.I), "PcD", True),
    (re.compile(r"defici[eê]n", re.I), "deficiência", True),
    (re.compile(r"estado civil", re.I), "estado civil", False),
    (re.compile(r"data de nascimento|nascid[oa] em", re.I), "data de nascimento", False),
    (re.compile(r"\b\d{2} anos de idade\b|\bidade\b", re.I), "idade", False),
    (re.compile(r"religi", re.I), "religião", False),
    (re.compile(r"\bra[cç]a\b|\betnia\b", re.I), "raça/etnia", True),
    (re.compile(r"gestante|gr[aá]vida|gravidez", re.I), "gestação", False),
    (re.compile(r"cuidados de familiar|doen[cç]a|tratamento m[eé]dico", re.I), "motivo pessoal/saúde", False),
]
# Termos que só geram aviso (podem ser nome de empresa ou atividade profissional)
TERMOS_ATENCAO = [
    (re.compile(r"\bfilhos?\b", re.I), "filhos"),
    (re.compile(r"\bcasad[oa]\b|\bsolteir[oa]\b|\bdivorciad[oa]\b", re.I), "estado civil"),
    (re.compile(r"sa[uú]de", re.I), "saúde"),
    (re.compile(r"g[eê]nero", re.I), "gênero"),
]


def varrer_privacidade(texto: str, afirmativa: bool = False) -> tuple[list[str], list[str]]:
    """Retorna (erros, avisos) encontrados num texto (JSON serializado ou HTML)."""
    erros, avisos = [], []
    for rx, nome in ((RE_EMAIL, "e-mail"), (RE_FONE, "telefone"), (RE_CPF, "CPF"), (RE_LINK, "link pessoal")):
        for m in rx.finditer(texto):
            erros.append(f"dado de contato/documento ({nome}): “{m.group(0)}”")
    for rx, nome, liberado_afirmativa in TERMOS_PROIBIDOS:
        if afirmativa and liberado_afirmativa:
            continue
        for m in rx.finditer(texto):
            ini = max(0, m.start() - 40)
            erros.append(f"dado pessoal sensível ({nome}): “…{texto[ini:m.end() + 40]}…”")
    for rx, nome in TERMOS_ATENCAO:
        for m in rx.finditer(texto):
            ini = max(0, m.start() - 40)
            avisos.append(f"confira se é dado pessoal ({nome}): “…{texto[ini:m.end() + 40]}…”")
    return erros, avisos


# ---------------------------------------------------------------- trechos literais

def normalizar(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"&(\w{1,3});", r"&\1", s)  # artefato "R&S;" de alguns PDFs
    s = s.replace("’", "'").replace("“", '"').replace("”", '"')
    s = re.sub(r"[–—−‐-]", "-", s)
    s = re.sub(r"[■•●▪]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip().lower()


SEP_FRAG = re.compile(r"\s*(?:…|\.\.\.|\s·\s|\s→\s|\[…\]|\[\.\.\.\])\s*")


def trecho_no_texto(trecho: str, texto_norm: str) -> list[str]:
    """Devolve os fragmentos do trecho que NÃO aparecem literalmente no texto."""
    faltam = []
    for frag in SEP_FRAG.split(trecho):
        f = normalizar(frag).strip(" .;,:\"'()")
        if len(f) < 4:
            continue
        if f not in texto_norm:
            faltam.append(frag.strip())
    return faltam


def slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
