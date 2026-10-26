---
name: analise-de-curriculo
description: Triagem de currículos e geração do painel de processo seletivo a partir de uma pasta de currículos e de uma vaga. Use quando eu pedir para analisar, triar ou selecionar currículos.
argument-hint: <pasta> [--saida <dir>] [vaga em texto livre]
---

# /analise-de-curriculo

Uso: `/analise-de-curriculo <pasta> [--saida <dir>] [vaga em texto livre]`

`BASE` = o diretório desta skill (informado como "Base directory for this skill"). Todos os scripts rodam com `BASE/scripts/rodar.sh <script>.py …`, que usa o ambiente virtual do projeto.

## Limites que você nunca cruza

- Nunca altere, mova nem apague nada na pasta de currículos. Só leia. A subpasta `_resultado` (e o que começa com `_` ou `.`) é ignorada na leitura.
- Nunca envie nada a candidatos (e-mail, convite, feedback) e nunca publique nada. Saída para terceiros só com prévia e ok explícito do usuário.
- O julgamento (notas, trechos, inconsistências, perguntas) é seu. Score, desempate, Top 3, validação e painel são dos scripts: não calcule score de cabeça.

## Fluxo

### 0. Argumentos e pastas
- `PASTA` = primeiro argumento. Se faltar, pergunte.
- Vaga, nesta ordem de precedência: (1) texto livre passado no comando; (2) `vaga.md` na pasta; (3) PDF/DOCX com "vaga" ou "anuncio" no nome. O script de extração aplica essa ordem.
- `TRAB=$(mktemp -d)` para os arquivos de trabalho (textos extraídos). Eles não vão para o resultado.
- `SAIDA` = `--saida <dir>` se passado; senão `PASTA/_resultado`. O resultado fica em `SAIDA/<AAAA-MM-DD>-<slug-da-vaga>/` (data de hoje; slug do cargo, minúsculo, com hífen). Se `PASTA` for somente leitura e não houver `--saida`, pergunte onde gravar antes de seguir.

### 1. Extrair o texto
```bash
BASE/scripts/rodar.sh extrair_texto.py "PASTA" --saida "$TRAB" [--vaga "texto livre"]
```
- Código de saída 3 = nenhuma fonte de vaga: pergunte a vaga ao usuário e rode de novo com `--vaga`.
- Leia `BASE/core/regras-avaliacao.md` inteiro, `$TRAB/extracao.json` e **todos** os `$TRAB/textos/*.txt` inteiros. Arquivo ilegível entra como `nao_avaliado`, com o motivo do manifesto, sem estimar o conteúdo.

### 2. Matriz de critérios
- Se a vaga traz requisitos: monte os critérios a partir deles (regras, seção 2), mostre a matriz em uma tabela curta e siga.
- Se não traz: proponha a matriz (obrigatórios, desejáveis, pesos sugeridos), mostre e **pare até o usuário aprovar**.

### 3. Avaliar cada currículo (regras, seções 1 a 9)
Para cada currículo decida `aprovado`, `eliminado`, `limitrofe` ou `nao_avaliado`. Aprovados e limítrofes recebem nota de 0 a 5 em **todos** os critérios, cada uma com trecho literal, natureza e comentário. Aprovados recebem 3 pontos fortes, 2 ou mais riscos e as inconsistências. `ordemRecencia` (1 = experiência mais recente e mais próxima da vaga) vale para aprovados e limítrofes, sem repetir. `id` = primeiro nome em minúsculas sem acento (desambigue com `-2`). Grave `SAIDA/…/processo.json` (formato abaixo; schema em `BASE/core/processo.schema.json`), com `top3: []` e `perguntas: {"comuns": [], "porCandidato": {}}`.

### 4. Ranking e Top 3 (código)
```bash
BASE/scripts/rodar.sh score.py "SAIDA/…/processo.json" --gravar
```
O script grava `top3` e os avisos de margem e empate. Com menos de 3 aprovados, siga só com eles e diga isso.

### 5. Perguntas do Top 3 (regras, seção 10)
Escreva em `perguntas`: `comuns` com B1…B6 (iguais para os três) e, em `porCandidato.<id>`, o `A` (7 a 8 perguntas, cada uma com trecho literal, cobrindo os obrigatórios com nota < 5 e **todas** as inconsistências) e o `B7`.

### 6. Validar (no máximo 2 correções)
```bash
BASE/scripts/rodar.sh validar.py "SAIDA/…/processo.json" --extracao "$TRAB/extracao.json"
```
Se der INVÁLIDO, corrija o JSON e valide de novo, no máximo 2 vezes. Se ainda falhar, pare e mostre os erros. Revise os AVISOS de privacidade.

### 7. Painel e resumo
```bash
BASE/scripts/rodar.sh gerar_painel.py "SAIDA/…/processo.json"
BASE/scripts/rodar.sh resumo_triagem.py "SAIDA/…/processo.json"
```
A pasta de resultado termina com 3 arquivos: `processo.json`, `painel.html` e `triagem.md`. Apague `$TRAB` (ele foi criado por você).

