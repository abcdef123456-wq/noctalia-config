# nc-gestes

Plugin Hyprland 0.57.2 des gestes d'ouverture de fenêtres de noctalia-config. Première étape : **la goutte**,
signature du thème Rose Aube (Émail). À l'ouverture, la vraie fenêtre naît sous la pilule de l'île, gonfle
jusqu'aux deux tiers de sa largeur finale en pendant au bout d'un col liquide, le col s'amincit et cède, puis la
fenêtre tombe à sa place.

L'animation est seulement visuelle : la fenêtre est posée, focalisable et à sa géométrie finale dès l'ouverture.
Le plugin s'appuie sur les « transformers » de fenêtre d'Hyprland (`Render::IWindowTransformer`), sans aucun
crochet en mémoire. Le col est dessiné hors du cadre de la fenêtre grâce à `transformedExtents`.

## Compiler

Il faut les en-têtes d'Hyprland (`pkg-config --exists hyprland`) et `g++`.

```sh
make -C plugins/nc-gestes          # produit plugins/nc-gestes/nc-gestes.so
```

Le `.so` ne vaut que pour l'Hyprland contre lequel il a été compilé : un `.so` d'une autre version est refusé au
chargement, avec une notification, sans rien enregistrer.

## Charger à la main

```sh
hyprctl plugin load "$PWD/plugins/nc-gestes/nc-gestes.so"
hyprctl plugin unload "$PWD/plugins/nc-gestes/nc-gestes.so"
```

Au déchargement, la goutte est retirée de toutes les fenêtres, même au milieu d'un geste, et le programme GL est
libéré.

## Commandes

```sh
hyprctl nc-gestes status                       # état en JSON
hyprctl nc-gestes anchor <écran> <x> <y> <l> <h>  # pilule de l'île au repos, logique, locale à l'écran
hyprctl nc-gestes set enabled 0                # ou 1
hyprctl nc-gestes set mode natif               # « goutte » ou « natif »
hyprctl nc-gestes set speed 1.25               # 0.1 à 10, durée de base 620 ms
```

Sans ancre envoyée, la pilule est supposée centrée en haut de l'écran (184 × 34 à 10 px du bord).

Fenêtres laissées à l'animation native : plein écran, espace spécial (terminal déroulant), fenêtres de moins de
80 × 80, cachées ou « override-redirect ».

## Repli

Si le plugin n'est pas chargé (pas d'en-têtes, version d'Hyprland différente, moteur de rendu autre que GL), ou si
le programme GL ne compile pas, rien ne change : l'animation `windowsIn` d'Hyprland reste celle du thème. Le plugin
ne remplace l'animation native que pour les fenêtres auxquelles il attache réellement une goutte.
