"""Suivre et répondre aux agents de code depuis Telegram (/agents, /repondre, /code), seulement en déploiement local.

Le gateway tourne sur le PC (DEPLOY_MODE=local) : `nc-claude etat --json` donne les sessions d'agents de code suivies (Claude
Code, Codex, OpenCode, Gemini CLI, Antigravity…) et `nc-claude ecrire SESSION TEXTE` tape dans le terminal (kitty) de CE PC. En
mode serveur la fonction est absente et le dit. Réglages (nc-reglages → Agents IA), tous à non par défaut :
TELEGRAM_AGENTS (la fonction), TELEGRAM_AGENTS_TEXTE (le dernier message de l'agent dans /agents). IA_MODE=non coupe tout.

  /agents (ou /claude)   les sessions : numéro court (10 minutes), NOM du dossier (jamais le chemin), agent, état. Aucun contenu
                         de conversation, sauf TELEGRAM_AGENTS_TEXTE=oui : le dernier message, filtré (secrets) et coupé à 600 signes.
  /repondre N texte      met la réponse en attente (une par discussion et utilisateur, 120 s) ; le bot demande /code 123456.
  /code XXXXXX           le code de l'appli d'authentification, vérifié par `nc-noeud totp controler` (le MÊME mécanisme que la
                         confirmation à distance de JARVIS : usage unique, essais comptés et bloqués) ; alors seulement :
                         `nc-claude ecrire SESSION TEXTE` en arguments exacts. Journal : date, agent, dossier, longueur, ok.

Réservé à l'utilisateur autorisé du bot et à la conversation privée ; un message modifié ne fait rien. Jamais de shell, jamais
d'argument venu de Telegram à part le texte (un seul argument, vérifié) ; la session est l'identifiant réel relu chez nc-claude.
"""
import asyncio
import datetime
import json
import logging
import os
from pathlib import Path
import re
import time
import unicodedata

logger = logging.getLogger("nc_agents")
DELAI_ETAT = 15
DELAI_ECRIRE = 20
DELAI_CODE = 10
VALIDITE = 600              # secondes pendant lesquelles un numéro de la liste reste valable
CONFIRMATION = 120          # secondes pour taper /code après /repondre
TEXTE_MAX = 2000            # signes au plus dans une réponse
EXTRAIT_MAX = 600           # signes au plus du dernier message de l'agent
DOSSIER_MAX = 40
SESSIONS_MAX = 40
SORTIE_MAX = 300000         # octets lus sur nc-claude avant de valider (le résultat rendu est reconstruit plus bas)
JOURNAL_MAX = 64 * 1024
JOURNAL_LIGNES = 200

# Les agents suivis par nc-claude (IAS de nc-claude) ; un autre nom, jamais affiché tel quel
NOMS = {"claude": "Claude Code", "antigravity": "Antigravity", "opencode": "OpenCode", "codex": "Codex", "gemini": "Gemini CLI",
        "cursor": "Cursor", "copilot": "Copilot", "qwen": "Qwen Code", "kiro": "Kiro", "amp": "Amp", "assistant": "JARVIS"}
# États internes de nc-claude → ce qui s'affiche
ETATS = {"attente": "t'attend", "demande": "t'attend", "terminal": "t'attend", "travail": "travaille", "fini": "fini", "pret": "prêt"}
IDENTIFIANT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:@-]{0,127}")
NUMERO = re.compile(r"[0-9]{1,3}")
CODE = re.compile(r"[0-9]{6}")
IMPOSSIBLE = "réponse impossible à distance (terminal non pris en charge)"
# Réponses qui ressemblent à une autorisation d'un agent (seules) : l'invite avertit
AUTORISATION = frozenset(("1", "2", "3", "y", "yes", "oui", "o", "n", "no", "non", "a", "always", "toujours"))
# Autres invisibles qui ne sont pas des caractères « Cf » : remplisseurs Hangul, point d'union de graphèmes, braille vide…
INVISIBLES = frozenset((0x034F, 0x115F, 0x1160, 0x17B4, 0x17B5, 0x2800, 0x3164, 0xFFA0))

