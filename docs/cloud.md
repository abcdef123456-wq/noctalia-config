# Cloud JARVIS

Le Cloud JARVIS est un espace de fichiers personnel sur **ton** serveur JARVIS. Il sert à passer des fichiers d'un de
tes PC à l'autre. Il n'y a pas de partage avec d'autres personnes : tous les PC associés au même serveur voient le même
espace.

`nc-cloud` est le client en terminal. Les réglages ont une section « Cloud JARVIS » (ci-dessous). Le panneau et le
dépôt d'un fichier sur l'île viendront ensuite ; ils passeront par `nc-cloud --json`.

## Activer

- Le serveur JARVIS doit être en mode serveur, avec le cloud activé de son côté. En mode local, le cloud est coupé.
- Ce PC doit déjà connaître le serveur : `nc-assistant configurer` (adresse et clé dans `~/.config/nc/assistant.conf`).
- Le jeton de ce PC va dans le trousseau de la session, par `secret-tool` : paquet `libsecret` sur Arch et Fedora,
  `libsecret-tools` sur Debian, `secret-tool` sur openSUSE. Il faut un trousseau ouvert (gnome-keyring, KeePassXC,
  KWallet…).
- `IA_MODE=non` ne coupe pas le cloud : ce n'est pas une IA. Sans serveur configuré, il n'y a rien.

Rien ne tourne en fond : aucun relevé, aucune file d'attente. Le serveur n'est interrogé que quand tu lances une commande.

Dans les réglages (`nc-reglages`, section « Cloud JARVIS ») : `CLOUD_JARVIS` est à `non` par défaut. À `oui`, la
section montre si ce PC est associé (lu sur ce PC, sans appel au serveur) et les boutons « Vérifier », « Associer » ou,
une fois associé, « État et quota » et « Dissocier » (avec confirmation). Chaque bouton lance la commande `nc-cloud`
du même nom ; sa dernière ligne (« Tout est prêt. », « À faire : … », « Utilisé : … sur … ») s'affiche en bas de la
fenêtre.

`CLOUD_JARVIS` coupe le bureau (réglages, panneau, recherche), pas une commande `nc-cloud` tapée exprès dans le
terminal ; seule `nc-cloud fenetre`, une action du bureau, refuse quand il n'est pas à `oui`.

## Le panneau de l'île

`nc-cloud fenetre`, l'entrée « Cloud JARVIS » de la recherche de l'île (seulement avec `CLOUD_JARVIS=oui` et ce PC
associé) ou `qs -c nc-ile ipc call ile cloud` ouvrent la fenêtre « Cloud JARVIS », sur l'écran qui a le focus à ce
moment ; elle y reste (changer d'écran ne la déplace pas) et ne se ferme que par toi (Fermer ou Échap). Le chemin en haut
ramène à un dossier parent.

- Un clic choisit une ligne et montre ses actions sous son nom ; un double-clic l'ouvre : un dossier, on y entre ; un
  fichier, une copie privée s'ouvre avec l'application par défaut (`nc-cloud ouvrir`, types sûrs seulement).
- Créer un dossier ou un fichier vide (le champ en haut). Télécharger un fichier dans le dossier Téléchargements
  (`XDG_DOWNLOAD_DIR`) ; s'il y existe déjà, rien n'est écrasé : le bouton devient « Remplacer ».
- Renommer, et Déplacer… : on parcourt les dossiers, puis « Déplacer ici » (jamais un dossier dans lui-même).
- Ou glisse une ligne : un aperçu suit le pointeur ; lâchée sur un dossier de la liste, elle y va ; sur « ↑ » (en tête
  du chemin), elle remonte dans le dossier parent sans que tu quittes le dossier affiché. La destination s'allume ; sur
  elle-même, sur un fichier ou dans son propre dossier, rien ne s'allume et rien ne part. Le serveur vérifie le reste.
- Supprimer… demande d'abord sur la ligne : « suppression définitive, toutes ses versions » ; pour un dossier, d'abord
  l'aperçu (« N fichier(s), M dossier(s), taille »). Si le dossier a changé entre-temps, rien n'est supprimé : nouvel
  aperçu, nouvelle question.
- Chaque action n'apparaît que si le serveur annonce sa capacité (déplacer, aperçu, suppression de dossier).

### Ouvrir dans Fichiers

« Ouvrir dans Fichiers » (en haut du panneau) ou `nc-cloud fichiers` monte le cloud par GVfs en WebDAV, ajoute un favori
« Cloud JARVIS » à la barre latérale du gestionnaire de fichiers, puis l'ouvre. C'est le serveur qui décide de la
lecture seule (le panneau dit le mode annoncé). Rien ne se monte tout seul : ni à la connexion, ni en fond.

- Identifiants : l'identifiant de ce PC et son jeton, donnés à GVfs dans le processus de nc-cloud seulement (jamais dans
  l'adresse, la ligne de commande, un fichier ni l'environnement), et jamais enregistrés par GVfs. Ils ne répondent qu'à
  UNE demande de mot de passe sans domaine ni proxy ; toute autre demande (proxy, domaine, seconde demande) et toute
  question de GVfs (certificat inconnu…) sont refusées (code 15 pour une demande inattendue).
