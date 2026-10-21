#!/usr/bin/env python3
"""Gera o triagem.md (e imprime o mesmo resumo) a partir de um processo.json.

Uso:
    resumo_triagem.py processo.json [-o triagem.md]

Conteúdo: tabela de todos os candidatos (posição, score, status e motivo em uma linha) e,
para cada um do Top 3, 3 pontos fortes com evidência, 2 riscos e as inconsistências a validar.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _comum import carregar, fmt, ranking_processo  # noqa: E402

STATUS = {"aprovado": "Aprovado", "eliminado": "Eliminado", "limitrofe": "Eliminado (limítrofe)", "nao_avaliado": "Não avaliado"}


def uma_linha(s: str) -> str:
    return " ".join(str(s).split()).replace("|", "/")


def montar(proc: dict) -> str:
    v = proc["vaga"]
    rk = ranking_processo(proc)
    byid = {c["id"]: c for c in proc["candidatos"]}
    top3 = proc["top3"]
    crit = {c["id"]: c["nome"] for c in proc["criterios"]}
    L = [f"# Triagem — {v['titulo']}", "",
         f"Data: {v['data']} · Candidatos: {len(proc['candidatos'])} · Aprovados no filtro: {len(rk)} · Top {len(top3)}", ""]
    L += ["| Pos. | Candidato | Score | Status | Motivo |", "|---:|---|---:|---|---|"]
    for i, x in enumerate(rk, 1):
        c = byid[x["id"]]
        st = f"Top {len(top3)}" if x["id"] in top3 else "Reserva"
        motivo = f"obrigatórios {x['obr']}/{sum(1 for k in proc['criterios'] if k['tipo'] == 'O') * 5}"
        L.append(f"| {i} | {c['nome']} | {fmt(x['score'])} | Aprovado · {st} | {motivo} |")
    for c in proc["candidatos"]:
        if c["status"] == "aprovado":
            continue
        falt = ", ".join(c.get("requisitosFaltantes", []))
        motivo = (f"Faltou {falt}: " if falt else "") + uma_linha(c.get("motivo", ""))
        L.append(f"| — | {c['nome']} | — | {STATUS[c['status']]} | {motivo} |")
    if proc.get("avisos"):
        L += ["", *[f"> Aviso: {a}" for a in proc["avisos"]]]
    lim = [c for c in proc["candidatos"] if c["status"] == "limitrofe"]
    if lim:
        L += ["", "**Limítrofes (decisão sua):**"]
        L += [f"- {c['nome']}: {uma_linha(c.get('criterioInclusao', ''))}" for c in lim]
    for cid in top3:
        c = byid[cid]
        x = next(r for r in rk if r["id"] == cid)
        L += ["", f"## {c['nome']} — {fmt(x['score'])}", "", "**Pontos fortes**"]
        L += [f"- {f['texto']} — “{f['trecho']}”" for f in c.get("fortes", [])[:3]]
        L += ["", "**Riscos**"]
        L += [f"- {r['texto']}{' (inferência)' if r.get('inferencia') else ''} — “{r['trecho']}”" for r in c.get("riscos", [])[:2]]
        L += ["", "**Inconsistências a validar**"]
        L += [f"- {i['texto']}" for i in c.get("inconsistencias", [])] or ["- Nenhuma."]
    L += ["", "Critérios: " + "; ".join(f"{k} {n}" for k, n in crit.items()), ""]
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("processo")
    ap.add_argument("-o", "--saida")
    a = ap.parse_args(argv)
    proc = carregar(a.processo)
    md = montar(proc)
    saida = Path(a.saida) if a.saida else Path(a.processo).resolve().parent / "triagem.md"
    saida.write_text(md, encoding="utf-8")
    print(md)
    print(f"\n(gravado em {saida})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
