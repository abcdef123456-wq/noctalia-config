# Assistant personnel distant

Le PC utilise un client Python 3 (bibliothèque standard) ; le serveur et ses modèles restent distants.
L'intégration utilise les dépendances déjà prévues par l'installateur : Python, kitty et `notify-send`.
Aucun paquet pip, modèle, service ou timer supplémentaire n'est installé sur le PC.

Le même client est fourni pour toutes les familles prises en charge : Arch et dérivées, Fedora/Nobara,
Debian/Ubuntu et openSUSE. Il ne dépend ni de la capture de fenêtres ni d'un module Quickshell.
Cela décrit la portabilité du code et de l'installation ; chaque distribution n'a pas été testée sur une machine réelle.

## Connexion

Le serveur doit déjà être déployé séparément. Ce dépôt ne lance pas le `deploy.sh` du serveur et n'installe pas son backend.
Dans un terminal :

```bash
nc-assistant configurer
nc-assistant etat
nc-assistant demander "Bonjour"
```

La même saisie est accessible dans **`nc-settings` → Agents IA (coucou) → Configurer l'assistant distant**.
Entrée ouvre la configuration dans le même terminal, puis revient aux réglages. La clé reste masquée.
Accès direct : `nc-settings assistant` (ou `nc-reglages assistant`).

La configuration demande l'URL HTTP(S) du gateway (éventuellement avec un préfixe de chemin), sa clé `X-Secret-Key`
et le `USER_ID`. La clé se saisit sans affichage. Le fichier `~/.config/nc/assistant.conf` est enregistré par renommage
atomique, avec les permissions `0600`. `nc-assistant configurer` peut ensuite modifier cette connexion.
La configuration n'est pas un script shell : ne pas la charger avec `source`.

L'installation complète propose cette connexion de manière facultative, seulement avec un terminal interactif.
`./install.sh --files-only` installe le client sans poser ces questions : lancer ensuite `nc-assistant configurer`.
Une configuration existante est préservée par l'installation et `nc-maj`, et exclue de `export.sh`.
Ni `nc-assistant etat`, ni `etat --local` n'affichent la clé. `etat --local` contrôle la configuration sans connexion réseau.
Les redirections HTTP sont refusées pour éviter de transmettre la clé à une autre adresse : configurer l'URL finale.
Pour accéder au serveur à travers Internet, utiliser son accès HTTPS ; le certificat est vérifié par Python.

## Depuis un autre réseau (Wi-Fi différent, Internet)

Une URL du type `http://192.168.1.28:8000` ou `http://mon-pi.local:8000` est
une adresse **privée** : elle exige un accès au réseau du serveur, directement ou par VPN.
Depuis un autre réseau sans ce routage, la bonne clé ne suffit pas. Il faut exposer le gateway (port `8000`) avec un tunnel côté serveur :

- **Cloudflare Tunnel** : URL HTTPS publique, aucun port à ouvrir ;
- **Tailscale** : URL HTTPS privée, visible seulement par tes appareils ;
- **Render** : gateway hébergé, relié au runner par un tunnel.

Le dépôt du serveur fournit `scripts/expose-gateway.sh` et le guide
`docs/ACCES_DISTANT.md`. Une fois l'URL HTTPS obtenue sur le serveur :

```bash
nc-assistant configurer
# URL     : https://assistant.tondomaine.fr
# Clé     : la SECRET_KEY du serveur
# USER_ID : ton identifiant
nc-assistant verifier
nc-assistant demander "Bonjour"
```

`nc-assistant verifier` teste `/api/status` et distingue : URL privée, clé
refusée (401/403), route introuvable (404), certificat TLS invalide, DNS
introuvable, connexion refusée, délai dépassé, runner hors ligne. Il affiche
aussi la latence et l'URL publique annoncée par le serveur. Aucune clé n'est
affichée.

`nc-settings` → **Agents IA (coucou)** contient désormais deux entrées :
« Configurer l'assistant distant » et « Tester l'assistant distant ».
En ligne de commande : `nc-settings assistant verifier`.

## Utilisation

| Accès | Comportement |
|---|---|
| Île : `Super + C`, puis bulle de conversation en haut à droite | Page Assistant avec saisie et réponses dans l’île |
| Recherche Spotlight : `Assistant` | Ouvre cette même page ; également accessible parmi les points de navigation de l’île |
| `Super + Alt + A`, ou application JARVIS | Cockpit natif plein écran ; voir [JARVIS](jarvis.md) |
| Application « Assistant distant » | Chat dans une fenêtre kitty flottante, centrée, avec les couleurs du terminal |
| `nc-assistant ouvrir` | Même fenêtre, depuis une commande |
| `nc-assistant chat` | Chat dans le terminal courant ; `exit`, `Ctrl+C` ou fin d'entrée pour quitter |
| `nc-assistant demander "question"` | Réponse en texte ; code de sortie non nul en cas d'échec |
| `nc-assistant verifier` | Teste URL, clé, TLS et runner ; `--json` pour un script |
| `nc-assistant briefing` | Texte du briefing et notification si disponible |
| `nc-reglages set SPOTLIGHT_IA assistant` | Sélection explicite pour les questions `?` dans Spotlight Quickshell |
| `nc-reglages set ASSISTANT_ILE non` | Désactive l'affichage de son activité dans Coucou |

