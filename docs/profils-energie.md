# Profils d'énergie poussés (`nc-energie`)

Trois pièces, du moins sensible au plus sensible :

| Pièce | Fichier | Droits |
|---|---|---|
| Liste blanche et validateur | `home/.local/bin/nc-energie-liste` | aucun (ne lit rien, ne lance rien) |
| Commande et fiche matériel | `home/.local/bin/nc-energie` | ton compte |
| Assistant root | `system/nc-energie-root` (installé dans `/usr/local/bin`) | root, par une règle sudo à commandes exactes |

## Ce que fait l'IA

Rien d'autre qu'un JSON : `{"profils": [{"nom", "description", "reglages": {clé: valeur}}]}` (et `"film_batterie": true` pour un
profil « film sur batterie »). Elle reçoit la fiche anonyme et la liste blanche de CE PC (`nc-energie autorise`), via `nc-ia`
(donc le filtre de secrets de `nc-ia`). Le résultat est vérifié par le validateur ; un profil refusé est refusé en entier, avec la
raison. `IA_MODE=non` : `nc-ia` n'est jamais appelé, seuls les profils par règles existent (le bouton de l'IA disparaît de l'île).

## Liste blanche

Niveau 1 (sans root) :

| Clé | Valeurs | Capacité |
|---|---|---|
| `profil` | `power-saver`, `balanced`, `performance` (ceux du service de ce PC) | profil |
| `luminosite` | 20, 30, … 100 | rétroéclairage |
| `EFFETS` | `tous`, `aucun` | |
| `ECO_EFFETS`, `ECO_IMAGES`, `HALO_BATTERIE`, `BAT_RELEVES`, `FOND_ANIME_BATTERIE` | `oui`, `non` | batterie |
| `ECO_CLAVIER`, `BAT_CLAVIER` | `oui`, `non` | clavier lumineux |
| `ECO_BLUETOOTH` | `oui`, `non` | Bluetooth |
| `ECO_AUTO` | 0, 10, 15, 20, 30 | batterie |
| `ECO_BRIGHTNESS_MAX` | 0, 30, 40, 50, 60 | rétroéclairage |
| `FOND_ANIME` | `non`, `aurore`, `vivant` | |
| `ILE_ANIM_BATTERIE` | `douces`, `continues` | batterie |
| `ILE_METEO`, `ILE_PRESSE`, `ILE_TELECHARGEMENTS` | `oui`, `non` | |
| `FENETRES_FLOU`, `FENETRES_ANIMATIONS` | `oui`, `non` | |
| `FENETRES_OMBRE` | 0, 22 | |
| `HZ_PERFORMANCE`, `HZ_BALANCED_AC` | `max` | écran |
| `HZ_BALANCED_BAT`, `HZ_ECO` | `max` ; `60` seulement dans un profil marqué « film sur batterie » (écran de plus de 60 Hz) | écran |

Niveau 2 (matériel, par `nc-energie-root`, sauf `limite_charge` par `nc-limite-charge`) :

| Clé | Valeurs | Capacité |
|---|---|---|
| `cpu_epp` | `performance`, `balance_performance`, `balance_power`, `power` (ceux du pilote) | EPP |
| `cpu_boost` | `on`, `off` | boost |
| `cpu_freq_max` | 100, 80, 60 (% de `cpuinfo_max_freq`) | fréquence |
| `platform_profile` | `low-power`, `quiet`, `cool`, `balanced`, `balanced-performance`, `performance` (ceux de `platform_profile_choices`) | plateforme ACPI |
| `nvidia_pm` | `auto`, `on` | carte NVIDIA |
| `nvidia_pl` | 0 à 3 (minimum à maximum lus, en paliers égaux), carte active seulement | NVIDIA + `nvidia-smi` |
| `wifi_power_save` | `on`, `off` | Wi-Fi + `iw` |
| `usb_autosuspend` | `on`, `off` (jamais clavier ni souris) | USB |
| `audio_power_save` | `on`, `off` | `snd_hda_intel` |
| `clavier_retro` | 0 à 3 (borné au maximum du clavier) | clavier lumineux |
| `limite_charge` | `on`, `off` | seuil de charge de la batterie |

Refusés pour toujours (testé) : courbes de ventilateur, undervolt, ryzenadj, TDP brut, toute écriture libre dans `/sys`, toute
option de rendu d'Hyprland (`render:*`, `cm_*`, `use_fp16`, `xp_mode`, `new_render_scheduling`…), la fréquence d'écran sous le
maximum hors profil film.

## L'assistant root

