#!/usr/bin/env python3
"""Connecteur Garmin : lancé par le Python du venv de nc-garmin (jamais par le système), une fois par synchronisation.
  nc-garmin-connecteur.py DOSSIER_JETONS AAAA-MM-JJ
Affiche UNE ligne JSON : {"metriques": {...}} ou {"erreur": "<categorie>"} (pas_connecte | reseau | service_change | trop_de_requetes
| python_ancien | installation). Le texte des erreurs de la bibliothèque n'est JAMAIS repris : il peut contenir une adresse, un jeton.
Connecteur non officiel (garminconnect) : peut cesser de marcher si Garmin change son service."""
import json
import math
import os
import re
import sys


def sortie(d, code=0):
    sys.stdout.write(json.dumps(d) + "\n")
    sys.exit(code)


# Avant tout import : Python 3.12 au moins (la bibliothèque l'exige)
if sys.version_info < (3, 12):
    sortie({"erreur": "python_ancien", "message": "Python 3.12 or newer is required in the venv / Python 3.12 minimum requis dans le venv"}, 2)

# Une variable GARMINTOKENS (même du JSON en ligne) ferait lire d'autres jetons : on l'ignore, le chemin est toujours explicite
os.environ.pop("GARMINTOKENS", None)

GRAVES = ("pas_connecte", "trop_de_requetes", "reseau")


def categorie(e):
    noms = {c.__name__ for c in type(e).__mro__}
    if noms & {"GarminConnectAuthenticationError", "GarminConnectInvalidFileFormatError", "_MFARequired"}:
        return "pas_connecte"
    if "GarminConnectTooManyRequestsError" in noms:
        return "trop_de_requetes"
    if "GarminConnectConnectionError" in noms or isinstance(e, (OSError, TimeoutError)):
        return "reseau"
    return "service_change"


def nombre(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else None


def premier(*vals):
    for v in vals:
        if nombre(v) is not None:
            return v
    return None


def serie(v, i=1, n=300):
    """Liste de paires [horodatage, valeur] -> au plus n valeurs finies (None si trop peu pour une courbe)."""
    if not isinstance(v, list):
        return None
    out = [x[i] for x in v[:20000] if isinstance(x, (list, tuple)) and len(x) > i and nombre(x[i]) is not None]
    if len(out) < 2:
        return None
    pas = -(-len(out) // n)
    return out[::pas]


def dico(v):
    return v if isinstance(v, dict) else {}


def collecte(api, jour):
    m = {}

    def essai(nom, f):
        try:
            m.update(f())
        except Exception as e:  # une seule mesure qui manque ne casse pas le reste ; les erreurs graves arrêtent tout
            c = categorie(e)
            if c in GRAVES:
                raise
            m.setdefault("_manque", []).append(nom)

    def corps():
        bb = api.get_body_battery(jour)
        niv = [x[1] for x in dico(bb[0] if isinstance(bb, list) and bb else {}).get("bodyBatteryValuesArray", []) if isinstance(x, list) and len(x) > 1 and nombre(x[1]) is not None]
        return {"body_battery": niv[-1] if niv else None,
                "bb_serie": serie(dico(bb[0] if isinstance(bb, list) and bb else {}).get("bodyBatteryValuesArray"))}

    def coeur():
        h = dico(api.get_heart_rates(jour))
        return {"fc_repos": nombre(h.get("restingHeartRate")), "fc_max": nombre(h.get("maxHeartRate")),
                "fc_serie": serie(h.get("heartRateValues"))}

    def sommeil():
        s = dico(dico(api.get_sleep_data(jour)).get("dailySleepDTO"))
        score = dico(dico(s.get("sleepScores")).get("overall")).get("value")
        return {"sommeil_s": nombre(s.get("sleepTimeSeconds")), "sommeil_score": nombre(score),
                "sommeil_profond_s": nombre(s.get("deepSleepSeconds")), "sommeil_leger_s": nombre(s.get("lightSleepSeconds")),
                "sommeil_paradoxal_s": nombre(s.get("remSleepSeconds")), "sommeil_eveil_s": nombre(s.get("awakeSleepSeconds"))}

    def stress():
        d = dico(api.get_stress_data(jour))
        return {"stress_moyen": nombre(d.get("avgStressLevel")), "stress_serie": serie([x for x in d.get("stressValuesArray", []) if isinstance(x, list) and len(x) > 1 and nombre(x[1]) is not None and x[1] >= 0] if isinstance(d.get("stressValuesArray"), list) else None)}

    def pas():
        s = dico(api.get_stats(jour))
        return {"pas": nombre(s.get("totalSteps")), "pas_objectif": nombre(s.get("dailyStepGoal")),
                "distance_m": nombre(s.get("totalDistanceMeters")), "calories_actives": nombre(s.get("activeKilocalories")), "etages": nombre(s.get("floorsAscended")),
                "minutes_intenses": nombre((nombre(s.get("moderateIntensityMinutes")) or 0)
                                           + (nombre(s.get("vigorousIntensityMinutes")) or 0))}

    def vfc():
        return {"vfc_nuit": nombre(dico(dico(api.get_hrv_data(jour)).get("hrvSummary")).get("lastNightAvg"))}

    def activite():
        a = api.get_activities(0, 1)
        a = dico(a[0]) if isinstance(a, list) and a else {}
        nom = a.get("activityName")
        return {"activite_nom": nom[:60] if isinstance(nom, str) else None,
                "activite_minutes": round(nombre(a.get("duration")) / 60) if nombre(a.get("duration")) is not None else None}

    def oxygene():
        s = dico(api.get_spo2_data(jour))
        r = dico(api.get_respiration_data(jour))
        return {"spo2": nombre(s.get("averageSpO2")), "respiration": nombre(r.get("avgWakingRespirationValue"))}

    def forme():
        mm = api.get_max_metrics(jour)
        mm = dico(mm[0] if isinstance(mm, list) and mm else {})
        tr = api.get_training_readiness(jour)
        tr = dico(tr[0] if isinstance(tr, list) and tr else {})
        return {"vo2max": premier(dico(mm.get("generic")).get("vo2MaxPreciseValue"), dico(mm.get("generic")).get("vo2MaxValue")),
                "readiness": nombre(tr.get("score"))}

    for nom, f in (("body_battery", corps), ("frequence_cardiaque", coeur), ("sommeil", sommeil), ("stress", stress), ("pas", pas),
                   ("vfc", vfc), ("activite", activite), ("oxygene", oxygene), ("forme", forme)):
        essai(nom, f)
    m.pop("_manque", None)
    return m


def main():
    if len(sys.argv) != 3 or not os.path.isabs(sys.argv[1]) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", sys.argv[2]):
        sortie({"erreur": "service_change"}, 2)
    jetons, jour = sys.argv[1], sys.argv[2]
    try:
        from garminconnect import Garmin
    except Exception:
        sortie({"erreur": "installation"}, 2)
    try:
        api = Garmin()
        api.login(tokenstore=jetons)
        sortie({"metriques": collecte(api, jour)})
    except SystemExit:
        raise
    except BaseException as e:
        sortie({"erreur": categorie(e)}, 1)


main()
