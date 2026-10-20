"""Réglages du PC Noctalia depuis Telegram (/nc) et depuis le cockpit (op noctalia de /api/nc/manage).

Seulement en déploiement local (DEPLOY_MODE=local, le gateway tourne sur le PC) : le mode serveur ne pilote pas le
bureau. Les actions sont une table fixe de commandes nc-* et powerprofilesctl du compte qui héberge le gateway, avec
leurs arguments vérifiés ici (jamais de shell, jamais d'argument libre : nc-reglages valide lui-même les valeurs).
Telegram : utilisateurs de la liste blanche du bot (TELEGRAM_ALLOWED_USER_IDS) ; une action sensible (éteindre un
écran) demande une confirmation, « /nc oui » dans les deux minutes. Les commandes qui touchent l'écran ont besoin de
l'environnement de la session Hyprland (importé dans systemd --user à l'ouverture de session).

  /nc                              état : profil d'énergie, batterie, écrans, mises à jour, thème
  /nc energie [performance|equilibre|eco]   lire ou changer le profil d'énergie
  /nc theme [sombre|clair]         thème de Noctalia (THEME_MODE)
  /nc fond                         fond d'écran suivant
  /nc ecran [pc|miroir|etendre|externe]     projection (pc et externe éteignent un écran : confirmation)
  /nc maj                          mises à jour du système en attente (comptées par nc-paquets)
  /nc reglage CLE [VALEUR]         un réglage de nc-reglages (nc-reglages liste pour les clés)
  /nc oui                          confirmer l'action sensible en attente
"""
import asyncio
import logging
import os
from pathlib import Path
import re
import time

logger = logging.getLogger("nc_noctalia")
BIN = Path.home() / ".local/bin"
DELAI = 20
CONFIRMATION = 120          # secondes pour répondre /nc oui
_en_attente = {}            # chat_id → (action, arguments, échéance)

PROFILS = {"performance": "performance", "perf": "performance", "equilibre": "balanced", "équilibré": "balanced",
           "equilibré": "balanced", "balanced": "balanced", "eco": "power-saver", "éco": "power-saver", "economie": "power-saver",
           "power-saver": "power-saver"}
THEMES = {"sombre": "dark", "dark": "dark", "clair": "light", "light": "light"}
ECRANS = ("pc", "miroir", "etendre", "externe")
CLE = re.compile(r"[A-Z][A-Z0-9_]{0,60}")

# Le catalogue, repris par actions.json (cockpit) : id, libellé, champs, lecture seule, sensible
ACTIONS = {
    "etat": dict(label="État du PC", fields=[], readonly=True),
    "energie": dict(label="Profil d'énergie", fields=[dict(key="profil", label="performance, equilibre ou eco (vide : lire)")], readonly=False),
    "theme": dict(label="Thème", fields=[dict(key="theme", label="sombre ou clair (vide : lire)")], readonly=False),
    "fond": dict(label="Fond d'écran suivant", fields=[], readonly=False),
    "ecran": dict(label="Projection", fields=[dict(key="mode", label="pc, miroir, etendre ou externe (vide : état)")], readonly=False, sensible=("pc", "externe")),
    "maj": dict(label="Mises à jour du système", fields=[], readonly=True),
    "reglage": dict(label="Un réglage de nc-reglages", fields=[dict(key="cle", label="Clé (nc-reglages liste)"), dict(key="valeur", label="Nouvelle valeur (vide : lire)")], readonly=False),
}


def local():
    return os.environ.get("DEPLOY_MODE", "local").strip().lower() != "server"


