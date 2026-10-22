# noctalia-config

Un bureau **Hyprland + Noctalia v5** complet, installable en une commande, sur n'importe quel PC compatible avec Noctalia
(portable ou fixe, Intel, AMD ou NVIDIA). La config Hyprland est au **format Lua** (Hyprland 0.55 ou plus).

- Couleurs tirées du fond d'écran : barre, terminal, Dolphin, bordures des fenêtres (vives ou sobres selon l'image) ;
- **île dynamique** au centre de la barre : l'heure, ta musique (pochette, égaliseur qui danse sur le son) ; elle
  s'étire comme sur iPhone pour le volume, la luminosité, un nouveau morceau, le chargeur, le profil d'énergie ; un clic
  (ou **Super + C**) et le centre de contrôle en sort : Wi-Fi, Bluetooth, son, luminosité, profils, mode jeu… ;
- **fenêtres comme sur macOS** : **Super + H** masque la fenêtre ; dans la barre, le titre de la fenêtre s'agrandit au
  survol et montre toutes les fenêtres du bureau, les masquées comprises (un clic les ramène), un clic ouvre le menu des
  fenêtres, la molette passe de l'une à l'autre ; trois doigts vers le haut : la vue de toutes les fenêtres ;
- **Super + R** : recherche compacte au centre de l'écran (applis, fichiers, calculs) ;
- **Super + W** : carrousel de fonds d'écran ; **Super + /** : fiche de tes raccourcis ;
- s'adapte à chaque écran : échelle choisie d'après sa taille réelle, panneaux et carrousel à la bonne taille et centrés ;
- écran de verrouillage épuré (heure, date, musique en cours), coins d'écran arrondis ;
- terminal kitty assorti, zsh avec oh-my-zsh et powerlevel10k, accueil (logo, processeur, mémoire, batterie) ;
- look façon Apple : île dynamique noir pur qui se déploie depuis la pilule et s'y rétracte (ressort physique),
  symboles dessinés dans l'esprit des SF Symbols dans l'île ; ailleurs, thème d'icônes maison « NC » (dossiers,
  corbeille, « Terminal », « Fichiers ») aux couleurs du fond d'écran, explorateur Nautilus façon Finder ;
- Neovim avec LazyVim et ses extras (C/C++, JavaScript, formatage, Git), plugins aux versions de `lazy-lock.json` ;
- 3 profils d'énergie (Performance, Équilibré, Économie), mêmes réglages sur tous les portables ; en Économie, animations,
  flou et changement de fond coupés ; **mode jeu** (Super + Alt + G) ;
- PC hybride (Intel/AMD + NVIDIA) : bureau sur la carte intégrée, la NVIDIA dort tant qu'un jeu ne la réveille pas ;
- captures d'écran à annoter, presse-papiers, émojis, lumière de nuit, loupe, en un raccourci chacun ;
- tes propres raccourcis en une commande (`nc-raccourci`), mise à jour en une commande (`nc-maj`) ;
- **un bureau qui réagit tout seul** : halo qui pulse sur les basses de ta musique, mode jeu automatique au lancement
  d'un jeu, marque-pages de fenêtres, fenêtres flottantes qui se rouvrent là où tu les as laissées ;
- écran de démarrage (logo animé, thème GRUB) et écran de connexion assortis, proposés à l'installation.

## Installation

