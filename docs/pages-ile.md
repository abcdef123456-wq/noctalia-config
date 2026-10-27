# Pages de l’île

Dans `nc-settings` (ou `nc-reglages`), **Pages de l’île** (île Quickshell seulement : le plugin Noctalia n'a pas ces pages)
permet d’activer ou désactiver chacune des 17 pages :
Musique, Agents IA, Minuteur, Recharge, Jeu, Centre de contrôle, JARVIS, Notifications, Son, Réseau, Bluetooth,
Système, Santé, Calendrier, Météo, Presse-papiers et Fenêtres. La page Santé (températures, ventilateurs, profil
d'énergie, alerte de surchauffe) n'existe que sur une machine qui a des capteurs (`nc-ile-etat capteurs`).

Les choix sont conservés dans `~/.config/nc/reglages.conf` et relus sans redémarrage. Les pages restent activées
par défaut ; les pages d’activité n’apparaissent que lorsqu’elles ont du contenu. Exemple :

```sh
nc-settings set ILE_PAGE_ASSISTANT non
nc-settings set ILE_PAGE_CLAUDE non
nc-settings reset ILE_PAGE_ASSISTANT
```

Désactiver une page masque son accès, y compris via la commande IPC `page`. Cela ne désactive pas sa fonction :
un minuteur continue, les notifications de fin d’un agent restent actives, et le cockpit JARVIS reste accessible.
Si la page ouverte est désactivée, l’île choisit une page encore disponible. Si elles sont toutes désactivées,
elle se referme et reste en pilule ; le Spotlight reste disponible. Il suffit de réactiver une page pour la rouvrir.

Les points de navigation restent dans une zone avec 32 px de marge verticale et une gouttière séparée du contenu.
Le point actif reste visible ; les voisins s’estompent avec la distance et disparaissent avant de dépasser.
La molette et les flèches permettent toujours d’atteindre les pages hors de cette zone.

La page Agents affiche seulement les sessions non terminées. Les transitions de fin et leur notification sont
conservées ; une session qui reprend son travail réapparaît. Aucun fichier d’historique n’est supprimé.

La page Météo : position estimée par ipwho.is d'après ton IP (ville vide ou « auto »), météo par Open-Meteo.
Une ville saisie n'envoie que son nom à Open-Meteo. Ville introuvable : message dans la page, aucun appel à ipwho.is.

Validation isolée : `python3 -B -m unittest tests.test_island_pages tests.test_assistant_page -q`.
Les essais QML nécessitent Quickshell et QtTest (dépendance de test uniquement).

## Centre de contrôle personnalisable

Le crayon en haut à droite du centre de contrôle ouvre le mode édition : chaque module (connexions, musique, nuit,
mode jeu, luminosité, volume, énergie) montre un œil (masquer) et deux flèches (monter, descendre) ; les modules masqués
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
(`x-kde-passwordManagerHint`, `x-nc-secret`) et ne journalise jamais le contenu. Dans la page : recherche, filtre
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

