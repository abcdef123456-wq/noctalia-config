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
Codes : 0 fait, 1 échec, 2 refusé, 3 rien de tel sur ce PC. Rien n'est réappliqué au démarrage.

## Appliquer et revenir

`nc-energie appliquer NOM` relit la fiche, revalide le profil contre ce PC, montre l'aperçu, demande confirmation, garde l'état
d'avant dans `$XDG_STATE_HOME/nc/energie-avant.json`, applique d'abord le matériel puis les réglages, et revient en arrière à
la première erreur. Deux profils de suite : `revenir` rend l'état d'origine. Une valeur d'avant hors liste (par exemple une
fréquence maximale à 70 %) ne peut pas être remise par l'assistant : l'aperçu le dit.

## Pas encore fait

- Mesure du gain avec `nc-conso` (5 minutes avant et après).
- Les messages sont en français seulement.
- Pas de réglage `vfr` : il n'existe pas parmi les réglages de `nc-reglages`.
