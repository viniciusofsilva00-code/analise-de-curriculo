#!/usr/bin/env bash
# Instala a skill /analise-de-curriculo para valer em qualquer pasta.
# Cria links simbólicos, então editar core/ ou skill/ no projeto já vale para a skill instalada.
set -euo pipefail
PROJ="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"
SKILL="$PROJ/skill/analise-de-curriculo"
DEST="$HOME/.claude/skills/analise-de-curriculo"

# core/ visível de dentro da skill (regras, schema e template: uma cópia só)
[ -L "$SKILL/core" ] || ln -s ../../core "$SKILL/core"
chmod +x "$SKILL/scripts/"*.sh "$SKILL/scripts/"*.py

mkdir -p "$HOME/.claude/skills"
if [ -e "$DEST" ] && [ ! -L "$DEST" ]; then
  echo "ERRO: $DEST já existe e não é um link criado por este instalador. Remova-o você mesmo e rode de novo." >&2
  exit 1
fi
ln -sfn "$SKILL" "$DEST"
echo "Skill instalada: $DEST -> $SKILL"
