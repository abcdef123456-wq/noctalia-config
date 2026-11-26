# Île essentielle et Centre de contrôle

L’île Quickshell se concentre sur **l’essentiel**. Les 23 thèmes fournis ont leur propre dessin, île fermée **et ouverte**.
Changer de thème remplace la scène sans redémarrer. Chez Dracula, la même forme biseautée s’étire de la pastille
au panneau, avec un filet violet-rose et des commandes natives ; l’éventuel contour fermé reste réglable.
Chez Sakura, les commandes bordent un ticket de salon de thé illustré ; chez Gruvbox, ce sont les touches d’un magnétophone.
Les mêmes emplacements servent au **transport du lecteur** sur Musique et aux **filtres de la boîte** sur Notifications.
Les autres pages conservent leurs outils sous une version courte de l’illustration.
Le thème personnel **Pénombre de papier** bénéficie aussi d’une scène dédiée : une grue en origami sur papier brun.

Les dessins sont originaux. Références : [lunanoir21](https://github.com/lunanoir21/quickshell-dynamic-island)
pour l’idée d’un instrument qui change de fonction, [Alan-Betty](https://github.com/Alan-Betty/quickshell-DynamicIsland)
pour les activités intégrées et [Impasto](https://github.com/andreumassanet/impasto) pour la continuité entre barre et pages.

- **Île fermée** : heure, date optionnelle, météo brève, notifications non lues et réactions en direct
  (musique, volume, luminosité, minuteur, appel, enregistrement vidéo, agents actifs).
- **Île ouverte** : par défaut **Essentiel**, **Notifications** et **Musique** (lorsqu’un lecteur est actif),
  plus un accès direct au **Centre de contrôle** et à la **Recherche**.

Tous les réglages rapides et panneaux détaillés (Wi-Fi/Ethernet, Bluetooth, VPN, Concentration, Lumière nocturne,
Caféine, Mode jeu, Volume, Luminosité, Profils d’énergie, Système, Batterie, Santé, Météo, Agenda, Presse-papiers,
Minuteur, Fenêtres) vivent dans le **panneau Centre de contrôle dédié** (`Super + C`, icônes de la barre, ou bouton
« Centre de contrôle » sur l’île ; `qs -c nc-ile ipc call ile controle`).
Seul un **bouton extérieur de la barre** fournit une ancre : sous la barre haute, au-dessus de la barre basse ou
vers l’intérieur d’une barre latérale, sur le même écran. Si la place manque, la carte cherche un autre côté.
Depuis la barre native Noctalia, l’ancre est le point du clic. Depuis l’île ou le raccourci, le centre s’ouvre à son
emplacement normal. Dans le centre, les détails et le retour utilisent la même carte, sans la déplacer.

Dans **Réglages**, une action qui retourne des informations ou qui échoue affiche son résultat dans une boîte de
dialogue nommée, avec un texte sélectionnable. Une édition ordinaire continue d’afficher un statut discret.

Dans `nc-settings` (ou `nc-reglages`), **Pages de l’île** (île Quickshell seulement : le plugin Noctalia n'a pas ces
pages) permet tout de même de réactiver ou masquer à la carte chacune des 20 pages sur l’île. Les choix sont conservés
dans `~/.config/nc/reglages.conf` et relus sans redémarrage. Un « oui » déjà réglé est gardé. Exemple :

```sh
nc-settings set ILE_PAGE_ASSISTANT oui
nc-settings set ILE_PAGE_MUSIQUE non
nc-settings reset ILE_PAGE_ASSISTANT
```

Désactiver une page masque son accès sur l’île. Les réglages rapides restent disponibles dans le panneau Centre de
contrôle (`Super + C`). Si la page ouverte est désactivée, l’île choisit une page encore disponible. Si elles sont
toutes désactivées, elle se referme et reste en pilule ; le Spotlight reste disponible.
Les onglets défilent si nécessaire et suivent la page active. Les flèches et la molette changent de page ; les
thèmes à navigation horizontale ajoutent un raccourci par points si plus de quatre pages sont disponibles.

La page Agents affiche seulement les sessions non terminées. Les transitions de fin et leur notification sont
conservées ; une session qui reprend son travail réapparaît. Aucun fichier d’historique n’est supprimé.

La page Météo : position estimée par ipwho.is d'après ton IP (ville vide ou « auto »), météo par Open-Meteo.
Une ville saisie n'envoie que son nom à Open-Meteo. Ville introuvable : message dans la page, aucun appel à ipwho.is.

Validation isolée : `python3 -B -m unittest tests.test_island_pages tests.test_assistant_page -q`.
Les essais QML nécessitent Quickshell et QtTest (dépendance de test uniquement).

## Ancienne page Centre de contrôle (optionnelle)

Dans cette page réactivable depuis les réglages de l’île, le crayon en haut à droite ouvre le mode édition.
Chaque module (connexions, musique, nuit, mode jeu, luminosité, volume, énergie) montre un œil (masquer) et
deux flèches (monter, descendre) ; les modules masqués
sont listés en dessous, un clic les remontre ; « Réinitialiser » rend la disposition de départ, « Terminer » ferme le
mode. Au moins un module reste visible. Clavier : ↑ ↓ choisissent un module, Maj + ↑ ↓ le déplacent, Espace ou Entrée
le masquent ou le remontrent, Échap termine ; les boutons portent un nom d’accessibilité et une infobulle s’affiche
en bas pendant le survol. Les modules se rangent en lignes de 168 points (deux pastilles s’empilent, les glissières se
partagent le reste de la ligne, l’énergie prend un bandeau) : sans changement, la disposition est exactement celle
d’avant. L’ordre et les modules masqués sont gardés dans `~/.local/state/nc/ile/centre.json` (`nc-ile-memo`, fichier
privé écrit d’un bloc) et relus au démarrage de l’île.

## Notifications

La page groupe les cartes par application (compteur, groupe repliable d’un clic sur son titre, la plus récente reste
visible). Filtres **Toutes / Non lues / Urgentes** et recherche sur le titre, le texte et l’application (`/` ou
Ctrl + F). Une notification est non lue (point bleu, titre en gras) jusqu’à ce qu’elle soit ouverte, répondue ou
marquée lue (bouton sur la carte, ou « Tout lu »). Sur une carte, au survol : marquer lue, **reporter** (15 min, 1 h,
demain à 9 h : la notification disparaît et revient en bannière à l’heure dite, même après un redémarrage de l’île —
elle est alors recréée à partir du texte gardé), **masquer cette application** (1 h ou toujours : ni bannière ni carte,
les applications masquées sont listées en haut, un clic les remontre), **répondre** quand l’application le permet
(réponse rapide `sendInlineReply` ; sinon le clic ouvre l’application), retirer. Clavier : ↑ ↓ choisir, Entrée ouvrir,
Suppr retirer, Échap vider la recherche. Les bannières, la concentration (et sa plage horaire) et les boutons d’action
des applications restent comme avant. L’état (lus, reports, applications masquées) est gardé dans
`~/.local/state/nc/ile/notifs.json` par `nc-ile-memo`.

## Presse-papiers

L’historique est gardé d’une session à l’autre (`~/.local/state/nc/ile/presse.json`, les images en fichiers privés
0600 dans `~/.local/state/nc/ile/images`, écrits d’un bloc par `nc-ile-memo`) : 50 textes et 12 images au plus, 64 Mio
d’images en tout ; les plus anciens non épinglés partent, leurs fichiers aussi. La capture (`nc-presse-capture`, lancé
par `wl-paste --watch`) ignore toujours ce qu’un gestionnaire de mots de passe marque comme secret
(`x-kde-passwordManagerHint`, `x-nc-secret`) et ne journalise jamais le contenu. Ce qui est déjà dans le
presse-papiers quand la veille démarre (île relancée) n'entre pas : c'est déjà dans l'historique, ou exclu exprès ;
seule une copie faite pendant que l'île était arrêtée manque. Dans la page : recherche, filtre
Tout / Textes / Images, épinglés en tête (épingle sur la carte), suppression d’une carte (croix ou Suppr), aperçu
complet d’un texte long (flèche), « Coller en texte brut » (recopie en `text/plain`, ferme l’île et envoie Ctrl + V
à la fenêtre active par le dispatcher `send_shortcut` de Hyprland), « Effacer » (les épinglés restent). Clavier : ↑ ↓ choisir,
Entrée recopier, Suppr supprimer, `/` ou Ctrl + F chercher, Échap vider la recherche. Réglage `ILE_PRESSE` (non : plus
de capture). Réglage `PRESSE_DUREE` (1, 7 par défaut, 30 jours ou `jamais`) : les entrées non épinglées plus vieilles
sont effacées quand la liste est lue (démarrage, ouverture de la page) ou écrite (chaque copie), sans minuteur. Une
même image copiée plusieurs fois ne fait qu'une entrée (identifiant tiré de l'empreinte du contenu). Pendant un partage
d'écran (`Partage.silence`), les aperçus (textes et miniatures) sont cachés.

## Intégration Google

`nc-settings → Intégration Google` : **Google dans l’île** (`GOOGLE_INTEGRATION`, non par défaut) et, en dessous,
un interrupteur par fonction (`GOOGLE_CALENDRIER`, oui). Sans l’interrupteur général, rien de Google n’apparaît et
aucun appel n’est fait : les pages restent celles de quelqu’un qui n’a pas de compte Google relié. Les données passent
par la connexion Google déjà faite pour JARVIS (`integrations/google-workspace/setup_oauth.py` côté JARVIS, qui écrit
`token.json`) : le gateway rafraîchit le jeton et lit l’API, le jeton ne quitte jamais le serveur, l’île ne reçoit
que les événements (`nc-jarvis requete`, op `google.calendar` ; `google.status` dit si c’est relié).

Page **Calendrier** avec Google Agenda : un point coloré sous les jours qui ont des événements (une couleur par
calendrier, tous les calendriers cochés dans Google Agenda), le prochain événement sous le titre, et au clic sur un
jour son agenda (heure ou « Toute la journée », titre, lieu, calendrier). Chargement, erreur et état vide sont
affichés ; « Actualiser » relit ; « + » ouvre JARVIS avec une demande de création d’événement déjà écrite (le jour
choisi). Rien n’est demandé au démarrage de l’île : seulement à l’ouverture de la page, un mois à la fois, gardé
5 minutes. Fuseau : `BRIEFING_TIMEZONE` du gateway, sinon Europe/Paris.

Le Cloud JARVIS n'est pas une page : c'est une fenêtre à part (`nc-cloud fenetre`, voir `docs/cloud.md`). Son entrée
« Cloud JARVIS » n'apparaît dans la recherche de l'île qu'avec `CLOUD_JARVIS=oui` et ce PC associé.

**Rappels dans le Spotlight** (Super + R) : `rappel 15h appeler le garage`, `rappel 20 min sortir le linge`,
`rappel demain 9h dentiste` (en anglais : `reminder 3pm call`, `reminder tomorrow 9am …`). Heures acceptées : `15h`,
`15h30`, `15:30`, `3pm` ; durées : `20 min`, `2 h`, `90 s`, `dans 1h30` / `in 2 hours`. Une heure déjà passée aujourd'hui
veut dire demain. La ligne montre l'heure comprise avant que tu valides (Entrée) ; si l'heure n'est pas comprise, rien
n'est créé. Le texte reste tel quel (200 caractères au plus, jamais interprété), 50 rappels au plus. `rappels` les
liste, Entrée sur l'un le supprime. À l'heure, une notification sort (bouton « Reporter » comme les autres) ; un rappel
échu pendant que l'île ou le PC était éteint s'affiche une fois au démarrage. Les rappels sont gardés dans un fichier
privé. Attention : `1h30` collé veut dire 01:30 ; pour une durée, écris `dans 1h30` ou `1 h 30`. Limite : un rappel échu
pendant la veille s'affiche au retour de l'écran (écran rallumé ou session déverrouillée).

**Note rapide dans le Spotlight** : `note acheter du pain` puis Entrée ajoute une ligne datée à la fin de
`~/.local/share/nc/notes.md` (`$XDG_DATA_HOME/nc/notes.md`). `note` ou `notes` seul montre les 20 dernières, la plus
récente en haut ; Entrée ouvre le fichier avec l'application par défaut. Une note reste une ligne : les retours à la
ligne et les caractères invisibles deviennent des espaces. 1000 caractères au plus. Le fichier est privé (0600) et
n'est jamais suivi s'il est remplacé par un lien. Rien n'est envoyé nulle part. Le fichier est un simple texte : tu peux
le modifier à la main. En ligne de commande : `nc-note ajouter < texte`, `nc-note liste`, `nc-note ouvrir`.

**Mot de passe dans le Spotlight** : `mdp 20` (`mdp` seul = 20, `password 20` en anglais ; 8 à 64 caractères) montre une
ligne « Copier un mot de passe de 20 caractères ». Rien n'est généré en tapant : à Entrée, `nc-mdp 20` tire le mot de
passe (module `secrets`, lettres, chiffres et symboles, au moins un de chaque), le copie par l'entrée standard de
`wl-copy` et l'île dit « copié », sans jamais l'afficher ; « Copie impossible » si `wl-copy` échoue ou dépasse 10 s.
Pendant toute la copie, une marque vide et datée (`$XDG_RUNTIME_DIR/nc-secret-copie`) dit à l'historique de l'île de ne
pas la garder ; une copie que tu fais toi-même dans les 5 secondes qui suivent n'y entre pas non plus. `--sensitive` est
ajouté si ton `wl-copy` (wl-clipboard 2.3 ou plus) le connaît : les lecteurs qui respectent cet indice l'ignorent aussi
(`nc-cloud presse` et `nc-noeud clipboard_read` refusent alors de le lire), pas les autres (cliphist de Noctalia s'il est
activé et ne regarde pas l'indice). Sans lui (Debian 13 : 2.2.1), seul l'historique de l'île l'ignore : `nc-cloud presse`,
`nc-noeud clipboard_read` et tout autre lecteur voient le mot de passe. Le mot de passe reste dans le presse-papiers jusqu'à ta
copie suivante. `wl-copy` le recopie dans un fichier effacé aussitôt : `nc-mdp` lui donne un dossier privé en mémoire
(sous `$XDG_RUNTIME_DIR`, rien n'est copié sans lui) ; wl-clipboard avant 2.3 (Debian 13) ignore ce dossier : son
fichier, déjà effacé mais encore ouvert, est sous `/tmp`, donc sur le disque si `/tmp` n'est pas un tmpfs, tant que le mot
de passe reste dans le presse-papiers.

**Processus et ports dans le Spotlight (lecture seule)** : `port 8080` (ou `port :8080`) dit quel programme écoute sur
ce port, en TCP et en UDP (`nc-processus port`, qui lit `ss -Hltune` sans élévation, paquet iproute2 : seulement l'inode
de chaque socket, que l'on cherche dans les descripteurs de TES processus ; sinon la ligne dit « Utilisé par un autre
compte » ; sans `ss`, cette recherche n'apparaît pas). `processus firefox` liste au plus 8 de tes processus dont le nom
contient le mot (lettres, chiffres et `._-`, 32 au plus) : nom, pid et commande, filtrés des caractères de contrôle et
de sens d'écriture, et bornés. Ces lignes s'ajoutent en tête des résultats ordinaires (applis, fichiers, calculs restent
dessous). `port` seul ou suivi d'autre chose qu'un nombre de 1 à 65535 : la recherche ordinaire seule. Rien n'agit sur
un processus, et rien ne tourne tant que tu ne le tapes pas.

**Raccourcis web personnels** : `~/.config/nc/liens-web.conf` (hors dépôt, `XDG_CONFIG_HOME` respecté), une ligne `préfixe<TAB>nom<TAB>URL` ; `%s` doit y figurer une seule fois et reçoit ta saisie par `encodeURIComponent`. Préfixe : 1 à 12 lettres minuscules ou chiffres, jamais `g`, `yt`, `w` ni un mot-clé de l'île (heure, mdp, port, processus, session, note, rappel…) ; URL en `http(s)://` ; nom de 40 caractères au plus sans caractère de contrôle ni de sens d'écriture ; fichier de 16 Kio et 50 lignes au plus (au-delà, rien n'est lu). Lignes vides et `#` ignorées, ligne fausse ignorée sans bruit. Relu à chaque ouverture de la recherche, rien de périodique ; `ajouter` et `retirer` gardent telles quelles les lignes qu'ils ne comprennent pas (commentaires compris) et refusent, sans rien écrire, un fichier de plus de 16 Kio ou 50 lignes, illisible ou qui n'est pas ordinaire ; fichier absent : rien ne change. `amz a&b c` donne une ligne « Rechercher sur Amazon ». Gestion : `nc-reglages liens-web liste`, `ajouter PRÉFIXE NOM URL`, `retirer PRÉFIXE` (la fenêtre des réglages, section « Barre et dock », liste, retire et ajoute : champ « Ajouter un lien web », saisie `préfixe nom URL`, même validation, un refus affiche son message et n'écrit rien). Limite : la recherche de fichiers et de paquets ne connaît pas encore ces préfixes.

**Horloges mondiales** : réglage `HORLOGES_VILLES` (section « Île », villes séparées par des virgules, 8 au plus, noms de 2 à 40 caractères sans chiffre ; vide par défaut, jamais modifiable à distance). « heure », « horloge(s) », « clock(s) » ou « world clock » seul ajoute une carte par ville (nom, heure, jour, écart) devant les résultats ordinaires ; une ville inconnue est ignorée, « heure tokyo » ne change pas. Un seul `date` par saisie, aucun réseau.

**Snippets** : `;mot` montre au plus 3 cartes « Copier : titre » pour les snippets de `~/.config/nc/snippets.conf` (`mot<TAB>titre<TAB>texte[<TAB>secret]`, `\n`, `\t` et `\\` échappés ; mêmes bornes et mêmes mots réservés que les raccourcis web). Le texte passe par l'entrée standard de `wl-copy`, ou de `nc-mdp --stdin` pour un secret ; jamais par argv, jamais exécuté. Un secret n'est jamais montré, ni dans la carte ni dans nc-reglages.