- GVfs suit le proxy du système, pas la règle « pas de proxy » de nc-cloud : si un proxy s'applique à l'adresse du
  cloud, le montage est refusé (code 14). Le serveur ne doit jamais rediriger le WebDAV vers un autre hôte.
- Si le montage échoue APRÈS l'envoi du jeton, le message le dit : vérifie avec `nc-cloud verifier`, et dans le doute
  dissocie puis associe ce PC (le jeton a pu être vu par un intermédiaire).
- En `https://`, le montage vise le nom du serveur (certificat vérifié par GVfs) ; en `http://` (ce PC, réseau privé,
  Tailscale), il vise l'adresse IP vérifiée par nc-cloud, jamais le nom ; `http://` vers Internet est refusé.
- Le favori est une ligne du fichier `~/.config/gtk-3.0/bookmarks`, sans identifiants ; les autres lignes ne bougent
  pas, au caractère près. Si ce fichier ne peut pas être modifié (un lien de dotfiles, ou pas de dossier `gtk-3.0`), le cloud est monté
  et ouvert quand même, et le message dit que le favori manque. `nc-cloud demonter` et `nc-cloud dissocier` démontent
  l'adresse notée au montage (seulement si la racine du montage est exactement celle du cloud) et retirent le favori.
- Il faut deux paquets facultatifs, qu'`install.sh` n'installe pas : sans eux, le bouton n'apparaît pas, et
  `nc-cloud verifier` comme `nc-diag` disent lequel manque.

| Distribution | gi (Gio) | WebDAV de GVfs |
| --- | --- | --- |
| Arch | `python-gobject`, `glib2` | `gvfs-dnssd` |
| Debian 13 | `python3-gi`, `gir1.2-glib-2.0` | `gvfs-backends` |
| Fedora | `python3-gobject-base`, `glib2` | `gvfs` |
| openSUSE | `python3-gobject`, `typelib-1_0-Gio-2_0` | `gvfs-backends` |

### Envoyer des fichiers

