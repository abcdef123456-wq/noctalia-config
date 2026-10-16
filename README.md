# noctalia-config

Un bureau **Hyprland + Noctalia v5** complet, installable en une commande, sur n'importe quel PC compatible avec Noctalia
(portable ou fixe, Intel, AMD ou NVIDIA). La config Hyprland est au **format Lua** (Hyprland 0.55 ou plus).

- Couleurs tirées du fond d'écran : barre, terminal, Dolphin, bordures des fenêtres (vives ou sobres selon l'image) ;
- **île dynamique** au centre de la barre : l'heure, ta musique (pochette, égaliseur qui danse sur le son) ; elle
  s'étire comme sur iPhone pour le volume, la luminosité, un nouveau morceau, le chargeur, le profil d'énergie ; un clic
  (ou **Super + C**) et le centre de contrôle en sort : Wi-Fi, Bluetooth, son, luminosité, profils, mode jeu… ;
- **Super + R** : recherche compacte au centre de l'écran (applis, fichiers, calculs) ;
- **Super + W** : carrousel de fonds d'écran ; **Super + /** : fiche de tes raccourcis ;
- s'adapte à chaque écran : échelle choisie d'après sa taille réelle, panneaux et carrousel à la bonne taille et centrés ;
- écran de verrouillage épuré (heure, date, musique en cours), coins d'écran arrondis ;
- terminal kitty assorti, zsh avec oh-my-zsh et powerlevel10k, accueil (logo, processeur, mémoire, batterie) ;
- look façon Apple : île dynamique noir pur qui se déploie depuis la pilule et s'y rétracte (ressort physique),
  symboles dessinés dans l'esprit des SF Symbols dans l'île ; ailleurs, thème d'icônes maison « NC » (dossiers,
  corbeille, « Terminal », « Fichiers ») aux couleurs du fond d'écran, explorateur Nautilus façon Finder ;
- Neovim avec LazyVim et ses extras (C/C++, JavaScript, formatage, Git), plugins aux versions de `lazy-lock.json` ;
- 3 profils d'énergie (Performance, Équilibré, Économie), mêmes réglages sur tous les portables ; en Économie, animations,
  flou et changement de fond coupés ; **mode jeu** (Super + Alt + G) ;
- PC hybride (Intel/AMD + NVIDIA) : bureau sur la carte intégrée, la NVIDIA dort tant qu'un jeu ne la réveille pas ;
- captures d'écran à annoter, presse-papiers, émojis, lumière de nuit, loupe, en un raccourci chacun ;
- tes propres raccourcis en une commande (`nc-raccourci`), mise à jour en une commande (`nc-maj`) ;
- **un bureau qui réagit tout seul** : halo qui pulse sur les basses de ta musique, mode jeu automatique au lancement
  d'un jeu, marque-pages de fenêtres, fenêtres flottantes qui se rouvrent là où tu les as laissées ;
- écran de démarrage (logo animé, thème GRUB) et écran de connexion assortis, proposés à l'installation.

## Installation

