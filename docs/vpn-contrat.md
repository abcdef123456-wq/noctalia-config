# Contrat des fournisseurs VPN (`nc-vpn`)

Ce que la fenêtre VPN lit et lance pour NordVPN, Proton VPN et Mullvad. Tout est en arguments (jamais une ligne de shell).
Ce contrat est la version 1.

## Lire : `nc-vpn fournisseurs-json`

```json
{"contrat": 1, "fournisseurs": [
  {"id": "nord", "nom": "NordVPN", "etat": "pret", "message": "Compte NordVPN connecté.",
   "pays": [{"code": "FR", "nom": "France"}], "pays_actif": "FR", "connecte": true,
   "peut_login": false, "probleme": "", "pilotage": "direct"},
  {"id": "proton", "nom": "Proton VPN", "etat": "sans_compte", "message": "…",
   "pays_actif": "", "connecte": false, "peut_login": true, "probleme": "", "pilotage": "appli"},
  {"id": "mullvad", "nom": "Mullvad", "etat": "absent", "message": "…",
   "pays_actif": "", "connecte": false, "peut_login": false, "probleme": "", "pilotage": "direct"}
]}
```

| Clé | Sens |
| --- | --- |
| `id` | `nord`, `proton` ou `mullvad` |
| `etat` | `absent` : commande introuvable (silencieux) ; `sans_compte` : client installé, pas de compte connecté (ou client inutilisable, voir `probleme`) ; `pret` : compte connecté |
| `message` | une phrase, dans la langue de la session (français ou anglais) ; texte brut |
| `pays` | **seulement si `etat` vaut `pret`** : `[{"code": "FR", "nom": "France"}]`, code en deux lettres majuscules, nom borné en texte brut. Liste vide pour Proton (le pays se choisit dans l'appli) |
| `pays_actif` | code du pays du tunnel de ce fournisseur, ou `""` |
| `connecte` | ce fournisseur a un tunnel monté (toujours `false` hors de l'état `pret`) |
| `peut_login` | `nc-vpn fournisseur ID login` est utile (installé, pas de compte connecté, et possible) |
| `probleme` | `""`, ou `permission` (groupe `nordvpn` manquant), `consentement` (première exécution de `nordvpn` : question interactive), `demon` (service arrêté), `delai`, `lancement` ; le `message` dit quoi faire |
| `pilotage` | `direct` : on pilote la CLI ; `appli` : on ouvre seulement l'application officielle (Proton) |

Jamais dans la sortie : adresse e-mail, numéro de compte, jeton, URL de connexion.

## Agir

- `nc-vpn fournisseur ID connecter CC` : `CC` doit être exactement deux lettres majuscules d'un pays ISO (`FR`) ; sinon refus (code 1) sans appel.
  Nord : `nordvpn connect NOM` (le nom exact donné par `nordvpn countries`). Mullvad : `mullvad relay set location fr`, puis `mullvad connect`.
  Proton : ouvre l'application officielle (choisir le pays s'y fait).
- `nc-vpn fournisseur ID deconnecter` : Nord `nordvpn disconnect` ; Mullvad `mullvad disconnect` ; Proton ouvre l'application.
- `nc-vpn fournisseur ID login` : le parcours officiel. Nord : `nordvpn login`, puis l'adresse qu'il donne est ouverte avec `xdg-open` seulement si
  c'est une URL https de `nordaccount.com` ou `nordvpn.com` (port 443, sans identifiant) ; elle n'est jamais affichée. Proton : ouvre l'application.
  Mullvad : ouvre l'application graphique (`mullvad-vpn`) ou dit de lancer `mullvad account login` dans un terminal.
  Aucune saisie de mot de passe, de numéro de compte ni de jeton chez nous. La fenêtre relit `fournisseurs-json` au retour.

Code de sortie : 0 en cas de succès, 1 avec un message `nc-vpn : …` sur la sortie d'erreur, 2 pour une commande inconnue.
Les messages d'erreur passent par un filtre (URL, e-mail, longues suites de chiffres ou de lettres retirés).

## Comment c'est décidé (sources officielles)

- **Nord** (dépôt NordSecurity/nordvpn-linux, dossier `cli/`) : sous-commandes `account`, `countries`, `connect`, `disconnect`, `status`, `login` (options
  `--callback`, `--token`, que nous n'utilisons pas). Connecté si `nordvpn account` écrit « Account information » (sa sortie, qui contient l'e-mail, n'est
  jamais gardée). `countries` donne des noms avec `_` (pas de code) : un code ISO est associé par une table intégrée, les noms inconnus sont écartés.
  `login` écrit « Continue in the browser: URL » et n'ouvre pas lui-même le navigateur. Le consentement (statistiques) est une question interactive
  « (y/n) » : stdin est fermé et la commande est tuée au délai ; le message dit d'ouvrir un terminal. « Permission denied » sur le socket : message sur le
  groupe `nordvpn`, aucune élévation.
- **Proton** (ProtonVPN/proton-vpn-gtk-app, python-proton-vpn-api-core) : pas de CLI officielle actuelle ; le paquet donne `protonvpn-app`
  (options `--start-minimized` et `--version` seulement). La connexion NetworkManager de l'appli est nommée « ProtonVPN SERVEUR » et créée sans être
  enregistrée : elle n'existe que pendant la connexion. Le compte est dans le stockage de l'appli (jetons) : jamais lu. À noter si un jour il faut
  fermer l'appli : confirmation explicite et pid mémorisé, jamais `pkill`.
- **Mullvad** (mullvad/mullvadvpn-app, `mullvad-cli`) : `status` écrit « Warning: You are not logged in to an account. » sans compte ; `account get`
  affiche le numéro (jamais lancé) ; `relay list` écrit « Nom (code) » par pays, les villes et relais en retrait.
