# Contribuer sans exécuter de CI sur GitHub

Ouvrir une PR vers `main` depuis une branche à jour. L'approbation de `@abcdef123456-wq` et le statut `ci-locale` sont deux conditions distinctes. Un changement de code après la revue impose une nouvelle approbation ; le résultat de CI ne vaut que pour le commit testé. Si `main` avance, mettre la branche à jour avant la fusion. GitHub interdit l'auto-approbation : ne pas ouvrir la PR sous le compte propriétaire si celui-ci doit l’approuver.

## Lancer les tests

Depuis une copie de confiance des outils, sur une machine Linux de CI avec Git, Docker, Python 3 et PyYAML :

```sh
outils/ci-locale --plan
outils/ci-locale "$(git rev-parse HEAD)"
```

**Sur chaque PR** : découverte de toute la suite de tests sur Debian 13, répartie entre plusieurs processus, et analyse statique sur Arch en parallèle. Le pilote réserve du temps au nettoyage ; l'attestation inclut aussi la récupération du commit et la publication dans son plafond de **15 minutes**. Une erreur ou un dépassement ne valide jamais la PR. Si GitHub est injoignable, le statut peut rester en attente et la fusion reste bloquée.

**Avant une livraison**, ou pour vérifier un changement d’installateur sur les quatre distributions :

```sh
outils/ci-locale --complete --parallele 4 "$(git rev-parse HEAD)"
```

Cette vérification séparée conserve les neuf tâches : tests et installation réelle sur Arch, Debian, Fedora et openSUSE, plus l'analyse statique. Elle n’est pas plafonnée à 15 minutes et ne publie pas le statut d’une PR. Les étapes de référence sont dans `.github/workflows/`. GitHub Actions reste désactivé.

## Publier le résultat d’une PR (collaborateur)

Tout collaborateur ayant l’accès **Write** au dépôt peut publier sa CI depuis son PC Linux. Installer GitHub CLI (`gh`) en plus des prérequis ci-dessus et se connecter avec son propre compte, sans clé partagée :

```sh
gh auth login --hostname github.com
outils/attester-ci-locale NUMERO_PR
```

Lancer la commande depuis une copie de confiance des outils, à jour depuis `main`, et non depuis la branche à tester. Le pilote récupère le commit de la PR sans changer de branche, l’exécute dans des conteneurs et publie `ci-locale` sur ce commit. Si la tête de la PR change pendant le test, relancer sur la nouvelle version.

La [règle de `main`](https://github.com/abcdef123456-wq/noctalia-config/settings/rules/27927625) accepte le statut quelle que soit sa source GitHub. Il s’agit d’une attestation de confiance : GitHub enregistre le compte qui publie le statut, mais ne prouve pas que les tests ont tourné. L’approbation du propriétaire reste obligatoire et distincte.

Pour la première PR, `CODEOWNERS` n’existe pas encore sur la branche de base. Une deuxième règle réserve donc la fusion au propriétaire en passant par une PR ; elle ne dispense jamais des autres contrôles. Après fusion de `.github/CODEOWNERS` sur `main`, le propriétaire peut supprimer la règle d’amorçage s’il veut permettre aux collaborateurs de cliquer sur Fusionner **après** son approbation.
