#!/usr/bin/env python3
"""Calcula o ranking da triagem, o Top 3 e os avisos de fronteira de um processo.json.

Uso:
    score.py processo.json            # mostra o ranking
    score.py processo.json --gravar   # grava top3 e avisos no próprio processo.json

A fórmula espelha PainelSelecao.calc (JavaScript, em core/painel-template.html);
tests/test_scores.py garante que os dois dão o mesmo resultado.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _comum import avisos_ranking, carregar, fmt, gravar, ranking_processo  # noqa: E402


def calcular(proc: dict) -> tuple[list[dict], list[str], list[str]]:
    rk = ranking_processo(proc)
    nomes = {c["id"]: c["nome"] for c in proc["candidatos"]}
    return rk, [x["id"] for x in rk[:3]], avisos_ranking(rk, nomes)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("processo")
    ap.add_argument("--gravar", action="store_true", help="grava top3 e avisos no processo.json")
    a = ap.parse_args(argv)
    proc = carregar(a.processo)
    rk, top3, avisos = calcular(proc)
    nomes = {c["id"]: c["nome"] for c in proc["candidatos"]}
    nobr = sum(1 for c in proc["criterios"] if c["tipo"] == "O") * 5
    print("Pos  Score  Obrig.  Candidato")
    for i, x in enumerate(rk, 1):
        print(f"{i:>3}  {fmt(x['score']):>5}  {x['obr']:>2}/{nobr}   {nomes[x['id']]}{'  [Top 3]' if x['id'] in top3 else ''}")
    for c in proc["candidatos"]:
        if c["status"] != "aprovado":
            print(f"  —      —      —    {c['nome']}  [{c['status']}]")
    for av in avisos:
        print(f"AVISO: {av}")
    if a.gravar:
        proc["top3"] = top3
        manuais = [x for x in proc.get("avisos", []) if not x.startswith(("Margem do 3º", "3º (", "Só "))]
        proc["avisos"] = avisos + manuais
        gravar(a.processo, proc)
        print(f"Gravado: top3 = {top3}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
