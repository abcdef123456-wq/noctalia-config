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
_en_attente = {}            # (chat_id, user_id) → (action, arguments, échéance, résumé) : celui qui demande est celui qui confirme

PROFILS = {"performance": "performance", "perf": "performance", "equilibre": "balanced", "équilibré": "balanced",
           "equilibré": "balanced", "balanced": "balanced", "eco": "power-saver", "éco": "power-saver", "economie": "power-saver",
           "power-saver": "power-saver"}
THEMES = {"sombre": "dark", "dark": "dark", "clair": "light", "light": "light"}
ECRANS = ("pc", "miroir", "etendre", "externe")
# VPN : liste blanche d'actions → argv de nc-vpn (jamais un shell). Le kill switch ne s'active ni ne se coupe d'ici : couper
# une protection à distance, avec un compte de messagerie ou une clé volés, démasquerait la connexion (lecture seule).
VPN_UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
# Délais de JARVIS : AU-DESSUS du pire cas de nc-vpn (connecter ~190 s : état 15, trousseau ~50, nmcli up 120 ; couper ~75 s), pour
# que nc-vpn finisse seul et efface son dossier de mot de passe. Au délai : SIGTERM au groupe (nc-vpn efface), SIGKILL 5 s après.
VPN_DELAIS = {"vpn_etat": 30, "vpn_connecter": 210, "vpn_deconnecter": 90, "vpn_tout": 210, "vpn_killswitch": 60}
GRACE_ARRET = 5             # secondes entre SIGTERM et SIGKILL
# Pourquoi le kill switch ne peut pas s'activer : table maison par `refus_code` (le texte `refus` de nc-vpn, qui peut nommer un
# serveur, n'est JAMAIS relayé) ; les limites sont un texte fixe d'ici.
VPN_REFUS = {"": "", "pas_installe": "l'assistant root n'est pas installé", "aucun_tunnel": "aucun tunnel n'est monté",
             "plusieurs_tunnels": "plusieurs tunnels sont montés (le kill switch n'en protège qu'un)",
             "serveur_nom": "l'adresse du serveur est un nom, pas une adresse IP", "mullvad": "Mullvad est connecté (sa propre protection)",
             "firewall": "un pare-feu en conflit", "nm_indisponible": "NetworkManager n'est pas disponible", "autre": "raison non précisée"}
VPN_LIMITES = ("Ne dure pas après un redémarrage.", "Ne couvre pas les conteneurs ni les machines virtuelles.",
               "Les adresses du serveur sont figées à l'activation.", "Un seul tunnel et un seul serveur.",
               "Le réseau local reste joignable.", "Un rechargement de nftables efface la protection.")
VPN_MAX_SORTIE = 60000      # octets lus sur nc-vpn avant de valider (le résultat rendu est borné plus bas)
VPN_AFFICHEES = 20          # connexions montrées dans la réponse (la liste complète reste dans nc-vpn)
VPN_MAX_LIGNES = 64         # connexions rendues au plus
VPN_ERREURS = {"uuid_invalide": "UUID invalide.", "inconnue": "Ce n'est pas un VPN connu de NetworkManager.",
               "nm_indisponible": "NetworkManager n'est pas disponible.", "echec": "nc-vpn a échoué (connexion refusée ou délai).",
               "echec_partiel": "Certains tunnels n'ont pas pu être coupés.", "occupe": "Un autre changement de VPN est en cours : réessaie dans un instant."}
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


async def executer(argv, delai=DELAI, limite=3000, fusion=True):
    """Une commande de l'hôte (liste d'arguments, jamais de shell) ; (code, sortie tronquée)."""
    programme = str(BIN / argv[0]) if not argv[0].startswith("/") and (BIN / argv[0]).exists() else argv[0]
    try:
        # Un groupe de processus à part : au délai, on arrête TOUT le groupe (nc-vpn et ses nmcli), pas seulement le père
        p = await asyncio.create_subprocess_exec(programme, *argv[1:], stdin=asyncio.subprocess.DEVNULL,
                                                 stdout=asyncio.subprocess.PIPE,
                                                 stderr=asyncio.subprocess.STDOUT if fusion else asyncio.subprocess.PIPE,
                                                 start_new_session=True)
    except OSError as exc:
        return 127, str(exc)[:200]

    async def lire(flux, borne):
        """Lit tout (pour ne pas bloquer le programme) mais ne garde que `borne` octets."""
        gardes = bytearray()
        while True:
            bloc = await flux.read(4096)
            if not bloc:
                return bytes(gardes)
            gardes += bloc[:max(0, borne - len(gardes))]

    taches = [asyncio.ensure_future(lire(p.stdout, limite))]
    if not fusion:
        taches.append(asyncio.ensure_future(lire(p.stderr, 4096)))     # lue pour ne pas bloquer, jamais relayée
    try:
        await asyncio.wait_for(asyncio.gather(*taches, p.wait()), delai)
    except asyncio.TimeoutError:
        await arreter_groupe(p)
        for t in taches:
            t.cancel()
        return 124, "Délai dépassé"
    sortie = taches[0].result()
    return p.returncode, re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", sortie.decode("utf-8", errors="replace"))[:limite].strip()


