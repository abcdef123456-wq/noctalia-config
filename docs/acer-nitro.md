# Acer Nitro (ANV16-72)

Ce guide ne concerne que les portables Acer Nitro. Sur les autres machines, rien de tout cela n'apparaît.

## linuwu-sense et l'erreur -5

Le module `linuwu-sense` donne au noyau le contrôle des profils de puissance et des ventilateurs de la Nitro. Sans lui, `platform_profile` est absent et le firmware garde la main.

Sur cette machine, le module ne se charge pas avec le dépôt d'origine : le noyau répond « erreur -5 » à l'enregistrement du profil. Le correctif est la PR #148 : https://github.com/0x7375646F/Linuwu-Sense/pull/148

`nc-diag` le dit quand il voit le module chargé sans `platform_profile`, ou le message -5 dans le journal du noyau.

## Installation à la main (AUR)

Rien n'est installé automatiquement. Exemple indicatif, à adapter :

```
git clone https://aur.archlinux.org/linuwu-sense-dkms-git.git
cd linuwu-sense-dkms-git
makepkg -si
```

Vérifiez que la PR #148 est bien dans la version construite, puis redémarrez.

## Mode jeu

Dans `~/.config/nc-profile.conf` :

- `JEU_CPU=30/45` : limites du processeur en watts (PL1/PL2) pendant le jeu.
- `JEU_GPU_MHZ=1500` : fréquence maximale de la carte graphique en jeu.
- `TURBO_VENTILOS=oui` : ventilateurs au maximum quand le turbo est actif.

La commande `nc-turbo` active ou coupe le turbo (drapeau `~/.config/nc/turbo`).

`nvidia-powerd` n'est jamais activé : il pousse la carte à 135 W, trop pour ce portable.

## Mesurer : `nc-diag perf`

`nc-diag perf [SECONDES]` (5 à 120, 15 par défaut) montre le profil, les limites, les ventilateurs, le turbo, puis mesure la batterie et le processeur sur la durée. Elle ne lance pas nvidia-smi.

## Les pièges

- `status` de la batterie ment (« Full » pendant une décharge). On regarde l'écart de charge entre deux lectures.
- `current_now` n'a pas de signe.
- La puissance `psys` est fausse sur cette machine : on ne l'utilise pas.
- `energy_uj` (RAPL) est réservé à root (faille Platypus). La puissance du processeur passe par `nc-energie-root puissance`, au plus une fois par seconde (sinon « inconnue »).

Pour les jeux eux-mêmes : voir docs/jeux.md.
