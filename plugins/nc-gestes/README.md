# nc-gestes

Plugin Hyprland 0.57.2 des gestes d'ouverture de fenêtres de noctalia-config : quatorze gestes de thème dessinés
sur la vraie texture de la fenêtre, par un seul programme GL. La signature d'Émail (Rose Aube) est **la goutte** :
la vraie fenêtre naît sous la pilule de l'île, gonfle jusqu'aux deux tiers de sa largeur finale en pendant au bout
d'un col liquide, le col s'amincit et cède, puis la fenêtre tombe à sa place.

| Geste | Thème | Durée | Ce qu'on voit |
|---|---|---:|---|
| `goutte` | rose-aube | 620 ms | gonfle sous l'île, col, rupture, chute |
| `paravent` | sakura | 360 ms | deux volets se déplient depuis la ligne médiane |
| `coupe` | solarized-clair | 320 ms | deux repères en L tracent le cadre, puis le remplissent |
| `horizon` | nord | 340 ms | remonte de derrière la ligne de son bord bas |
| `maree` | ocean | 380 ms | une ligne d'eau ondulante monte et découvre le contenu |
| `eventail` | everforest | 360 ms | les lames s'écartent depuis le milieu du bord bas |
| `rideau` | catppuccin | 320 ms | un velours plissé s'ouvre depuis le centre |
| `cathodique` | vaporwave | 300 ms | un trait s'étire, puis s'ouvre en écran, sans éclair |
| `fuite` | synthwave | 360 ms | avance depuis l'horizon, en perspective |
| `vantaux` | dracula | 320 ms | deux battants pivotent sur les bords, ombre de fente |
| `balayage` | matrice | 280 ms | front tramé (Bayer 4 × 4) de gauche à droite |
| `averse` | pluie-verte | 300 ms | lignes de 18 px de haut en bas, colonnes décalées |
| `paliers` | retro | 290 ms | une bande s'élargit, puis s'étend en hauteur, par crans |
| `contour` | oled | 300 ms | le filet du contour se trace, puis le contenu apparaît |

Les traits de `coupe` et `contour` prennent la couleur de la bordure de la fenêtre, donc celle du thème.

L'animation est seulement visuelle : la fenêtre est posée, focalisable et à sa géométrie finale dès l'ouverture.
Le plugin s'appuie sur les « transformers » de fenêtre d'Hyprland (`Render::IWindowTransformer`), sans aucun
crochet en mémoire. Seule la goutte dessine hors du cadre de la fenêtre (son col), grâce à `transformedExtents`.

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

Au déchargement, les gestes sont retirés de toutes les fenêtres, même au milieu d'une animation, et le programme GL est
libéré.

## Commandes

```sh
hyprctl nc-gestes status                       # état en JSON
hyprctl nc-gestes anchor <écran> <x> <y> <l> <h>  # pilule de l'île au repos, logique, locale à l'écran
hyprctl nc-gestes set enabled 0                # ou 1
hyprctl nc-gestes set mode natif               # un geste du tableau, ou « natif » (aucun)
hyprctl nc-gestes set speed 1.25               # 0.1 à 10 ; divise la durée de base
```

Sans ancre envoyée, la pilule est supposée centrée en haut de l'écran (184 × 34 à 10 px du bord).

Fenêtres laissées à l'animation native : plein écran, espace spécial (terminal déroulant), fenêtres de moins de
80 × 80, cachées ou « override-redirect ».

## Repli

Si le plugin n'est pas chargé (pas d'en-têtes, version d'Hyprland différente, moteur de rendu autre que GL), ou si
le programme GL ne compile pas, rien ne change : l'animation `windowsIn` d'Hyprland reste celle du thème. Pour
chaque geste, `nc/apparence.lua` (réglage `FENETRES_GESTE`) garde une animation native proche. Le plugin ne remplace
l'animation native que pour les fenêtres auxquelles il attache réellement un geste.
