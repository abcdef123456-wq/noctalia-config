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
batterie**, elle se met en pause partout (rien n'est appelé) et revient sur secteur ou hors Économie (réglage « En pause
en Économie sur batterie »).

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
  `Espace i t` transformer selon une consigne, `Espace i c` corriger (annulable avec `u`). `Espace a` reste Claude Code.
- **Diagnostic** : `nc-diag ia` explique ce que `nc-diag` a trouvé et dit quoi faire (rien n'est envoyé si tout va bien).
- **Dictée partout (Super + D)** : maintiens Super + D et parle, relâche : le texte est écrit dans la fenêtre active
  (Discord, navigateur, Neovim, terminal…). Un appui bref lance une dictée longue, le suivant l'écrit. Transcription par
  JARVIS, une clé Groq, OpenAI ou Gemini, ou **whisper.cpp** sur ce PC (`whisper-cli` et un modèle dans
  `~/.local/share/nc/whisper/`, sans internet). `wtype` écrit directement ; sans lui, le texte est collé et ton
  presse-papiers remis. Réglage « Dictée partout ».
- **Dictée** (micro du chat) : par JARVIS ; sans JARVIS, ou s'il ne répond pas, par Groq, OpenAI ou Gemini (Whisper).
- **Agents** (Claude Code, Codex, OpenCode… dans l'île) : section « Agents IA » des réglages ; coupés avec le reste.
- `nc-diag` dit quelle IA répond et vérifie que le fichier des clés est privé.

## L'IA qui gère le bureau (avec ta confirmation)

Coupée par défaut : **nc-reglages → Intelligence artificielle → L'IA peut agir → Oui, après ma confirmation** (ou, la
première fois, Entrée sur « Autoriser l'IA à proposer des actions » en tapant `@` dans le Spotlight). Ensuite,
`@ ` dans le Spotlight (ou `nc-ia agir "…"`) : « @ redémarre l'île », « @ coupe le Bluetooth et passe en économie »,
« @ un service est en échec, répare-le ». L'IA voit l'état du bureau (services de ta session, Wi-Fi, Bluetooth, profil
d'énergie, luminosité, volume) et propose un plan ; chaque action apparaît comme une ligne, faite seulement quand tu
appuies sur Entrée dessus (ou sur « Tout faire »). Ce qu'elle peut proposer se choisit domaine par domaine :

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