_listes = {}                # (chat_id, user_id) → {"t": date de la liste, "ids": {numéro: identifiant de session}, "ecrire": {numéro: bool}}
_attente = {}               # (chat_id, user_id) → la réponse en attente de son code
executer = None             # remplacé par les tests ; sinon nc_noctalia.executer (groupe de processus, délai, sortie bornée)


def local():
    return os.environ.get("DEPLOY_MODE", "local").strip().lower() != "server"


def reglage(cle, defaut="non"):
    """Un réglage de nc-reglages (relu à chaque appel : changé dans l'île, il vaut tout de suite)."""
    valeur = defaut
    try:
        for ligne in (Path.home() / ".config/nc/reglages.conf").read_text(encoding="utf-8", errors="replace").splitlines():
            if ligne.startswith(cle + "="):
                valeur = ligne.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return valeur


def indisponible():
    """Pourquoi la fonction ne répond pas (texte pour Telegram), ou None si elle est active."""
    if not local():
        return "Cette fonction pilote les terminaux de CE PC : elle est absente en mode serveur (DEPLOY_MODE=server)."
    if reglage("IA_MODE", "auto") == "non":
        return "L'IA du bureau est coupée (IA_MODE=non) : rien n'est suivi."
    if reglage("TELEGRAM_AGENTS") != "oui":
        return ("Désactivé. Sur le PC : nc-reglages → Agents IA → « Agents de code depuis Telegram » (ou l'île, page Agents IA, "
                "bouton ⚙). Pour répondre, il faut aussi le code d'authentification : nc-noeud totp creer.")
    return None


async def _executer(argv, delai, limite, entree=None):
    fonction = executer
    if fonction is None:
        import nc_noctalia
        fonction = nc_noctalia.executer
    if entree is None:
        return await fonction(argv, delai, limite, False)
    return await fonction(argv, delai, limite, False, entree=entree)


# ── Texte sûr ───────────────────────────────────────────────────────────────────────────────────────────────────
def _invisible(c):
    return unicodedata.category(c) in ("Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp") or ord(c) in INVISIBLES


def propre(texte, n):
    """Un texte rendu sûr pour l'affichage : chaînes seulement, caractères de contrôle, d'inversion d'écriture et invisibles
    retirés, espaces ramenés à un seul, n signes au plus (« … » s'il est coupé)."""
    if not isinstance(texte, str):
        return ""
    texte = "".join(" " if c.isspace() else ("" if _invisible(c) else c) for c in texte)
    texte = re.sub(r" {2,}", " ", texte).strip()
    return texte if len(texte) <= n else texte[:max(0, n - 1)] + "…"


MASQUE = "[masqué]"
SECRETS = (
    (re.compile(r"-----BEGIN [A-Z0-9 ]+-----.*?(?:-----END [A-Z0-9 ]+-----|\Z)", re.S), "[clé masquée]"),
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}"), MASQUE),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{8,}"), MASQUE),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{8,}"), MASQUE),
    (re.compile(r"\bxox[a-z]-[A-Za-z0-9-]{6,}"), MASQUE),
    (re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{12,}"), MASQUE),
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{16,}"), "Bearer " + MASQUE),
    (re.compile(r"(?i)\b([a-z0-9_.-]*(?:password|passwd|pwd|token|secret|api[_-]?key))\s*[=:]\s*(?:\"[^\"]*\"|'[^']*'|\S+)"),
     r"\1=" + MASQUE),
    (re.compile(r"/(home|Users)/[^/\s\"']+"), r"/\1/…"),
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+"), "…@…"),
    (re.compile(r"\b[0-9A-Fa-f]{32,}\b"), MASQUE),
    (re.compile(r"[A-Za-z0-9+/_-]{32,}={0,2}"), MASQUE),
)


