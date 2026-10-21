#!/usr/bin/env python3
"""Monta app/analise-curriculos-app.html a partir de app/src/app-fonte.html e do núcleo (core/).

Embute, para não editar à mão em dois lugares:
- core/regras-avaliacao.md        -> const REGRAS (texto usado nos prompts do sample)
- core/painel-template.html       -> CSS e motor do painel (renderização) + template inteiro (botão "Baixar painel.html")

Uso:  python scripts/build_app.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
FONTE = RAIZ / "app" / "src" / "app-fonte.html"
SAIDA = RAIZ / "app" / "analise-curriculos-app.html"
SITE = RAIZ / "docs" / "index.html"  # GitHub Pages (main, pasta /docs): mesma página com o esqueleto HTML
ESQUELETO = ('<!doctype html>\n<html lang="pt-BR">\n<head>\n<meta charset="utf-8">\n'
             '<meta name="viewport" content="width=device-width,initial-scale=1">\n</head>\n<body>\n{}\n</body>\n</html>\n')
REGRAS = RAIZ / "core" / "regras-avaliacao.md"
TEMPLATE = RAIZ / "core" / "painel-template.html"
CDN_OK = ("https://cdnjs.cloudflare.com/", "https://fonts.googleapis.com", "https://fonts.gstatic.com")


def js_str(texto: str) -> str:
    """String JS segura dentro de <script> (não fecha a tag nem abre comentário HTML)."""
    return json.dumps(texto, ensure_ascii=False).replace("</", "<\\/").replace("<!--", "<\\!--")


def entre(texto: str, ini: str, fim: str) -> str:
    a, b = texto.index(ini) + len(ini), texto.index(fim)
    return texto[a:b].strip()


def build() -> Path:
    fonte = FONTE.read_text(encoding="utf-8")
    template = TEMPLATE.read_text(encoding="utf-8")
    css = entre(template, "<!-- PAINEL:CSS:INICIO -->", "<!-- PAINEL:CSS:FIM -->")
    engine = entre(template, "<!-- PAINEL:ENGINE:INICIO -->", "<!-- PAINEL:ENGINE:FIM -->")
    regras = REGRAS.read_text(encoding="utf-8")

    for marca in ("<!--PAINEL_CSS-->", "<!--PAINEL_ENGINE-->", "/*REGRAS_MD*/\"\"", "/*PAINEL_TEMPLATE*/\"\""):
        if fonte.count(marca) != 1:
            raise SystemExit(f"marcador {marca!r} deve aparecer uma vez em {FONTE}")
    out = (fonte.replace("<!--PAINEL_CSS-->", css)
                .replace("<!--PAINEL_ENGINE-->", engine)
                .replace("/*REGRAS_MD*/\"\"", js_str(regras))
                .replace("/*PAINEL_TEMPLATE*/\"\"", js_str(template)))

    # contrato da página publicada
    inicio = out.lstrip()[:200].lower()
    if not inicio.startswith("<title>"):
        raise SystemExit("o app deve começar com <title>")
    for proibido in ("<!doctype", "<html", "<head", "<body"):
        # só conta fora dos <script>: o template embutido e o relatório têm doctype, mas como string JS
        fora_js = re.sub(r"<script\b[^>]*>.*?</script>", "", out, flags=re.S | re.I)
        if re.search(re.escape(proibido) + r"\b", fora_js, re.I):  # \b: <header não conta como <head
            raise SystemExit(f"o app não pode conter {proibido} (a publicação envolve a página num esqueleto)")
    for url in re.findall(r'(?:src|href)="(https?://[^"]+)"', out):
        if not url.startswith(CDN_OK):
            raise SystemExit(f"recurso externo fora da lista permitida: {url}")
        if "cdnjs" in url and not re.search(r"/\d+\.\d+\.\d+/", url):
            raise SystemExit(f"script do cdnjs sem versão fixa: {url}")

    SAIDA.write_text(out, encoding="utf-8")
    SITE.parent.mkdir(exist_ok=True)
    SITE.write_text(ESQUELETO.format(out), encoding="utf-8")
    (SITE.parent / ".nojekyll").write_text("", encoding="utf-8")  # serve o HTML como está, sem Jekyll
    return SAIDA


if __name__ == "__main__":
    p = build()
    print(f"App gerado: {p.relative_to(RAIZ)} ({p.stat().st_size // 1024} KB) + {SITE.relative_to(RAIZ)} (GitHub Pages)")
    sys.exit(0)
