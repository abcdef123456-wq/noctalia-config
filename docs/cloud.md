# Cloud JARVIS

Le Cloud JARVIS est un espace de fichiers personnel sur **ton** serveur JARVIS. Il sert à passer des fichiers d'un de
tes PC à l'autre. Il n'y a pas de partage avec d'autres personnes : tous les PC associés au même serveur voient le même
espace.

`nc-cloud` est le client en terminal. L'interface (glisser un fichier sur l'île) viendra plus tard ; elle passera par
`nc-cloud --json`.

## Activer

- Le serveur JARVIS doit être en mode serveur, avec le cloud activé de son côté. En mode local, le cloud est coupé.
- Ce PC doit déjà connaître le serveur : `nc-assistant configurer` (adresse et clé dans `~/.config/nc/assistant.conf`).
- Le jeton de ce PC va dans le trousseau de la session, par `secret-tool` : paquet `libsecret` sur Arch et Fedora,
  `libsecret-tools` sur Debian, `secret-tool` sur openSUSE. Il faut un trousseau ouvert (gnome-keyring, KeePassXC,
  KWallet…).
- `IA_MODE=non` ne coupe pas le cloud : ce n'est pas une IA. Sans serveur configuré, il n'y a rien.

Rien ne tourne en fond : aucun relevé, aucune file d'attente. Le serveur n'est interrogé que quand tu lances une commande.

## Associer ce PC

```sh
nc-cloud verifier          # ce qui est prêt ou manque
nc-cloud associer portable # le nom est facultatif (nom du PC par défaut)
```

L'association utilise la clé JARVIS une fois. Ensuite, chaque commande utilise le jeton de ce PC, jamais la clé. Le
jeton est rangé dans le trousseau et nulle part ailleurs. Si le trousseau le refuse, l'association est annulée et ce PC
est tout de suite révoqué sur le serveur. `nc-cloud dissocier` révoque ce PC sur le serveur, puis efface son jeton.

## Commandes

| Commande | Effet |
| --- | --- |
| `nc-cloud verifier` | serveur configuré, transport sûr, cloud annoncé, `secret-tool`, trousseau ouvert, PC associé |
| `nc-cloud associer [NOM]` | associe ce PC ; refusé s'il l'est déjà |
| `nc-cloud dissocier` | révoque ce PC, efface son jeton et ses envois interrompus |
| `nc-cloud etat` | état, quota et limites annoncés par le serveur |
| `nc-cloud lister [ID] [--suite CURSEUR]` | une page d'un dossier (la racine par défaut), avec la commande de la suite |
| `nc-cloud dossier PARENT NOM` | crée un dossier (`root` pour la racine) |
| `nc-cloud deposer [--dans ID] FICHIER…` | envoie jusqu'à 8 fichiers ordinaires (dossiers et liens refusés, un message chacun) |
| `nc-cloud reprendre [N]` | liste les envois interrompus ; avec N, reprend celui-là |
| `nc-cloud telecharger ID DEST [--dossier PARENT] [--remplacer]` | télécharge un fichier (de la racine, ou de PARENT) |
| `nc-cloud supprimer ID --revision REVISION` | supprime un fichier (jamais un dossier), seulement si le serveur l'annonce |

`--json` donne une ligne JSON par événement : `progression`, `resultat` (un par fichier : `publie`, `refuse`, `echec`,
`annule`, `telecharge`, `supprime`), `conflit`, `erreur`, et `verification`, `page`, `etat`, `envois`.

Un fichier refusé (nom refusé, trop d'envois en cours, quota) n'arrête pas les autres : chacun a son résultat. Hors
ligne, cloud coupé, PC révoqué, transport refusé ou serveur changé arrêtent toute la commande.

Codes de sortie :

| Code | Sens |
| --- | --- |
| 0 | fait |
| 1 | erreur |
| 2 | mauvais usage |
| 3 | hors ligne (serveur ou stockage injoignable) |
| 4 | PC non associé, ou révoqué, ou trousseau fermé |
| 5 | pas de cloud (serveur non configuré, mode local, option coupée) |
| 6 | conflit |
| 7 | quota dépassé ou disque du serveur plein |
| 8 | annulé |
| 9 | transport refusé (HTTP en clair sur Internet, redirection) |
| 10 | serveur changé |
| 11 | fichier source modifié |
| 12 | empreinte fausse |

## Sécurité

- **Transport** : la règle est celle de `nc-assistant` (`adresse_fixee`), appliquée en refus. HTTPS, ou HTTP seulement
  vers ce PC, un réseau privé ou Tailscale. En HTTP, ce sont les adresses résolues qui comptent (un nom `*.ts.net` doit
  donner une adresse Tailscale), et la connexion va à l'adresse vérifiée. Le certificat est toujours vérifié, aucune
  redirection n'est suivie, aucun proxy n'est utilisé.
- La clé et le jeton partent dans les en-têtes, jamais dans l'adresse ni sur la ligne de commande. Ils n'apparaissent
  dans aucun message, aucune sortie `--json`, aucun fichier d'état. Le corps d'une erreur du serveur n'est jamais
  affiché, seulement son code.
- **Identité** : le serveur, l'espace et l'appareil sont notés à l'association. Une réponse qui en annonce d'autres
  arrête l'opération (code 10).
- **Noms reçus** : les noms du serveur sont nettoyés à l'affichage (caractères de contrôle et de mise en forme
  invisibles retirés). Pour écrire un fichier, seul le dernier élément du nom est gardé, et `..` est refusé. Une réponse
  démesurée, trop imbriquée ou avec une demi-paire de substitution est refusée (« réponse du serveur invalide »).