Une seule ligne (Arch, Fedora, Debian 13, Ubuntu) : installe git s'il manque, télécharge le dépôt dans
`~/noctalia-config` (ou le met à jour), puis lance `./install.sh` :

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/abcdef123456-wq/noctalia-config/main/get.sh)
```

Sans `curl` (Debian minimal) : `bash <(wget -qO- https://raw.githubusercontent.com/abcdef123456-wq/noctalia-config/main/get.sh)`

Ou à la main :

```bash
git clone https://github.com/abcdef123456-wq/noctalia-config.git ~/noctalia-config
cd ~/noctalia-config
./install.sh
```

Lance-le **sans sudo** : il demande ton mot de passe quand il en a besoin. Puis ferme et rouvre ta session, en choisissant
**« Hyprland (uwsm-managed) »** sur l'écran de connexion.

Le script fait tout seul :

| Étape | Ce qu'il fait |
|---|---|
| Détection | ta distribution, ton écran (définition, taille réelle), ton clavier, ton navigateur, ta langue, ta carte graphique |
| Hyprland et Noctalia v5 | les installe s'ils manquent (voir le tableau ci-dessous) |
| Paquets | installe les outils nécessaires (terminal, gestionnaire de fichiers, captures d'écran…) |
| Fichiers | copie la config, adaptée à ton PC, après avoir **sauvegardé** ce qu'elle remplace |
| Terminal | propose zsh, oh-my-zsh, powerlevel10k et la police du terminal, et zsh comme shell par défaut |
| Neovim | propose la config LazyVim, les outils qu'elle utilise (ripgrep, fd, Node.js, gitui…) et ses plugins (Neovim 0.11.2 ou plus) |
| Services | active la barre, la synchronisation des couleurs, les miniatures du carrousel, les profils d'énergie, la mise en veille |
| Étapes système | propose, **une par une** : profils d'énergie, Wi-Fi (Arch), écran de démarrage, écran de connexion, pilote NVIDIA |

Relancé, il **saute tout ce qui est déjà en place** (paquets, fichiers identiques, terminal, Neovim, étapes système déjà
faites) : seul ce qui manque ou a changé est fait.

| Distribution | Hyprland et Noctalia v5 |
|---|---|
| Arch et dérivées (CachyOS, EndeavourOS, Manjaro…) | installés depuis les dépôts officiels |
| Fedora (44 ou plus) | Noctalia et Quickshell depuis les dépôts officiels ; Hyprland depuis le dépôt communautaire COPR `sdegler/hyprland` (le script te le montre et demande avant) |
| Debian 13, Debian Sid, Ubuntu 26.04 | Noctalia via le dépôt officiel de Noctalia (le script te montre les adresses et demande avant). Debian 13 : Hyprland 0.55, Noctalia et TLP viennent de « trixie-backports », la source officielle de Debian pour les versions récentes, que le script propose d'activer ; Neovim récent (0.11+) proposé depuis neovim.io |
| openSUSE Tumbleweed et Slowroll | Noctalia via le dépôt indiqué par la documentation (idem) |
| Autres (NixOS, Gentoo…) | installe-les toi-même ([guide](https://docs.noctalia.dev/noctalia/getting-started/installation/)), puis relance le script |

Hyprland doit être en version **0.55 ou plus** (le script vérifie). Les paquets dont le nom diffère selon la distribution sont
essayés un par un : ce qui manque est signalé à la fin sans tout arrêter. Hors Arch, la police du terminal
(« CaskaydiaCove Nerd Font ») est proposée en téléchargement depuis la page officielle de Nerd Fonts.

| Commande | Effet |
|---|---|
| `./install.sh` | tout : paquets, fichiers, terminal, Neovim, services, puis une question avant chaque étape système |
| `./install.sh --no-system` | seulement ta session (aucune modification système, à part l'installation de paquets) |
| `./install.sh --files-only` | seulement la copie des fichiers |
| `./install.sh --restore` | remet tes fichiers comme avant la dernière installation |

Le script :
- ne lance **jamais** de mise à jour système. S'il manque un paquet dans ta base, il te demande de la faire toi-même ;
- **sauvegarde** chaque fichier remplacé dans `~/.local/state/noctalia-config/backup-<date>/` ;
- ne touche au démarrage (Plymouth, GRUB, initramfs) que si tu réponds **oui** (non par défaut) ;
- n'écrase jamais tes images (fonds d'écran, photo de profil) ni les fichiers que le bureau régénère (couleurs, profil d'énergie) ;
- remplace chaque fichier d'un coup : Hyprland, qui recharge sa config à chaque changement, ne la voit jamais incomplète ;
- retire l'ancienne config Hyprland au format `.conf` (sauvegardée) : seul `hypridle.conf` reste, hypridle ne lisant que ce format ;
- peut être relancé sans risque : ce qui est déjà à jour n'est pas recopié ;
- met à jour une installation faite avec l'ancienne version de ce dépôt (fichiers « legion ») : les anciens fichiers sont
  retirés après sauvegarde, et une session ouverte passe directement au format Lua.

> Attention : ta config Noctalia existante (`~/.config/noctalia/config.toml`) est remplacée (une copie est gardée). Les réglages
> faits depuis l'interface de Noctalia sont dans `~/.local/state/noctalia/settings.toml` et ne sont pas touchés.

## Raccourcis

Les principaux : **Super + R** recherche · **Super + W** fonds d'écran · **Super + /** fiche des raccourcis · **Super + Entrée** terminal ·
**Super + L** verrouiller · **Super + C** centre de contrôle. La liste complète est dans [RACCOURCIS.md](RACCOURCIS.md).

| Nouveau | Raccourci |
|---|---|
| Capture de l'écran · d'une zone · à annoter | **Impr. écran** · **Super + P** · **Super + Maj + S** |
| Historique du presse-papiers · émojis | **Super + Maj + V** · **Super + .** |
| Lumière de nuit · ne pas déranger | **Super + N** · **Super + Maj + N** |
| Loupe (zoom autour du curseur) | **Super + Ctrl + molette**, ou **Super + =** / **Super + -** |
| Mode jeu : effets coupés, image envoyée sans attendre l'écran, notifications en pause | **Super + Alt + G** (même touche pour sortir) |
| Revenir au bureau précédent | **Super + chiffre** du bureau où tu es déjà |

## Île dynamique

Au centre de la barre, une pilule noire comme l'île de l'iPhone : l'heure, ta musique (pochette, onde sonore). Elle
s'étire quelques secondes pour le volume, la luminosité, un nouveau morceau, le chargeur, le profil d'énergie, le mode
jeu. Un clic (ou **Super + C**) et elle se déploie en centre de contrôle façon iOS : Wi-Fi, Bluetooth, ne pas déranger,
mode jeu, musique, curseurs verticaux de luminosité et de volume, lumière de nuit, halo musical, profil d'énergie,
capture, notifications, réglages, verrouillage, extinction. **Appui long (ou clic droit)** sur Wi-Fi, Bluetooth ou le
volume : page de détails (réseaux avec mot de passe, appareils, sorties audio et micro). Clic ailleurs ou **Échap** : elle
se referme dans la pilule.

Sur Arch, l'île est dessinée par **Quickshell** par-dessus la barre de Noctalia (`~/.config/quickshell/nc-ile`,
service `nc-ile`), avec les icônes Material Symbols Rounded. Ailleurs, la même île est fournie par le plugin Noctalia
`nc/ile` (un peu moins libre : elle s'ouvre juste sous la barre).

## Automatismes

| | |
|---|---|
| **Halo musical** | Quand de la musique joue, le halo coloré de la fenêtre active pulse sur les basses (cava écoute la sortie son). Coupé en Économie, en mode jeu et sur batterie (sauf en Performance). **Super + Alt + M** pour le couper ou le remettre ; `nc-pouls demo` pour le voir sans musique. |
| **Mode jeu automatique** | Un jeu s'ouvre (Steam, Proton, gamescope, `.exe`) : profil Performance et mode jeu. Le dernier jeu fermé : retour au profil d'avant, effets et notifications rétablis. |
| **Marque-pages de fenêtres** | **Super + Ctrl + 1…4** : le premier appui attache la fenêtre active à la touche ; ensuite, la touche t'amène à elle depuis n'importe quel bureau, et depuis elle te ramène à la fenêtre d'avant. **Super + Ctrl + Maj + 1…4** pour en attacher une autre. |
| **Fenêtres flottantes** | Chaque appli flottante (calculatrice, réglages, lecteur…) se rouvre à la taille et à la place où tu l'as fermée, en proportion de l'écran. |

### Tes raccourcis

Le plus simple : `nc-raccourci` (ou `nc-reglages`, section Raccourcis). Tous les raccourcis y sont listés ; Entrée sur
l'un d'eux pour changer ses touches (tu appuies sur la nouvelle combinaison) ou le désactiver, « Ajouter un raccourci »
pour en créer un. En ligne de commande :

```bash
nc-raccourci ajoute "Super+B" firefox              # Super + B : va à Firefox s'il est ouvert, sinon le lance
nc-raccourci ajoute "Super+Alt+S" "ile son"        # ouvre la page Son de l'île (aussi : bureau 3, ou une commande)
nc-raccourci change "Super+Entrée" "Super+T"       # un raccourci de la config sur d'autres touches
nc-raccourci desactive "Super+N"                   # désactive un raccourci de la config
nc-raccourci retablit tout                         # annule tes changements de raccourcis de la config
nc-raccourci liste                                 # tous les raccourcis, et tes changements
```

Tout est gardé dans `~/.config/nc/raccourcis.conf`, jamais touché par les mises à jour ; une combinaison déjà prise est refusée.

Ils apparaissent tout de suite dans la fiche **Super + /** (section « Mes raccourcis »). Une combinaison déjà prise est
refusée, en tenant compte de la disposition du clavier (AZERTY, QWERTZ…). Ils sont rangés dans `~/.config/hypr/perso.lua`,
que tu peux aussi éditer (exemples dedans) et qu'aucune mise à jour ne remplace.

## Écrans

Chaque écran reçoit sa définition native et une échelle choisie d'après sa densité de pixels (mêmes seuils que Hyprland), sans
jamais descendre sous 1600 x 900 points utiles : un portable 15" en 1920 x 1080 est à 1,2 (et non 1,5, où tout paraît zoomé).
La recherche, la fiche des raccourcis et le carrousel se dessinent à la taille de l'écran et restent centrés.

Pour forcer une échelle, dans `~/.config/hypr/perso.lua` :

```lua
hl.monitor({ output = "HDMI-A-1", mode = "preferred", position = "auto", scale = 1 })
```

## Énergie

Trois profils, à choisir dans la barre (icône d'énergie) ou avec **Super + Alt + P** :

- **Performance** : fréquence maximale de l'écran interne, effets complets, processeur à fond ;
- **Équilibré** (par défaut) ;
- **Économie** : écran interne à 60 Hz, sans flou ni animations, luminosité limitée, clavier éteint, Bluetooth coupé s'il est inutilisé.

Les profils viennent du service de ta distribution : TLP sur un portable sous Arch (réglages communs à tous les portables, limite
de charge à environ 80 % proposée si la batterie la gère), `tuned-ppd` sur Fedora, `power-profiles-daemon` ailleurs. Un service
déjà en place est gardé. Fréquences par profil : `~/.config/nc-profile.conf` (voir `nc-profile-sync`).

Sur un **portable**, les profils viennent de TLP et tlp-pd avec les réglages du dépôt (`system/tlp.d/10-nc.conf` : processeur,
turbo, carte PCIe, mode de la plateforme) : les mêmes sur Arch, Fedora 44+, Debian 13 et openSUSE Tumbleweed. Ailleurs, et
sur un PC fixe, le service de la distribution est utilisé. La limite de charge à 80 % est proposée si la batterie la gère
(Lenovo, ASUS, Dell, ThinkPad… ; pas encore les Acer sous Linux).

### PC hybride (carte intégrée + NVIDIA)

- Le bureau tourne sur la carte intégrée, qui porte l'écran interne : la NVIDIA peut s'endormir (batterie, chaleur, bruit).
  Si un écran est branché sur une prise reliée à la NVIDIA à l'ouverture de session, les deux cartes sont utilisées.
  Écran ou projecteur branché après coup sur une de ces prises (souvent le HDMI) : une notification propose de rouvrir
  la session (Hyprland ne peut pas ajouter une carte en cours de route) ou de toujours garder la NVIDIA.
  Réglage dans `~/.config/uwsm/gpu-mode` : `auto` (défaut), `igpu`, `both` ou `off` (détails dans `~/.config/uwsm/env-hyprland`).
- Lancer une appli sur la NVIDIA : `nvidia-run <commande>` (Steam : `nvidia-run %command%`) ; en Performance, les applis
  lancées depuis la barre y vont d'elles-mêmes.
- Pilote : sur Arch, le script installe le pilote officiel s'il manque (`nvidia-open`, nécessaire aux RTX 50). Sur Debian 13,
  les RTX 50 demandent le pilote de NVIDIA (celui de Debian, 550, est trop ancien) : le script donne la marche à suivre.

## Personnaliser sans perdre tes réglages

Ces fichiers sont à toi : `install.sh` ne les remplace jamais.

| Fichier | Pour |
|---|---|
| `~/.config/nc/reglages.conf`, `~/.config/nc/raccourcis.conf` | tes réglages (`nc-reglages`) et tes raccourcis (`nc-raccourci`) |
| `~/.config/hypr/perso.lua` | règles de fenêtres, écrans, tout réglage Hyprland en plus (format Lua de Hyprland) |
| `~/.zshrc.perso` | tes alias et variables du terminal |
| `~/.config/kitty/perso.conf` | tes réglages de kitty |

## Mettre à jour ton bureau

```bash
nc-maj        # récupère la dernière version depuis GitHub, puis ne refait que ce qui a changé
nc-reglages   # tes réglages, aux flèches : île et Spotlight, apparence, lumière nocturne, barre et dock, fenêtres,
              # fonds d'écran, énergie, son et luminosité, clavier et souris, veille et couvercle, terminal,
              # captures, raccourcis — gardés à chaque mise à jour
```

Tes fichiers personnels (`perso.lua`, `~/.zshrc.perso`, `perso.conf`), tes fonds d'écran, ta photo de profil et tes couleurs
ne sont jamais remplacés.

## Mettre à jour le dépôt depuis ta machine

```bash
cd ~/noctalia-config
./export.sh        # recopie la config actuelle ; ce qui est propre au PC devient un repère (@HOME@, @MONITOR@…)
git add -A && git commit -m "Mise à jour" && git push
```

## Contenu

- `home/` : la config (Hyprland en Lua dans `.config/hypr/`, Noctalia v5, plugins, kitty, zsh, Neovim, Qt/KDE, scripts `nc-*`) ;
- `system/` : profils d'énergie TLP, thème GRUB « nc », écran de connexion SDDM (étapes optionnelles) ;
- `install.sh`, `export.sh`, `RACCOURCIS.md`.

Les plugins `nc/launcher`, `nc/carousel` et `nc/keys` (recherche, fonds d'écran, raccourcis) sont écrits pour ce dépôt.
L'écran de connexion s'appuie sur le thème libre [sddm-astronaut-theme](https://github.com/Keyitdev/sddm-astronaut-theme).
Les fonds d'écran appartiennent à leurs auteurs.