Sans configuration, l'ouverture du chat dans un terminal interactif propose de la créer.
La roue dentée de la page Assistant ouvre la même configuration sécurisée dans un terminal.
La page conserve son brouillon, sa requête et ses échanges quand on ferme l’île ou change d’écran/page.
Cet affichage reste en mémoire (24 messages, 48 000 caractères maximum), jusqu’au redémarrage de l’île.
La corbeille efface uniquement l’affichage local : elle ne réinitialise pas le contexte distant.
Les réponses sont sélectionnables et affichées en texte brut, avec une limite de 16 000 caractères par réponse.
Une seule question part à la fois ; fermer la page ne l’annule pas. Aucune reconnexion ou répétition automatique.
Le client interne `requete-ile` reçoit la question par une ligne JSON sur l’entrée standard, sans fichier temporaire
ni question dans les arguments du processus. Le terminal reste disponible pour les réponses plus longues.
Le mode automatique du Spotlight garde la priorité des IA existantes ; l'assistant arrive en dernier,
seulement si son fichier de connexion existe. La sélection explicite affiche une erreur utile si la connexion manque.
Le protocole `--flux` fournit des lignes JSON compatibles avec Spotlight ; la réponse arrive en une seule fois,
car le contrat HTTP fourni ne décrit pas de flux de tokens.

Sans Quickshell, le lanceur de repli Noctalia accepte `? question` pour ouvrir le chat kitty avec cette question.
La réponse apparaît dans kitty. Les commandes, le raccourci et le briefing restent disponibles.

Le logo de l'assistant dans l'île reprend l'emblème blanc animé de `pfp.mp4` fourni par l'utilisateur.
Les images sont livrées dans un atlas PNG transparent (161 images de 64 × 64, à 100/3 images par seconde),
affiché par QtQuick : aucun codec vidéo, QtMultimedia ou ffmpeg n'est nécessaire sur la machine cible.
Un fond noir rond conserve le contraste du logo blanc, y compris dans les thèmes clairs.
Il s'anime pendant l'activité, reste fixe au repos et lorsque les effets sont désactivés, et s'arrête quand il est masqué.
Le même logo apparaît dans la pilule, la page des agents et les réponses du Spotlight ; le chat kitty garde son affichage texte.

## Activité, concurrence et limites du contrat serveur

Les requêtes passent par `nc-claude assistant debut|fini|fin`, avec le même verrou et la même écriture atomique
que les autres agents. Le client ne réécrit jamais lui-même `etat.json`.
Chaque chat ou commande ponctuelle reçoit un identifiant local distinct. Une commande ponctuelle ne permet pas
d'envoyer du texte depuis l'île vers un shell redevenu inactif. Un chat ouvert dans kitty peut être retrouvé depuis l'île.
À la fermeture du chat ou lors d'une erreur/interruption réseau, son activité est nettoyée.

Le contrat du document `PLAN_INTEGRATION_NOCTALIA.md` prévoit :

- `POST /api/ask` : `prompt`, `platform: "desktop"`, `user_id`, `continue_session: true` ; réponse `output` ;
- `GET /api/status` : état du serveur et éventuellement `runner_alive` ;
- `POST /api/briefing` : `force_refresh: false` ; réponse `output` ;
- authentification via l'en-tête `X-Secret-Key`.

Ce contrat ne décrit pas d'identifiant indépendant de conversation distante. Les chats utilisant le même `USER_ID`
partagent donc le contexte prévu par le serveur, même si leur affichage local est distinct.
Le client refuse les requêtes simultanées pour une même URL et un même `USER_ID` sur ce PC, sans les envoyer au serveur.
Ce verrou ne coordonne pas les autres PC. Il n'y a pas de nouvelle tentative automatique d'une question interrompue,
car le serveur peut continuer à la traiter après la coupure réseau.

Le délai réseau est réglable via `TIMEOUT` dans la configuration (180 secondes par défaut, entre 1 et 600).
Une réponse JSON invalide, trop volumineuse, un échec métier ou HTTP est signalé comme une erreur.
L'API fournie ne décrit ni demandes d'autorisation interactives, ni événements d'outils, ni annulation distante :
l'île affiche uniquement le début et la fin des requêtes. Aucun de ces événements supplémentaires n'est simulé.

## Validation

Les tests utilisent un serveur HTTP local simulant ce contrat et des dossiers temporaires, sans contacter de serveur
personnel ni modifier la session graphique. Ils vérifient les échanges, les erreurs, le verrou, les états de Coucou,
la sélection Spotlight et la préservation de la configuration.

```bash
python3 -B -m unittest discover -s tests -v
```

Restent à valider : les routes et réponses du véritable backend (dépôt indiqué non consultable pendant l'intégration),
l'authentification réelle, l'ouverture visuelle du chat et le rendu de l'île sur les machines des autres distributions.
Un serveur répondant à `/api/status` ne suffit pas à valider `/api/ask` et `/api/briefing`.
