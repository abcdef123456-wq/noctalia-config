# noctalia-config

Un bureau **Hyprland + Noctalia v5** complet, installable en une commande, sur n'importe quel PC compatible avec Noctalia.
Il a été fait sur un Lenovo Legion Pro 5, avec des réglages en plus si tu as un **Legion**.

- Couleurs tirées du fond d'écran : barre, terminal, Dolphin, bordures des fenêtres (vives ou sobres selon l'image) ;
- **Super + R** : recherche compacte au centre de l'écran (applis, fichiers, calculs) ;
- **Super + W** : carrousel de fonds d'écran ; **Super + /** : fiche de tes raccourcis ;
- écran de verrouillage épuré (heure, date, musique en cours), coins d'écran arrondis ;
- terminal kitty assorti, avec un accueil (logo, processeur, mémoire, batterie) ;
- si c'est un **Lenovo Legion** : 3 profils énergétiques (Performance, Équilibré, Économie) ;
- mode Économie : animations, flou et changement automatique de fond coupés.

## Installation

```bash
git clone git@github.com:abcdef123456-wq/noctalia-config.git ~/noctalia-config
cd ~/noctalia-config
./install.sh
```

Lance-le **sans sudo** : il demande ton mot de passe quand il en a besoin. Puis ferme et rouvre ta session, en choisissant
**« Hyprland (uwsm-managed) »** sur l'écran de connexion.

Le script fait tout seul :

| Étape | Ce qu'il fait |
|---|---|
| Détection | ta distribution, ton écran, ton clavier, ton navigateur, et si c'est un portable ou un Legion |
| Hyprland et Noctalia v5 | les installe s'ils manquent (voir le tableau ci-dessous) |
| Paquets | installe les outils nécessaires (terminal, gestionnaire de fichiers, captures d'écran…) |
| Fichiers | copie la config, adaptée à ton écran et à ton clavier, après avoir **sauvegardé** ce qu'elle remplace |
| Services | active la barre, la synchronisation des couleurs, les miniatures du carrousel, la mise en veille |
| Étapes système | propose, **une par une**, l'énergie (Legion), le Wi-Fi, le démarrage et l'écran de connexion (Arch) |

| Distribution | Hyprland et Noctalia v5 |
|---|---|
| Arch et dérivées (CachyOS, EndeavourOS, Manjaro…) | installés depuis les dépôts officiels |
| Fedora | installés depuis les dépôts officiels |
| Debian 13, Debian Sid, Ubuntu 26.04 | Noctalia via le dépôt officiel de Noctalia (le script te montre les adresses et demande avant) |
| openSUSE Tumbleweed et Slowroll | Noctalia via le dépôt indiqué par la documentation (idem) |
| Autres (NixOS, Gentoo…) | installe-les toi-même ([guide](https://docs.noctalia.dev/noctalia/getting-started/installation/)), puis relance le script |

Hyprland doit être en version **0.53 ou plus** (le script vérifie). Les paquets dont le nom diffère selon la distribution sont
essayés un par un : ce qui manque est signalé à la fin sans tout arrêter. Les polices « CaskaydiaCove Nerd Font » et
« Adwaita Sans » ne sont installées automatiquement que sur Arch ; ailleurs, le terminal et la barre utilisent une police de secours
tant que tu ne les installes pas.

| Commande | Effet |
|---|---|
| `./install.sh` | tout : paquets, fichiers, services, puis une question avant chaque étape système |
| `./install.sh --no-system` | seulement ta session (aucune modification système, à part l'installation de paquets) |
| `./install.sh --files-only` | seulement la copie des fichiers |
| `./install.sh --legion` / `--no-legion` | forcer ou refuser les profils énergétiques « Legion » |
| `./install.sh --restore` | remet tes fichiers comme avant la dernière installation |

Le script :
- ne lance **jamais** de mise à jour système. S'il manque un paquet dans ta base, il te demande de la faire toi-même ;
- **sauvegarde** chaque fichier remplacé dans `~/.local/state/legion-dotfiles/backup-<date>/` ;
- ne touche au démarrage (GRUB, Plymouth) que si tu réponds **oui** (non par défaut), sur Arch seulement ;
- n'écrase jamais tes images ni les fichiers de couleurs que le bureau régénère ;
- peut être relancé sans risque : ce qui est déjà à jour n'est pas recopié.

> Attention : ta config Noctalia existante (`~/.config/noctalia/config.toml`) est remplacée (une copie est gardée). Les réglages
> faits depuis l'interface de Noctalia sont dans `~/.local/state/noctalia/settings.toml` et ne sont pas touchés.

## Raccourcis

Les principaux : **Super + R** recherche · **Super + W** fonds d'écran · **Super + /** fiche des raccourcis · **Super + Entrée** terminal ·
**Super + L** verrouiller · **Super + C** centre de contrôle. La liste complète est dans [RACCOURCIS.md](RACCOURCIS.md).

## Si c'est un Lenovo Legion

Le script le détecte (vendeur Lenovo, nom contenant « Legion »). Il propose alors les **profils énergétiques**, à choisir dans la
barre (icône d'énergie) ou avec **Super + Alt + P** :

- **Performance** : fréquence maximale de l'écran, effets complets, processeur et ventilateurs à fond ;
- **Équilibré** (par défaut) ;
- **Économie** : écran à 60 Hz, sans flou ni animations, luminosité et processeur limités, clavier éteint, Bluetooth coupé s'il est inutilisé.

Sur Arch, c'est TLP avec des réglages communs à tous les Legion (AMD ou Intel) ; ailleurs, `power-profiles-daemon`. La fréquence de
l'écran, le rétroéclairage de l'écran et celui du clavier sont **détectés automatiquement**. Si ta batterie propose la charge
limitée à environ 80 % (« Long_Life »), le script te propose de l'activer.

Non inclus volontairement, car ils dépendent du modèle exact et pourraient empêcher Hyprland de démarrer sur un autre Legion :
le choix automatique de la carte graphique (iGPU / RTX), les correctifs du son au réveil, les réglages de noyau.
Pour lancer une appli sur la carte NVIDIA : `nvidia-run <commande>` (Steam : `nvidia-run %command%`).

## Mettre à jour le dépôt depuis ta machine

```bash
cd ~/noctalia-config
./export.sh        # recopie la config actuelle ; ce qui est propre au PC devient un repère (@HOME@, @MONITOR@…)
git add -A && git commit -m "Mise à jour" && git push
```

## Contenu

- `home/` : config pour tout le monde (Hyprland, Noctalia v5, plugins, kitty, Qt/KDE, scripts) ;
- `legion/` : ce qui n'est installé que sur un Legion (profils énergétiques, réglages TLP) ;
- `system/` : thème GRUB « legion » et écran de connexion SDDM (étapes optionnelles, Arch) ;
- `install.sh`, `export.sh`, `RACCOURCIS.md`.

Les plugins `legion/launcher`, `legion/carousel` et `legion/keys` (recherche, fonds d'écran, raccourcis) sont écrits pour ce dépôt.
Les fonds d'écran appartiennent à leurs auteurs.
