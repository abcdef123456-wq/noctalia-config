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

## Vie privée

Les données restent sur ta machine. Pendant un partage d'écran, le panneau, l'infobulle et le résumé sont vides :
le masquage se fait à un seul endroit (`GarminEtat.qml`).
