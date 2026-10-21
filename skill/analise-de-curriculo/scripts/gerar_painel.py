#!/usr/bin/env python3
"""Injeta um processo.json no template e grava um painel.html autocontido.

Uso:
    gerar_painel.py processo.json [-o painel.html]

Recusa gerar o painel se o JSON for inválido ou se o HTML final contiver dado de contato
ou dado pessoal sensível (LGPD).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _comum import achar_core, carregar, varrer_privacidade  # noqa: E402
from validar import erros_schema  # noqa: E402

MARCA = "/*PROCESSO_JSON*/"


def montar_html(proc: dict, template: str | None = None) -> str:
    if template is None:
        template = (achar_core() / "painel-template.html").read_text(encoding="utf-8")
    if MARCA not in template:
        raise ValueError("template sem o marcador /*PROCESSO_JSON*/")
    dados = json.dumps(proc, ensure_ascii=False)
    # dentro de <script> o JSON não pode fechar a tag nem abrir comentário HTML
    dados = dados.replace("</", "<\\/").replace("<!--", "<\\!--")
    html = template.replace(MARCA, dados)
    titulo = proc["vaga"]["titulo"].replace("<", "").replace(">", "")
    return html.replace("<title>Painel do Processo Seletivo</title>", f"<title>Painel · {titulo}</title>", 1)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("processo")
    ap.add_argument("-o", "--saida", help="arquivo de saída (padrão: painel.html ao lado do processo.json)")
    a = ap.parse_args(argv)
    proc = carregar(a.processo)
    E = erros_schema(proc)
    if E:
        print("ERRO: processo.json inválido; rode validar.py", *E[:10], sep="\n  ")
        return 1
    html = montar_html(proc)
    erros, _ = varrer_privacidade(json.dumps(proc, ensure_ascii=False), afirmativa=bool(proc["vaga"].get("afirmativa")))
    if erros:
        print("ERRO: o painel exporia dados pessoais; corrija o processo.json:", *erros[:10], sep="\n  ")
        return 1
    saida = Path(a.saida) if a.saida else Path(a.processo).resolve().parent / "painel.html"
    saida.write_text(html, encoding="utf-8")
    print(f"Painel gerado: {saida} ({len(html) // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