- **Noms envoyés** : la règle du serveur, vérifiée avant l'envoi (240 octets au plus après normalisation NFC, aucun
  caractère de contrôle).

## Envois, reprise, conflits

- L'empreinte SHA-256 du fichier entier et celle de chaque morceau sont calculées en lisant le fichier par blocs : il
  n'est jamais chargé en entier en mémoire. Le fichier source n'est jamais modifié ni supprimé.
- Avant tout dépôt, une connexion authentifiée est vérifiée. Hors ligne, rien n'est mis en attente.
- Chaque envoi a une clé d'idempotence aléatoire et un manifeste privé dans `~/.local/state/nc-cloud/envois/` (dossier
  0700, fichiers 0600, sans jeton ni clé). Le bac à sable de JARVIS ne peut pas le lire.
- Après une coupure, `nc-cloud reprendre N` demande d'abord l'état au serveur. Si la publication avait réussi, il
  affiche ce succès et ne renvoie rien. Sinon, il revérifie le serveur et le fichier source, puis n'envoie que les
  morceaux manquants. Si le fichier source a changé (taille, date ou empreinte), l'envoi est annulé : dépose-le à
  nouveau.
- La révision du dossier de destination est relue avant chaque fichier. Si un autre PC publie dans ce dossier pendant
  l'envoi, une seule nouvelle intention est faite, puis le conflit est signalé.
- Un nom déjà pris se voit avant l'envoi (le serveur ne le refuse qu'à la publication) : rien ne part pour rien.
- **Conflit** (le nom existe, ou la version a changé) : rien n'est choisi tout seul. L'envoi est annulé, le conflit
  est signalé (ligne `conflit` avec l'entrée actuelle, code 6), et tu relances avec
  `--si-existe garder` (conserver les deux), `--si-existe remplacer:REVISION` (la révision montrée, un seul fichier)
  ou `--si-existe annuler`. Chaque nouvel appel est une nouvelle intention, avec une nouvelle clé.
- **Ctrl + C** (ou SIGTERM) annule l'envoi sur le serveur. Si la publication a gagné la course, le succès est affiché.
- `reprendre` regarde d'abord l'état de l'envoi : expiré, annulé ou invalidé (fichier supprimé par un autre PC), il est
  perdu, et rien n'est relu ni envoyé. Avant de reprendre, chaque morceau déjà reçu est comparé à la source. Si le
  dossier de destination a changé depuis, l'ancien envoi est annulé et un nouvel envoi part (une fois), en le disant.
- « Trop de demandes » (le limiteur du serveur) arrête la commande sans rien perdre : réessaie dans un instant.
- `telecharger` n'écrase pas un fichier existant sans `--remplacer`. Il écrit d'abord dans un fichier caché du même
  dossier (`.nc-cloud-…partiel`, nom court ; verrouillé : deux téléchargements vers le même fichier ne se mélangent pas ;
  refusé si ce fichier est un lien ou n'est pas à toi), vérifie la taille et l'empreinte du fichier écrit, puis renomme.
  Si le serveur l'annonce (`features.entry_by_id`), le fichier est lu par son identifiant ; sinon, il est cherché dans
  son dossier (`--dossier`). Après une coupure, relance la même commande : il reprend où
  il s'est arrêté (`Range` et `If-Range`).

## Suppression

Seulement si le serveur l'annonce (`features.file_delete`), sinon « ce serveur ne sait pas supprimer ». Un fichier à la
fois, jamais un dossier. `--revision` est obligatoire : la révision montrée par `nc-cloud lister`. Si le fichier a changé
depuis, rien n'est supprimé (code 6). Le script ne demande pas de confirmation : c'est à l'appelant de la demander. Si la
réponse se perd, relance la même commande : elle rejoue la même demande (même clé), sans risque.

## Limites et ce qui n'est pas fait

- Pas de déplacement ni de renommage, pas de suppression de dossier.
- Pas de dossier entier, pas de partage avec d'autres personnes, pas de synchronisation automatique.
- Pas d'interface graphique pour l'instant, ni d'ouverture dans le gestionnaire de fichiers (WebDAV en lecture seule).
- Une association dont la réponse se perd en route laisse un appareil sans jeton côté serveur : révoque-le depuis le
  serveur. Si Ctrl + C ou le trousseau interrompt l'association, ce PC est révoqué tout de suite ; si cette révocation
  échoue, le message donne l'identifiant de l'appareil à révoquer.
- Pas de délai total : un serveur très lent peut faire durer un transfert. Ctrl + C attend la fin de l'annulation côté
  serveur.
- Limites du serveur par défaut : 5 Gio par fichier, morceaux de 4 Mio, 8 envois en cours par PC, 20 Gio de quota
  partagé (versions conservées comprises).