async def executer(argv, delai=DELAI):
    """Une commande de l'hôte (liste d'arguments, jamais de shell) ; (code, sortie tronquée)."""
    programme = str(BIN / argv[0]) if not argv[0].startswith("/") and (BIN / argv[0]).exists() else argv[0]
    try:
        p = await asyncio.create_subprocess_exec(programme, *argv[1:], stdin=asyncio.subprocess.DEVNULL,
                                                 stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    except OSError as exc:
        return 127, str(exc)[:200]
    try:
        sortie, _ = await asyncio.wait_for(p.communicate(), delai)
    except asyncio.TimeoutError:
        p.kill()
        await p.wait()
        return 124, "Délai dépassé"
    return p.returncode, re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", sortie.decode("utf-8", errors="replace"))[:3000].strip()


def preparer(action, arguments):
    """Vérifie une action et ses arguments ; renvoie (argv, sensible) ou lève ValueError (message pour l'utilisateur)."""
    arguments = [str(a).strip() for a in arguments if str(a).strip()]
    if action == "etat":
        return None, False
    if action == "energie":
        if not arguments:
            return ["powerprofilesctl", "get"], False
        profil = PROFILS.get(arguments[0].lower())
        if not profil:
            raise ValueError("Profil : performance, equilibre ou eco.")
        return ["powerprofilesctl", "set", profil], False
    if action == "theme":
        if not arguments:
            return ["nc-reglages", "get", "THEME_MODE"], False
        theme = THEMES.get(arguments[0].lower())
        if not theme:
            raise ValueError("Thème : sombre ou clair.")
        return ["nc-reglages", "set", "THEME_MODE", theme], False
    if action == "fond":
        return ["noctalia", "msg", "wallpaper", "random"], False
    if action == "ecran":
        if not arguments:
            return ["nc-ecrans", "etat"], False
        mode = arguments[0].lower()
        if mode not in ECRANS:
            raise ValueError("Mode : pc, miroir, etendre ou externe.")
        return ["nc-ecrans", mode], mode in ACTIONS["ecran"]["sensible"]
    if action == "maj":
        return ["nc-paquets"], False
    if action == "reglage":
        if not arguments or not CLE.fullmatch(arguments[0]):
            raise ValueError("Réglage : /nc reglage CLE [VALEUR] (nc-reglages liste pour les clés).")
        if len(arguments) == 1:
            return ["nc-reglages", "get", arguments[0]], False
        valeur = " ".join(arguments[1:])
        if len(valeur) > 200 or any(ord(c) < 32 for c in valeur):
            raise ValueError("Valeur : 200 caractères au plus, sans retour à la ligne.")
        return ["nc-reglages", "set", arguments[0], valeur], False
    raise ValueError("Action inconnue : " + ", ".join(ACTIONS))


async def etat():
    lignes = []
    for titre, argv in (("🔋", ["nc-sysinfo", "power"]), ("🖥", ["nc-sysinfo", "ecrans"]), ("⚡", ["powerprofilesctl", "get"]),
                        ("🎨", ["nc-reglages", "get", "THEME_MODE"]), ("📦", ["nc-paquets"])):
        code, sortie = await executer(argv, 10)
        if code == 0 and sortie:
            lignes.append(titre + " " + sortie.splitlines()[0][:200])
    return "\n".join(lignes) or "État indisponible (nc-sysinfo, powerprofilesctl, nc-paquets)."


async def agir(action, arguments, confirme=False):
    """Exécute une action du catalogue ; {success, output, confirm?}. confirm : une confirmation est nécessaire."""
    if not local():
        return dict(success=False, output="Le mode serveur ne pilote pas le bureau : réglages seulement en déploiement local.")
    if action not in ACTIONS:
        return dict(success=False, output="Action inconnue : " + ", ".join(ACTIONS))
    try:
        argv, sensible = preparer(action, arguments)
    except ValueError as exc:
        return dict(success=False, output=str(exc))
    if argv is None:
        return dict(success=True, output=await etat())
    if sensible and not confirme:
        return dict(success=False, confirm=True, output="Action sensible (un écran va s'éteindre) : confirme avec /nc oui dans les deux minutes.")
    code, sortie = await executer(argv)
    logger.info("Action /nc %s %s → code %s", action, " ".join(arguments), code)
    return dict(success=code == 0, output=sortie or ("Fait." if code == 0 else "Échec (code %s)." % code))


def aide():
    return ("🖥 Réglages du PC Noctalia :\n"
            "/nc — état (énergie, batterie, écrans, mises à jour, thème)\n"
            "/nc energie [performance|equilibre|eco]\n"
            "/nc theme [sombre|clair]\n"
            "/nc fond — fond d'écran suivant\n"
            "/nc ecran [pc|miroir|etendre|externe] — projection (pc et externe : confirmation)\n"
            "/nc maj — mises à jour du système en attente\n"
            "/nc reglage CLE [VALEUR] — un réglage de nc-reglages\n"
            "/nc oui — confirmer l'action sensible en attente")


async def commande(texte, chat_id, maintenant=None):
    """Le texte après /nc → la réponse (pour Telegram)."""
    maintenant = time.time() if maintenant is None else maintenant
    mots = (texte or "").split()
    if mots and mots[0].lower() in ("aide", "help", "?"):
        return aide()
    if mots and mots[0].lower() in ("oui", "yes", "confirmer"):
        attente = _en_attente.pop(chat_id, None)
        if not attente or attente[2] < maintenant:
            return "Rien à confirmer (ou plus de deux minutes ont passé)."
        r = await agir(attente[0], attente[1], confirme=True)
        return ("✅ " if r["success"] else "❌ ") + r["output"]
    action, arguments = (mots[0].lower(), mots[1:]) if mots else ("etat", [])
    if action not in ACTIONS:
        return "Commande inconnue.\n\n" + aide()
    r = await agir(action, arguments)
    if r.get("confirm"):
        _en_attente[chat_id] = (action, arguments, maintenant + CONFIRMATION)
        return "⚠️ " + r["output"]
    return ("✅ " if r["success"] else "❌ ") + r["output"]


def handler(tb):
    """Le handler Telegram de /nc : liste blanche du bot, puis commande()."""
    async def nc(update, context):
        user = update.effective_user
        if not tb._is_allowed(user.id):
            logger.warning("/nc refusé à l'utilisateur Telegram %s.", user.id)
            await update.message.reply_text("⛔ Accès non autorisé.")
            return
        reponse = await commande(" ".join(context.args or []), update.effective_chat.id)
        await update.message.reply_text(reponse[:4000])
    return nc
