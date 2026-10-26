#!/usr/bin/env python3
"""Prepara um pedido de triagem dentro do GitHub Actions (repositório de dados privado).

Lê o evento da issue em $GITHUB_EVENT_PATH (nunca interpola título/corpo no shell), acha o
marcador do pedido, confere a pasta entrada/<id>/ e junta os comentários "ajuste:" em work/ajustes.md.

Uso na Action:   python sistema/scripts/acao_preparar.py
Uso local:       python scripts/acao_preparar.py --evento evento.json [--comentarios c.json] [--raiz .]
Saídas ($GITHUB_OUTPUT): id, entrada, destino.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

RE_ID = re.compile(r"<!--\s*triagem-id:\s*([0-9]{14}-[a-z0-9]{4})\s*-->")


def achar_id(corpo: str) -> str | None:
    m = RE_ID.search(corpo or "")
    return m.group(1) if m else None


def ajustes(comentarios: list[dict]) -> list[str]:
    """Comentários humanos que começam com 'ajuste:' (os do bot ficam de fora)."""
    out = []
    for c in comentarios:
        corpo = (c.get("body") or "").strip()
        if (c.get("user") or {}).get("type") == "Bot" or "<!-- triagem:" in corpo:
            continue
        if corpo.lower().startswith("ajuste:"):
            out.append(corpo[len("ajuste:"):].strip())
    return out


def buscar_comentarios(repo: str, numero: int, token: str) -> list[dict]:
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/issues/{numero}/comments?per_page=100",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--evento", default=os.environ.get("GITHUB_EVENT_PATH"))
    ap.add_argument("--comentarios", help="JSON com os comentários (teste local)")
    ap.add_argument("--raiz", default=".")
    a = ap.parse_args(argv)
    raiz = Path(a.raiz)
    evento = json.loads(Path(a.evento).read_text(encoding="utf-8"))
    issue = evento["issue"]
    pid = achar_id(issue.get("body", ""))
    if not pid:
        print("ERRO: a issue não tem o marcador <!-- triagem-id: ... --> (pedido feito fora do site?)", file=sys.stderr)
        return 2
    entrada = raiz / "entrada" / pid
    if not entrada.is_dir() or not any(entrada.iterdir()):
        print(f"ERRO: pasta {entrada} vazia ou inexistente", file=sys.stderr)
        return 2
    if a.comentarios:
        coms = json.loads(Path(a.comentarios).read_text(encoding="utf-8"))
    else:
        coms = buscar_comentarios(os.environ["GITHUB_REPOSITORY"], issue["number"], os.environ["GITHUB_TOKEN"])
    work = raiz / "work"
    work.mkdir(exist_ok=True)
    adj = ajustes(coms)
    (work / "ajustes.md").write_text(
        "\n\n".join(f"- {x}" for x in adj) if adj else "", encoding="utf-8")
    saidas = {"id": pid, "entrada": f"entrada/{pid}", "destino": f"resultados/{pid}"}
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            for k, v in saidas.items():
                f.write(f"{k}={v}\n")
    print(json.dumps({**saidas, "ajustes": len(adj)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