`nc-energie-root etat | epp V | boost V | freqmax V | platform V | nvidia-pm V | nvidia-pl V | wifi-ps V | usb-autosuspend V |
audio-ps V | kbd V` (et `sudoers COMPTE`, qui n'écrit rien : la ligne sudo exacte). La règle sudo a une commande par
sous-commande et valeur (`nc-energie-root sudoers COMPTE` la montre) ; `visudo -cf` la vérifie à l'installation. Les chemins de
`/sys` sont construits dans le script, chaque écriture vérifie que le fichier existe déjà, aucune chaîne libre n'est acceptée.
Codes : 0 fait, 1 échec, 2 refusé, 3 rien de tel sur ce PC, 4 écrit mais la valeur relue est différente ou instable, 5 contrôleur de la plateforme resté sur un autre profil. Rien n'est réappliqué au démarrage.

## Profil de la plateforme (ventilateurs, limites du firmware)

Le noyau expose le profil de la plateforme dans `/sys/firmware/acpi/platform_profile` (choix communs dans
`platform_profile_choices`) et, par pilote, dans `/sys/class/platform-profile/*/{name,choices,profile}`. Avec plusieurs pilotes,
le fichier global ne propose que les choix communs et vaut `custom` quand leurs profils diffèrent (doc du noyau :
`Documentation/userspace-api/sysfs-platform_profile.rst`). Un portable n'a pas toujours les noms « standard » : `quiet` ou
`cool` à la place de `low-power`, `balanced-performance` sans `performance`.

Qui écrit le profil de la plateforme (un seul responsable) :

| Service de profils actif | Responsable du profil de la plateforme | Ce que fait le dépôt |
|---|---|---|
| TLP + `tlp-pd` (installé par `install.sh` sur portable) | TLP | écrit `/etc/tlp.d/12-nc-plateforme.conf` d'après les choix du noyau |
| `power-profiles-daemon` | lui (TLP ne touche pas au profil quand il tourne) | rien : `nc-diag` lit et compare |
| `tuned-ppd` / `tuned` | tuned | rien : `nc-diag` lit et compare |

`nc-profile-sync` n'écrit jamais dans `/sys` : il lit le profil du service et adapte l'interface et les cartes graphiques.

### TLP : une valeur par profil, choisie pour ce portable

`system/nc-tlp-plateforme` (lancé par `install.sh`, sans droits) lit les choix du noyau et produit le fichier TLP :
Performance : `performance`, sinon `balanced-performance` ; Équilibré : `balanced` ; Économie : `low-power`, sinon `quiet`,
sinon `cool`. `max-power` n'est jamais choisi. Un profil sans équivalent n'est pas écrit. Un réglage `PLATFORM_PROFILE_ON_*`
que tu as mis toi-même dans `/etc/tlp.conf` ou dans un de tes fichiers de `/etc/tlp.d` reste prioritaire : le fichier du dépôt
n'est alors pas posé.

Versions de TLP lues (sources `defaults.conf` et `func.d/10-tlp-func-cpu`) :

| TLP | Paramètres | Plusieurs valeurs ? |
|---|---|---|
| 1.9.0, 1.9.1, 1.10.0, 1.10.1, 1.10.2 | `PLATFORM_PROFILE_ON_AC` / `_BAT` / `_SAV` | non : une valeur, écrite telle quelle |
| 1.11.0-beta.2 | `_PRF` / `_BAL` / `_SAV` (les anciens `_AC` / `_BAT` sont traduits à l'exécution) | oui, mais chaque valeur trouvée est écrite dans l'ordre, sans s'arrêter à la première : la dernière l'emporte |

Une seule valeur choisie ici donne donc le même résultat avec toutes ces versions. Les anciens suffixes ne sont pas écrits pour
TLP 1.11 (ils y remplaceraient la liste de TLP par une seule valeur).

**Acer : « performance » est le mode Turbo, plus bruyant ; « Équilibré » reste le mode courant** (à confirmer par un essai réel). `nc-diag` le rappelle sur un portable Acer qui propose `performance` et `balanced-performance`. Détail, sans l'avoir confirmé sur un vrai PC : dans le pilote `acer-wmi` du noyau (chemin « Predator V4 »), `performance`
correspond au mode Turbo d'Acer et `balanced-performance` au mode Performance. TLP 1.11 préfère `balanced-performance` pour
les portables de jeu (moins de bruit de ventilateur). Ici Performance garde `performance` d'abord ; si l'usage montre trop de
bruit sur un Nitro, il suffit de mettre `balanced-performance` d'abord dans `system/nc-tlp-plateforme`.

### Diagnostic

`nc-diag` (section Énergie) distingue le **profil logiciel actif** (service de profils) du **mode matériel** lu dans `/sys` :
service qui pilote, profil demandé, profil lu et choix du noyau, contrôleurs (nom, profil, choix). Le mode matériel n'est
« confirmé » que s'il correspond au profil logiciel (power-saver : `low-power`, `quiet` ou `cool` ; balanced : `balanced` ;
performance : `performance` ou `balanced-performance`). Sans service : valeur lue, rien n'est confirmé. Pilote absent,
lecture refusée, `custom` ou contrôleurs en désaccord : un avertissement qui le dit, jamais un faux succès.
`nc-energie-root etat` donne les mêmes lectures (`platform`, `platform_choices`, `platform_ctl=nom|profil|choix`).

### Écriture par `nc-energie` (profils avancés)

`nc-energie-root platform V` n'écrit que le fichier global, si `V` est dans `platform_profile_choices`, puis **relit** la valeur
(toutes les 0,2 s pendant 5 s au plus, jusqu'à la valeur voulue sur 2 lectures de suite) et celle de chaque contrôleur (en lecture seule). Code 4 : écrit mais relu
différent ou instable (un service l'a réécrit, ou le firmware l'a refusé) ; code 5 : le fichier global est juste mais un contrôleur garde un autre profil ; `nc-energie` annule alors le profil entier et le dit. Dans
`nc-energie appliquer`, le profil du service passe AVANT le profil de la plateforme (le service réécrit souvent ce dernier) ; à la fin, `nc-energie` relit le profil du service, le profil de la plateforme, l'EPP, le boost et la fréquence maximale : un réglage réécrit par un service donne « non confirmé » (code 4), jamais un succès. `revenir` remet d'abord le profil du service, attend qu'il soit stable, remet le profil de la plateforme en dernier et relit tout.

**Limite connue** : « stable » veut dire la bonne valeur sur 2 lectures de suite, soit 0,2 à 0,4 s. Avec tlp-pd, `tlp PROFIL` est lancé
détaché (sans attendre sa fin) : s'il réécrit le profil de la plateforme, l'EPP ou le boost plus tard que ces deux lectures, `nc-energie`
peut annoncer un succès que TLP défait ensuite. `nc-diag` (section Énergie) relit l'état réel à tout moment. À mesurer sur un vrai
portable avec tlp-pd avant d'allonger la fenêtre.

### Valider sur un Acer Nitro (compatibilité réelle à confirmer)

Tant que ce test n'a pas eu lieu, rien ne prouve que les profils matériels marchent sur un Nitro précis : le pilote peut ne pas
fournir de profil matériel du tout, auquel cas seuls les profils logiciels agissent (CPU, écran, interface). Procédure, sans
numéro de série :

1. Référence du PC : `cat /sys/class/dmi/id/product_name /sys/class/dmi/id/board_name` (jamais le numéro de série).
2. Distribution, noyau (`uname -r`), service actif (`systemctl is-active tlp-pd power-profiles-daemon tuned-ppd tuned`), version
   de TLP (`tlp-stat -s`).
3. Choix et états : `cat /sys/firmware/acpi/platform_profile /sys/firmware/acpi/platform_profile_choices`, et pour chaque
   dossier de `/sys/class/platform-profile/` : `name`, `choices`, `profile`. `nc-diag` affiche l'essentiel.
4. `cat /etc/tlp.d/12-nc-plateforme.conf` (valeurs choisies pour ce PC).
5. Pour chaque profil (Performance, Équilibré, Économie), **sur secteur puis sur batterie** : le choisir dans la barre
   (Super + Alt + P), attendre 5 secondes, relire `platform_profile` et noter la valeur relue ; lancer `nc-diag`.
6. S'il existe une touche physique Acer de mode : l'appuyer, relire la valeur, et noter si le service la remet.
7. Joindre ces résultats à un ticket : la compatibilité n'est confirmée qu'avec la valeur relue de chaque profil sur secteur et
   sur batterie.

## Appliquer et revenir

`nc-energie appliquer NOM` relit la fiche, revalide le profil contre ce PC, montre l'aperçu, demande confirmation, garde l'état
d'avant dans `$XDG_STATE_HOME/nc/energie-avant.json`, applique d'abord le matériel puis les réglages, et revient en arrière à
la première erreur. Deux profils de suite : `revenir` rend l'état d'origine. Une valeur d'avant hors liste (par exemple une
fréquence maximale à 70 %) ne peut pas être remise par l'assistant : l'aperçu le dit.

## Pas encore fait

- Mesure du gain avec `nc-conso` (5 minutes avant et après).
- Les messages sont en français seulement.
- Pas de réglage `vfr` : il n'existe pas parmi les réglages de `nc-reglages`.

## Tout retirer

`nc-energie revenir` remet d'abord l'état d'avant le dernier profil. Pour retirer ensuite les assistants root et leurs
règles sudo (posés par install.sh avec ton accord) :

```bash
sudo rm -f /etc/sudoers.d/nc-energie /usr/local/bin/nc-energie-root            # profils d'énergie poussés
sudo rm -f /etc/sudoers.d/nc-limite-charge /usr/local/bin/nc-limite-charge     # limite de charge de la batterie
```

Sans eux, nc-energie ne propose plus que les réglages sans root (profil, luminosité, effets…).
