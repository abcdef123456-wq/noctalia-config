# Contributions des agents IA

Si tu as poussé un changement sur une PR, attends que `ci-locale` soit vert, puis relis toi-même le diff complet de la PR sur le commit testé. Vérifie que le diff répond à la demande, ne contient pas de changement hors sujet et n’introduit pas de régression visible. Si tu corriges quelque chose, pousse le nouveau commit, relance la CI et relis le nouveau diff.

Ne demande pas la fusion automatique avant cette relecture. Au moment de fusionner, protège le SHA testé et relu avec `gh pr merge NUMERO_PR --auto --squash --match-head-commit SHA_TESTE`. Voir [le guide de CI locale](docs/ci-locale.md).
