# legion-dotfiles

Ma config Arch Linux : **Hyprland + Noctalia**, faite sur un Lenovo Legion Pro 5 16ADR10 (AMD + RTX).
Couleurs tirées du fond d'écran (barre, terminal, Dolphin, bordures), 3 profils énergétiques, GPU hybride économe,
carrousel de fonds d'écran, barre de recherche d'applications compacte, démarrage soigné (GRUB, Plymouth, SDDM).

## Installation

Prérequis : Arch Linux avec **Hyprland** et **Noctalia** déjà installés (`paru -S noctalia-shell`).

```bash
git clone git@github.com:thxotrue/legion-dotfiles.git ~/legion-dotfiles
cd ~/legion-dotfiles
./install.sh
```

Lance-le **sans sudo** : il demande ton mot de passe quand il en a besoin. Puis ferme et rouvre ta session.

| Commande | Effet |
|---|---|
| `./install.sh` | tout : paquets, fichiers, services, puis une question avant chaque étape système |
| `./install.sh --no-system` | seulement ta session (aucune modification système, à part l'installation de paquets) |
| `./install.sh --files-only` | seulement la copie des fichiers |
| `./install.sh --restore` | remet tes fichiers comme avant la dernière installation |

Le script :
- ne lance **jamais** de mise à jour système (`pacman -Syu`). S'il manque un paquet dans ta base, il te demande de la faire toi-même ;
- **sauvegarde** chaque fichier remplacé dans `~/.local/state/legion-dotfiles/backup-<date>/` ;
- ne touche au démarrage (GRUB, Plymouth, initramfs) que si tu réponds **oui** (non par défaut) ;
- n'écrase jamais tes images ni l'état propre au PC (historique du menu, réglages d'écran générés) ;
- peut être relancé sans risque : ce qui est déjà à jour n'est pas recopié.

Étapes système proposées : profils énergétiques TLP (portables), pays du Wi-Fi, thème de démarrage, écran de connexion
(nécessite `sddm-astronaut-theme` depuis l'AUR), nettoyage automatique du cache pacman.

## Raccourcis principaux

| Touches | Action |
|---|---|
| Super + R | barre de recherche d'applications (applications courantes quand elle est vide) |
| Super + W | carrousel de fonds d'écran |
| Super + ² | terminal déroulant |
| Super + Entrée | terminal |
| Super + , | réglages de Noctalia |
| Super + L | verrouiller |

## Profils énergétiques

Choisis dans la barre (icône d'énergie) :
- **Performance** : écran 165 Hz, effets complets, applications lancées sur la RTX ;
- **Équilibré** (par défaut) : tout sur la puce AMD, la RTX dort ;
- **Économie** : 60 Hz, sans flou ni ombres, luminosité et processeur limités, clavier éteint.

Forcer une application sur la RTX : `nvidia-run <commande>` (Steam : `nvidia-run %command%`).

## Mettre à jour le dépôt depuis ce PC

```bash
cd ~/legion-dotfiles
./export.sh                      # recopie la config actuelle (chemins et écran rendus génériques, secrets vidés)
git add -A && git commit -m "Mise à jour" && git push
```

## Contenu

- `home/` : fichiers de config (chemins du compte remplacés par `@HOME@`, écran interne par `@MONITOR@`) ;
- `system/` : réglages TLP, thème GRUB « legion », écran de connexion SDDM ;
- `tools/noctalia-qt612-patch.py` : correctif de Noctalia 4.4 pour Qt 6.12 (appliqué automatiquement si besoin) ;
- `install.sh`, `export.sh`.

Extension de carrousel : [motor-dev/wallpaperCarousel](https://github.com/motor-dev/wallpaperCarousel) (MIT), modifiée.
Les fonds d'écran appartiennent à leurs auteurs.