def filtrer(texte):
    """Retire d'un texte ce qui ressemble à un secret ou à une donnée personnelle (jetons, clés, mots de passe, chemins /home/…,
    e-mails, longues suites hexadécimales ou base64). Un garde-fou : une autre forme de secret passerait."""
    for motif, remplacement in SECRETS:
        texte = motif.sub(remplacement, texte)
    return texte


def extrait(message):
    """Le dernier message d'un agent, prêt pour Telegram : filtré, nettoyé, 600 signes au plus."""
    if not isinstance(message, str):
        return ""
    return propre(filtrer(message[:8000]), EXTRAIT_MAX)


def nom_dossier(valeur):
    """Le NOM d'un dossier (jamais un chemin), 40 signes au plus, en texte brut."""
    if not isinstance(valeur, str):
        return "?"
    nom = propre(filtrer(valeur.rstrip("/").rsplit("/", 1)[-1]), DOSSIER_MAX)
    return nom or "?"


def verifier_texte(texte):
    """None si la réponse peut partir, sinon pourquoi elle est refusée (texte pour Telegram)."""
    if not texte.strip():
        return "Texte vide : /repondre N texte"
    if len(texte) > TEXTE_MAX:
        return "Texte trop long (%d signes au plus)." % TEXTE_MAX
    if "\n" in texte or "\r" in texte:
        return "Un seul paragraphe : pas de retour à la ligne."
    for c in texte:
        o = ord(c)
        if o < 32 or 127 <= o <= 159:
            return "Caractère de contrôle ou séquence d'échappement refusé."
        if _invisible(c) or (c.isspace() and c != " "):
            return "Caractère invisible ou d'inversion d'écriture refusé."
    if texte.lstrip().startswith("!"):
        return "Un texte qui commence par ! est refusé (certains agents le lancent comme une commande du shell)."
    return None


def ressemble_a_une_autorisation(texte):
    mot = texte.strip().lower().rstrip(".!")
    return mot in AUTORISATION or (len(mot) == 1 and mot.isdigit())


# ── Les sessions de nc-claude ───────────────────────────────────────────────────────────────────────────────────
def _nom_agent(valeur):
    if not isinstance(valeur, str):
        return None
    return NOMS.get(valeur) or (propre(valeur, 20) if re.fullmatch(r"[a-z][a-z0-9_-]{0,19}", valeur) else "agent")


def valider(brut, avec_texte):
    """La sortie JSON de `nc-claude etat --json` (contrat 1) → liste de sessions reconstruites champ par champ, ou None."""
    try:
        d = json.loads(brut)
    except (ValueError, RecursionError):
        return None
    if not isinstance(d, dict) or d.get("contrat") != 1 or isinstance(d.get("contrat"), bool) or not isinstance(d.get("sessions"), list):
        return None
    sessions = []
    for x in d["sessions"][:SESSIONS_MAX]:
        if not isinstance(x, dict) or not isinstance(x.get("id"), str) or not IDENTIFIANT.fullmatch(x["id"]):
            continue
        agent = _nom_agent(x.get("agent"))
        if agent is None:
            continue
        s = {"id": x["id"], "agent": agent, "dossier": nom_dossier(x.get("dossier")),
             "etat": ETATS.get(x.get("etat") if isinstance(x.get("etat"), str) else "", "état inconnu"),
             "ecrire": x.get("ecrire") is True}
        if avec_texte and x.get("message"):
            s["message"] = extrait(x["message"])
        sessions.append(s)
    return sessions


async def lire_sessions(avec_texte=False):
    """Les sessions suivies (argv exact, délai borné), ou None si nc-claude ne répond pas correctement."""
    argv = ["nc-claude", "etat", "--json"] + (["--texte"] if avec_texte else [])
    code, sortie = await _executer(argv, DELAI_ETAT, SORTIE_MAX)
    return valider(sortie, avec_texte) if code == 0 else None


