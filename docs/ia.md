# Intelligence artificielle du bureau

Une seule IA pour tout le bureau, choisie parmi ce que tu as : une clé d'API, un programme installé, ton serveur
JARVIS ou un modèle sur ton PC. Tout passe par `nc-ia` (`nc-ai` en anglais), sur toutes les distributions, sans
dépendance à installer (Python seul).

## Choisir l'IA, ou n'en avoir aucune

**nc-reglages → Intelligence artificielle → IA du bureau** :

- **Automatique** (par défaut) : la meilleure disponible répond ; si elle échoue (pas connectée, crédit épuisé, réseau),
  la suivante prend le relais dans la même réponse. Une IA qui vient d'échouer passe en dernier pendant 10 minutes.
- **Celle que je choisis** : une seule, celle de « IA choisie ». Une IA qui ne lit pas les images laisse les captures
  à la meilleure qui sait le faire.
- **Aucune (tout couper)** : plus d'IA nulle part. Le Spotlight ne propose plus que les réponses de la config (sans
  IA), les pages JARVIS et Agents disparaissent de l'île, JARVIS, la dictée, les alertes Telegram et les raccourcis d'IA
  répondent « IA désactivée », et les hooks des agents (Claude Code, Codex…) ne montrent plus rien dans l'île. Rien
  n'est désinstallé : remettre « Automatique » rallume tout.

**Sans connexion internet**, l'IA disparaît partout (Spotlight, presse-papiers, notifications, raccourcis, terminal)
et revient d'elle-même avec la connexion ; seule une IA de ce PC (Ollama) reste proposée. **En profil Économie sur
batterie**, l'IA qui tourne toute seule (alertes Telegram, automatismes) se met en pause et revient sur secteur ou hors
Économie ; ce que tu lances toi-même marche toujours (réglage « Arrière-plan en pause en Économie sur batterie »).

**Ordre du mode automatique** : la plus rapide (les API, puis JARVIS, puis les programmes), mes abonnements d'abord
(Claude Code, Codex… déjà payés), sur ce PC d'abord (Ollama : rien ne sort du PC tant qu'il répond), ou JARVIS d'abord.

## Les IA reconnues

| IA | Ce qu'il faut | Lit les images |
|---|---|---|
| Claude (API Anthropic) | une clé (`nc-ia configurer`) ; modèle `claude-opus-5-5` à effort bas | oui |
| ChatGPT (API OpenAI) | une clé ; le plus récent des modèles « mini » de ton compte | oui |
| Gemini (API Google) | une clé ; le plus récent des modèles « flash » | oui |
| Mistral, Groq, DeepSeek, OpenRouter | une clé | OpenRouter |
| JARVIS | la connexion à ton serveur (`nc-assistant configurer`) | non |
| Claude Code, Codex, Gemini CLI, OpenCode, Qwen Code | le programme installé et connecté (ton abonnement) | Claude Code, Codex, Gemini CLI |
| Ollama | Ollama qui tourne sur ce PC (ou ailleurs : `OLLAMA_HOST`) et un modèle (`ollama pull llama3.2`) | selon le modèle |

### Les programmes en ligne de commande : les mêmes droits pour tous

Claude Code, Codex, Gemini CLI, OpenCode et Qwen Code (et les suivants) répondent à une simple question dans le **même bac
à sable** que la session de confiance de JARVIS (`nc-bac`, une unité `systemd-run --user`). Pour tous :

- aucun outil d'écriture ni de commande (chaque programme est bridé), dans un dossier de travail vide ;
- ton dossier personnel est en **lecture seule**, et rien de secret n'est lisible : `~/.ssh`, `~/.gnupg`, les navigateurs,
  les messageries, les clés d'API de nc-ia (`~/.config/nc`), les assistants de code et leurs jetons, `$XDG_RUNTIME_DIR`
  (bus, Hyprland, agents ssh et gpg…) ;
- **chaque programme travaille dans un faux dossier personnel**, créé pour la demande et jeté après (`HOME` y pointe) :
  on y copie seulement ses identifiants et sa config (`~/.claude/.credentials.json`, `~/.claude.json`, `~/.codex/auth.json`,
  `~/.gemini/oauth_creds.json`…). Ses **vrais** dossiers (`~/.claude`, `~/.codex`, `~/.gemini`, `~/.qwen`,
  `~/.config/opencode`, `~/.local/share/opencode`) sont **illisibles et non inscriptibles** : un hook, une commande, un
  agent, une règle, un `AGENTS.md`, un script de shell, un fichier de mémoire ou un serveur MCP créé par le programme
  disparaît avec la demande et ne sera jamais exécuté hors du bac. Seul un **jeton rafraîchi** revient dans le vrai
  fichier, après la demande, s'il est resté un JSON valide (256 Ko au plus) et si ton fichier n'a pas changé entre-temps ;
