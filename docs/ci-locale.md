# Contribuer sans exécuter de CI sur GitHub

Ouvrir une PR vers `main` depuis une branche à jour. GitHub exige le statut `ci-locale`, mais pas d’approbation humaine. Le statut ne vaut que pour le commit testé : après un nouveau push ou une mise à jour depuis `main`, relancer la CI sur la nouvelle tête.

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

La [règle de `main`](https://github.com/abcdef123456-wq/noctalia-config/settings/rules/27927625) accepte le statut quelle que soit sa source GitHub. Il s’agit d’une attestation de confiance : un compte avec l’accès **Write** peut publier un succès sans exécuter les tests, et ce succès permet la fusion sans revue. N’accorder cet accès qu’aux personnes de confiance.

## Demander la fusion automatique

Sur une PR prête à fusionner, un collaborateur avec l’accès **Write** peut armer la fusion, puis lancer la CI :

```sh
gh pr merge NUMERO_PR --auto --squash
outils/attester-ci-locale NUMERO_PR
```

GitHub fusionne lorsque `ci-locale` est vert et que la PR est à jour avec `main`. La fusion automatique s’active par PR ; lancer la CI seule ne la demande pas.
Pour annuler la demande, utiliser `gh pr merge NUMERO_PR --disable-auto`.
Les commandes `gh pr merge` supposent qu’elles sont exécutées depuis une copie du dépôt GitHub `abcdef123456-wq/noctalia-config`.
Seule la fusion est gérée par GitHub : les tests restent locaux.