def numeroter(cle, sessions, maintenant):
    """Un numéro court par session : gardé tant que la liste précédente a moins de 10 minutes, sinon repartir de 1. Le numéro
    désigne l'identifiant réel (gardé ici), jamais l'inverse. Renvoie {identifiant: numéro}."""
    avant = _listes.get(cle)
    anciens = {i: n for n, i in avant["ids"].items()} if avant and 0 <= maintenant - avant["t"] <= VALIDITE else {}
    numeros = {s["id"]: anciens[s["id"]] for s in sessions if s["id"] in anciens}
    pris = set(numeros.values())
    for s in sessions:
        if s["id"] not in numeros:
            n = next(i for i in range(1, 1000) if i not in pris)
            numeros[s["id"]] = n
            pris.add(n)
    _listes[cle] = {"t": maintenant, "ids": {n: i for i, n in numeros.items()},
                    "ecrire": {numeros[s["id"]]: s["ecrire"] for s in sessions}}
    return numeros


# ── Journal local des envois (jamais le texte) ──────────────────────────────────────────────────────────────────
def fichier_journal():
    return Path.home() / ".local/state/nc-jarvis/agents-envois.log"


def journaliser(agent, dossier, longueur, ok, maintenant=None):
    """Une ligne par envoi : date, agent, nom du dossier, longueur, ok ou echec. Fichier 0600, borné (les plus anciennes lignes
    partent). Une erreur de disque est journalisée, jamais fatale."""
    f = fichier_journal()
    date = datetime.datetime.fromtimestamp(time.time() if maintenant is None else maintenant).astimezone().isoformat(timespec="seconds")
    ligne = "\t".join((date, propre(agent, 30), propre(dossier, DOSSIER_MAX), str(int(longueur)), "ok" if ok else "echec")) + "\n"
    try:
        f.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(f, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            os.fchmod(fd, 0o600)
            os.write(fd, ligne.encode("utf-8"))
            taille = os.fstat(fd).st_size
        finally:
            os.close(fd)
        if taille > JOURNAL_MAX:
            lignes = f.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)[-JOURNAL_LIGNES:]
            tmp = f.with_name(f.name + ".tmp")
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
            try:
                os.write(fd, "".join(lignes).encode("utf-8"))
            finally:
                os.close(fd)
            os.replace(tmp, f)
    except OSError as exc:
        logger.warning("Journal des envois aux agents non écrit : %s", exc)


# ── Le code de confirmation : celui de nc-noeud ─────────────────────────────────────────────────────────────────
TOTP_ABSENT = ("Le code de confirmation n'est pas prêt sur ce PC, donc rien ne peut être envoyé. Sur le PC : nc-noeud totp creer, "
               "ajoute la clé dans ton appli d'authentification, puis nc-noeud totp verifier 123456.")
TOTP_BLOQUE = "Le code de confirmation est bloqué (trop de codes faux). Sur le PC : nc-noeud totp verifier 123456."


async def totp_pret():
    """None si nc-noeud a un code vérifié et non bloqué, sinon le message à montrer."""
    code, _ = await _executer(["nc-noeud", "totp", "pret"], DELAI_CODE, 200)
    if code == 0:
        return None
    if code == 4:
        return TOTP_BLOQUE
    if code == 127:
        return "nc-noeud est introuvable sur ce PC : le code de confirmation ne peut pas être vérifié."
    return TOTP_ABSENT


async def totp_controler(code):
    """Le code est lu par `nc-noeud totp controler` sur son entrée standard (jamais dans la ligne de commande) : usage unique,
    codes faux comptés et bloqués comme pour la confirmation à distance. Renvoie (bon, message si refusé)."""
    sortie, _ = await _executer(["nc-noeud", "totp", "controler"], DELAI_CODE, 200, entree=(code + "\n").encode("ascii"))
    if sortie == 0:
        return True, ""
    if sortie == 3:
        return False, TOTP_ABSENT
    if sortie == 4:
        return False, TOTP_BLOQUE
    if sortie in (124, 127):
        return False, "Le code n'a pas pu être vérifié (nc-noeud ne répond pas) : rien n'est envoyé."
    return False, "Code refusé (faux ou déjà utilisé) : rien n'est envoyé. Refais /repondre pour une nouvelle demande."