async def arreter_groupe(p):
    """SIGTERM au groupe du processus (il peut effacer ses fichiers temporaires), puis SIGKILL au groupe s'il traîne."""
    import signal
    for sig, attente in ((signal.SIGTERM, GRACE_ARRET), (signal.SIGKILL, None)):
        try:
            os.killpg(p.pid, sig)
        except (ProcessLookupError, PermissionError):
            break
        try:
            await asyncio.wait_for(p.wait(), attente)
            break
        except asyncio.TimeoutError:
            continue
    try:
        await asyncio.wait_for(p.wait(), 2)
    except asyncio.TimeoutError:
        pass


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
        if not d["disponible"]:                  # NetworkManager absent : pas de liste à vérifier (nc-vpn la rend vide)
            return False, VPN_ERREURS["nm_indisponible"]
        lignes = _liste(d.get("connexions"), True)
        if lignes is None:
            return invalide
        if not lignes:
            return True, "Aucune connexion VPN ou WireGuard dans NetworkManager."
        texte = ["VPN : %d connexion(s)" % len(lignes)]
        for c in lignes[:VPN_AFFICHEES]:
            texte.append("%s %s [%s]%s\n  %s" % ("●" if c["active"] else "○", c["nom"], c["type"],
                                                " " + c["interface"] if c["interface"] else "", c["uuid"]))
        if len(lignes) > VPN_AFFICHEES:
            texte.append("… et %d autre(s)." % (len(lignes) - VPN_AFFICHEES))
        return True, "\n".join(texte)
    if action == "vpn_killswitch":
        # `refus` et `limites` (textes de nc-vpn, dans la langue du bureau, pouvant nommer un serveur) ne sont pas relayés
        rc = d.get("refus_code", "")
        if code != 0 or not all(isinstance(d.get(k), bool) for k in ("installe", "voulu")) or d.get("actif") not in (True, False, None) \
                or not isinstance(rc, str):
            return invalide
        rc = rc if rc in VPN_REFUS else "autre"
        etat = "actif" if d["actif"] is True else "inactif" if d["actif"] is False else "inconnu"
        texte = "Kill switch : " + etat + (" (voulu dans les réglages)" if d["voulu"] else " (coupé dans les réglages)")
        if not d["installe"]:
            texte += " ; assistant root non installé"
        if d["actif"] is not True and rc:
            texte += "\nImpossible à activer : " + VPN_REFUS[rc] + "."
        texte += "\nLimites : " + " ".join(VPN_LIMITES)
        return True, texte
    ok = d.get("ok")
    if not isinstance(ok, bool) or ok != (code == 0):
        return invalide
    if not ok:
        c = d.get("code")
        texte = VPN_ERREURS.get(c if isinstance(c, str) else "", VPN_ERREURS["echec"])
        if action == "vpn_tout":
            rates = _liste(d.get("rates"), False) or []
            if rates:
                texte += " Restent montés : " + ", ".join(r["nom"] for r in rates[:8]) + "."
        return False, texte
    if action == "vpn_tout":
        coupes, rates = _liste(d.get("coupes"), False), _liste(d.get("rates"), False)
        if d.get("action") != "tout-deconnecter" or coupes is None or rates is None:
            return invalide
        if rates:
            return False, VPN_ERREURS["echec_partiel"] + " Restent montés : " + ", ".join(r["nom"] for r in rates[:8]) + "."
        return True, ("Tunnels coupés : " + ", ".join(c["nom"] for c in coupes[:8]) + ".") if coupes else "Aucun tunnel n'était monté."
    voulu = "connecter" if action == "vpn_connecter" else "deconnecter"
    c = _connexion(d, False)
    if d.get("action") != voulu or c is None or c["uuid"] != (uuid or "").lower() or not isinstance(d.get("actif"), bool) \
            or d["actif"] != (voulu == "connecter") or not isinstance(d.get("deja"), bool):
        return invalide
    if voulu == "connecter":
        return True, ("Déjà connecté : " if d["deja"] else "Connecté : ") + c["nom"]
    return True, ("Déjà coupé : " if d["deja"] else "Tunnel coupé : ") + c["nom"]


