# Santé Garmin (panneau de l'île)

Un panneau de l'île affiche tes mesures Garmin : batterie corporelle, sommeil, rythme cardiaque, stress, pas, VFC, etc.
Tu choisis les cartes affichées et tu peux noter ton hydratation.

## L'activer

- Mets `GARMIN_ACTIF=oui` dans les réglages (section Garmin de nc-reglages), puis rouvre la session ou recharge Hyprland.
- Ouvre le panneau avec Super + Alt + S. La première carte propose d'installer le connecteur puis de te connecter.
- Le mode démo montre des mesures d'exemple sans compte. Avec `GARMIN_ACTIF=non`, rien ne tourne et le raccourci n'existe pas.

À l'ouverture, le panneau lit l'état puis lance une synchronisation. « Actualiser » force la synchronisation.
Il n'y a aucune minuterie : panneau fermé, rien ne s'exécute.

## Connecteur non officiel

Le connecteur utilise la bibliothèque `garminconnect`, qui n'est pas un service officiel de Garmin.
Il peut cesser de marcher si Garmin change son service.

## Clés lues, non confirmées

Les clés JSON lues (`bodyBatteryValuesArray`, `dailySleepDTO`, `sleepScores`, `hrvSummary`, `avgStressLevel`...,
voir `home/.local/libexec/nc-garmin-connecteur.py`) n'ont PAS été confirmées avec un vrai compte Garmin.
Une mesure peut donc manquer ou rester vide. Si c'est le cas, le panneau n'affiche rien pour cette carte.

Le tableau du haut (5 jauges, courbes de la journée, phases du sommeil, distance) lit en plus ces noms, eux aussi
**à confirmer avec un vrai compte** :

| Mesure | Clé lue chez Garmin | Clé du panneau |
|---|---|---|
| Distance du jour | `totalDistanceMeters` (résumé du jour) | `distance_m` |
| Phases du sommeil | `deepSleepSeconds`, `lightSleepSeconds`, `remSleepSeconds`, `awakeSleepSeconds` (`dailySleepDTO`) | `sommeil_profond_s`, `sommeil_leger_s`, `sommeil_paradoxal_s`, `sommeil_eveil_s` |
| Courbe Body Battery | `bodyBatteryValuesArray`, valeur en 2ᵉ position de chaque paire | `bb_serie` |
| Courbe du cœur | `heartRateValues`, paires [heure, valeur] | `fc_serie` |
| Courbe du stress | `stressValuesArray`, paires [heure, valeur] ; les valeurs négatives (pas de mesure) sont écartées | `stress_serie` |

Toutes ces clés sont facultatives. Une jauge sans valeur affiche « — », et une courbe ou la barre du sommeil sans
données reste cachée. Chaque courbe garde 300 points au plus.

## Vie privée

Les données restent sur ta machine. Pendant un partage d'écran, le panneau, l'infobulle et le résumé sont vides :
le masquage se fait à un seul endroit (`GarminEtat.qml`).
