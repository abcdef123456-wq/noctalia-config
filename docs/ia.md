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

`nc-ia configurer` (ou la ligne « Clés d'API des IA » de la fenêtre des réglages) : choisis le service, colle la clé
(saisie masquée), elle est essayée tout de suite. Les clés sont dans `~/.config/nc/ia.conf` (lisible par toi seul,
0600) ; elles ne passent jamais en argument d'une commande ni dans un journal, et ne partent que vers l'adresse du
service (aucune redirection suivie). Les variables habituelles (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`…) marchent aussi.

Dans le même fichier, si besoin : `MODELE_<SERVICE>=nom` (`nc-ia modele openai gpt-5-mini`), `URL_<SERVICE>=https://…`
pour une passerelle ou un serveur compatible (LiteLLM, LM Studio…), en HTTPS (HTTP seulement vers ce PC).

## Partout dans le bureau

- **Spotlight (Super + R)** : `? ta question` — d'abord les réponses de la config (instantanées, sans IA), puis l'IA ;
  la commande qu'elle propose se lance avec Entrée. L'en-tête dit quelle IA a répondu. « IA du Spotlight » peut en
  imposer une autre, ou aucune pour le Spotlight seulement.
- **Texte sélectionné (Super + Alt + I)**, ou `! ` dans le Spotlight : résumer, traduire, corriger, reformuler,
  expliquer, rédiger une réponse, ou une consigne libre (`! en liste à puces`). Le texte sélectionné, sinon le texte
  copié ; Entrée copie le résultat. Sans l'île, un menu (fuzzel, wofi, rofi ou bemenu) puis le résultat copié.
- **Une zone de l'écran (Super + Alt + Maj + I)** : un message d'erreur, un graphique… l'IA l'explique dans une
  notification (« Lire en entier » ouvre la réponse complète) ; la réponse est aussi copiée.
- **Terminal** : **Alt + I** transforme la description tapée (« trouver les fichiers de plus de 1 Go ») en commande,
  laissée dans l'invite pour être relue — jamais lancée toute seule. `ia question` répond ; `journalctl -b -p err | ia
  résume` travaille sur la sortie d'une commande.
- **Dictée** (micro du chat) : par JARVIS ; sans JARVIS, ou s'il ne répond pas, par Groq, OpenAI ou Gemini (Whisper).
- **Agents** (Claude Code, Codex, OpenCode… dans l'île) : section « Agents IA » des réglages ; coupés avec le reste.
- `nc-diag` dit quelle IA répond et vérifie que le fichier des clés est privé.

Chaque usage se coupe à part : « IA sur le texte sélectionné », « IA dans le terminal », « Expliquer une zone de
l'écran ». Rien ne tourne en arrière-plan : une IA n'est appelée que quand tu le demandes.
