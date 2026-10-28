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
| `nc-vpn etat-json` | `{"contrat", "disponible": bool, "connexions": [C], "actives": [C]}` ; `C` = `{"uuid": str, "nom": str, "type": "vpn"\|"wireguard", "active": bool, "interface": str}` (`interface` vide si le tunnel n'est pas monté). NetworkManager ou nmcli absent : `{"contrat": 1, "disponible": false, "connexions": [], "actives": []}`, code 0. |
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
