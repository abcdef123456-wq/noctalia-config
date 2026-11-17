#!/usr/bin/env python3
"""Connexion à Garmin, lancée par nc-garmin dans un terminal (kitty), avec le Python du venv.
  nc-garmin-login.py DOSSIER_JETONS
L'adresse e-mail est demandée ici (input), le mot de passe par getpass, le code à deux facteurs par input : rien n'est passé en
argument ni en variable d'environnement, rien n'est écrit dans un journal. Seuls les jetons sont gardés, en 0600 dans DOSSIER_JETONS.
Connecteur non officiel : peut cesser de marcher si Garmin change son service."""
import getpass
import os
import stat
import sys


def dire(fr, en):
    fr_ok = (os.environ.get("NC_LANGUE") or os.environ.get("LANG", "")).startswith("fr")
    print(fr if fr_ok else en)


if sys.version_info < (3, 12):
    dire("Python 3.12 minimum requis dans le venv.", "Python 3.12 or newer is required in the venv.")
    sys.exit(2)

# GARMINTOKENS ferait lire ou écrire ailleurs : ignoré, le chemin est toujours explicite et absolu
os.environ.pop("GARMINTOKENS", None)

CATEGORIES = {
    "pas_connecte": ("Identifiants ou code refusés.", "Credentials or code refused."),
    "reseau": ("Garmin est injoignable.", "Garmin cannot be reached."),
    "trop_de_requetes": ("Trop de requêtes : réessaie plus tard.", "Too many requests: try again later."),
    "service_change": ("Le service Garmin a changé : le connecteur doit être mis à jour.", "The Garmin service changed: the connector needs an update."),
}


def categorie(e):
    noms = {c.__name__ for c in type(e).__mro__}
    if noms & {"GarminConnectAuthenticationError", "GarminConnectInvalidFileFormatError", "_MFARequired"}:
        return "pas_connecte"
    if "GarminConnectTooManyRequestsError" in noms:
        return "trop_de_requetes"
    if "GarminConnectConnectionError" in noms or isinstance(e, (OSError, TimeoutError)):
        return "reseau"
    return "service_change"


def main():
    if len(sys.argv) != 2 or not os.path.isabs(sys.argv[1]):
        dire("Usage : nc-garmin login", "Usage: nc-garmin login")
        return 2
    jetons = sys.argv[1]
    try:
        from garminconnect import Garmin
    except Exception:
        dire("Le connecteur n'est pas installé : lance nc-garmin installer.", "The connector is not installed: run nc-garmin installer.")
        return 2
    try:
        dire("Connecteur non officiel : peut cesser de marcher si Garmin change son service.",
             "Unofficial connector: it may stop working if Garmin changes its service.")
        courriel = input("E-mail Garmin : ").strip()
        mdp = getpass.getpass("Mot de passe / Password : ")
        api = Garmin(courriel, mdp, prompt_mfa=lambda: input("Code MFA : ").strip())
        api.login(tokenstore=jetons)
        api.dump(jetons)
        for f in os.listdir(jetons):  # les jetons ne sont lisibles que par toi
            p = os.path.join(jetons, f)
            if stat.S_ISREG(os.lstat(p).st_mode):
                os.chmod(p, 0o600)
    except (KeyboardInterrupt, EOFError):
        dire("Annulé.", "Cancelled.")
        return 1
    except BaseException as e:
        fr, en = CATEGORIES[categorie(e)]  # jamais le texte de la bibliothèque
        dire(fr, en)
        return 1
    dire("Connecté. Tu peux fermer cette fenêtre.", "Connected. You can close this window.")
    return 0


sys.exit(main())
