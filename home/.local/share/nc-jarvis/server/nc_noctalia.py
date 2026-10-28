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
  /nc vpn [connecter UUID|deconnecter UUID|tout|killswitch]   les tunnels VPN du PC, par « nc-vpn --json » (contrat 1) ;
                                   connecter, déconnecter et tout couper demandent « /nc oui » ; le kill switch se LIT seulement
  /nc oui                          confirmer l'action sensible en attente
"""
import asyncio
import json
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
# VPN : liste blanche d'actions → argv de nc-vpn (jamais un shell). Le kill switch ne s'active ni ne se coupe d'ici : couper
# une protection à distance, avec un compte de messagerie ou une clé volés, démasquerait la connexion (lecture seule).
VPN_UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
VPN_DELAIS = {"vpn_etat": 15, "vpn_connecter": 130, "vpn_deconnecter": 70, "vpn_tout": 130, "vpn_killswitch": 20}
VPN_MAX_SORTIE = 60000      # octets lus sur nc-vpn avant de valider (le résultat rendu est borné plus bas)
VPN_MAX_LIGNES = 64         # connexions rendues au plus
VPN_ERREURS = {"uuid_invalide": "UUID invalide.", "inconnue": "Ce n'est pas un VPN connu de NetworkManager.",
               "nm_indisponible": "NetworkManager n'est pas disponible.", "echec": "nc-vpn a échoué (connexion refusée ou délai).",
               "echec_partiel": "Certains tunnels n'ont pas pu être coupés."}
CLE = re.compile(r"[A-Z][A-Z0-9_]{0,60}")
# Réglages changeables à distance (Telegram, cockpit) : LISTE BLANCHE, copie de DISTANT_PERMIS de nc-reglages (qui la
# vérifie aussi, côté PC, avec « set --distant » : ce contrôle-ci ne suffit pas, un gateway compromis le contournerait).
# tests/test_reglage_distant.py vérifie que les deux listes sont identiques. Jamais NOEUD_*, IA_*, ALERTES_*, MAJ_*…
DISTANT_PERMIS = frozenset((
    "THEME_MODE", "ILE_STYLE", "ILE_CONTOUR", "ILE_HEURE", "ILE_SURVOL", "ILE_DATE", "ILE_ANIM_BATTERIE", "ILE_BANNIERES",
    "ILE_BANNIERE_DUREE", "ILE_METEO", "COINS_ECRAN", "EFFETS", "FENETRES_ESPACE", "FENETRES_MARGE", "FENETRES_BORDURE",
    "FENETRES_ARRONDI", "FENETRES_HALO", "BARRE_OPACITE", "DOCK", "DOCK_AUTO", "DOCK_TAILLE", "DOCK_LOUPE", "DOCK_POSITION",
    "NUIT", "NUIT_TEMPERATURE", "TERMINAL_OPACITE", "TERMINAL_TAILLE", "VOLUME_PAS", "LUMINOSITE_PAS"))

# Le catalogue, repris par actions.json (cockpit) : id, libellé, champs, lecture seule, sensible
ACTIONS = {
    "etat": dict(label="État du PC", fields=[], readonly=True),
    "energie": dict(label="Profil d'énergie", fields=[dict(key="profil", label="performance, equilibre ou eco (vide : lire)")], readonly=False),
    "theme": dict(label="Thème", fields=[dict(key="theme", label="sombre ou clair (vide : lire)")], readonly=False),
    "fond": dict(label="Fond d'écran suivant", fields=[], readonly=False),
    "ecran": dict(label="Projection", fields=[dict(key="mode", label="pc, miroir, etendre ou externe (vide : état)")], readonly=False, sensible=("pc", "externe")),
    "maj": dict(label="Mises à jour du système", fields=[], readonly=True),
    "reglage": dict(label="Un réglage de nc-reglages", fields=[dict(key="cle", label="Clé (nc-reglages liste)"), dict(key="valeur", label="Nouvelle valeur (vide : lire)")], readonly=False),
    "vpn_etat": dict(label="VPN : tunnels du PC", fields=[], readonly=True),
    "vpn_connecter": dict(label="VPN : monter un tunnel", fields=[dict(key="uuid", label="UUID de la connexion (vpn_etat)")], readonly=False, sensible=True),
    "vpn_deconnecter": dict(label="VPN : couper un tunnel", fields=[dict(key="uuid", label="UUID de la connexion (vpn_etat)")], readonly=False, sensible=True),
    "vpn_tout": dict(label="VPN : couper tous les tunnels", fields=[], readonly=False, sensible=True),
    "vpn_killswitch": dict(label="VPN : état du kill switch (lecture seule)", fields=[], readonly=True),
}


def local():
    return os.environ.get("DEPLOY_MODE", "local").strip().lower() != "server"


async def executer(argv, delai=DELAI, limite=3000):
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
    return p.returncode, re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", sortie.decode("utf-8", errors="replace"))[:limite].strip()


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
        return ["nc-reglages", "set", "--distant", "THEME_MODE", theme], False
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
    if action.startswith("vpn_"):
        return vpn_argv(action, arguments), ACTIONS[action].get("sensible", False)
    if action == "reglage":
        if not arguments or not CLE.fullmatch(arguments[0]):
            raise ValueError("Réglage : /nc reglage CLE [VALEUR] (nc-reglages liste pour les clés).")
        if len(arguments) == 1:
            return ["nc-reglages", "get", arguments[0]], False
        if arguments[0] not in DISTANT_PERMIS:
            # Écrire un réglage est réservé à une liste blanche (apparence, confort) ; la lecture reste libre
            raise ValueError(arguments[0][:60] + " ne se change pas à distance (depuis ce PC seulement).")
        valeur = " ".join(arguments[1:])
        if len(valeur) > 200 or any(ord(c) < 32 for c in valeur):
            raise ValueError("Valeur : 200 caractères au plus, sans retour à la ligne.")
        return ["nc-reglages", "set", "--distant", arguments[0], valeur], False   # nc-reglages revérifie la liste
    raise ValueError("Action inconnue : " + ", ".join(ACTIONS))


def vpn_argv(action, arguments):
    """L'argv exact de nc-vpn pour une action VPN de la liste blanche ; ValueError (message) sinon. L'UUID est vérifié ICI,
    avant tout appel (forme stricte, minuscules) ; nc-vpn le revérifie et ne l'accepte que s'il est connu de NetworkManager."""
    if action in ("vpn_connecter", "vpn_deconnecter"):
        if len(arguments) != 1 or not VPN_UUID.fullmatch(arguments[0]):
            raise ValueError("UUID invalide : 8-4-4-4-12 chiffres hexadécimaux (/nc vpn pour les connaître).")
        return ["nc-vpn", "connecter" if action == "vpn_connecter" else "deconnecter", arguments[0].lower(), "--json"]
    if arguments:
        raise ValueError("Cette action VPN n'a pas d'argument.")
    if action == "vpn_etat":
        return ["nc-vpn", "etat-json"]
    if action == "vpn_tout":
        return ["nc-vpn", "tout-deconnecter", "--json"]
    if action == "vpn_killswitch":
        return ["nc-vpn", "killswitch", "etat-json"]
    raise ValueError("Action VPN inconnue.")


def _texte(v, n):
    """Un texte de nc-vpn rendu sûr : chaîne, sans caractère de contrôle, de n caractères au plus."""
    return "".join(c for c in v if c.isprintable())[:n] if isinstance(v, str) else None


def _connexion(c, avec_etat):
    """Une connexion de nc-vpn reconstruite champ par champ (rien d'autre ne passe) ; None si invalide."""
    if not isinstance(c, dict) or not isinstance(c.get("uuid"), str) or not VPN_UUID.fullmatch(c["uuid"]):
        return None
    nom = _texte(c.get("nom"), 80)
    if nom is None:
        return None
    r = {"uuid": c["uuid"].lower(), "nom": nom}
    if avec_etat:
        interface = _texte(c.get("interface"), 32)
        if c.get("type") not in ("vpn", "wireguard") or not isinstance(c.get("active"), bool) or interface is None:
            return None
        r.update(type=c["type"], active=c["active"], interface=interface)
    return r


def _liste(brut, avec_etat):
    if not isinstance(brut, list) or len(brut) > 256:
        return None
    res = [_connexion(c, avec_etat) for c in brut[:VPN_MAX_LIGNES]]
    return None if any(r is None for r in res) else res


def vpn_valider(action, code, sortie, uuid=None):
    """La sortie JSON de nc-vpn (contrat 1) → (succès, texte). La sortie est analysée, vérifiée champ par champ puis
    RECONSTRUITE : seuls les champs du contrat sortent, bornés ; un texte libre de nc-vpn n'est jamais relayé."""
    invalide = (False, "Réponse de nc-vpn invalide (mettre à jour nc-vpn ?).")
    if code == 124:
        return False, "Délai dépassé"
    if code == 127:
        return False, "nc-vpn est introuvable."
    try:
        d = json.loads(sortie)
    except (ValueError, RecursionError):
        return invalide
    if not isinstance(d, dict) or d.get("contrat") != 1 or isinstance(d.get("contrat"), bool):
        return invalide
    if action == "vpn_etat":
        if code != 0 or not isinstance(d.get("disponible"), bool):
            return invalide
        lignes = _liste(d.get("connexions"), True)
        if lignes is None:
            return invalide
        return True, json.dumps({"contrat": 1, "disponible": d["disponible"], "connexions": lignes}, ensure_ascii=False)
    if action == "vpn_killswitch":
        limites = d.get("limites")
        refus = _texte(d.get("refus"), 300)
        if code != 0 or not all(isinstance(d.get(k), bool) for k in ("installe", "voulu")) or d.get("actif") not in (True, False, None) \
                or refus is None or not isinstance(limites, list) or len(limites) > 12:
            return invalide
        textes = [_texte(x, 300) for x in limites]
        if any(t is None for t in textes):
            return invalide
        return True, json.dumps({"contrat": 1, "installe": d["installe"], "voulu": d["voulu"], "actif": d["actif"],
                                 "refus": refus, "limites": textes}, ensure_ascii=False)
    ok = d.get("ok")
    if not isinstance(ok, bool) or ok != (code == 0):
        return invalide
    if not ok:
        c = d.get("code")
        extra = {}
        if action == "vpn_tout":
            for k in ("coupes", "rates"):
                extra[k] = _liste(d.get(k), False) if k in d else []
                if extra[k] is None:
                    extra[k] = []
        return False, VPN_ERREURS.get(c if isinstance(c, str) else "", VPN_ERREURS["echec"]) + (" " + json.dumps(extra, ensure_ascii=False) if extra else "")
    if action == "vpn_tout":
        coupes, rates = _liste(d.get("coupes"), False), _liste(d.get("rates"), False)
        if d.get("action") != "tout-deconnecter" or coupes is None or rates is None:
            return invalide
        return True, json.dumps({"contrat": 1, "ok": True, "action": "tout-deconnecter", "coupes": coupes, "rates": rates}, ensure_ascii=False)
    voulu = "connecter" if action == "vpn_connecter" else "deconnecter"
    c = _connexion(d, False)
    if d.get("action") != voulu or c is None or c["uuid"] != (uuid or "").lower() or not isinstance(d.get("actif"), bool) \
            or d["actif"] != (voulu == "connecter") or not isinstance(d.get("deja"), bool):
        return invalide
    return True, json.dumps({"contrat": 1, "ok": True, "action": voulu, "uuid": c["uuid"], "nom": c["nom"],
                             "actif": d["actif"], "deja": d["deja"]}, ensure_ascii=False)


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
        quoi = "un tunnel VPN va changer d'état" if action.startswith("vpn_") else "un écran va s'éteindre"
        return dict(success=False, confirm=True, output="Action sensible (" + quoi + ") : confirme avec /nc oui dans les deux minutes.")
    if action.startswith("vpn_"):
        code, sortie = await executer(argv, VPN_DELAIS[action], VPN_MAX_SORTIE)
        succes, texte = vpn_valider(action, code, sortie, argv[2] if action in ("vpn_connecter", "vpn_deconnecter") else None)
        logger.info("Action /nc %s %s → code %s", action, " ".join(arguments), code)
        return dict(success=succes, output=texte)
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
            "/nc vpn — tunnels VPN ; /nc vpn connecter UUID, /nc vpn deconnecter UUID, /nc vpn tout (confirmation) ; /nc vpn killswitch (lecture)\n"
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
    if action == "vpn":
        # /nc vpn [connecter UUID | deconnecter UUID | tout | killswitch] → l'action de la liste blanche (les autres mots : refusés)
        sous = arguments[0].lower() if arguments else "etat"
        action = {"etat": "vpn_etat", "connecter": "vpn_connecter", "deconnecter": "vpn_deconnecter", "tout": "vpn_tout",
                  "tout-deconnecter": "vpn_tout", "killswitch": "vpn_killswitch"}.get(sous)
        if not action:
            return "Commande VPN inconnue.\n\n" + aide()
        arguments = arguments[1:]
    elif action.startswith("vpn_"):
        return "Commande inconnue.\n\n" + aide()       # les identifiants internes ne se tapent pas
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
        # L'heure du message, pas celle du traitement : une confirmation « /nc oui » ne vaut que dans les deux minutes
        # qui suivent l'envoi de sa commande (revue SRV-03)
        date = getattr(update.message, "date", None)
        reponse = await commande(" ".join(context.args or []), update.effective_chat.id,
                                 date.timestamp() if date is not None else None)
        await update.message.reply_text(reponse[:4000])
    return nc