# ── Les commandes ───────────────────────────────────────────────────────────────────────────────────────────────
def _arguments(brut):
    """Ce qui suit le nom de la commande, tel qu'écrit (retours à la ligne compris : context.args les aurait effacés)."""
    m = re.match(r"\s*/[A-Za-z0-9_]+(?:@\w+)?(?:\s+(.*))?\Z", brut or "", re.S)
    return (m.group(1) or "").strip() if m else ""


async def cmd_agents(brut, chat_id, user_id, prive, maintenant):
    refus = indisponible()
    if refus:
        return refus
    if not prive:
        return "⛔ Les agents ne se suivent que dans la discussion privée avec le bot."
    avec_texte = reglage("TELEGRAM_AGENTS_TEXTE") == "oui"
    sessions = await lire_sessions(avec_texte)
    if sessions is None:
        return "❌ nc-claude ne répond pas (mettre à jour nc-claude ?)."
    cle = (chat_id, user_id)
    if not sessions:
        _listes.pop(cle, None)
        return "Aucun agent de code suivi. Sur le PC : nc-claude installer tout (leurs hooks)."
    numeros = numeroter(cle, sessions, maintenant)
    lignes = ["🤖 Agents de code (%d) :" % len(sessions)]
    for s in sorted(sessions, key=lambda s: numeros[s["id"]]):
        lignes.append("%d. %s · %s · %s" % (numeros[s["id"]], s["agent"], s["dossier"], s["etat"]))
        if not s["ecrire"]:
            lignes.append("   ↳ " + IMPOSSIBLE)
        if s.get("message"):
            lignes.append("   « " + s["message"] + " »")
    lignes.append("Répondre : /repondre N texte (puis /code avec les 6 chiffres de ton appli). Liste valable 10 minutes.")
    return "\n".join(lignes)


async def cmd_repondre(brut, chat_id, user_id, prive, maintenant):
    refus = indisponible()
    if refus:
        return refus
    if not prive:
        return "⛔ Les réponses aux agents ne se demandent que dans la discussion privée avec le bot."
    m = re.match(r"(\S+)\s+(.*)\Z", _arguments(brut), re.S)
    if not m or not NUMERO.fullmatch(m.group(1)):
        return "Usage : /repondre N texte (N : le numéro donné par /agents)."
    numero, texte = int(m.group(1)), m.group(2).strip()
    cle = (chat_id, user_id)
    liste = _listes.get(cle)
    if not liste or not 0 <= maintenant - liste["t"] <= VALIDITE:
        return "La liste a plus de 10 minutes (ou n'existe pas) : tape /agents d'abord."
    if numero not in liste["ids"]:
        return "Numéro inconnu : tape /agents pour la liste."
    if not liste["ecrire"].get(numero):
        return "❌ Agent %d : %s." % (numero, IMPOSSIBLE)
    erreur = verifier_texte(texte)
    if erreur:
        return "❌ " + erreur
    erreur = await totp_pret()
    if erreur:
        return "❌ " + erreur
    sessions = await lire_sessions(False)
    s = next((x for x in sessions or () if x["id"] == liste["ids"][numero]), None)
    if s is None or not s["ecrire"]:
        _listes.pop(cle, None)
        return "❌ Cette session n'est plus là (ou n'accepte plus l'écriture) : tape /agents."
    avant = _attente.get(cle)
    remplace = ""
    if avant and avant["echeance"] >= maintenant:
        remplace = "La demande en attente (%s) est remplacée.\n" % avant["resume"]
    resume = "%s · %s" % (s["agent"], s["dossier"])
    _attente[cle] = {"id": s["id"], "agent": s["agent"], "dossier": s["dossier"], "texte": texte, "echeance": maintenant + CONFIRMATION,
                     "resume": resume}
    avertissement = ""
    if ressemble_a_une_autorisation(texte):
        avertissement = "\n⚠️ attention : tu autorises peut-être une commande de l'agent."
    elif texte.lstrip().startswith("/"):
        avertissement = "\n⚠️ Ce texte commence par / : l'agent peut le prendre pour une commande."
    etat = "" if s["etat"] == "t'attend" else "\n(l'agent est dans l'état « %s », pas « t'attend »)" % s["etat"]
    return ("⚠️ " + remplace + "Envoyer à %s (%s), %d signes :\n« %s »%s%s\nConfirme avec /code 123456 (les 6 chiffres de ton appli "
            "d'authentification) dans les deux minutes." % (s["agent"], s["dossier"], len(texte), texte, etat, avertissement))