Une seule ligne (Arch, Fedora, Debian 13, Ubuntu) : installe git s'il manque, télécharge le dépôt dans
`~/noctalia-config` (ou le met à jour), puis lance `./install.sh` :

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/abcdef123456-wq/noctalia-config/main/get.sh)
```

Sans `curl` (Debian minimal) : `bash <(wget -qO- https://raw.githubusercontent.com/abcdef123456-wq/noctalia-config/main/get.sh)`

Ou à la main :

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
| Étapes système | propose, **une par une** : profils d'énergie, Wi-Fi (Arch), écran de démarrage, écran de connexion, pilote NVIDIA |

Relancé, il **saute tout ce qui est déjà en place** (paquets, fichiers identiques, terminal, Neovim, étapes système déjà
faites) : seul ce qui manque ou a changé est fait.

| Distribution | Hyprland et Noctalia v5 |
|---|---|
| Arch et dérivées (CachyOS, EndeavourOS, Manjaro…) | installés depuis les dépôts officiels |
| Fedora (44 ou plus) | Noctalia depuis les dépôts officiels ; Quickshell récent via le COPR `errornointernet/quickshell` si nécessaire ; Hyprland via le COPR `sdegler/hyprland` (le script propose les dépôts avant de les activer) |
| Debian 13, Debian Sid, Ubuntu 26.04 | Noctalia via le dépôt officiel de Noctalia (le script te montre les adresses et demande avant). Debian 13 : Hyprland 0.55, Noctalia et TLP viennent de « trixie-backports », la source officielle de Debian pour les versions récentes, que le script propose d'activer ; Neovim récent (0.11+) proposé depuis neovim.io |
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
- n'écrase jamais tes images (fonds d'écran, photo de profil) ni les fichiers que le bureau régénère (couleurs, profil d'énergie) ;
- remplace chaque fichier d'un coup : Hyprland, qui recharge sa config à chaque changement, ne la voit jamais incomplète ;
- retire l'ancienne config Hyprland au format `.conf` (sauvegardée) : seul `hypridle.conf` reste, hypridle ne lisant que ce format ;
- peut être relancé sans risque : ce qui est déjà à jour n'est pas recopié ;
- met à jour une installation faite avec l'ancienne version de ce dépôt (fichiers « legion ») : les anciens fichiers sont
  retirés après sauvegarde, et une session ouverte passe directement au format Lua.

> Attention : ta config Noctalia existante (`~/.config/noctalia/config.toml`) est remplacée (une copie est gardée). Les réglages
> faits depuis l'interface de Noctalia sont dans `~/.local/state/noctalia/settings.toml` et ne sont pas touchés.

## Raccourcis

Les principaux : **Super + R** recherche · **Super + W** fonds d'écran · **Super + /** fiche des raccourcis · **Super + Entrée** terminal ·
**Super + L** verrouiller · **Super + C** centre de contrôle. La liste complète est dans [RACCOURCIS.md](RACCOURCIS.md).

| Nouveau | Raccourci |
|---|---|
| Capture de l'écran · d'une zone · à annoter | **Impr. écran** · **Super + P** · **Super + Maj + S** |
| Projeter sur un second écran ou un projecteur : écran du PC seulement, dupliquer, étendre (côté au choix), second écran seulement (comme Windows + P) | **Super + O** |
| Historique du presse-papiers · émojis | **Super + Maj + V** · **Super + .** |
| Lumière de nuit · ne pas déranger | **Super + N** · **Super + Maj + N** |
| Loupe (zoom autour du curseur) | **Super + Ctrl + molette**, ou **Super + =** / **Super + -** |
| Mode jeu : effets coupés, image envoyée sans attendre l'écran, notifications en pause | **Super + Alt + G** (même touche pour sortir) |
| Revenir au bureau précédent | **Super + chiffre** du bureau où tu es déjà |
| IA sur le texte sélectionné (résumer, traduire, corriger…) · expliquer une zone de l'écran | **Super + I** · **Super + Maj + I** |
| Le terminal écrit la commande décrite (relue avant Entrée) | **Alt + I** |

## Île dynamique

Au centre de la barre, une pilule noire comme l'île de l'iPhone : l'heure, ta musique (pochette, onde sonore). Elle
s'étire quelques secondes pour le volume, la luminosité, un nouveau morceau, le chargeur, le profil d'énergie, le mode
jeu. Un clic (ou **Super + C**) et elle se déploie en centre de contrôle façon iOS : Wi-Fi, Bluetooth, ne pas déranger,
mode jeu, musique, curseurs verticaux de luminosité et de volume, lumière de nuit, halo musical, profil d'énergie,
capture, notifications, réglages, verrouillage, extinction. **Appui long (ou clic droit)** sur Wi-Fi, Bluetooth ou le
volume : page de détails (réseaux avec mot de passe, appareils, sorties audio et micro). Clic ailleurs ou **Échap** : elle
se referme dans la pilule.

**Super + R** ouvre le Spotlight : applis, fenêtres, fichiers, calculs, `> commande`, **`? question`** (et toute
question comme « comment changer le fond d'écran » : réponses instantanées de la config, sans IA — réglages, raccourcis,
commandes, documentation, `nc-aide-config` ; Entrée sur un réglage ouvre la fenêtre des réglages dessus, l'IA reste
proposée en dernier ; la recherche de la fenêtre des réglages comprend aussi ces questions), et
**`+ nom` pour installer un logiciel** (dépôts de ta distribution, AUR avec paru ou yay, Flatpak ; `nc-logiciels`) :
Entrée ouvre un terminal qui l’installe, après ton mot de passe (et la recette PKGBUILD pour l’AUR). En tapant sans
préfixe, deux logiciels à installer dont le nom commence par ta saisie s’ajoutent en bas (réglage « Logiciels à
installer dans le Spotlight »).

**L'IA du bureau** ([détails](docs/ia.md)) : une clé d'API (Anthropic, OpenAI, Gemini, Mistral, Groq, DeepSeek,
OpenRouter), Claude Code, Codex, Gemini CLI, OpenCode, Ollama ou JARVIS — **automatique** (la meilleure disponible, la
suivante si elle échoue), **choisie**, ou **aucune** (tout est coupé, sur toutes les distributions) dans
**nc-reglages → Intelligence artificielle**. Elle répond au `? ` du Spotlight, travaille sur le texte sélectionné
(**Super + I**, ou `! ` dans le Spotlight : résumer, traduire, corriger…), explique une zone de l'écran
(**Super + Maj + I**), écrit une commande dans le terminal (**Alt + I**, à relire avant Entrée ; `ia question`).
Aussi : pastille IA du centre de contrôle, presse-papiers et notifications de l'île, bouton des captures, clic droit
dans les fichiers, Neovim (`Espace i`), `nc-diag ia`, et, si tu l'actives, `@ ` dans le Spotlight : l'IA propose de
gérer les services de ta session, le Wi-Fi, le Bluetooth, l'énergie, le son, les réglages ou les mises à jour, et
chaque action attend ta confirmation. Clés : `nc-ia configurer`, la fenêtre « Clés des IA » (privées, jamais affichées, essayées tout de suite).

Pour l’île Quickshell, **nc-settings → Pages de l’île** permet d’activer ou désactiver chaque page.
Les [réglages de pages](docs/pages-ile.md) prennent effet sans redémarrage.

Sur Arch, l'île est dessinée par **Quickshell** par-dessus la barre de Noctalia (`~/.config/quickshell/nc-ile`,
service `nc-ile`), avec les icônes Material Symbols Rounded. Ailleurs, la même île est fournie par le plugin Noctalia
`nc/ile` (un peu moins libre : elle s'ouvre juste sous la barre).

## Automatismes

| | |
|---|---|
| **Halo musical** | Quand de la musique joue, le halo coloré de la fenêtre active pulse sur les basses (cava écoute la sortie son). Coupé en Économie, en mode jeu et sur batterie (sauf en Performance). **Super + Alt + M** pour le couper ou le remettre ; `nc-pouls demo` pour le voir sans musique. |
| **Mode jeu automatique** | Un jeu s'ouvre (Steam, Proton, gamescope, `.exe`) : profil Performance et mode jeu. Le dernier jeu fermé : retour au profil d'avant, effets et notifications rétablis. |
| **Marque-pages de fenêtres** | **Super + Ctrl + 1…4** : le premier appui attache la fenêtre active à la touche ; ensuite, la touche t'amène à elle depuis n'importe quel bureau, et depuis elle te ramène à la fenêtre d'avant. **Super + Ctrl + Maj + 1…4** pour en attacher une autre. |
| **Fenêtres flottantes** | Chaque appli flottante (calculatrice, réglages, lecteur…) se rouvre à la taille et à la place où tu l'as fermée, en proportion de l'écran. |

### Tes raccourcis

Le plus simple : `nc-raccourci` (ou `nc-reglages`, section Raccourcis). Tous les raccourcis y sont listés ; Entrée sur
l'un d'eux pour changer ses touches (tu appuies sur la nouvelle combinaison) ou le désactiver, « Ajouter un raccourci »
pour en créer un. En ligne de commande :

```bash
nc-raccourci ajoute "Super+B" firefox              # Super + B : va à Firefox s'il est ouvert, sinon le lance
nc-raccourci ajoute "Super+Alt+S" "ile son"        # ouvre la page Son de l'île (aussi : bureau 3, ou une commande)
nc-raccourci change "Super+Entrée" "Super+T"       # un raccourci de la config sur d'autres touches
nc-raccourci desactive "Super+N"                   # désactive un raccourci de la config
nc-raccourci retablit tout                         # annule tes changements de raccourcis de la config
nc-raccourci liste                                 # tous les raccourcis, et tes changements
```

Tout est gardé dans `~/.config/nc/raccourcis.conf`, jamais touché par les mises à jour ; une combinaison déjà prise est refusée.

Ils apparaissent tout de suite dans la fiche **Super + /** (section « Mes raccourcis »). Une combinaison déjà prise est
refusée, en tenant compte de la disposition du clavier (AZERTY, QWERTZ…). Ils sont rangés dans `~/.config/hypr/perso.lua`,
que tu peux aussi éditer (exemples dedans) et qu'aucune mise à jour ne remplace.

## Écrans

Chaque écran reçoit sa définition native et une échelle choisie d'après sa densité de pixels (mêmes seuils que Hyprland), sans
jamais descendre sous 1600 x 900 points utiles : un portable 15" en 1920 x 1080 est à 1,2 (et non 1,5, où tout paraît zoomé).
Sur un écran à haute fréquence, la définition native est le mode que l'écran dit préférer : un écran 1440p à 144 Hz branché
en HDMI annonce aussi un 3840 x 2160 à 60 Hz (compatibilité consoles) qui n'est pas sa dalle ; il reste en 1440p à 144 Hz.
La recherche, la fiche des raccourcis et le carrousel se dessinent à la taille de l'écran et restent centrés.

Pour forcer une échelle, dans `~/.config/hypr/perso.lua` :

```lua
hl.monitor({ output = "HDMI-A-1", mode = "preferred", position = "auto", scale = 1 })
```

## Énergie

Trois profils, à choisir dans la barre (icône d'énergie) ou avec **Super + Alt + P** :

- **Performance** : fréquence maximale de l'écran interne, effets complets, processeur à fond ;
- **Équilibré** (par défaut) ;
- **Économie** : écran interne à 60 Hz, sans flou ni animations, luminosité limitée, clavier éteint, Bluetooth coupé s'il est inutilisé ;
  l'île coupe aussi ses animations et l'analyse du son de l'onde musicale (cava), et ne charge plus d'images décoratives
  (pochettes, images des notifications, fond flouté de la vue des fenêtres, icônes des logiciels à installer). Chaque
  coupure se règle dans nc-reglages → Énergie (« Couper les effets », « Pas d'images décoratives en Économie »).

Les profils viennent du service de ta distribution : TLP sur un portable sous Arch (réglages communs à tous les portables, limite
de charge à environ 80 % proposée si la batterie la gère), `tuned-ppd` sur Fedora, `power-profiles-daemon` ailleurs. Un service
déjà en place est gardé. Fréquences par profil : `~/.config/nc-profile.conf` (voir `nc-profile-sync`).

Sur un **portable**, les profils viennent de TLP et tlp-pd avec les réglages du dépôt (`system/tlp.d/10-nc.conf` : processeur,
turbo, carte PCIe, mode de la plateforme) : les mêmes sur Arch, Fedora 44+, Debian 13 et openSUSE Tumbleweed. Ailleurs, et
sur un PC fixe, le service de la distribution est utilisé. La limite de charge à 80 % est proposée si la batterie la gère
(Lenovo, ASUS, Dell, ThinkPad… ; pas encore les Acer sous Linux).

### PC hybride (carte intégrée + NVIDIA)

- Le bureau tourne sur la carte intégrée, qui porte l'écran interne : la NVIDIA peut s'endormir (batterie, chaleur, bruit).
  Si un écran est branché sur une prise reliée à la NVIDIA à l'ouverture de session, les deux cartes sont utilisées.
  Écran ou projecteur branché après coup sur une de ces prises (souvent le HDMI) : une notification propose de rouvrir
  la session (Hyprland ne peut pas ajouter une carte en cours de route) ou de toujours garder la NVIDIA.
  Réglage dans `~/.config/uwsm/gpu-mode` : `auto` (défaut), `igpu`, `both` ou `off` (détails dans `~/.config/uwsm/env-hyprland`).
- Lancer une appli sur la NVIDIA : `nvidia-run <commande>` (Steam : `nvidia-run %command%`) ; en Performance, les applis
  lancées depuis la barre y vont d'elles-mêmes.
- Pilote : sur Arch, le script installe le pilote officiel s'il manque (`nvidia-open`, nécessaire aux RTX 50). Sur Debian 13,
  les RTX 50 demandent le pilote de NVIDIA (celui de Debian, 550, est trop ancien) : le script donne la marche à suivre.

Les services Google (agenda dans le calendrier de l’île, par la connexion Google de JARVIS) ne s’affichent que si
**nc-settings → Intégration Google** est activé : sans compte Google relié, rien ne change (voir [docs/pages-ile.md](docs/pages-ile.md)).

## Personnaliser sans perdre tes réglages

[JARVIS](docs/jarvis.md) relie le chat de l’île à une petite fenêtre de chat vierge (**Super + Maj + A**, épinglable
sur tous les bureaux avec Super + Ctrl + P) et à un cockpit extensible en plein écran (**Super + Ctrl + A**,
ou application JARVIS). Il gère les modules, le modèle et la session, la mémoire, les rappels mobiles,
Telegram/Discord et les services. Dans l’île, le micro dicte dans le champ de saisie (`nc-dictee`, transcription
par le serveur), sans envoi automatique. Rappels récurrents (`/rappel telegram tous les jours 08:30 …`, `/rappels`,
`/supprimer`), alertes Telegram de la machine (batterie faible, service en échec, fin de mise à jour : réglage
« Alertes Telegram ») et réglages du PC depuis le bot (`/nc`, déploiement local seulement) sont décrits dans
[docs/jarvis.md](docs/jarvis.md). **nc-settings → Agents IA** propose la connexion et les déploiements facultatifs
sur ce PC ou sur un serveur SSH. Le client n’exécute pas lui-même de modèle ; le backend JARVIS-BIS reste séparé.
Le même client est fourni sur Arch, Fedora/Nobara, Debian/Ubuntu et openSUSE. Sans Quickshell, les commandes
et le [chat terminal](docs/assistant-distant.md) restent accessibles. Aucun backend n’est installé ni démarré par `nc-maj`.

Depuis un autre réseau que celui du serveur, une URL `192.168.x.x` ou `*.local` ne suffit pas : expose le gateway
avec un tunnel HTTPS côté serveur (Cloudflare Tunnel, Tailscale ou Render), puis configure cette URL publique.
La connexion se règle dans une fenêtre (**Connexion JARVIS** : « Configurer la connexion » du cockpit, la fenêtre des
réglages, ou `nc-assistant configurer`), avec un bouton « Tester la connexion ». `nc-assistant verifier` (ou
**nc-reglages → Agents IA → Tester l'assistant distant**) diagnostique réseau, clé, certificat TLS et état du runner.

**Firefox** (étape facultative de `install.sh`, réglage « Firefox au style de l’île » dans nc-reglages → Apparence,
ou `nc-firefox installer`) : les préférences du dépôt vont dans ton
profil (`user.js` : barres compactes, sélecteur de fichiers du bureau, vidéo décodée par la carte graphique, session
rouverte, sans contenu sponsorisé ni télémétrie) avec le style de l’île (`chrome/userChrome.css` : onglets et barre
d’adresse en pastilles, aux couleurs du fond d’écran quand le thème de Firefox est du même côté, sombre ou clair).
Relance Firefox ensuite ; `nc-firefox desinstaller` remet tout comme avant. Pour que le thème de Firefox suive le fond
d’écran **en direct**, le réglage « Firefox aux couleurs du fond d’écran » (nc-reglages → Apparence) pose une petite
extension non signée (Developer Edition, Nightly ou ESR) reliée à `nc-firefox` par la messagerie native ; un thème
choisi dans Firefox reste prioritaire. Les fichiers : `home/.local/share/nc/firefox/`.

Ces fichiers sont à toi : `install.sh` ne les remplace jamais.

| Fichier | Pour |
|---|---|
| `~/.config/nc/reglages.conf`, `~/.config/nc/raccourcis.conf` | tes réglages (`nc-reglages`, ou la fenêtre avec recherche : **Super + Alt + ,**, `nc-reglages fenetre`, appli « Réglages du bureau ») et tes raccourcis (`nc-raccourci`, ou la section Raccourcis de cette fenêtre : Entrée puis la nouvelle combinaison) |
| `~/.config/hypr/perso.lua` | règles de fenêtres, écrans, tout réglage Hyprland en plus (format Lua de Hyprland) |
| `~/.zshrc.perso` | tes alias et variables du terminal |
| `~/.config/kitty/perso.conf` | tes réglages de kitty |
| `~/.config/nc/assistant.conf` | URL et clé de ton assistant distant (0600, jamais exporté) |

## Mettre à jour ton bureau

```bash
nc-aide       # à quoi sert chaque commande (nc-aide NOM : le détail)
nc-sauvegarde # tes réglages dans un fichier (restaurer FICHIER pour les remettre ; --fonds : avec tes fonds)
nc-claude     # les IA dans l'île (étapes, fin, demandes, lui écrire) : Claude Code, opencode, Codex, Gemini CLI, Cursor, Copilot, Qwen, Kiro, Amp, Antigravity ; installer IA / retirer IA / diag
nc-diag       # vérifie toute l'installation ; nc-diag rapport : le bilan copié, à envoyer pour avoir de l'aide
nc-maj        # récupère la dernière version depuis GitHub, puis ne refait que ce qui a changé
nc-reglages   # tes réglages, aux flèches : île et Spotlight, apparence, animations, lumière nocturne, barre et dock, fenêtres,
              # fonds d'écran, énergie, son et luminosité, clavier et souris, veille et couvercle, terminal,
              # captures, raccourcis — gardés à chaque mise à jour
nc-anim liste # les animations du bouton d'arrêt (nc-anim NOM pour en voir une) ;
              # nc-anim nouvelle NOM crée la tienne dans ~/.config/nc/animations
```

Tes fichiers personnels (`perso.lua`, `~/.zshrc.perso`, `perso.conf`), tes fonds d'écran, ta photo de profil et tes couleurs
ne sont jamais remplacés.

Si `nc-maj` s'arrête sur « Not possible to fast-forward » et que tu n'as rien modifié toi-même dans le dépôt :

```bash
git -C ~/noctalia-config branch sauvegarde && git -C ~/noctalia-config fetch && git -C ~/noctalia-config reset --hard origin/main && ~/noctalia-config/install.sh
```

**Sessions** (`nc-session`, **Super + Maj + W** ou `session ` dans le Spotlight) : enregistre la disposition du moment
— applis ouvertes, leur bureau, leur place si elles sont libres, le dossier et le programme des terminaux (Neovim…) —
sous un nom (« Dev », « Cours »…), et rouvre-la d'un coup : les applis déjà ouvertes vont sur leur bureau, les autres sont
lancées puis placées. Une session peut se rouvrir à chaque ouverture de session (nc-reglages → Fenêtres).

**Mises à jour du système** (île, page Notifications → « Mettre à jour », ou `nc-paquets mettre-a-jour`) : sur un disque
en **Btrfs**, un instantané du système est pris juste avant (snapper ou Timeshift s'ils sont là, sinon
`/.snapshots/nc-avant-maj-…`, les 3 derniers gardés) pour revenir en arrière si une mise à jour casse quelque chose ;
avec **grub-btrfs**, on démarre dessus depuis le menu GRUB. Réglage « Instantané avant chaque mise à jour ». Avec l'IA, chaque mise à jour (config ou système) laisse un rapport en clair dans les réglages → Mises à jour,
annoncé par une notification.

## Mettre à jour le dépôt depuis ta machine

```bash
cd ~/noctalia-config
./export.sh        # recopie la config actuelle ; ce qui est propre au PC devient un repère (@HOME@, @MONITOR@…)
git add -A && git commit -m "Mise à jour" && git push
```

L'export refuse de remplacer `home/` s'il contient des modifications locales, y compris de nouveaux fichiers.
Utilise `./export.sh --preview` pour comparer la configuration installée au dépôt sans remplacer ton travail.
Les fichiers sont préparés et contrôlés avant le remplacement.

Les corrections de la vue des fenêtres, de Coucou et des contrôles Quickshell sont détaillées dans la
[note de validation](docs/corrections-2026-10-19.md), avec les essais graphiques restant à effectuer sur Debian,
Fedora/Nobara et les configurations à plusieurs écrans.

## Contenu

- `home/` : la config (Hyprland en Lua dans `.config/hypr/`, Noctalia v5, plugins, kitty, zsh, Neovim, Firefox, Qt/KDE, scripts `nc-*`) ;
- `system/` : profils d'énergie TLP, thème GRUB « nc », écran de connexion SDDM (étapes optionnelles) ;
- `install.sh`, `export.sh`, `RACCOURCIS.md`.

Les plugins `nc/launcher`, `nc/carousel` et `nc/keys` (recherche, fonds d'écran, raccourcis) sont écrits pour ce dépôt.
L'écran de connexion s'appuie sur le thème libre [sddm-astronaut-theme](https://github.com/Keyitdev/sddm-astronaut-theme).
Les fonds d'écran appartiennent à leurs auteurs.
