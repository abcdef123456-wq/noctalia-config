# Contribuer sans exécuter de CI sur GitHub

Ouvrir une PR vers `main` depuis une branche à jour. L'approbation de `@abcdef123456-wq` et le statut `ci-locale` sont deux conditions distinctes. Un changement de code après la revue impose une nouvelle approbation ; le résultat de CI ne vaut que pour le commit testé. Si `main` avance, mettre la branche à jour avant la fusion. GitHub interdit l'auto-approbation : ne pas ouvrir la PR sous le compte propriétaire si celui-ci doit l’approuver.

## Lancer les tests

Depuis une copie de confiance des outils, sur une machine Linux de CI avec Git, Docker, Python 3 et PyYAML :

```sh
outils/ci-locale --plan
outils/ci-locale "$(git rev-parse HEAD)"
```

La matrice comprend les tests et une installation réelle sur Arch, Debian, Fedora et openSUSE, plus l'analyse statique. Les commandes de référence sont dans `.github/workflows/`. GitHub Actions est désactivé au niveau du dépôt, y compris les tâches planifiées. Un essai personnel n'envoie aucun résultat à GitHub.

## Attester une PR (mainteneur)

Utiliser une machine de CI isolée : pas de clé d’administration ni d’accès au réseau privé dans les conteneurs. **Ne jamais lancer le pilote fourni par une branche non relue** ; le lancer depuis la copie de confiance, sans checkout de la PR. Pour la toute première installation, relire les deux pilotes avant de les utiliser.

1. Sous le compte propriétaire, [créer l’App privée](https://github.com/settings/apps/new?name=noctalia-ci-locale-abcdef123456&url=https%3A%2F%2Fgithub.com%2Fabcdef123456-wq%2Fnoctalia-config&statuses=write&public=false&webhook_active=false). Seule permission à accorder : **Commit statuses → Read and write**, plus la lecture implicite des métadonnées. Désactiver le webhook et installer l’App sur ce seul dépôt.
2. Générer sa clé privée. La conserver hors du dépôt, dans un dossier privé sur la machine de CI, avec les droits `600`. Ne pas fournir cette clé aux contributeurs. Exporter `CI_LOCALE_APP_ID` (App ID numérique, pas Installation ID) et `CI_LOCALE_CLE_PRIVEE` (chemin absolu de la clé).
3. Exécuter `outils/attester-ci-locale NUMERO_PR`. Le pilote récupère le commit depuis GitHub, lance les vérifications et publie leur résultat. La clé ne sert qu'à publier le statut ; aucun compte humain ne doit déclarer le succès manuellement.
4. **Une seule fois**, après la première publication, dans [la règle de `main`](https://github.com/abcdef123456-wq/noctalia-config/settings/rules/27927625), choisir cette App comme **source attendue** du statut `ci-locale`, à la place de GitHub Actions, puis enregistrer. Ne jamais choisir « Any source » : un collaborateur en écriture pourrait alors publier lui-même un succès. Avant cette liaison, la fusion est bloquée volontairement.

Pour la première PR, `CODEOWNERS` n’existe pas encore sur la branche de base. Une deuxième règle réserve donc la fusion au propriétaire en passant par une PR ; elle ne dispense jamais des autres contrôles. Après fusion de `.github/CODEOWNERS` sur `main`, le propriétaire peut supprimer la règle d’amorçage s’il veut permettre aux collaborateurs de cliquer sur Fusionner **après** son approbation.
