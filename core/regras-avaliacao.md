# Regras de avaliação de currículos (núcleo único)

Este arquivo é a única fonte das regras. A skill `/analise-de-curriculo` e o app do claude.ai leem este mesmo texto. Mudou uma regra, mude só aqui (e rode `scripts/build_app.py` para atualizar a cópia embutida no app).

## 1. Evidência

1. O currículo é a única fonte sobre o candidato. Não use conhecimento externo sobre a pessoa, a empresa ou a instituição.
2. Toda nota de 0 a 5 cita o trecho **literal** do currículo que a sustenta, no campo `trecho`. Copie o texto exatamente como está (pode omitir partes com ` … ` entre fragmentos literais). Comentários seus vão no campo `comentario`, nunca dentro do `trecho`.
3. Nota 0 sem evidência usa `trecho: "Sem menção"` e `natureza: "ausente"`.
4. Habilidade que aparece **só** na lista de habilidades, só no objetivo/resumo ou só num curso vale como "declarada, não evidenciada" (`natureza: "declarado"`) e recebe **no máximo nota 3**.
5. Separe o que está escrito do que é inferência. Toda inferência aparece marcada como tal (`natureza: "inferencia"`, ou o texto "(inferência)" em riscos e inconsistências).
6. Escala de notas:
   - 5: evidência direta, recente e completa do critério, em experiência ou formação.
   - 4: evidência direta, mas parcial (método não descrito, escopo não claro) ou não recente.
   - 3: evidência indireta ou só declarada.
   - 2: atividade vizinha que cobre parte pequena do critério.
   - 1: menção fraca ou nível abaixo do pedido (ex.: "Inglês: Básico" para intermediário).
   - 0: sem menção.

## 2. Requisitos e matriz

1. Se a vaga trouxer requisitos, use-os: cada requisito obrigatório vira um critério `tipo: "O"`, cada desejável vira `tipo: "D"`. As responsabilidades da vaga podem virar um critério desejável agregado.
2. Se a vaga não trouxer requisitos, monte uma matriz (obrigatórios, desejáveis e pesos), mostre ao usuário e **espere o ok antes de pontuar**.
3. Os pesos são sugestão: aparecem como sugeridos e ficam editáveis no painel. Obrigatórios pesam mais que desejáveis.
4. IDs dos critérios: `C1`, `C2`, … na ordem: obrigatórios primeiro, depois desejáveis.

## 3. Filtro eliminatório

1. Um requisito obrigatório só conta se aparece no currículo como **experiência ou atuação** (ou como formação, no caso de requisito de formação). Aparecer só em objetivo, título, lista de habilidades ou curso não basta para passar no filtro.
2. Quem não tem um obrigatório sai (`status: "eliminado"`), e o painel registra o requisito que faltou (`requisitosFaltantes`) e o motivo.
3. Caso de fronteira, em que uma experiência parecida poderia contar, sai marcado como `status: "limitrofe"`, com o `criterioInclusao` explicado ("se você aceitar X como Y, ele entra na disputa") para o usuário decidir. Limítrofes também recebem notas, para que o painel possa simular a inclusão.
4. Inconsistência nunca elimina ninguém (ver seção 5).

## 4. Score e desempate (calculados em código, não pelo Claude)

1. Score de triagem = soma(nota ÷ 5 × peso) ÷ soma dos pesos × 100.
2. Desempate: primeiro a soma das notas dos obrigatórios; depois a experiência mais recente e mais próxima da vaga (`ordemRecencia`: 1 = mais recente e mais próxima; o Claude preenche esse número para cada aprovado, sem repetir).
3. Se a margem do 3º para o 4º lugar for menor que 3 pontos, ou se os dois empatarem na soma dos obrigatórios, o sistema avisa.
4. Top 3 = os três primeiros aprovados no ranking. Com menos de 3 aprovados, selecione só os que passaram e diga isso. Não complete a lista com quem não atende.

## 5. Inconsistências

1. Aponte: lacunas de datas; períodos sobrepostos; tempo declarado diferente da soma das datas; título incompatível com a trajetória; resultado sem base numérica; certificação com emissora estranha.
2. Cada inconsistência dos candidatos do Top 3 vira pergunta do Bloco A. Nunca vira eliminação.

## 6. Dados pessoais e LGPD

1. Idade, gênero, foto, estado civil, filhos, religião, origem, raça, deficiência e saúde **não entram** na análise, nas notas, nos trechos, nas perguntas nem no painel. Se um trecho útil contiver um desses dados, omita a parte com ` … `.
2. Exceção: vaga afirmativa declarada pelo usuário no campo da vaga (`vaga.afirmativa`). Mesmo assim, o dado só entra para verificar o critério afirmativo.
3. O motivo pessoal de uma lacuna de carreira não é perguntado nem registrado. A pergunta é sobre a atividade profissional no período.
4. No painel aparecem só nome, cidade (apenas quando a vaga exige presença física: presencial ou híbrido) e dados profissionais. Contatos (e-mail, telefone, endereço, links pessoais) e documentos (CPF, RG, registro profissional com número) ficam de fora.

## 7. Prestígio

Nome de empresa ou instituição não pontua por si. Conta o que a pessoa fez lá.

## 8. Riscos

1. Cada candidato do Top 3 tem pelo menos 2 riscos, cada um com citação.
2. Senioridade incompatível com a faixa salarial da vaga entra como risco, marcado como inferência.

## 9. Arquivo ilegível

Marque como `status: "nao_avaliado"`, com o motivo, sem estimar o conteúdo.

## 10. Perguntas de entrevista (Top 3)

**Bloco A — validação do currículo** (7 a 8 por candidato):
- cada pergunta presa a um `trecho` literal do currículo e a um critério (`crit`);
- campos: `q` (pergunta), `boa` (o que uma boa resposta mostra), `alerta` (sinal de alerta);
- cubra os obrigatórios com nota menor que 5 e todas as inconsistências;
- lacuna de carreira: pergunte sobre a atividade profissional no período, nunca o motivo pessoal.

**Bloco B — aderência à vaga**:
- 6 perguntas **comuns** aos três candidatos (`B1`…`B6`), mais 1 específica de cada candidato (`B7`);
- cada uma ligada a um critério (`crit`), em formato STAR ou caso prático;
- rubrica com âncoras para as notas 1, 3 e 5 (`a1`, `a3`, `a5`).

## 11. Saída

O resultado é um `processo.json` válido contra `core/processo.schema.json`. Pontos fortes (3 por candidato do Top 3) e riscos (2 ou mais) trazem `texto` + `trecho`.