### 8. Resposta no chat
Mostre o mesmo resumo do `triagem.md` (tabela de todos os candidatos e, para o Top 3, os pontos fortes, os riscos e as inconsistências). Mostre também os avisos e os limítrofes. Termine com uma linha do que o usuário faz a seguir, por exemplo: "Abra `painel.html`, conduza as entrevistas e registre as respostas. Exporte o JSON para continuar no app."

## Modo automático (GitHub Actions, sem ninguém no chat)

Quando o pedido chega pela Action do repositório de dados (o prompt informa "Pasta dos currículos", "Destino exato" e `work/ajustes.md`):

- Não há ninguém para responder no chat. Nunca pergunte nada na resposta e nunca espere confirmação.
- Arquivos de trabalho vão em `work/trab/` (crie com `mkdir -p work/trab`), não em `mktemp`. Rode `extrair_texto.py "<pasta>" --saida work/trab`.
- A vaga está em `vaga.md` dentro da pasta (formulário do site). Se ele citar um arquivo de anúncio, leia também esse anúncio extraído.
- Leia `work/ajustes.md`: são respostas do usuário a perguntas anteriores ou pedidos de ajuste. Elas valem mais que a vaga.
- **Matriz sem requisitos**: se a vaga não traz requisitos e `work/ajustes.md` não aprova uma matriz, escreva em `work/perguntas.md` a matriz proposta (tabela com critério, tipo e peso) e a pergunta "Posso pontuar com esta matriz?". Depois pare, sem gravar o resultado.
- Grave os 3 arquivos **direto no destino informado** (por exemplo, `resultados/<id>/processo.json`), sem a subpasta de data. Os passos 4 a 7 são os mesmos; no 7, `gerar_painel.py` e `resumo_triagem.py` gravam ao lado do `processo.json`.
- Não faça commit nem push: a Action faz isso depois de validar.

## Formato do processo.json (resumo)

```json
{
  "schemaVersion": "1.0", "geradoPor": "skill", "geradoEm": "2026-10-20T10:00:00",
  "vaga": {"id": "nexora-analista-de-rh", "titulo": "Analista de RH — Nexora", "cargo": "Analista de RH", "empresa": "Nexora",
           "area": "RH", "local": "São Paulo, SP", "modelo": "hibrido", "contrato": "CLT", "faixa": "R$ 3.800–5.200",
           "data": "2026-10-20", "exigePresenca": true, "afirmativa": "", "fonteRequisitos": "Requisitos tirados do anúncio."},
  "criterios": [{"id": "C1", "nome": "Graduação em Administração ou correlata", "tipo": "O", "peso": 10}],
  "candidatos": [
    {"id": "ana", "nome": "Ana Souza", "arquivo": "01_cv_ana.pdf", "cidade": "São Paulo, SP", "cargo": "Analista de RH · Empresa X",
     "status": "aprovado", "ordemRecencia": 1,
     "notas": {"C1": {"nota": 5, "trecho": "Bacharelado em Administração", "natureza": "escrito", "comentario": ""}},
     "fortes": [{"texto": "R&S em volume", "trecho": "Condução de 30 processos seletivos/ano"}],
     "riscos": [{"texto": "Título sênior acima da faixa", "trecho": "Analista Sênior", "inferencia": true}],
     "inconsistencias": [{"texto": "Redução de 20% sem base de comparação", "inferencia": false}]},
    {"id": "bia", "nome": "Bia Lima", "arquivo": "02_cv_bia.pdf", "status": "eliminado", "motivo": "Sem experiência em T&D.", "requisitosFaltantes": ["C5"]},
    {"id": "caio", "nome": "Caio Reis", "arquivo": "03_cv_caio.pdf", "status": "limitrofe", "ordemRecencia": 2, "motivo": "…",
     "requisitosFaltantes": ["C5"], "criterioInclusao": "Se você aceitar PDI como vivência de T&D, ele entra na disputa.", "notas": {}},
    {"id": "dani", "nome": "03_cv_dani.pdf", "arquivo": "03_cv_dani.pdf", "status": "nao_avaliado", "motivo": "sem texto extraível (provável PDF escaneado)"}
  ],
  "top3": ["ana"], "avisos": [],
  "perguntas": {
    "comuns": [{"id": "B1", "crit": "C4", "q": "Caso: …", "a1": "…", "a3": "…", "a5": "…"}],
    "porCandidato": {"ana": {"A": [{"id": "A1", "crit": "C4", "trecho": "Condução de 30 processos seletivos/ano", "q": "…", "boa": "…", "alerta": "…"}],
                              "B7": {"id": "B7", "crit": "C11", "q": "…", "a1": "…", "a3": "…", "a5": "…"}}}
  }
}
```

Lembretes que o validador cobra: trecho literal (fragmentos separados por ` … `); `declarado` ≤ 3; `ausente` = 0 com `"Sem menção"`; nenhum e-mail, telefone, link pessoal, "PcD", deficiência, saúde, idade ou motivo pessoal de lacuna em nenhum campo; `cidade` só se `exigePresenca`.