- Un petit nuage dans la pilule (à côté de l'heure, avec `CLOUD_JARVIS=oui` et ce PC associé) : un clic ouvre le
  panneau ; le survoler n'ouvre pas l'île. Pendant un envoi, il devient une flèche d'envoi en couleur d'accent, et une
  notification dit la fin.
- Glisse des fichiers sur l'île fermée : un cadre d'accent apparaît ; au lâcher, le panneau s'ouvre avec les fichiers
  reçus et le dossier de destination (le dossier affiché). Rien ne part avant « Envoyer ici ». C'est une copie : les
  fichiers restent où ils sont. L'île ouverte (la page JARVIS et ses pièces jointes) garde son propre dépôt.
- « Importer des fichiers… » ouvre le sélecteur de fichiers du bureau (le portail, `nc-cloud choisir`) ; l'annuler garde
  la sélection d'avant. Il faut un portail qui sait choisir des fichiers : `xdg-desktop-portal-gtk`, installé par
  `install.sh` sur les 4 distributions (celui de Hyprland ne le fait pas). Sans lui, le panneau dit de déposer les
  fichiers sur l'île, et `nc-diag` le signale. Fermer le panneau referme le sélecteur ; il ne reste ouvert qu'une heure
  au plus.
- 8 fichiers locaux au plus ; le reste est écarté et le panneau le dit. Un dossier, un lien ou un fichier spécial est
  refusé ligne par ligne, comme une adresse qui n'est pas un chemin net (`/` final, `.` ou `..`).
- Avant « Envoyer ici », chaque fichier montre son chemin complet et sa taille (`nc-cloud examiner`, rien ne part). Un
  fichier protégé (la liste des pièces jointes de JARVIS : `~/.ssh`, `~/.gnupg`, `~/.config/nc`, trousseaux, `.env`,
  clés…) ne partira pas, ni par le panneau ni par `nc-cloud deposer`. Un fichier caché du dossier personnel s'affiche
  en orange, et le bouton devient « Envoyer quand même ».
- La liste des envois : progression par fichier, « Annuler l'envoi », résultat de chacun. Un nom déjà pris : « Conserver
  les deux », « Remplacer » ou « Annuler ». Une coupure (hors ligne) : « Reprendre / vérifier » ; à l'ouverture du
  panneau, les envois interrompus de ce PC (après un redémarrage, par exemple) y apparaissent aussi.
- Fermer le panneau n'arrête pas un envoi. À la première publication de chaque envoi, le dossier affiché et le quota
  sont relus une fois (panneau fermé : à sa réouverture).
- « Effacer les terminés » retire de la liste les envois publiés, annulés, refusés ou en échec (jamais ceux en cours,
  interrompus ou en conflit), sans rien demander au serveur ni toucher un fichier ; ces lignes partent seules après 24 h.
  La liste vit dans l'île : un redémarrage de l'île la vide (les envois interrompus reviennent, eux).

Tout passe par `nc-cloud --json` ; panneau fermé, rien ne tourne, sauf un envoi lancé. Sans DEST, `nc-cloud telecharger ID` utilise aussi ce
dossier Téléchargements.

### Annuler une suppression

Le serveur efface pour de bon. Avant de supprimer un fichier depuis le panneau, nc-cloud en garde une copie privée sur
ce PC (`~/.cache/nc-cloud/corbeille/`, dossiers 0700, fichiers 0600). La copie est téléchargée AVANT la suppression et
son empreinte est vérifiée. Si la copie échoue, rien n'est supprimé, et la question revient : « supprimer quand même,
sans copie ? ».

- Après la suppression, un bandeau « Supprimé : nom · Annuler » reste 20 secondes.
- Une ligne « Corbeille locale » reste dans le panneau tant que la copie existe : « Remettre » redépose le fichier au
  même endroit. Il reçoit un nouvel identifiant, et l'historique de ses versions est perdu.
- Une copie est gardée 24 h. Toutes les copies tiennent dans 500 Mio : les plus vieilles cèdent la place.
- Un fichier de plus de 500 Mio n'a pas de copie : la question le dit avant.
- Les dossiers n'ont pas de copie : leur question dit toujours « définitive ».

En ligne de commande : `nc-cloud supprimer ID --revision R --copie --dossier PARENT`, `nc-cloud corbeille` (la liste)
et `nc-cloud corbeille --remettre COPIE`.

### Place utilisée, dans le centre de contrôle

Le centre de contrôle de l'île a un module « Cloud » : la place utilisée sur le quota (« 1 Mo sur 20 Go »). Il
n'existe qu'avec Cloud JARVIS actif et ce PC associé. La valeur est demandée à l'ouverture du centre, au plus une fois
par 10 minutes, et gardée en mémoire ; île fermée, rien n'est demandé. Hors ligne, la dernière valeur reste, en gris.
Un clic ouvre le panneau. Comme les autres modules, il se masque et se déplace (le crayon).
### Mon bureau me suit

Dans les réglages, section Cloud JARVIS, deux boutons, chacun en deux temps :

- « Sauvegarder mes réglages dans le cloud » prépare d'abord l'archive, sur ce PC (`nc-sauvegarde creer
  --pour-le-cloud`). Tu vois le nombre et les noms des réglages qui partent. « Envoyer » la dépose dans le dossier
  « Bureau » du cloud, sous un nom daté.
- « Reprendre mes réglages depuis le cloud » télécharge la plus récente dans un dossier privé et montre sa date et
  les réglages qu'elle changerait. « Remettre » la restaure, toujours SANS `--avec-code`.

Ce qui part et revient : une liste blanche, à un seul endroit (`SECTIONS_CLOUD` de nc-reglages, commande
`nc-reglages pour-le-cloud`), appliquée à l'envoi ET à la reprise.

- Un réglage passe s'il est connu du catalogue, si sa section part, et si sa valeur est valide pour son genre.
- Les sections qui partent : pages de l'île, île, notifications, apparence, animations, lumière nocturne, barre et
  dock, fenêtres, fonds d'écran, son et luminosité, clavier et souris, terminal.
- Même dans ces sections, ne partent jamais : le VPN, le verrou, les sessions, l'IA, la ville de la météo, les polices
  et le thème du curseur, l'agent de code, l'écran (VRR), aucun texte libre, aucun dossier.
- Restent ceux de chaque PC : énergie, veille, applications, intelligence artificielle, agents IA, Google, Garmin,
  Cloud JARVIS, mises à jour, captures.
- À la reprise, c'est une fusion : seuls les réglages de la liste changent, toutes tes autres lignes restent.

Les autres fichiers :

- Partent aussi tes raccourcis d'applications (aucune commande), tes palettes et ta photo de profil.
- Une palette part si c'est un fichier ordinaire à un seul lien, avec un nom simple. La photo part si c'est une image.
- Ne partent jamais : aucun fichier qui lance du code, aucun fond d'écran, ni `style.conf` ni `style-avant`
  (`nc-reglages appliquer` les refait).
- Les en-têtes de l'archive ne portent pas ton nom d'utilisateur.

Une archive venue du cloud est refusée en entier si elle contient quoi que ce soit d'autre. Elle est lue avec des
bornes :

- 32 Mio au plus, aussi au téléchargement ;
- un seul flux gzip, décompressé avec un plafond de 80 Mio ;
- 500 éléments au plus ;
- seulement des fichiers ordinaires, et des en-têtes PAX de 8 Kio au plus, vérifiés avant tarfile.

Si le serveur sait supprimer, les 5 sauvegardes les plus récentes sont gardées, jamais celle qu'on vient d'envoyer.
Un nom daté de plus de 10 minutes dans le futur est ignoré : il n'est ni choisi, ni compté, ni supprimé, et c'est dit.
Un fichier d'une autre forme n'est jamais touché.

Limite : les raccourcis remis remplacent ceux de ce PC (comme `nc-sauvegarde restaurer`). Les anciens sont gardés
dans `~/.cache/nc/avant-restauration`.

### Récents

En haut du panneau, « Récents » montre les 5 derniers fichiers que CE PC a envoyés ou ouverts ; un clic en ouvre un.
La liste est locale (`~/.local/state/nc-cloud/recents.json`, 0600 : ids et noms seulement), jamais demandée au
serveur. Un fichier supprimé ailleurs en sort au premier refus. « Effacer les récents » la vide, et `dissocier`
aussi.

### Une note glissée sur l'île

Un TEXTE glissé sur l'île fermée (une phrase d'une page, d'un message…) ouvre le panneau avec son aperçu. Rien ne part
avant « Enregistrer la note ». La note devient un `.txt` (UTF-8) dans le dossier « Notes » de la racine, créé s'il
manque, nommé d'après ses premiers mots, avec la date et l'heure. Un nom déjà pris reçoit un suffixe « (2) » : rien
n'est écrasé. 64 Kio au plus. Une adresse de fichier glissée suit l'envoi de fichiers ci-dessus.

Le texte passe par l'entrée standard de `nc-cloud note`, jamais par ses arguments (lisibles de tous dans la liste des
processus). Le fichier local (`~/.local/state/nc-cloud/notes/`, 0600) disparaît après l'envoi. Il ne reste que si
l'envoi est interrompu, pour `nc-cloud reprendre`.

