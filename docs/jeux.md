# Jeux sur portable hybride (Acer Nitro et autres)

Ce que noctalia-config fait pour les jeux, et ce qu'il ne fait jamais seul.

## Options de lancement Steam

Dans Steam : clic droit sur le jeu, Propriétés, Options de lancement :

    PROTON_ENABLE_NVAPI=1 gamemoderun mangohud %command%

`gamemoderun` démarre gamemode, `mangohud` affiche les images par seconde et les températures.

## Ce qui est installé

- `~/.config/gamemode.ini` : fourni seulement s'il n'existe pas. S'il existe, install.sh le sauvegarde puis ajoute `start=` et `end=` dans `[custom]` sans toucher au reste. Un `start=` ou `end=` déjà écrit par vous n'est jamais remplacé.
- `desiredgov=` est vide : gamemode ne change pas le gouverneur CPU.
- Il n'y a pas de section `[gpu]` : gamemode la refuse dans le fichier de l'utilisateur.
- `~/.config/MangoHud/MangoHud.conf` : conf minimale, fournie seulement si elle n'existe pas. Jamais écrasée.
- Rien n'est installé si gamemode ou MangoHud sont absents.

## nc-gpu-jeu

gamemode lance `nc-gpu-jeu debut` au début du jeu et `nc-gpu-jeu fin` à la fin.

- `debut` : pose la limite de fréquence du GPU (`nc-energie-root gpu-frequence jeu`), seulement en profil Performance et si `JEU_GPU_MHZ` n'est pas `off`. Le GPU oublie la limite quand il s'endort (RTD3) : c'est pour cela qu'on la repose à chaque lancement.
- `fin` : retire la limite.
- Le GPU endormi n'est jamais réveillé (l'assistant root le vérifie).
- Sans assistant root ou sans réglage : silencieux, code 0.

`JEU_GPU_MHZ` se règle dans nc-reglages, section Énergie (ou dans `~/.config/nc-profile.conf`). Par défaut `off`, sauf sur l'Acer Nitro ANV16-72 (1500).

## nvidia-powerd

Jamais activé automatiquement : avec un chargeur de 135 W, il vide la batterie en jeu.