async def killswitch_actif():
    """True / False / None (inconnu) : l'état du kill switch, lu par nc-vpn (lecture seule, mêmes validations que /nc vpn killswitch)."""
    code, sortie = await executer(["nc-vpn", "killswitch", "etat-json"], VPN_DELAIS["vpn_killswitch"], VPN_MAX_SORTIE, False)
    succes, _ = vpn_valider("vpn_killswitch", code, sortie)
    if not succes:
        return None
    return json.loads(sortie)["actif"]


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
        if action.startswith("vpn_"):
            if action == "vpn_tout":
                resume = "couper TOUS les tunnels VPN"
            else:
                resume = ("connecter" if action == "vpn_connecter" else "couper") + " le tunnel " + argv[2][:8] + "…"
            note = ""
            if action != "vpn_connecter":
                actif = await killswitch_actif()
                note = (" Le kill switch est actif : JARVIS perdra le réseau et ne pourra pas remonter le tunnel." if actif is True else
                        " Le kill switch est inactif : ta connexion réelle sera visible." if actif is False else
                        " État du kill switch inconnu : la connexion réelle peut devenir visible.")
            return dict(success=False, confirm=True, resume=resume,
                        output="Action sensible : " + resume + "." + note + " Confirme avec /nc oui dans les deux minutes.")
        return dict(success=False, confirm=True, resume="projection " + " ".join(arguments),
                    output="Action sensible (un écran va s'éteindre) : confirme avec /nc oui dans les deux minutes.")
    if action.startswith("vpn_"):
        code, sortie = await executer(argv, VPN_DELAIS[action], VPN_MAX_SORTIE, False)
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


async def commande(texte, chat_id, maintenant=None, user_id=None, prive=True):
    """Le texte après /nc → la réponse (pour Telegram). La confirmation appartient à (chat, utilisateur) : un autre membre du
    même chat ne confirme pas. Une action sensible n'est acceptée que dans la discussion privée avec le bot (prive)."""
    cle = (chat_id, user_id)
    maintenant = time.time() if maintenant is None else maintenant
    mots = (texte or "").split()
    if mots and mots[0].lower() in ("aide", "help", "?"):
        return aide()
    if mots and mots[0].lower() in ("oui", "yes", "confirmer"):
        if not prive:
            return "Les actions sensibles ne se confirment que dans la discussion privée avec le bot."
        attente = _en_attente.pop(cle, None)
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
        if not prive:
            return "⛔ Action sensible refusée ici : demande-la dans la discussion privée avec le bot."
        avant = _en_attente.get(cle)
        remplace = ""
        if avant and avant[2] >= maintenant:
            remplace = "L'action en attente (%s) est remplacée.\n" % avant[3]
        _en_attente[cle] = (action, arguments, maintenant + CONFIRMATION, r.get("resume", action))
        return "⚠️ " + remplace + r["output"]
    return ("✅ " if r["success"] else "❌ ") + r["output"]


def handler(tb):
    """Le handler Telegram de /nc : liste blanche du bot, puis commande()."""
    async def nc(update, context):
        if getattr(update, "edited_message", None) is not None:
            return            # un message modifié ne lance ni ne confirme rien
        user = update.effective_user
        if not tb._is_allowed(user.id):
            logger.warning("/nc refusé à l'utilisateur Telegram %s.", user.id)
            await update.message.reply_text("⛔ Accès non autorisé.")
            return
        # L'heure du message, pas celle du traitement : une confirmation « /nc oui » ne vaut que dans les deux minutes
        # qui suivent l'envoi de sa commande (revue SRV-03)
        date = getattr(update.message, "date", None)
        prive = getattr(update.effective_chat, "type", None) == "private"
        reponse = await commande(" ".join(context.args or []), update.effective_chat.id,
                                 date.timestamp() if date is not None else None, user.id, prive)
        await update.message.reply_text(reponse[:4000])
    return nc