### Envoyer une capture d'écran

Avec Cloud JARVIS actif et ce PC associé, la notification d'une capture (`nc-capture`) a un bouton « Envoyer au
cloud ». Il dépose la capture dans le dossier « Captures » de la racine (créé s'il manque), puis une notification dit
le résultat : envoyée, cloud injoignable, ou même nom déjà là (rien n'est remplacé). La capture locale ne bouge pas.
Le bouton n'apparaît que d'après le réglage et le fichier d'association de ce PC : aucun appel au serveur pour le
décider, et rien ne part sans le clic.

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
| `nc-cloud fichiers` | monte le cloud dans le gestionnaire de fichiers (WebDAV), pose le favori « Cloud JARVIS », l'ouvre |
| `nc-cloud demonter` | démonte et retire le favori (à lancer aussi si tu coupes `CLOUD_JARVIS`) |
| `nc-cloud choisir` | le sélecteur de fichiers du bureau (portail) ; écrit les fichiers choisis, n'envoie rien |
| `nc-cloud lister [ID] [--suite CURSEUR]` | une page d'un dossier (la racine par défaut), avec la commande de la suite |
| `nc-cloud dossier PARENT NOM` | crée un dossier (`root` pour la racine) |
| `nc-cloud deposer [--dans ID \| --racine NOM] FICHIER…` | envoie jusqu'à 8 fichiers ordinaires (dossiers et liens refusés, un message chacun) |
| `nc-cloud recents [--effacer]` | les 5 derniers fichiers envoyés ou ouverts par ce PC (liste locale) |
| `nc-cloud bureau preparer\|envoyer\|telecharger\|restaurer\|oublier` | tes réglages dans « Bureau » du cloud, en deux temps |
| `nc-cloud note` | enregistre le texte lu sur l'entrée standard dans « Notes » (64 Kio au plus) |
| `nc-cloud examiner FICHIER…` | taille, fichier caché ou refusé, de chaque fichier ; n'envoie rien |
| `nc-cloud reprendre [N]` | liste les envois interrompus ; avec N, reprend celui-là |
| `nc-cloud telecharger ID DEST [--dossier PARENT] [--remplacer]` | télécharge un fichier (de la racine, ou de PARENT) |
| `nc-cloud supprimer ID --revision REV [--recursif --arbre TREE]` | supprime un fichier, ou un dossier si le serveur le sait (voir plus bas) |
| `nc-cloud entree ID [--dossier PARENT]` | une entrée par son id, avec sa révision actuelle |
| `nc-cloud deplacer ID --revision REV --vers PARENT [--nom NOM]` | déplace et/ou renomme (même id, même historique) |
| `nc-cloud renommer ID --revision REV NOM` | renomme dans le même dossier |
| `nc-cloud apercu ID` | ce qu'une suppression retirerait : fichiers, dossiers, taille, et l'arbre (`tree_revision`) |
| `nc-cloud creer PARENT NOM` | crée un fichier vide |
| `nc-cloud ouvrir ID [--dossier PARENT]` | ouvre une copie privée du fichier avec l'application par défaut |

`--json` donne une ligne JSON par événement : `progression`, `resultat` (un par fichier : `publie`, `refuse`, `echec`,
`annule`, `telecharge`, `supprime`, `deplace`, `ouvert`), `conflit`, `erreur`, et `verification`, `page`, `etat`, `envois`,
`entree`, `apercu`.

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

## Suppression, déplacement, renommage

Chaque action n'existe que si le serveur l'annonce, sinon « ce serveur ne sait pas … » et rien ne part :
`features.file_delete` (supprimer un fichier), `features.directory_delete` (supprimer un fichier ou un dossier),
`features.delete_preview` (`apercu`), `features.entry_move` (`deplacer`, `renommer`).

- `--revision` est obligatoire : la révision montrée par `nc-cloud lister` ou `nc-cloud entree`. Elle part telle
  quelle (`If-Match`), jamais relue en douce : si l'entrée a changé depuis, rien n'est fait (code 6).
- Un dossier non vide ne se supprime qu'avec `--recursif` ET `--arbre TREE`, celui de `nc-cloud apercu ID` que tu as
  confirmé. Si quelque chose a changé dans le dossier depuis l'aperçu, rien n'est supprimé (code 6) : refais l'aperçu.
- Déplacer : un dossier ne va ni dans lui-même ni dans un de ses sous-dossiers, et un nom déjà pris n'est jamais
  écrasé (code 6). Après un déplacement, l'ancien et le nouveau dossier ont changé de révision.
- Le script ne demande pas de confirmation : c'est à l'appelant de la demander. Si la réponse se perd, relance la même
  commande : elle rejoue la même demande (même clé, noté dans `~/.local/state/nc-cloud`), sans risque. Rien n'est
  relancé tout seul.
- Une commande proposée à copier (après `apercu`, la suite de `lister`, les révisions de `entree` et `lister`) ne
  contient que des valeurs vérifiées et protégées pour le shell, sous la forme `--option=VALEUR` ; une valeur
  inattendue n'est jamais proposée.

## Ouvrir

`nc-cloud ouvrir ID` télécharge une copie dans `~/.cache/nc-cloud/ouverts/` (dossiers 0700, fichier 0400, jamais
exécutable), la relit depuis le disque pour vérifier son empreinte, puis l'ouvre avec `xdg-open` (ou `gio open`).
Seuls s'ouvrent d'ici les types d'une courte liste : images, audio et vidéo courants (PNG, JPEG, GIF, WebP, MP3,
Ogg, FLAC, MP4, WebM, MKV, WMV…, jamais SVG ni listes de lecture), texte simple (`.txt`, `.md`, `.csv`), PDF, documents OpenDocument et Office (odt, ods, odp, docx, xlsx, pptx). Le type est lu deux fois, dans le
contenu (`file`) et dans le nom, et les deux doivent être de la même famille : une archive nommée `.png` ne s'ouvre pas,
car hors d'un bureau connu `xdg-open` choisit l'application d'après le contenu. Seule la dernière extension du nom
compte (`x.txt.gz` : refusé), un nom sans extension ou avec `:`, `#`, `?` ou `;` est refusé, et la copie ne garde jamais
le nom du serveur tel quel : son extension est fixée d'après le contenu (`photo.PNG` devient `photo.png` ; un texte simple garde
sa propre extension `.txt`, `.md` ou `.csv`). Les types attendus d'après le nom sont dans une table de nc-cloud, la même
sur les 4 distributions (jamais `/etc/mime.types`, qui change de l'une à l'autre). Tout le reste (HTML, SVG, XML, listes de lecture, scripts, lanceurs, archives…), un
fichier de plus de 200 Mio, ou un PC sans `file` : « télécharge-le d'abord ».
L'empreinte vérifiée est celle que le serveur annonce lui-même : elle protège d'une coupure ou d'une corruption, pas
d'un serveur hostile ; c'est la liste des types qui protège. La copie n'est jamais renvoyée au serveur ; les copies de
plus de 24 h sont retirées au prochain `ouvrir`.

