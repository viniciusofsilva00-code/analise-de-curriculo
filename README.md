# Sistema de análise de currículos

Triagem de currículos e painel de entrevistas, sem chave de API: usa a sua conta Claude. São duas portas de entrada com o mesmo núcleo (`core/`): as mesmas regras, o mesmo `processo.json` e o mesmo painel. Um processo iniciado numa porta abre na outra.

| | Porta 1: skill no Claude Code | Porta 2: app no claude.ai |
|---|---|---|
| Como chama o Claude | a própria sessão do Claude Code | capability `sample` da página publicada |
| Entrada | pasta + vaga | formulário + pasta/arquivos (PDF, DOCX) |
| Saída | `_resultado/<data>-<vaga>/` com `processo.json`, `painel.html` e `triagem.md` | painel na própria página; exporta `processo.json`, `painel.html` e o relatório |

## Porta 1: `/analise-de-curriculo`

```
/analise-de-curriculo <pasta> [--saida <dir>] [vaga em texto livre]
```

- Vaga, por precedência: o texto do comando, depois um `vaga.md` na pasta, depois um PDF/DOCX com "vaga" ou "anuncio" no nome. Sem nenhuma dessas fontes, a skill pergunta.
- Sem requisitos na vaga, a skill mostra a matriz e espera o seu ok antes de pontuar.
- O resultado vai para `<pasta>/_resultado/AAAA-MM-DD-<vaga>/`. Se a pasta for somente leitura (como a do caso de referência), use `--saida`.
- Os currículos nunca são alterados e a pasta `_resultado` é ignorada na leitura.

Instalação, uma vez só: `bash scripts/instalar_skill.sh`. O instalador cria um link de `~/.claude/skills/analise-de-curriculo` para `skill/analise-de-curriculo/`, então editar o projeto já vale para a skill.

## Porta 2: app com botão

1. Gere o app: `.venv/bin/python scripts/build_app.py`. O build embute `core/regras-avaliacao.md` e o painel.
2. No app desktop do Claude (Cowork), peça: **"publique `app/analise-curriculos-app.html` como artifact com capabilities `{sample: {}, downloads: true}`"**.
3. Na página: preencha a vaga, selecione a pasta (ou arraste os arquivos) e clique em **Avaliar**. Cada etapa é um clique, e o botão Parar fica visível durante a chamada:
   matriz (só sem requisitos) → triagem (em lotes de cerca de 190 KB, cada lote com o seu botão) → perguntas do Top 3 → painel.

Teste local: abra `app/analise-curriculos-app.html` no navegador. Sem `claude.use`, a página entra em modo de teste e aceita um `processo.json` importado.

### Pelo plano Claude, a partir do site (como no oficina_ia)

O site envia os currículos para um repositório de dados **privado** (`dados-template/` é o conteúdo dele). Lá, o GitHub Actions roda o Claude Code com o seu plano (segredo `CLAUDE_CODE_OAUTH_TOKEN`, gerado por `claude setup-token`), seguindo a seção "Modo automático" da skill. O resultado volta para `resultados/<id>/`, e o site abre o painel lendo-o pela API, com o seu token. Nada de candidato vai para o repositório público nem para o Pages.

Configuração, uma vez só:
1. Crie o repositório privado `triagem-cv-dados` com o conteúdo de `dados-template/`.
2. Nele, em Settings → Secrets → Actions, crie `CLAUDE_CODE_OAUTH_TOKEN` (o mesmo valor usado no oficina_ia serve; para gerar outro, rode `claude setup-token`).
3. Gere um token fine-grained só para esse repositório, com **Contents** e **Issues** em *Read and write*, e cole no site, na seção 0, opção "Meu plano Claude (via GitHub)".

### Site no GitHub Pages

O build também gera `docs/index.html`, que é a mesma página com o cabeçalho HTML completo. No GitHub, abra **Settings → Pages**, escolha "Deploy from a branch", branch `main` e pasta `/docs`. No Pages, o app roda em **modo de teste**: abre um `processo.json` no painel, mas o botão Avaliar só funciona no claude.ai.

## O que é código e o que é julgamento

- **Código** (determinístico): extração de texto (`extrair_texto.py` no Python; pdf.js e mammoth no app), score, desempate, Top 3, bloqueio, validação (`validar.py`), barreira de privacidade e montagem do painel. O score tem uma implementação só, `PainelSelecao.calc` no template, e um teste confere que o espelho em Python dá o mesmo resultado.
- **Claude**: as notas com o trecho literal, a natureza de cada evidência, as inconsistências e as perguntas.

## Mudar regras, critérios ou vaga

- Regra de avaliação: edite `core/regras-avaliacao.md` e rode `scripts/build_app.py` para levar a mudança ao app.
- Vaga nova: basta outra pasta, outro `vaga.md` ou outro texto no comando. Não precisa editar código.
- Pesos: ajuste no próprio painel. O ranking recalcula na hora e os pesos vão junto no JSON exportado.

## Painel (`painel.html`)

O painel tem quatro partes:
- **Triagem e critérios**: ranking, pesos editáveis, eliminados e limítrofes com o requisito que faltou, e evidências por candidato.
- **Uma aba por candidato do Top 3**: Bloco A (validação: Confirmado = 100, Parcial = 50, Não confirmado = 0) e Bloco B (aderência: nota ÷ 5 × 100).
- **Comparativo e decisão**: final = (30 × triagem + 30 × validação + 40 × aderência) ÷ soma dos pesos. A recomendação só aparece com tudo preenchido. Um item obrigatório "Não confirmado" bloqueia o candidato.
- **Barra de ações**: exportar e importar JSON, baixar o relatório HTML (imprima em PDF pelo navegador) e limpar as respostas, com confirmação na própria página.

## Instalar a partir do git

```
git clone <url-do-repositório> sistema-analise-curriculos && cd sistema-analise-curriculos
python3 -m venv .venv && .venv/bin/pip install pypdf python-docx jsonschema playwright pytest
PLAYWRIGHT_BROWSERS_PATH=.venv/ms-playwright .venv/bin/playwright install chromium
bash scripts/instalar_skill.sh
```

Se o `python3 -m venv` reclamar de `ensurepip`, crie com `--without-pip` e instale o pip pelo `get-pip.py` oficial (bootstrap.pypa.io). A pasta `exemplos/` (resultados com nomes de candidatos) fica fora do git; os testes de privacidade do caso de referência são pulados até você rodá-lo de novo.

## Testes

```
./testar.sh
```

O comando roda o schema, as regras, a extração, os scores do gabarito (Python × JS), o painel no Chromium (pesos, bloqueio, recomendação, exportar/importar, console e 400 px), a privacidade do caso de referência e o app (build, modo local e fluxo completo com o `sample` simulado). As dependências ficam em `.venv/` (pypdf, python-docx, jsonschema, playwright e o Chromium do Playwright).

## Estrutura

```
core/         regras-avaliacao.md · processo.schema.json · painel-template.html
skill/analise-de-curriculo/   SKILL.md · scripts/ (extrair_texto, validar, score, gerar_painel, resumo_triagem, rodar.sh)
app/          analise-curriculos-app.html (gerado) · src/app-fonte.html
scripts/      build_app.py · instalar_skill.sh
tests/        fixture-processo.json (do painel aprovado) · testes pytest/Playwright
exemplos/referencia/   resultado do caso de referência pela porta 1
```

Garantias: o sistema nunca envia nada a candidatos e nunca publica nada sozinho. Saída para terceiros só com prévia e o seu ok.
