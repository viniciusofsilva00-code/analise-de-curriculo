#!/usr/bin/env python3
"""Valida um processo.json contra o schema e contra as regras checáveis de core/regras-avaliacao.md.

Uso:
    validar.py processo.json [--extracao <dir>/extracao.json]

Com --extracao, confere também se cada trecho citado aparece literalmente no currículo.
Saída: lista de ERROS (bloqueiam) e AVISOS (para revisar). Código de saída 0 = válido, 1 = inválido.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _comum import (achar_core, avisos_ranking, carregar, normalizar, ranking_processo,  # noqa: E402
                    trecho_no_texto, varrer_privacidade)


def erros_schema(proc: dict) -> list[str]:
    from jsonschema import Draft202012Validator

    schema = json.loads((achar_core() / "processo.schema.json").read_text(encoding="utf-8"))
    v = Draft202012Validator(schema)
    out = []
    for e in sorted(v.iter_errors(proc), key=lambda e: list(e.absolute_path)):
        caminho = "/".join(str(p) for p in e.absolute_path) or "(raiz)"
        out.append(f"schema: {caminho}: {e.message}")
    return out


def checar_regras(proc: dict, extracao: dict | None, base_extracao: Path | None) -> tuple[list[str], list[str]]:
    E, W = [], []
    crit = proc["criterios"]
    ids_crit = [c["id"] for c in crit]
    obrig = {c["id"] for c in crit if c["tipo"] == "O"}
    if len(set(ids_crit)) != len(ids_crit):
        E.append("critérios com ID repetido")
    if not obrig:
        W.append("nenhum critério obrigatório: o filtro eliminatório não terá efeito")
    cands = proc["candidatos"]
    byid = {c["id"]: c for c in cands}
    if len(byid) != len(cands):
        E.append("candidatos com ID repetido")

    # notas
    for c in cands:
        notas = c.get("notas")
        if c["status"] in ("eliminado", "limitrofe"):
            rf = c.get("requisitosFaltantes", [])
            if not rf:
                E.append(f"{c['id']}: {c['status']} sem o requisito que faltou (requisitosFaltantes)")
            for r in rf:
                if r not in obrig:
                    E.append(f"{c['id']}: requisitosFaltantes cita {r}, que não é obrigatório")
        if c["status"] == "nao_avaliado":
            if notas:
                E.append(f"{c['id']}: não avaliado não pode ter notas (não estime o conteúdo)")
            continue
        if notas is None:
            continue
        faltam = [i for i in ids_crit if i not in notas]
        sobram = [i for i in notas if i not in ids_crit]
        if faltam:
            E.append(f"{c['id']}: sem nota para {', '.join(faltam)}")
        if sobram:
            E.append(f"{c['id']}: nota para critério inexistente {', '.join(sobram)}")
        for cid, n in notas.items():
            if n["natureza"] == "declarado" and n["nota"] > 3:
                E.append(f"{c['id']}/{cid}: habilidade só declarada recebeu {n['nota']}; o máximo é 3")
            if n["natureza"] == "ausente" and n["nota"] != 0:
                E.append(f"{c['id']}/{cid}: natureza 'ausente' exige nota 0")
            if n["nota"] > 0 and normalizar(n["trecho"]) in ("sem mencao", "sem menção"):
                E.append(f"{c['id']}/{cid}: nota {n['nota']} sem trecho que a sustente")

    # recência única entre os que disputam
    disputa = [c for c in cands if c["status"] in ("aprovado", "limitrofe")]
    recs = [c.get("ordemRecencia") for c in disputa]
    if len(set(recs)) != len(recs):
        E.append("ordemRecencia repetida entre aprovados/limítrofes (é critério de desempate: use 1, 2, 3…)")

    # top 3 calculado em código
    rk = ranking_processo(proc)
    esperado = [x["id"] for x in rk[:3]]
    if proc["top3"] != esperado:
        E.append(f"top3 {proc['top3']} difere do ranking calculado {esperado} (rode score.py --gravar)")
    for a in avisos_ranking(rk, {c["id"]: c["nome"] for c in cands}):
        if a not in proc.get("avisos", []):
            W.append(f"aviso de ranking não registrado em 'avisos': {a}")

    # Top 3: fortes, riscos, perguntas
    pq = proc["perguntas"]
    comuns = pq["comuns"]
    if proc["top3"]:
        ids_b = [b["id"] for b in comuns]
        if ids_b != ["B1", "B2", "B3", "B4", "B5", "B6"]:
            E.append(f"Bloco B: são 6 perguntas comuns B1…B6 (encontrado: {ids_b})")
    for b in comuns:
        if b["crit"] not in ids_crit:
            E.append(f"Bloco B {b['id']}: critério {b['crit']} inexistente")
    if set(pq["porCandidato"]) != set(proc["top3"]):
        E.append(f"perguntas.porCandidato deve ter exatamente o Top 3 {proc['top3']} (tem {sorted(pq['porCandidato'])})")
    for cid in proc["top3"]:
        c = byid.get(cid)
        if not c:
            E.append(f"top3 cita candidato inexistente: {cid}")
            continue
        if c["status"] != "aprovado":
            E.append(f"{cid} está no Top 3 sem ter sido aprovado no filtro")
        if len(c.get("fortes", [])) != 3:
            E.append(f"{cid}: são 3 pontos fortes (tem {len(c.get('fortes', []))})")
        if len(c.get("riscos", [])) < 2:
            E.append(f"{cid}: são pelo menos 2 riscos (tem {len(c.get('riscos', []))})")
        p = pq["porCandidato"].get(cid)
        if not p:
            continue
        nA = len(p["A"])
        if not 7 <= nA <= 8:
            E.append(f"{cid}: Bloco A tem {nA} perguntas (são 7 a 8)")
        ids_a = [q["id"] for q in p["A"]]
        if len(set(ids_a)) != len(ids_a):
            E.append(f"{cid}: Bloco A com ID repetido")
        for q in p["A"]:
            if q["crit"] not in ids_crit:
                E.append(f"{cid}/{q['id']}: critério {q['crit']} inexistente")
        if p["B7"]["id"] != "B7":
            E.append(f"{cid}: a pergunta específica do Bloco B deve ter id B7")
        if p["B7"]["crit"] not in ids_crit:
            E.append(f"{cid}/B7: critério {p['B7']['crit']} inexistente")
        if len(c.get("inconsistencias", [])) > nA:
            W.append(f"{cid}: há mais inconsistências que perguntas no Bloco A; confira se todas viraram pergunta")

    # privacidade
    afirm = bool(proc["vaga"].get("afirmativa"))
    texto = json.dumps({k: v for k, v in proc.items() if k != "respostas"}, ensure_ascii=False)
    e2, w2 = varrer_privacidade(texto, afirmativa=afirm)
    E += [f"privacidade: {x}" for x in e2]
    W += [f"privacidade: {x}" for x in w2]
    if not proc["vaga"]["exigePresenca"]:
        for c in cands:
            if c.get("cidade"):
                E.append(f"{c['id']}: cidade só entra quando a vaga exige presença física")

    # trechos literais
    if extracao is not None:
        textos = {}
        for item in extracao.get("curriculos", []):
            if item.get("texto_arquivo"):
                textos[item["arquivo"]] = normalizar((base_extracao / item["texto_arquivo"]).read_text(encoding="utf-8"))
        for c in cands:
            if c["status"] == "nao_avaliado":
                continue
            tn = textos.get(c["arquivo"])
            if tn is None:
                E.append(f"{c['id']}: arquivo '{c['arquivo']}' não está na extração")
                continue
            citacoes = []
            for cid, n in (c.get("notas") or {}).items():
                if n["natureza"] != "ausente":
                    citacoes.append((f"nota {cid}", n["trecho"]))
            citacoes += [(f"forte {i+1}", f["trecho"]) for i, f in enumerate(c.get("fortes", []))]
            citacoes += [(f"risco {i+1}", f["trecho"]) for i, f in enumerate(c.get("riscos", []))]
            citacoes += [(f"Bloco A {q['id']}", q["trecho"]) for q in pq["porCandidato"].get(c["id"], {}).get("A", [])]
            for onde, tr in citacoes:
                faltam = trecho_no_texto(tr, tn)
                if faltam:
                    E.append(f"{c['id']}/{onde}: trecho não encontrado literalmente no currículo: “{' | '.join(faltam)}”")
    return E, W


def validar(proc: dict, extracao_path: str | Path | None = None) -> tuple[list[str], list[str]]:
    E = erros_schema(proc)
    if E:
        return E, []  # regras dependem da estrutura
    extracao = base = None
    if extracao_path:
        extracao = carregar(extracao_path)
        base = Path(extracao_path).resolve().parent
    E2, W = checar_regras(proc, extracao, base)
    return E + E2, W


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("processo")
    ap.add_argument("--extracao", help="extracao.json gerado por extrair_texto.py (confere trechos literais)")
    a = ap.parse_args(argv)
    try:
        proc = carregar(a.processo)
    except json.JSONDecodeError as e:
        print(f"INVÁLIDO: o arquivo não é JSON ({e})")
        return 1
    E, W = validar(proc, a.extracao)
    for w in W:
        print(f"AVISO: {w}")
    if E:
        print(f"INVÁLIDO: {len(E)} erro(s)")
        for e in E:
            print(f"  ERRO: {e}")
        return 1
    print("VÁLIDO" + (f" ({len(W)} aviso(s))" if W else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
