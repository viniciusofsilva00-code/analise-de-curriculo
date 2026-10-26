# triagem-cv-dados (privado)

Repositório de dados do **triagem_cv** · um projeto vini_lab. Guarda currículos e resultados de processos seletivos, então **precisa ser privado**: a Action se recusa a rodar se ele ficar público.

- `entrada/<id>/`: o que o site envia (currículos e `vaga.md`).
- `resultados/<id>/`: `processo.json`, `painel.html` e `triagem.md`, gravados pela Action.
- A avaliação roda no GitHub Actions com o Claude Code, usando o seu plano Claude (segredo `CLAUDE_CODE_OAUTH_TOKEN`), sem chave de API.
- O código (regras, skill e scripts) vem do repositório público `analise-de-curriculo`.

Dados pessoais: apague o processo pelo site quando ele terminar. O histórico do git guarda versões antigas; para apagar de vez, apague o repositório.
