# nc-vpn : le contrat JSON (version 1)

Ce contrat est fait pour les scripts et pour JARVIS. Il décrit ce que `nc-vpn` imprime avec `--json`, et ce qui ne changera pas
tant que `"contrat": 1`. Un champ n'est retiré, ou son sens changé, que dans une version 2.

- Chaque réponse JSON est un objet sur UNE ligne de la sortie standard, avec `"contrat": 1`.
- Succès : code de sortie 0 et `"ok": true` (sauf `etat-json`, qui n'a pas de champ `ok` : il n'échoue jamais).
- Erreur : code de sortie 1, objet `{"contrat": 1, "ok": false, "code": "...", "erreur": "texte"}` sur la sortie standard
  (pas sur l'erreur standard). `code` est stable ; `erreur` est un texte pour un humain, dans la langue du bureau :
  ne le comparez pas. Forme de commande inconnue : code 2, aide sur l'erreur standard.
- Aucun secret, aucun mot de passe, aucune adresse IP : les connexions sont désignées par leur UUID et leur nom
  (un libellé choisi par l'utilisateur dans NetworkManager). Tout passe par nmcli en arguments, jamais par un shell.
  Attention : pour un `.ovpn` ou un `.conf` importé, NetworkManager reprend le NOM DU FICHIER, qui est souvent le nom d'hôte
  du serveur (par exemple `xx-yyy.prod.fournisseur.example_udp`). Ce `nom` peut donc révéler le serveur, et il part tel quel
  vers un client automatique (JARVIS le relaie à Telegram, au propriétaire du compte). Pour l'éviter : renomme la connexion
  dans NetworkManager. Idée notée, pas faite : un réglage `VPN_JARVIS_NOMS=non` qui remplacerait le nom par « tunnel 1, 2… »
  et les 8 premiers caractères de l'UUID dans les réponses de JARVIS.

## Commandes

| Commande | Succès |
|---|---|
| `nc-vpn etat-json` | `{"contrat", "disponible": bool, "connexions": [C], "actives": [C]}` ; `C` = `{"uuid": str, "nom": str, "type": "vpn"\|"wireguard", "active": bool, "interface": str, "fournisseur": str, "pays": str, "depuis"?: int}` (`interface` vide si le tunnel n'est pas monté ; `fournisseur` et `pays` (code ISO à 2 lettres ou vide) sont déduits du nom de la connexion, sans réseau ; `depuis` : secondes depuis l'époque de l'activation, seulement pour un tunnel monté et si NetworkManager le donne). Champs ajoutés sans changer de version : un client ignore les champs qu'il ne connaît pas. NetworkManager ou nmcli absent : `{"contrat": 1, "disponible": false, "connexions": [], "actives": []}`, code 0. |
| `nc-vpn connecter UUID --json` | `{"contrat", "ok": true, "action": "connecter", "uuid", "nom", "actif": true, "deja": bool}` (`deja` : il était déjà monté) |
| `nc-vpn deconnecter UUID --json` | idem avec `"action": "deconnecter"`, `"actif": false` |
| `nc-vpn tout-deconnecter --json` | `{"contrat", "ok": true, "action": "tout-deconnecter", "coupes": [{"uuid","nom"}], "rates": []}` ; aucun tunnel monté : listes vides, succès |
| `nc-vpn killswitch etat-json` | `{"contrat", "installe": bool, "voulu": bool, "actif": bool\|null, "refus_code": str, "refus": str, "limites": [str]}` (`actif` null : inconnu). `refus_code` est STABLE : `""` (rien à signaler), `pas_installe`, `aucun_tunnel`, `plusieurs_tunnels`, `serveur_nom`, `mullvad`, `firewall` (réservé), `nm_indisponible`, `autre`. `refus` et `limites` sont des textes pour un humain, dans la langue du bureau : ils peuvent nommer le serveur (nom d'hôte). Un client automatique ne les relaie pas et ne s'appuie que sur `refus_code`. |
| `nc-vpn killswitch activer --json` | `{"contrat", "ok": true, "action": "killswitch-activer", "actif": true}` |
| `nc-vpn killswitch desactiver --json` | `{"contrat", "ok": true, "action": "killswitch-desactiver", "actif": false}` |

`--json` se met en dernier argument. Sans lui, `connecter`, `deconnecter`, `tout-deconnecter` et `killswitch activer|desactiver`
gardent leur sortie en texte pour le bureau (inchangée).

## Codes d'erreur (`code`)

| code | sens |
|---|---|
| `uuid_invalide` | l'UUID n'a pas la forme 8-4-4-4-12 chiffres hexadécimaux (rien n'est lancé) |
| `inconnue` | cet UUID n'est pas un VPN ou un WireGuard de NetworkManager |
| `nm_indisponible` | NetworkManager ou nmcli n'est pas disponible |
| `echec` | nmcli a refusé (mot de passe manquant, délai, tunnel en panne…) |
| `echec_partiel` | `tout-deconnecter` : certains tunnels sont restés montés ; la réponse porte aussi `coupes` et `rates` |
| `occupe` | un autre `connecter`, `deconnecter` ou `tout-deconnecter` est en cours (verrou `flock` non bloquant) : réessayer plus tard |
| `killswitch_coupe` | `killswitch activer` : `VPN_KILLSWITCH` n'est pas à `oui` dans les réglages |
| `killswitch_refuse` | l'assistant root a refusé ou n'est pas installé |
| `killswitch_actif` | `fournisseur nord connecter` ou `fournisseur proton connecter` (avec la CLI) : le kill switch NetworkManager est actif et bloquerait le tunnel ; il faut le couper d'abord |

## Alias de compatibilité

`nc-vpn status --json` = `etat-json`, `nc-vpn connect UUID` = `connecter UUID`, `nc-vpn disconnect UUID` = `deconnecter UUID`
(avec ou sans `--json`). Un alias est réécrit en commande d'origine avant tout traitement : même code, mêmes sorties, mêmes appels.

## JARVIS

JARVIS (Telegram et cockpit) pilote le VPN de la machine qui l'héberge, par `nc-vpn` en arguments (jamais un shell), avec une
liste blanche : état, connecter, déconnecter, tout déconnecter, état du kill switch. Connecter, déconnecter et tout couper demandent une
confirmation (`/nc oui` sur Telegram, dans la discussion privée, par la même personne). Le kill switch ne s'active ni ne se coupe depuis JARVIS : couper une protection à
distance, avec un compte de messagerie volé, démasquerait la connexion. Voir `docs/jarvis.md`.

`/nc oui` ne protège pas d'un compte volé. Couper un tunnel (ou tout couper) quand le kill switch est inactif démasque la
connexion. Les réponses de JARVIS sont des textes résumés, construits à partir de `refus_code` : ni `refus` ni `limites`
(qui peuvent nommer un serveur) ne sont relayés. Voir « Limites de la protection » dans `docs/jarvis.md`.

Attention : si le kill switch est actif, déconnecter le tunnel coupe aussi l'accès réseau de JARVIS ; on ne pourra pas le
reconnecter à distance.

Après la mise à jour du dépôt, relance `nc-jarvis deployer` pour que le serveur de JARVIS reçoive cette nouvelle action
(c'est toi qui le fais, la mise à jour ne le lance jamais).

## Contrat des fournisseurs VPN (`nc-vpn`)

Ce que la fenêtre VPN lit et lance pour NordVPN, Proton VPN et Mullvad. Tout est en arguments (jamais une ligne de shell).
Ce contrat est la version 1.

### Lire : `nc-vpn fournisseurs-json`

```json
{"contrat": 1, "fournisseurs": [
  {"id": "nord", "nom": "NordVPN", "etat": "pret", "message": "Compte NordVPN connecté.",
   "pays": [{"code": "FR", "nom": "France"}], "pays_actif": "FR", "connecte": true,
   "peut_login": false, "probleme": "", "pilotage": "direct"},
  {"id": "proton", "nom": "Proton VPN", "etat": "pilote_appli", "message": "…",
   "pays_actif": "", "connecte": false, "peut_login": true, "probleme": "", "pilotage": "appli"},
  {"id": "mullvad", "nom": "Mullvad", "etat": "absent", "message": "…",
   "pays_actif": "", "connecte": false, "peut_login": false, "probleme": "", "pilotage": "direct"}
]}
```

| Clé | Sens |
| --- | --- |
| `id` | `nord`, `proton` ou `mullvad` |
| `etat` | `absent` : commande introuvable (silencieux) ; `sans_compte` : client installé, pas de compte connecté (ou client inutilisable, ou appareil révoqué, voir `probleme`) ; `pilote_appli` : Proton seulement, sans sa CLI (application graphique seule) ou avec l'application ouverte (`probleme` vaut alors `appli_ouverte`) : tout (compte, pays, connexion) se fait dans l'application ; `pret` : compte connecté |
| `message` | une phrase, dans la langue de la session (français ou anglais) ; texte brut |
| `pays` | **seulement si `etat` vaut `pret`** : `[{"code": "FR", "nom": "France"}]`, code en deux lettres majuscules ; le nom vient TOUJOURS du code ISO (table interne français ou anglais selon la langue du bureau), jamais d'une CLI ; liste triée par ce nom. Absente à l'état `pilote_appli` de Proton (le pays se choisit dans l'appli) |
| `pays_actif` | code du pays du tunnel de ce fournisseur, ou `""` |
| `connecte` | ce fournisseur a un tunnel monté (toujours `false` hors des états `pret` et `pilote_appli`) ; pour Proton, une connexion NetworkManager « ProtonVPN … » (interface `proton0`) est ACTIVE (jamais `protonvpn status`) |
| `peut_login` | `nc-vpn fournisseur ID login` est utile (installé, pas de compte connecté, et possible ; pour Proton : « Se connecter au compte » à l'état `sans_compte`, « Ouvrir Proton VPN » à l'état `pilote_appli`) |
| `probleme` | `""`, ou `permission` (groupe `nordvpn` manquant), `consentement` (première exécution de `nordvpn` : question interactive), `demon` (service arrêté), `delai`, `lancement`, `revoque` (Mullvad : l'appareil a été révoqué), `illisible` (Proton : `protonvpn info` n'a rien donné de lisible), `non_verifie` (Proton : le compte n'a pas encore été vérifié, voir plus bas), `appli_ouverte` (Proton : l'application graphique tourne, la CLI refuse de travailler en même temps) ; le `message` dit quoi faire |
| `pilotage` | `direct` : on pilote la CLI ; `appli` : on ouvre seulement l'application officielle (Proton sans sa CLI, ou application ouverte) |
| `pays_probleme` | `""`, ou `delai` : Proton prêt dont `protonvpn countries list` a dépassé son délai (20 s). Le compte reste valide (`etat` vaut `pret`) et `pays` est vide ; l'île affiche « Liste des pays indisponible (délai dépassé) » avec un bouton « Réessayer » qui relance `fournisseurs-json --verifier-proton` (mêmes gardes : verrou, pas pendant un tunnel « activating »). Toujours `""` hors de l'état `pret`. Champ ajouté sans changer de version : un client ignore les champs qu'il ne connaît pas |

Jamais dans la sortie : adresse e-mail, nom ou numéro de compte, jeton, adresse IP, URL de connexion. Identifiants lus par la CLI mais jamais gardés : Proton (`protonvpn info` écrit le nom du compte, `connect` écrit une IP) et Mullvad ; seuls des booléens et un code pays en sont tirés. Le numéro de compte Mullvad est lu par la CLI mais jamais gardé :
`mullvad account get` n'est lancé que pour un oui/non, sa sortie est lue en mémoire (4 Kio au plus), analysée puis jetée, et n'apparaît dans aucun
message, journal, erreur ni JSON. Toutes les lectures de CLI sont réellement bornées (64 Kio, 1 Mio pour `mullvad relay list`) : passé la borne, ou le délai,
le groupe de processus est arrêté (SIGTERM puis SIGKILL).

### Agir

- `nc-vpn fournisseur ID connecter CC` : `CC` doit être exactement deux lettres majuscules d'un pays ISO (`FR`) ; sinon refus (code 1) sans appel.
  Nord : `nordvpn connect NOM` (le nom exact donné par `nordvpn countries`). Mullvad : `mullvad relay set location fr`, puis `mullvad connect`.
  Proton avec sa CLI : `protonvpn connect --country FR` (le code ISO en majuscules, forme exacte des sources) ; sans la CLI, ouvre l'application officielle (choisir le pays s'y fait).
- `connecter` et `deconnecter` (fournisseurs et `mullvad …`) prennent le même verrou que `connecter UUID` : une 2e demande en même temps répond `occupe`.
  `fournisseur nord connecter` et `fournisseur proton connecter` (avec la CLI) sont refusés (`killswitch_actif`) si le kill switch NetworkManager est actif.
  Si l'application graphique Proton tourne, la CLI refuse de travailler : message « Ferme l'application Proton VPN pour piloter depuis l'île », code 1, et nous ne la fermons jamais.
- `nc-vpn fournisseur ID deconnecter` : Nord `nordvpn disconnect` ; Mullvad `mullvad disconnect` ; Proton `protonvpn disconnect` (sans la CLI : ouvre l'application).
- `nc-vpn fournisseur ID login` : le parcours officiel. Nord : `nordvpn login`, puis l'adresse qu'il donne est ouverte avec `xdg-open` seulement si
  c'est une URL https de `nordaccount.com` ou `nordvpn.com` (port 443, sans identifiant) ; elle est d'abord comparée, brute, à une forme stricte
  (hôte en minuscules, chiffres et `-`, aucune barre oblique inverse, guillemet, accent grave, accolade, `|`, `^` ; `%` permis seulement dans le chemin
  et la requête), puis `urlsplit` doit lire exactement le même hôte ; elle n'est jamais affichée. Proton : ouvre l'application officielle si elle est installée, sinon une fenêtre `kitty` (argv) qui demande le nom de compte dans le terminal puis lance `protonvpn signin -- NOM` ; le mot de passe, le code TOTP ou la clé de sécurité sont demandés par Proton lui-même. L'appel attend la fermeture de la fenêtre. Dans l'île, le bouton « Se connecter au compte » (tous les fournisseurs) ferme d'abord la fenêtre VPN, qui garde sinon tout le clavier (focus exclusif) et avalerait le nom de compte ou le mot de passe tapés dans le terminal ; le login tourne dans un processus à part (il ne grise pas les autres actions) et l'état est relu à sa fin, avec une nouvelle vérification explicite du compte Proton. Avec `-- NOM`, l'option `--totp` de `protonvpn signin` ne peut pas être donnée : un compte protégé par une clé de sécurité doit avoir la clé sous la main, ou se connecter par l'application Proton. Ouvrir la fenêtre ou lancer la CLI peut déclencher une demande de déverrouillage du trousseau de clés (Proton y lit sa session).
  Mullvad : ouvre l'application graphique (`mullvad-vpn`) ou dit de lancer `mullvad account login` dans un terminal.
  Aucune saisie de mot de passe, de numéro de compte ni de jeton chez nous. La fenêtre relit `fournisseurs-json` au retour.

Code de sortie : 0 en cas de succès, 1 avec un message `nc-vpn : …` sur la sortie d'erreur, 2 pour une commande inconnue.
Les messages d'erreur passent par un filtre (URL, e-mail, longues suites de chiffres ou de lettres retirés).

### Comment c'est décidé (sources officielles)

- **Nord** (dépôt NordSecurity/nordvpn-linux, dossier `cli/`) : sous-commandes `account`, `countries`, `connect`, `disconnect`, `status`, `login` (options
  `--callback`, `--token`, que nous n'utilisons pas). Connecté si `nordvpn account` écrit « Account information » (sa sortie, qui contient l'e-mail, n'est
  jamais gardée). `countries` donne des noms avec `_` (pas de code) : un code ISO est associé par une table intégrée, les noms inconnus sont écartés.
  `login` écrit « Continue in the browser: URL » et n'ouvre pas lui-même le navigateur. Le consentement (statistiques) est une question interactive
  « (y/n) » : stdin est fermé et la commande est tuée au délai ; le message dit d'ouvrir un terminal. « Permission denied » sur le socket : message sur le
  groupe `nordvpn`, aucune élévation.
- **Proton** (ProtonVPN/proton-vpn-cli, paquet `proton-vpn-cli` 1.0.5, commande `protonvpn`, module `proton.vpn.cli` ; fichiers lus sans jamais lancer la
  commande) : trois états comme les autres fournisseurs, d'après `protonvpn info`.
  - `info` écrit `Account: 'NOM'` (`'None'` sans compte, `commands/account.py` et `core/api.py`) : seul « un compte existe » est gardé, NOM est jeté.
    La liste des pays est `countries list` (`countries` seul est un groupe sans action) : un tableau « Country  Code », code en majuscules
    (`commands/location_discovery.py`) ; seul le code est gardé, le nom vient de la table ISO. Sans compte elle écrit « Authentication required… » (session
    perdue : état `sans_compte`).
  - **`protonvpn status` n'est jamais lancé** : ce n'est pas une lecture pure. Il passe par `get_vpn_connector` (`commands/server.py` ; `core/api.py`
    l.121-139), donc par `initialize_state` puis `_apply_kill_switch_setting` (`core/vpnconnector.py` l.284-306) : il RÉAPPLIQUE le réglage du kill
    switch de Proton (et sa protection IPv6), ce qui, pendant un `connect` lancé ailleurs, peut les désactiver. Le tunnel, son serveur et son pays se lisent
    dans NetworkManager : la connexion s'appelle « ProtonVPN NOM_DU_SERVEUR » (`backend/networkmanager/core/networkmanager.py` l.221, `_get_servername` ;
    `protocol/wireguard/wireguard.py` l.153, `openvpn/openvpn.py` l.249, `protun/protun.py` l.175) et son interface est `proton0`
    (`VIRTUAL_DEVICE_NAME`, `wireguard.py` l.97, `openvpn.py` l.201, `protun.py` l.129). Le nom du serveur donne le pays : `IT#23` donne IT, `UK#3` donne
    GB ; Secure Core : si le 1er segment est CH, IS ou SE et le 2e un pays ISO, c'est le 2e (`CH-US#1` donne US), sinon le 1er (`US-CA#12` donne US).
    Les formes `CH-US#1` et `US-CA#12` ne sont pas dans les sources lues (seul `IT#23` y figure) : c'est la règle retenue.
  - **`info` et `countries list` ne sont pas sûrs en arrière-plan** : ils n'appellent pas `get_vpn_connector` eux-mêmes (`Controller.create` fait
    `get_settings`, donc `ProtonVPNAPI.load_settings`, `core/api.py` l.218), mais `load_settings` passe par `_force_protun_for_free_users` puis
    `_should_force_protun_for_free_users` (l.150-180) qui appelle `get_vpn_connector` pour un compte gratuit quand le drapeau PROTUN_ONLY est présent : le même
    effet de bord est possible. Règle : lire l'état de Proton par sa CLI peut réappliquer ses protections ; noctalia-config ne le fait jamais en arrière-plan.
    `info` et `countries list` ne sont lancés que par `nc-vpn fournisseurs-json --verifier-proton`, demandé par l'île à l'ouverture de l'onglet Proton (une
    fois par ouverture de la fenêtre) ou à la fin d'une connexion au compte ; jamais par un événement NetworkManager, au démarrage, par `relire()`, par
    l'indicateur ni par `fournisseurs-json` seul. Même alors, rien n'est lancé si un tunnel Proton monte (NetworkManager « activating ») ou si le verrou des
    changements est tenu (ils prennent ce verrou le temps de la lecture). Sans l'option, l'état du compte et la liste des pays viennent du dernier relevé,
    gardé dans `$XDG_RUNTIME_DIR/nc-vpn-proton.json` (mémoire vive, mode 0600) : seulement `compte` (oui/non), `appli_ouverte`, `probleme` et des codes
    pays ISO, jamais un nom de compte. Sans relevé : `sans_compte` avec `probleme` = `non_verifie`.
  - `connect --country X` : `X` est un code à deux lettres (insensible à la casse) ou un nom anglais (`core/controller.py`, `validate_country_input` :
    deux caractères = code) ; nous donnons toujours le code ISO MAJUSCULE, validé avant tout appel. Sur le palier gratuit, choisir un pays est refusé par
    la CLI (« not available on the free plan ») : message prévu, jamais la sortie brute. Un compte payant dont la requête n'aboutit pas peut recevoir un
    code 0 sans « Connected to » : c'est traité comme un refus. `disconnect` écrit `Disconnected.`.
  - Aucune question interactive en dehors de `signin` (mot de passe `getpass`, code `click.prompt`, clé de sécurité) : stdin est fermé et chaque lecture a
    un délai. `signin` demande un NOM D'UTILISATEUR en argument obligatoire : la fenêtre `kitty` le lit dans le terminal.
  - Conflit avec l'application graphique (`proton/vpn/cli/__init__.py`, `_vpn_gui_running`) : si le nom `proton.vpn.app.gtk` est sur le bus de session, la
    CLI écrit « Error: Proton VPN desktop app is currently running » sur la sortie standard et sort avec le code 0, avant toute commande. Nous lisons ce
    texte : état `pilote_appli` avec `probleme` = `appli_ouverte`, ou refus clair d'une action. Nous ne fermons jamais l'application. Non vérifié : si les
    deux programmes partagent la même session de compte (une connexion faite dans l'application est-elle vue par la CLI ?) : le code lu ne le dit pas.
  - CLI absente mais application `protonvpn-app` présente : l'ancien état `pilote_appli` (jamais `sans_compte` : le compte est celui de l'appli, qu'on ne
    lit pas ; sa connexion NetworkManager « ProtonVPN SERVEUR » n'existe que pendant la connexion). Ni l'une ni l'autre : `absent`. Dans la fenêtre, le tunnel
    NetworkManager « ProtonVPN … » est la ligne de la carte principale ; l'état du fournisseur ne la double pas.
- **Mullvad** (mullvad/mullvadvpn-app, `mullvad-cli/src/cmds/account.rs`) : `status` n'affiche PAS d'avertissement de compte quand il est déconnecté.
  `account get` écrit « Not logged in on any account », « The current device has been revoked » ou « Mullvad account: <numéro> » (code 0 dans les
  trois cas) : seul le oui/non en est tiré, le numéro est lu mais jamais gardé ; `relay list` écrit « Nom (code) » par pays, les villes et relais en retrait.