async def cmd_code(brut, chat_id, user_id, prive, maintenant):
    refus = indisponible()
    if refus:
        return refus
    if not prive:
        return "⛔ Le code ne se tape que dans la discussion privée avec le bot."
    code = _arguments(brut)
    if not CODE.fullmatch(code):
        return "Le code fait 6 chiffres collés : /code 123456."
    cle = (chat_id, user_id)
    demande = _attente.pop(cle, None)            # avant tout await : un seul /code emporte la demande
    if not demande or demande["echeance"] < maintenant:
        return "Rien à confirmer (ou plus de deux minutes ont passé) : refais /repondre."
    bon, message = await totp_controler(code)
    if not bon:
        return "❌ " + message
    sessions = await lire_sessions(False)
    s = next((x for x in sessions or () if x["id"] == demande["id"]), None)
    if s is None or not s["ecrire"]:
        return "❌ Cette session n'est plus là (ou n'accepte plus l'écriture) : rien n'est envoyé."
    # L'argv exact : l'identifiant vient de nc-claude (validé), le texte est UN argument (vérifié : une ligne, sans contrôle)
    sortie, _ = await _executer(["nc-claude", "ecrire", s["id"], demande["texte"]], DELAI_ECRIRE, 500)
    ok = sortie == 0
    journaliser(s["agent"], s["dossier"], len(demande["texte"]), ok, maintenant)
    logger.info("Réponse à un agent (%s, %s, %d signes) : %s", s["agent"], s["dossier"], len(demande["texte"]), "ok" if ok else "échec")
    return ("✅ Envoyé à %s (%s)." if ok else "❌ Échec de l'envoi à %s (%s) : son terminal n'accepte plus l'écriture ?") % (s["agent"], s["dossier"])


def handler(tb, commande):
    """Le handler Telegram d'une commande : liste blanche du bot, messages modifiés ignorés, heure du message (pas celle du
    traitement), conversation privée ou non, puis la commande."""
    async def h(update, context):
        if getattr(update, "edited_message", None) is not None:
            return
        message = getattr(update, "message", None)
        if message is None:
            return
        user = update.effective_user
        if not tb._is_allowed(user.id):
            logger.warning("Commande agents refusée à l'utilisateur Telegram %s.", user.id)
            await message.reply_text("⛔ Accès non autorisé.")
            return
        date = getattr(message, "date", None)
        prive = getattr(update.effective_chat, "type", None) == "private"
        brut = message.text if isinstance(getattr(message, "text", None), str) else "/x " + " ".join(context.args or [])
        reponse = await commande(brut, update.effective_chat.id, user.id, prive, date.timestamp() if date is not None else time.time())
        await message.reply_text(reponse[:4000])
    return h


def commandes(tb):
    """[(noms, handler)] pour nc_telegram.commandes_nc."""
    return [(["agents", "claude"], handler(tb, cmd_agents)), (["repondre"], handler(tb, cmd_repondre)),
            (["code"], handler(tb, cmd_code))]


MENU = (("agents", "Suivre tes agents de code (réglage requis)"), ("repondre", "Répondre à un agent : /repondre N texte"),
        ("code", "Confirmer avec le code : /code 123456"))