## Limites et ce qui n'est pas fait

- Pas de dossier entier, pas de partage avec d'autres personnes, pas de synchronisation automatique.
- Fichiers : la fin de session et les coupures réseau sont l'affaire de GVfs ; un montage perdu se refait par le bouton.
- Fichiers : aucun vrai montage GVfs n'a été essayé ici (tests avec un faux module `gi`). Pas vérifié : ce que gvfsd-dav
  fait de « jamais enregistrer », s'il suit une redirection vers un autre hôte, son invite exacte. Le premier essai réel
  est à faire avec un vrai serveur.
- Fichiers : le contrôle du proxy lit l'environnement de nc-cloud et les réglages du bureau ; un proxy posé seulement
  dans l'environnement du service de GVfs n'est pas vu. Le refus d'une demande qui parle de « proxy » dépend de la
  langue de GVfs : la vraie protection est le contrôle fait avant le montage.
- Une association dont la réponse se perd en route laisse un appareil sans jeton côté serveur : révoque-le depuis le
  serveur. Si Ctrl + C ou le trousseau interrompt l'association, ce PC est révoqué tout de suite ; si cette révocation
  échoue, le message donne l'identifiant de l'appareil à révoquer.
- Pas de délai total : un serveur très lent peut faire durer un transfert. Ctrl + C attend la fin de l'annulation côté
  serveur.
- Limites du serveur par défaut : 5 Gio par fichier, morceaux de 4 Mio, 8 envois en cours par PC, 20 Gio de quota
  partagé (versions conservées comprises).
