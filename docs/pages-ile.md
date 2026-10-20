# Pages de l’île

Dans `nc-settings` (ou `nc-reglages`), **Pages de l’île** permet d’activer ou désactiver chacune des 16 pages :
Musique, Agents IA, Minuteur, Recharge, Jeu, Centre de contrôle, JARVIS, Notifications, Son, Réseau, Bluetooth,
Système, Calendrier, Météo, Presse-papiers et Fenêtres.

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

Validation isolée : `python3 -B -m unittest tests.test_island_pages tests.test_assistant_page -q`.
Les essais QML nécessitent Quickshell et QtTest (dépendance de test uniquement).
