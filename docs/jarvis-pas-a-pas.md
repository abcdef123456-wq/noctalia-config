# JARVIS pas à pas (Debian 13)

Ce guide est pour toi si tu débutes. Tu vas installer le serveur JARVIS sur ton PC, le relier à un bot Telegram,
et lui écrire depuis ton téléphone. Chaque étape dit quoi taper et ce que tu dois voir. Si ce que tu vois ne
ressemble pas à ce qui est écrit, arrête-toi et va voir « Les erreurs courantes » plus bas.

## Avant de commencer

Il te faut :

- un PC sous Debian 13, avec un compte qui peut utiliser `sudo` (le mot de passe de ton compte) ;
- une connexion Internet ;
- un compte Telegram sur ton téléphone ;
- un compte Claude (celui de Claude Code) ;
- environ une heure, car les installations prennent du temps.

Trois règles :

- Les commandes sont entre `` ` ``. Tu les copies, tu les colles dans le terminal, puis tu appuies sur Entrée.
- Quand tu tapes un mot de passe, rien ne s’affiche. C’est normal.
- Ton jeton Telegram est comme un mot de passe. Ne le donne à personne et ne le mets dans aucun message ni fichier partagé.

## Partie 1 : Debian 13

### Étape 1 : Ouvrir un terminal

1. Appuie sur **Super + Entrée** (la touche Super est celle avec le logo Windows ou Linux).
   Si le bureau n’est pas encore installé, ouvre le menu des applications et cherche « Terminal ».
   Tu dois voir : une fenêtre avec du texte et un curseur qui clignote.

### Étape 2 : Installer noctalia-config (si ce n’est pas déjà fait)

La commande `nc-jarvis` vient avec le bureau noctalia-config. Si tu l’as déjà installé, passe à l’étape 3.

1. Vérifie. Tape : `command -v nc-jarvis`
   Tu dois voir : un chemin qui finit par `nc-jarvis`, par exemple `~/.local/bin/nc-jarvis`.
   Si rien ne s’affiche, continue.
2. Si `curl` n’est pas installé (Debian minimal), tape d’abord : `sudo apt install curl`
   Tape ton mot de passe, puis Entrée, puis `o` et Entrée si on te le demande.
3. Installe le bureau. Tape :
   `bash <(curl -fsSL https://raw.githubusercontent.com/abcdef123456-wq/noctalia-config/main/get.sh)`
   Tu dois voir : le dépôt qui se télécharge, puis l’installeur qui pose des questions.
4. Réponds aux questions :
   - `o` pour les paquets et les fichiers ;
   - `n` pour chaque étape système (profils d’énergie, Wi-Fi, écran de démarrage, écran de connexion, pilote NVIDIA).
     JARVIS n’en a pas besoin.
   Si on te demande ton mot de passe, tape-le (rien ne s’affiche), puis Entrée.
5. Attends la fin. Tu dois voir : un message de fin, puis le curseur revient.
6. Ouvre un nouveau terminal (Super + Entrée), puis tape : `command -v nc-jarvis`
   Tu dois voir : le chemin de `nc-jarvis`, comme à l’étape 2.1.

### Étape 3 : Vérifier ce qui manque

1. Tape : `nc-jarvis verifier`
2. Tu dois voir : une liste de contrôles.
   - Une ligne avec **✓** est prête.
   - Une ligne avec **✗** manque. La commande à taper est écrite à côté.

Garde cette liste sous les yeux. Les étapes 4 à 6 installent ce qui manque le plus souvent.

### Étape 4 : Installer les outils (git, Python, Node)

1. Tape : `sudo apt update`
   Tu dois voir : des lignes qui défilent, puis le curseur revient.
2. Tape : `sudo apt install git python3 python3-venv python3-pip nodejs npm curl`
   Tape ton mot de passe, puis Entrée. Si on te demande « Voulez-vous continuer ? », tape `o` puis Entrée.
   Tu dois voir : des lignes qui défilent, puis le curseur revient.
3. Vérifie Python. Tape : `python3 --version`
   Tu dois voir : `Python 3.` suivi d’un nombre égal ou supérieur à 11. Sur Debian 13, c’est 3.13.

### Étape 5 : Installer et connecter Claude Code

JARVIS a besoin d’un « moteur » : un programme d’IA installé et connecté sur ton PC. Ce guide prend Claude Code,
que le déployeur appelle `claude`. Le déployeur connaît aussi `codex`, `opencode` et `agy`, mais ce guide ne les couvre pas.

1. Tape : `npm install -g @anthropic-ai/claude-code`
   Tu dois voir : des lignes, puis le curseur revient.
   Si tu vois « EACCES » ou « permission denied », ne mets pas `sudo` devant. Envoie tout le message à la personne qui t’aide.
2. Vérifie. Tape : `claude --version`
   Tu dois voir : un numéro de version.
3. Tape : `claude`, puis suis les indications pour te connecter avec ton compte Claude.
   Une page s’ouvre dans le navigateur.
   Tu dois voir : l’invite de Claude Code, une fois la connexion faite.
4. Tape `/exit`, puis Entrée, pour quitter.

### Étape 6 : Récupérer le jeton Telegram

1. Dans Telegram, cherche **@BotFather** (le bot officiel de Telegram).
2. Écris-lui : `/newbot`
3. Il demande un nom (celui que tu verras dans ta liste), puis un identifiant qui finit par `bot`, par exemple `mon_jarvis_bot`.
4. Il répond avec une ligne qui ressemble à `123456789:ABCdef…`. C’est ton jeton. Copie-la en entier.
   Tu dois voir : un message de félicitations avec cette ligne.
5. Garde-la pour l’étape 8. Ne la partage avec personne.

### Étape 7 : Récupérer ton identifiant Telegram

1. Dans Telegram, cherche **@userinfobot**.
2. Écris-lui : `/start`
3. Il répond avec tes informations. Repère la ligne **Id**, suivie d’un nombre. Copie ce nombre.
   Ce nombre dit à JARVIS que c’est toi qui peux lui parler.

### Étape 8 : Lancer le déployeur

1. Tape : `nc-jarvis deployer`
2. Tu dois voir : le titre « JARVIS-BIS : local », le dossier d’installation, puis une première question.
   Réponds aux questions comme dans ce tableau. Elles arrivent une par une.

| Question | Ce que tu réponds |
| --- | --- |
| Préparer ce backend (Git, venv et dépendances Python) ? | `o`, puis Entrée. Cette étape peut prendre plusieurs minutes. |
| Moteur initial : agy, codex, claude, opencode | `claude`, puis Entrée. |
| Token Telegram (vide : conserver) | Colle le jeton de l’étape 6. Rien ne s’affiche : c’est normal. Entrée. |
| Token Discord (vide : conserver) | Entrée (rien). On ne se sert pas de Discord ici. |
| IDs Telegram autorisés | Ton identifiant de l’étape 7, puis Entrée. |
| IDs Discord autorisés | Entrée (rien). |
| Configurer les modules maintenant ? | `n`, puis Entrée. Tu pourras le faire plus tard. |
| Installer/mettre à jour ces services ? | `o`, puis Entrée. |
| Activer et démarrer/redémarrer ces deux services maintenant ? | `o`, puis Entrée. |
| Remplacer la connexion client existante par ce backend local ? | `o`, puis Entrée. Cette question n’apparaît que si une connexion existe déjà. |

3. Tu dois voir à la fin : `Préparation terminée.`
   Si tu vois « Déploiement arrêté : … », passe à « Les erreurs courantes ».
4. Vérifie que les deux services tournent. Tape :
   `systemctl --user status assistant-gateway assistant-runner`
   Tu dois voir : `Active: active (running)` pour les deux services.

### Étape 9 : Écrire /start à ton bot

1. Dans Telegram, ouvre le bot que tu as créé à l’étape 6 (il porte le nom que tu lui as donné).
2. Écris : `/start`, puis envoie.
3. Tu dois voir : une réponse du bot. Tu peux maintenant lui écrire comme à une personne.

Le bot ne répond qu’à ton identifiant Telegram. Si quelqu’un d’autre lui écrit, il ne répond pas.

## Sur Fedora, Arch et openSUSE

Les étapes sont les mêmes. Change seulement les commandes d’installation de l’étape 4 (et l’étape 2.2 si `curl` manque) :

- **Fedora** : `sudo dnf install git python3 python3-pip nodejs npm curl`
  Le module venv est déjà inclus avec `python3`.
- **Arch** : `sudo pacman -Syu` puis `sudo pacman -S --needed git python python-pip nodejs npm curl`
- **openSUSE Tumbleweed ou Slowroll** : `sudo zypper install git python3 python3-pip nodejs npm curl`
  Si `python3 -m venv --help` affiche une erreur, installe le paquet venv de ta version de Python
  (`python3-venv`, ou `python311-venv` selon `python3 --version`).

Sur openSUSE Leap 15.6, l’installeur ne met pas en place le bureau. Demande de l’aide avant de continuer.

## Les erreurs courantes et quoi faire

### Le déployeur s’arrête pendant la création de l’environnement Python

Tu vois un message qui parle de `venv` ou de `ensurepip`. Il manque le paquet venv.
Tape : `sudo apt install python3-venv` (sur Fedora, Arch ou openSUSE, voir la section plus haut).
Puis relance : `nc-jarvis deployer`. Il garde ce qui est déjà bon.

### Un port est déjà pris (8000 ou 8080)

JARVIS utilise les ports 8000 et 8080. Si un autre programme les occupe, le service ne démarre pas.

1. Tape : `ss -ltnp | grep -E ':(8000|8080) '`
   Tu dois voir : la ligne du programme qui occupe le port, ou rien.
2. Si c’est un ancien JARVIS, demande de l’aide avant d’arrêter quoi que ce soit.
   Ne tue jamais un programme que tu ne reconnais pas.

### Le moteur (Claude Code) n’est pas connecté

Le bot répond par une erreur, ou ne répond pas, et `nc-jarvis verifier` marque le moteur en **✗**.

1. Tape : `claude`
2. Pose une question simple, par exemple « Bonjour ».
   Tu dois voir : une réponse de Claude.
   Si Claude te demande encore de te connecter, refais l’étape 5.
3. Tape `/exit`, puis Entrée.

### Le bot ne répond pas

Fais ces vérifications dans l’ordre.

1. Tape : `nc-jarvis verifier` et regarde les **✗**.
2. Lis le journal du service qui parle à Telegram. Tape :
   `journalctl --user -u assistant-gateway -n 50`
   Tu dois voir : les 50 dernières lignes. Si tu demandes de l’aide, garde-les.
   Pour le service qui fait tourner le moteur, tape aussi :
   `journalctl --user -u assistant-runner -n 50`
3. Vérifie ton identifiant Telegram (étape 7). Avec un mauvais identifiant, le bot ignore tes messages.
   Relance `nc-jarvis deployer` et corrige la question « IDs Telegram autorisés ».
   Pour les autres questions, appuie simplement sur Entrée : les valeurs déjà bonnes sont gardées.

### Ça s’arrête quand je ferme ma session

Les services ne restent actifs après la fermeture de ta session que si l’option « linger » est activée.

1. Tape : `sudo loginctl enable-linger "$USER"`
   Tape ton mot de passe, puis Entrée.
2. Vérifie. Tape : `loginctl show-user "$USER" -p Linger`
   Tu dois voir : `Linger=yes`.

Sur un serveur allumé en permanence, c’est la personne qui administre le serveur qui fait cette étape.

### Le déployeur affiche une autre erreur

Lis le message. Il dit en général ce qui manque ou quel fichier pose problème.
Ne supprime rien dans `~/.local/share/jarvis-bis` ni dans `~/.config/nc` pour « réparer » : tu perdrais tes données.
Si tu ne comprends pas le message, va à la fin de ce guide.

## Ce qu’il ne faut pas faire

- Ne lance jamais deux bots (ou deux serveurs) avec le même jeton Telegram.
- Ne mets jamais ton jeton, ni ta clé `SECRET_KEY`, dans un message, un fichier partagé ou une capture d’écran.
- Ne supprime pas les dossiers de JARVIS pour « recommencer » : relance plutôt le déployeur.

## Si tu es bloqué

Tape `nc-jarvis verifier`, copie tout ce qui s’affiche et envoie-le à la personne qui t’aide (il n’y a aucun secret dedans).