- l'environnement est une liste blanche : le `PATH`, la langue, le proxy, et **sa propre clé** seulement (par exemple
  `ANTHROPIC_API_KEY` pour Claude Code) ; ni `GITHUB_TOKEN`, ni les clés des autres fournisseurs ;
- l'invite passe par l'entrée standard (Claude Code, Codex) et non dans la ligne de commande ; le journal du gestionnaire
  systemd n'écrit que « nc-ia » ; `$VAR` et `${VAR}` dans une question ne sont jamais remplacés ;
- aucun autre processus visible, pas de `ptrace` ni de trousseau du noyau, pas de `sudo`, `/tmp` privé ;
- **le réseau reste ouvert** (HTTP/HTTPS vers leur API, mais rien ne l'empêche de joindre autre chose), **127.0.0.1 reste
  joignable** (les services locaux de ta machine) et **`/dev/shm` est partagé** avec le reste du système : ce qu'ils peuvent
  lire peut donc partir vers leur fournisseur. Ce qu'ils peuvent lire, c'est ce qui n'est pas dans la liste des secrets :
  `NOEUD_BAC_INTERDITS` (nc-reglages) y ajoute tes dossiers. Pendant qu'un autre programme d'IA tourne en même temps, sa
  copie de jeton (dans `~/.local/state/nc-ia/etat`) est lisible par le premier le temps de la demande.

**Sans bac** (pas de `systemd-run`, systemd avant 257, espaces de noms refusés), les programmes en ligne de commande ne sont
**pas lancés** : une IA par API prend le relais. Le réglage `IA_BAC_REPLI` (nc-reglages, « non » par défaut) les laisse
tourner quand même, avec leurs seules limites propres (lecture seule, outils retirés, pas de config utilisateur) : sans bac,
Codex peut lire tes fichiers et ces programmes peuvent lire tes clés. Un `NOEUD_BAC_INTERDITS` invalide refuse toujours le
lancement. `nc-ia etat` affiche « bac des IA : actif » ou « indisponible ici » (et si le repli est autorisé).

`nc-ia etat` dit laquelle répond pour chaque usage et lesquelles sont disponibles ; `nc-ia tester` pose une question
d'un mot à chacune (réglages → « Tester les IA disponibles »).

## Clés d'API

`nc-ia configurer` (ou la ligne « Clés d'API des IA » de la fenêtre des réglages) ouvre la fenêtre **Clés des IA** :
pour chaque service, colle la clé (masquée), « Enregistrer » l'essaie tout de suite, « Créer une clé » ouvre la page du
service ; en bas, ce qui est déjà sur le PC (Claude Code, Codex, Ollama, JARVIS…) et « Essayer toutes les IA ». Sans
l'île (ou `nc-ia configurer --terminal`), les mêmes questions au clavier. Les clés sont dans `~/.config/nc/ia.conf` (lisible par toi seul,
0600) ; elles ne passent jamais en argument d'une commande ni dans un journal, et ne partent que vers l'adresse du
service (aucune redirection suivie). Les variables habituelles (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`…) marchent aussi.

Dans le même fichier, si besoin : `MODELE_<SERVICE>=nom` (`nc-ia modele openai gpt-5-mini`), `URL_<SERVICE>=https://…`
pour une passerelle ou un serveur compatible (LiteLLM, LM Studio…), en HTTPS (HTTP seulement vers ce PC).

## Partout dans le bureau

- **Spotlight (Super + R)** : `? ta question` — d'abord les réponses de la config (instantanées, sans IA), puis l'IA ;
  la commande qu'elle propose se lance avec Entrée. L'en-tête dit quelle IA a répondu. « IA du Spotlight » peut en
  imposer une autre, ou aucune pour le Spotlight seulement.
- **Texte sélectionné (Super + I)**, ou `! ` dans le Spotlight : résumer, traduire, corriger, reformuler,
  expliquer, rédiger une réponse, ou une consigne libre (`! en liste à puces`). Le texte sélectionné, sinon le texte
  copié ; Entrée copie le résultat. Sans l'île, un menu (fuzzel, wofi, rofi ou bemenu), et la réponse comme
  ci-dessous.
- **Une zone de l'écran (Super + Maj + I)** : le curseur devient une croix, entoure un message d'erreur, un graphique…
  l'IA l'explique.
- **Où arrivent ces réponses** (zone de l'écran, texte par le menu, clic droit sur un fichier, bouton des captures) :
  dans la conversation — la fenêtre de chat, celle de JARVIS quand JARVIS répond, sinon au nom de l'IA qui a répondu.
  Une notification l'annonce, un clic ouvre la conversation sur cette réponse, et tu peux continuer à poser des
  questions : la suite va à la même IA, avec le contexte. Rien de plus dans l'île. Réglages « Où arrivent les
  réponses » (la conversation, ou une notification seule) et « Copier aussi les réponses ».
- **Terminal** : **Alt + I** transforme la description tapée (« trouver les fichiers de plus de 1 Go ») en commande,
  laissée dans l'invite pour être relue — jamais lancée toute seule. `ia question` répond ; `journalctl -b -p err | ia
  résume` travaille sur la sortie d'une commande.
- **Centre de contrôle** : la pastille **IA** coupe l'IA partout d'un clic, ou la rallume dans le mode d'avant
  (automatique ou choisie) ; dessous, celle qui répond.
- **Presse-papiers de l'île** : le bouton ✦ d'une entrée ouvre le Spotlight sur `! ` avec ce texte-là (résumer,
  traduire…), ou fait expliquer une image.
- **Notifications** : « Résumer » (à partir de deux) : ce qui demande une action d'abord, le reste par appli ; envoyé
  seulement quand tu cliques.
- **Captures** : la notification d'une capture a un bouton « Demander à l'IA ».
- **Fichiers** : clic droit → Scripts → IA (Nautilus), le sous-menu IA de Dolphin ou les actions de Nemo : résumer,
  expliquer, traduire, corriger un texte, du code, un PDF (avec pdftotext) ou une image ; `nc-ia fichier CHEMIN`.
- **Neovim** : `Espace i i` demander (avec les lignes choisies en contexte), en visuel `Espace i e` expliquer,
  `Espace i t` transformer selon une consigne, `Espace i c` corriger (annulable avec `u` ; un échec de l'IA ne touche
  à rien). Les demandes s'écrivent dans une fenêtre où tout se voit et où l'on colle (`p`, `Ctrl + R "`) : `Ctrl + S`
  envoie, `q` annule, `Ctrl + P` / `Ctrl + N` rappellent les 20 dernières. La réponse : `y` copie, `i` insère, `q` ferme.
  `Espace i f` fait la tâche décrite (la sélection, ou ce qu'on tape) avec le fichier en contexte : le code s'ouvre dans
  un aperçu, `a` l'ajoute dessous, `r` remplace la sélection, `y` le copie ; rien n'est remplacé d'office.
  `Espace i a` ouvre l'agent de l'IA choisie (Claude Code, Codex, Gemini CLI, OpenCode, Qwen Code…) dans un terminal
  en bas, à la racine du projet, la sélection pour demande ; `Espace i A` pour en choisir un autre parmi les IA
  disponibles. L'agent garde ses propres demandes de permission. `Espace a` reste Claude Code.
- **Mises à jour expliquées** : après une mise à jour de la config (`nc-maj`) ou du système, l'IA écrit un rapport
  facile à comprendre (ce qui se voit d'abord, s'il faut redémarrer) en tête de **Mises à jour** dans la fenêtre des
  réglages, avec **Détails** (la liste complète) ; une notification y mène. C'est automatique : sans connexion, sans
  IA, ou en Économie sur batterie, le rapport ne donne que les faits (les nouveautés, les paquets importants, s'il faut
  redémarrer), sans notification.
- **Services en panne** : quand un service du bureau s'arrête en échec (l'île, Noctalia, le son, les portails, l'agent
  polkit…), une notification propose **Redémarrer** (le compteur de démarrages remis à zéro, puis « reparti » ou
  l'erreur) et, si l'IA est permise, **Expliquer** : l'IA lit son état et la fin de son journal (clés et mots de passe
  masqués) et répond dans la conversation. Rien n'est envoyé sans ton clic ; une fois par demi-heure au plus pour un
  même service ; rien pendant la fermeture de la session ; jamais les services du système. `nc-ia panne SERVICE`,
  réglages « Signaler les services en panne » (ceux du bureau, tous ceux de ta session, aucun) et « Services à ne
  jamais signaler » (nc-reglages → Notifications).
- **Diagnostic** : `nc-diag ia` explique ce que `nc-diag` a trouvé et dit quoi faire (rien n'est envoyé si tout va bien).
- **Dictée partout (Super + D)** : maintiens Super + D et parle, relâche : le texte est écrit dans la fenêtre active
  (Discord, navigateur, Neovim, terminal…). Un appui bref lance une dictée longue, le suivant l'écrit. Transcription par
  JARVIS, une clé Groq, OpenAI ou Gemini, ou **whisper.cpp** sur ce PC (`whisper-cli` et un modèle dans
  `~/.local/share/nc/whisper/`, sans internet). `wtype` écrit directement ; sans lui, le texte est collé et ton
  presse-papiers remis (texte, image ou fichiers, avec un seul type : une copie web revient sans sa mise en forme, et
  des fichiers coupés dans Fichiers redeviennent copiés). S'il ne peut pas être lu, rien n'est collé : le texte est
  copié pour Ctrl + V, et la dernière dictée reste dans `$XDG_RUNTIME_DIR/nc-dictee-derniere.txt` jusqu'à la fin de
  la session. Réglage « Dictée partout ».
- **Dictée** (micro du chat) : par JARVIS ; sans JARVIS, ou s'il ne répond pas, par Groq, OpenAI ou Gemini (Whisper).
- **Agents** (Claude Code, Codex, OpenCode… dans l'île) : section « Agents IA » des réglages ; coupés avec le reste.
- `nc-diag` dit quelle IA répond et vérifie que le fichier des clés est privé.

## L'IA qui gère le bureau (avec ta confirmation)

Coupée par défaut : **nc-reglages → Intelligence artificielle → L'IA peut agir → Oui, après ma confirmation** (ou, la
première fois, Entrée sur « Autoriser l'IA à proposer des actions » en tapant `@` dans le Spotlight). Ensuite,
`@ ` dans le Spotlight (ou `nc-ia agir "…"`) : « @ redémarre l'île », « @ coupe le Bluetooth et passe en économie »,
« @ un service est en échec, répare-le ». L'IA voit l'état du bureau (services de ta session, Wi-Fi, Bluetooth, profil
d'énergie, luminosité, volume) et propose un plan ; chaque action apparaît comme une ligne, avec l'état d'aujourd'hui
lu sans IA (« Luminosité : 70 % (maintenant : 40 %) », ou « (déjà le cas) »), faite seulement quand tu appuies sur
Entrée dessus (ou sur « Tout faire »). Ce qu'elle peut proposer se choisit domaine par domaine :

- **fenêtres et bureaux** : **Super + Maj + O** range toutes les fenêtres (regroupées par activité sur des
  bureaux nommés, puis disposées), **Super + Ctrl + O** celles du bureau affiché (l'IA ne voit alors que lui, et rien
  ne peut en sortir) : là, l'IA cherche la disposition la plus utile sans suivre le découpage automatique de Hyprland —
  chaque fenêtre dans sa zone de l'écran (par exemple l'éditeur sur 60 % à gauche, le navigateur sur 40 % à droite).
  Les fenêtres restent **en tuiles** : le bureau prend la disposition « zones » (hypr/nc/zones.lua), un arbre de
  découpes aux proportions choisies par l'IA. Super + flèches, Super + Maj + flèches (échanger), Super + Ctrl +
  flèches (agrandir, rétrécir), changer le sens de la division, ouvrir ou fermer une fenêtre marchent comme ailleurs ;
  le redimensionnement à la souris ne fait rien sur ce bureau. Après `hyprctl reload`, le bureau reprend sa
  disposition habituelle. Hyprland sans dispositions en Lua : les fenêtres deviennent libres, posées à leur place. Le raccourci est ta demande : c'est fait **tout de suite**, sans passer par le Spotlight, même
  si « L'IA peut agir » est coupé — seulement des fenêtres et des bureaux, chaque action revérifiée — puis une
  notification de l'île dit ce qui a bougé, avec **Annuler** (bureau, état libre ou plein écran, place et nom des
  bureaux remis comme avant). Toutes les fenêtres bougent en même temps, d'un seul glissement. **Rappuyer** sur le
  même raccourci sans avoir rien changé depuis remet la disposition d'avant (sans IA) ; l'appui suivant range à
  nouveau. Réglage « Ranger les fenêtres » : tout de suite (défaut), me montrer le plan d'abord,
  ou non. Dans le Spotlight (« @ »), l'IA peut aussi déplacer, échanger, rendre libre ou plein écran, nommer un
  bureau. L'IA voit l'appli, le titre (50 caractères) et la place de chaque fenêtre ;
- **services de la session** : redémarrer, démarrer, arrêter (signalé ⚠), lire le journal pour comprendre un échec —
  jamais les services du système ;
- **Wi-Fi et Bluetooth** : allumer, couper ;
- **énergie** : profil d'énergie, luminosité ;
- **son** : volume, son coupé ;
- **réglages du bureau** : ceux de nc-reglages, jamais ceux de l'IA ;
- **mises à jour** : les chercher ; les installer ouvre un terminal qui demande ton mot de passe.

L'IA ne lance jamais de commande elle-même : son plan ne peut contenir que ces actions, chaque action est revérifiée
au moment de la faire (service qui existe dans ta session, valeurs bornées, domaine toujours permis), un plan expire
après 10 minutes, et rien ne se fait sans toi.

Chaque usage se coupe à part : « IA sur le texte sélectionné », « IA dans le terminal », « Expliquer une zone de
l'écran ». Rien ne tourne en arrière-plan : une IA n'est appelée que quand tu le demandes.
