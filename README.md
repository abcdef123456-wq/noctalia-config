# noctalia-config

Un bureau **Hyprland + Noctalia v5** complet, installable en une commande, sur n'importe quel PC compatible avec Noctalia
(portable ou fixe, Intel, AMD ou NVIDIA). La config Hyprland est au **format Lua** (Hyprland 0.55 ou plus).

- Couleurs tirées du fond d'écran : barre, terminal, Dolphin, bordures des fenêtres (vives ou sobres selon l'image) ;
- **Super + R** : recherche compacte au centre de l'écran (applis, fichiers, calculs) ;
- **Super + W** : carrousel de fonds d'écran ; **Super + /** : fiche de tes raccourcis ;
- s'adapte à chaque écran : échelle choisie d'après sa taille réelle, panneaux et carrousel à la bonne taille et centrés ;
- écran de verrouillage épuré (heure, date, musique en cours), coins d'écran arrondis ;
- terminal kitty assorti, zsh avec oh-my-zsh et powerlevel10k, accueil (logo, processeur, mémoire, batterie) ;
- Neovim avec LazyVim et ses extras (C/C++, JavaScript, formatage, Git), plugins aux versions de `lazy-lock.json` ;
- 3 profils d'énergie (Performance, Équilibré, Économie) ; en Économie, animations, flou et changement de fond coupés ;
- écran de démarrage (logo animé, thème GRUB) et écran de connexion assortis, proposés à l'installation.

## Installation

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
| Étapes système | propose, **une par une** : profils d'énergie, Wi-Fi (Arch), écran de démarrage, écran de connexion |

| Distribution | Hyprland et Noctalia v5 |
|---|---|
| Arch et dérivées (CachyOS, EndeavourOS, Manjaro…) | installés depuis les dépôts officiels |
| Fedora | installés depuis les dépôts officiels |
| Debian 13, Debian Sid, Ubuntu 26.04 | Noctalia via le dépôt officiel de Noctalia (le script te montre les adresses et demande avant) ; sur Debian 13, Hyprland 0.55 vient de « trixie-backports » |
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
- n'écrase jamais tes images ni les fichiers que le bureau régénère (couleurs, profil d'énergie) ;
- peut être relancé sans risque : ce qui est déjà à jour n'est pas recopié ;
- met à jour une installation faite avec l'ancienne version de ce dépôt (fichiers « legion ») : les anciens fichiers sont
  retirés après sauvegarde, et une session ouverte passe directement au format Lua.

> Attention : ta config Noctalia existante (`~/.config/noctalia/config.toml`) est remplacée (une copie est gardée). Les réglages
> faits depuis l'interface de Noctalia sont dans `~/.local/state/noctalia/settings.toml` et ne sont pas touchés.

## Raccourcis

Les principaux : **Super + R** recherche · **Super + W** fonds d'écran · **Super + /** fiche des raccourcis · **Super + Entrée** terminal ·
**Super + L** verrouiller · **Super + C** centre de contrôle. La liste complète est dans [RACCOURCIS.md](RACCOURCIS.md).

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

PC hybride (carte intégrée + NVIDIA) : lancer une appli sur la carte NVIDIA avec `nvidia-run <commande>`
(Steam : `nvidia-run %command%`) ; en Performance, les applis lancées depuis la barre y vont d'elles-mêmes.

## Personnaliser sans perdre tes réglages

Ces fichiers sont à toi : `install.sh` ne les remplace jamais.

| Fichier | Pour |
|---|---|
| `~/.config/hypr/perso.lua` | tes raccourcis, règles de fenêtres, écrans (format Lua de Hyprland) |
| `~/.zshrc.perso` | tes alias et variables du terminal |
| `~/.config/kitty/perso.conf` | tes réglages de kitty |

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
