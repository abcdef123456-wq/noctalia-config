# nc-gestes

Plugin Hyprland 0.57.2 des gestes d'ouverture de fenêtres de noctalia-config : quatorze gestes de thème dessinés
sur la vraie texture de la fenêtre, par un seul programme GL. La signature d'Émail (Rose Aube) est **la goutte** :
une goutte de l'émail de l'île (la couleur de sa pilule) gonfle dessous, pend à un col en sablier qui s'amincit jusqu'au
fil, se pince (une gouttelette suit), tombe en s'étirant un peu, puis s'ouvre en fenêtre à sa place sur un ressort
amorti. Le vrai contenu de la fenêtre y entre en fondu dès que l'appli l'a dessiné (son premier commit après
l'ouverture), au plus tard pendant l'ouverture : la goutte n'est jamais un aplat vide.

| Geste | Thème | Durée | Ce qu'on voit |
|---|---|---:|---|
| `goutte` | rose-aube | 680 ms | gonfle sous l'île (56 % du temps), col en sablier, pincement, chute, s'ouvre |
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

## Dans la session

Tout est automatique, sans root :

- `install.sh` copie `Makefile` et `src/` dans `~/.local/share/nc/plugins/nc-gestes`, puis lance `nc-plugin-sync`
  s'il y a les en-têtes (pas en `--files-only`).
- `nc-plugin-sync`, lancé aussi en arrière-plan au démarrage de la session (`nc/session.lua`), compile vers
  `~/.local/lib/noctalia-config/nc-gestes.so` seulement quand le commit d'Hyprland ou les sources changent
  (`nc-gestes.abi`), puis charge le plugin. Sans session, sans en-têtes, sans compilateur, ou avec les en-têtes
  d'un autre commit qu'Hyprland en cours : il ne fait rien et sort avec 0.
- `nc.gestes_sync()` (`nc/energie.lua`, à chaque chargement de la config) envoie `set enabled/mode/speed` : le geste
  du thème, ou `natif` pour un geste natif ou `auto` ; coupé avec les animations (réglage, caractère `aucun`,
  Économie, « Aucun effet », mode jeu, « Aucune sur batterie » de l'île) ; durée suivant la vitesse des animations
  et le caractère, un peu plus courte sur batterie en « Douces ».
- L'île (`Ile.qml`) envoie `anchor` (avec la surface de sa pilule et l'accent du thème) quand la pilule au repos ou le
  thème change, jamais pendant un ressort ; `nc-plugin-sync` la redemande après un chargement
  (`qs -c nc-ile ipc call ile gestesAncre`).

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
hyprctl nc-gestes anchor <écran> <x> <y> <l> <h> [<#surface> <#accent>]  # pilule de l'île au repos (logique,
                                               # locale à l'écran) et ses couleurs, dont la goutte est faite
hyprctl nc-gestes set enabled 0                # ou 1
hyprctl nc-gestes set mode natif               # un geste du tableau, ou « natif » (aucun)
hyprctl nc-gestes set speed 1.25               # 0.1 à 10 ; divise la durée de base
```

Sans ancre envoyée, la pilule est supposée centrée en haut de l'écran (184 × 34 à 10 px du bord) ; sans couleurs, la
goutte prend l'émail vert sombre de la maquette.

Fenêtres laissées à l'animation native : plein écran, espace spécial (terminal déroulant), fenêtres de moins de
80 × 80, cachées ou « override-redirect ».

## Repli

Si le plugin n'est pas chargé (pas d'en-têtes, version d'Hyprland différente, moteur de rendu autre que GL), ou si
le programme GL ne compile pas, rien ne change : l'animation `windowsIn` d'Hyprland reste celle du thème. Pour
chaque geste, `nc/apparence.lua` (réglage `FENETRES_GESTE`) garde une animation native proche. Le plugin ne remplace
l'animation native que pour les fenêtres auxquelles il attache réellement un geste.
