"""nc-energie-liste : la liste blanche des profils d'énergie poussés et son validateur. Rien n'est lancé, rien n'est lu :
une fiche matériel de test (générique) et des profils JSON. Le profil entier est rejeté, avec la raison, pour une clé
inconnue, une valeur hors liste, une capacité absente, une option de rendu d'Hyprland, un 60 Hz hors profil film marqué,
un texte non imprimable."""
import copy
import importlib.machinery
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "home/.local/bin"


def charger():
    l = importlib.machinery.SourceFileLoader("nc_energie_liste_test", str(BIN / "nc-energie-liste"))
    m = importlib.util.module_from_spec(importlib.util.spec_from_loader("nc_energie_liste_test", l))
    l.exec_module(m)
    return m


L = charger()

# Un portable générique complet : tout est détecté
FICHE = {
    "version": 1,
    "cpu": {"marque": "AMD", "coeurs": 16, "pilote": "amd-pstate-epp",
            "epp_disponibles": ["performance", "balance_performance", "balance_power", "power"], "boost": True},
    "gpu": {"integree": "AMD", "nvidia": True, "mux": "hybride"},
    "batterie": {"presente": True, "sante_pct": 91},
    "ecran": {"resolution": "2560x1600", "hz_max": 165},
    "profils": {"service": "power-profiles-daemon", "disponibles": ["power-saver", "balanced", "performance"]},
    "plateforme": {"choix": ["low-power", "balanced", "performance"]},
    "clavier": {"max": 3},
    "capacites": list(L.CAPACITES),
    "assistant_root": True,
}


def fiche(sans=()):
    f = copy.deepcopy(FICHE)
    for c in sans:
        f["capacites"].remove(c)
    return f


def profil(reglages, **plus):
    p = {"nom": "Cours / bureautique", "description": "Sobre pour la journée.", "reglages": reglages}
    p.update(plus)
    return p


class Valides(unittest.TestCase):
    def test_profil_complet(self):
        p, err = L.valider_profil(profil({"profil": "balanced", "luminosite": 60, "cpu_epp": "balance_power", "cpu_boost": "off",
                                          "cpu_freq_max": "80", "platform_profile": "low-power", "nvidia_pm": "auto", "nvidia_pl": 1,
                                          "wifi_power_save": "on", "usb_autosuspend": "on", "audio_power_save": "on",
                                          "clavier_retro": "1", "limite_charge": "on", "HALO_BATTERIE": "non",
                                          "EFFETS": "aucun", "FENETRES_FLOU": "non", "FENETRES_OMBRE": "0",
                                          "FENETRES_ANIMATIONS": "non", "HZ_ECO": "max", "FOND_ANIME": "non"}), FICHE)
        self.assertIsNone(err)
        self.assertEqual(p["id"], "cours-bureautique")
        self.assertEqual(p["reglages"]["luminosite"], "60", "un entier JSON devient sa chaîne")
        self.assertFalse(p["film_batterie"])

    def test_chaque_valeur_de_chaque_cle_passe(self):
        for cle in L.CLES:
            permises = L.valeurs_permises(cle, FICHE, film=True)
            self.assertTrue(permises, cle)
            for v in permises:
                p, err = L.valider_profil(profil({cle: v}, film_batterie=True), FICHE)
                self.assertIsNone(err, f"{cle}={v}")
                self.assertEqual(p["reglages"], {cle: v})

    def test_niveaux(self):
        self.assertEqual({c for c, d in L.CLES.items() if d[0] == 2},
                         {"cpu_epp", "cpu_boost", "cpu_freq_max", "platform_profile", "nvidia_pm", "nvidia_pl", "wifi_power_save",
                          "usb_autosuspend", "audio_power_save", "clavier_retro", "limite_charge"})
        self.assertEqual(set(L.CLES_REGLAGES) | {"profil", "luminosite"}, {c for c, d in L.CLES.items() if d[0] == 1})


class Rejets(unittest.TestCase):
    def rejet(self, p, f=FICHE, contient=""):
        v, err = L.valider_profil(p, f)
        self.assertIsNone(v, p)
        self.assertIn(contient, err)
        return err

    def test_cle_inconnue(self):
        self.rejet(profil({"profil": "balanced", "pirate": "oui"}), contient="clé inconnue : pirate")

    def test_valeur_hors_liste(self):
        self.rejet(profil({"cpu_freq_max": "70"}), contient="valeur hors liste")
        self.rejet(profil({"luminosite": "5"}), contient="valeur hors liste")
        self.rejet(profil({"luminosite": "150"}), contient="valeur hors liste")
        self.rejet(profil({"cpu_epp": "turbo"}), contient="valeur hors liste")
        self.rejet(profil({"nvidia_pl": "4"}), contient="valeur hors liste")
        self.rejet(profil({"profil": "max-power"}), contient="valeur hors liste")
        self.rejet(profil({"ECO_AUTO": "45"}), contient="valeur hors liste")
        self.rejet(profil({"cpu_boost": "maybe"}), contient="valeur hors liste")

    def test_valeurs_qui_ne_sont_pas_des_chaines(self):
        for v in (True, None, 1.5, ["on"], {"a": 1}):
            self.rejet(profil({"cpu_boost": v}), contient="valeur de la liste attendue")

    def test_commande_chemin_code_dans_les_valeurs(self):
        for v in ("on; rm -rf ~", "$(id)", "`id`", "/etc/passwd", "../x", "on && reboot", "on|cat"):
            self.rejet(profil({"cpu_boost": v}))
        self.rejet(profil({"wifi_power_save": "on\nusb_autosuspend"}))

    def test_capacite_absente(self):
        for cle, val, cap in (("cpu_epp", "power", "epp"), ("cpu_boost", "off", "boost"), ("cpu_freq_max", "80", "freqmax"),
                              ("platform_profile", "low-power", "platform"), ("nvidia_pm", "auto", "nvidia_pm"),
                              ("nvidia_pl", "1", "nvidia_pl"), ("wifi_power_save", "on", "wifi"), ("usb_autosuspend", "on", "usb"),
                              ("audio_power_save", "on", "audio"), ("clavier_retro", "1", "clavier"),
                              ("limite_charge", "on", "limite_charge"), ("luminosite", "40", "luminosite"),
                              ("profil", "balanced", "profil"), ("HALO_BATTERIE", "non", "batterie"),
                              ("ECO_BLUETOOTH", "oui", "bluetooth"), ("HZ_ECO", "max", "ecran"), ("ECO_CLAVIER", "oui", "clavier")):
            self.rejet(profil({cle: val}), f=fiche(sans=[cap]), contient="pas cette capacité")
            # La même valeur passe quand la capacité est là
            self.assertIsNone(L.valider_profil(profil({cle: val}), FICHE)[1], cle)

    def test_valeur_non_proposee_par_ce_pc(self):
        # EPP : le pilote n'en propose que deux ; plateforme : « quiet » n'est pas dans platform_profile_choices
        f = fiche()
        f["cpu"]["epp_disponibles"] = ["performance", "power"]
        self.rejet(profil({"cpu_epp": "balance_power"}), f=f, contient="valeur hors liste")
        self.assertIsNone(L.valider_profil(profil({"cpu_epp": "power"}), f)[1])
        self.rejet(profil({"platform_profile": "quiet"}), contient="valeur hors liste")
        self.assertIsNone(L.valider_profil(profil({"platform_profile": "low-power"}), FICHE)[1])
        f["profils"]["disponibles"] = ["balanced", "power-saver"]       # pas de Performance sur ce PC
        self.rejet(profil({"profil": "performance"}), f=f, contient="valeur hors liste")
        f["clavier"]["max"] = 1
        self.rejet(profil({"clavier_retro": "2"}), f=f, contient="valeur hors liste")
        self.assertIsNone(L.valider_profil(profil({"clavier_retro": "1"}), f)[1])

    def test_options_de_rendu_hyprland_et_interdits(self):
        for cle in ("render:direct_scanout", "render:new_render_scheduling", "new_render_scheduling", "cm_enabled", "cm_auto_hdr",
                    "use_fp16", "render:use_fp16", "xp_mode", "render:xp_mode", "misc:vfr", "vfr", "decoration:blur:enabled",
                    "fan_curve", "ventilateurs", "fan_speed", "pwm1", "courbe_ventilateur", "undervolt", "undervolt_mv", "ryzenadj",
                    "tdp", "tdp_watts", "stapm_limit", "ryzenadj_tctl", "/sys/class/x", "/proc/sys/kernel/x", "../../etc",
                    "hyprctl", "sudo", "commande", "cmd;id", "a|b", "a&b", "$(id)", "`id`"):
            err = self.rejet(profil({"profil": "balanced", cle: "1"}))
            self.assertTrue(err.startswith("clé interdite") or err.startswith("clé inconnue"), err)
        self.assertIn("interdite", self.rejet(profil({"render:direct_scanout": "0"})))
        self.assertIn("interdite", self.rejet(profil({"new_render_scheduling": "true"})))
        self.assertIn("interdite", self.rejet(profil({"cm_enabled": "0"})))

    def test_aucune_cle_de_la_liste_ne_touche_au_rendu_ni_aux_ventilateurs(self):
        for cle in L.CLES:
            self.assertIsNone(L.INTERDITS.search(cle), f"{cle} est interdite par le validateur lui-même")

    def test_60_hz_seulement_dans_le_profil_film_marque(self):
        for cle in ("HZ_ECO", "HZ_BALANCED_BAT"):
            self.rejet(profil({cle: "60"}), contient="seulement dans un profil « film sur batterie »")
            self.rejet(profil({cle: "60"}, film_batterie=False), contient="film sur batterie")
            p, err = L.valider_profil(profil({cle: "60"}, film_batterie=True, nom="Film sur batterie"), FICHE)
            self.assertIsNone(err)
            self.assertTrue(p["film_batterie"])
        # Les autres écrans ne descendent jamais, même marqués film
        for cle in ("HZ_PERFORMANCE", "HZ_BALANCED_AC"):
            self.rejet(profil({cle: "60"}, film_batterie=True), contient="valeur hors liste")
        # Ni 30, ni 120, ni « low » (60 Hz ou la plus basse) : « max » ou 60 (film) seulement
        for v in ("30", "120", "low", "144", "165", "59"):
            self.rejet(profil({"HZ_ECO": v}, film_batterie=True), contient="valeur hors liste")
        # Écran de 60 Hz au plus : rien à gagner, 60 refusé
        f = fiche()
        f["ecran"]["hz_max"] = 60
        self.rejet(profil({"HZ_ECO": "60"}, film_batterie=True), f=f, contient="impossible sur cet écran")
        self.assertIsNone(L.valider_profil(profil({"HZ_ECO": "max"}), f)[1])
        self.rejet(profil({"HZ_ECO": "max"}, film_batterie="oui"), contient="vrai ou faux")

    def test_texte_non_imprimable_ou_hors_bornes(self):
        r = {"profil": "balanced"}
        for nom in ("Cours\nJeu", "Cours\x00", "Cours\x1b[31m", "Cours‮", "", "   ", "x" * 41, "-rf", "<b>Cours</b>", 5, None):
            self.rejet(profil(r, nom=nom), contient="nom")
        for d in ("a\nb", "a\tb", "x" * 241, "", "<script>", None, 3):
            self.rejet(profil(r, description=d), contient="description")
        p, err = L.valider_profil(profil(r, nom="  Jeu é  "), FICHE)
        self.assertIsNone(err)
        self.assertEqual(p["nom"], "Jeu é")

    def test_forme_du_profil(self):
        self.rejet("profil", contient="pas un objet")
        self.rejet(profil({}), contient="non vide")
        self.rejet(profil("balanced"), contient="non vide")
        self.rejet({"nom": "A", "description": "B"}, contient="non vide")
        self.rejet(profil({"profil": "balanced"}, commande="rm -rf ~"), contient="champ inconnu")
        self.rejet(profil({"profil": "balanced"}, script="x"), contient="champ inconnu")
        self.rejet(profil({str(i): "1" for i in range(41)}), contient="plus de 40")
        self.rejet(profil({1: "x"}), contient="clé")

    def test_un_seul_mauvais_reglage_rejette_tout_le_profil(self):
        self.rejet(profil({"profil": "balanced", "luminosite": "50", "cpu_epp": "n'importe quoi"}), contient="cpu_epp")


class Listes(unittest.TestCase):
    def test_liste_blanche_selon_le_pc(self):
        b = L.liste_blanche(FICHE)
        self.assertEqual(b["cpu_epp"], list(L.EPP))
        self.assertEqual(b["platform_profile"], ["low-power", "balanced", "performance"])
        self.assertEqual(b["HZ_ECO"], ["max"])
        self.assertEqual(L.liste_blanche(FICHE, film=True)["HZ_ECO"], ["max", "60"])
        vide = L.liste_blanche({"capacites": [], "profils": {"disponibles": []}})
        self.assertEqual(set(vide), {"EFFETS", "FOND_ANIME", "ILE_METEO", "ILE_PRESSE", "ILE_TELECHARGEMENTS", "FENETRES_FLOU",
                                     "FENETRES_OMBRE", "FENETRES_ANIMATIONS"}, "sans capacité : seulement les réglages sans matériel")

    def test_valider_liste(self):
        bons, rejets = L.valider_liste({"profils": [
            profil({"profil": "balanced"}), profil({"profil": "balanced"}, nom="Cours / bureautique"),
            profil({"render:x": "1"}, nom="Pirate"), profil({"cpu_boost": "off"}, nom="Autre"), "n'importe quoi",
            profil({"profil": "power-saver"}, nom="Troisième"), profil({"profil": "power-saver"}, nom="Quatrième"),
            profil({"profil": "power-saver"}, nom="Cinquième")]}, FICHE, maxi=4)
        self.assertEqual([p["id"] for p in bons], ["cours-bureautique", "autre", "troisieme", "quatrieme"])
        raisons = {r["nom"]: r["raison"] for r in rejets}
        self.assertIn("nom en double", raisons["Cours / bureautique"])
        self.assertIn("interdite", raisons["Pirate"])
        self.assertEqual(L.valider_liste("pas une liste", FICHE)[0], [])

    def test_module_sans_effet_de_bord(self):
        source = (BIN / "nc-energie-liste").read_text(encoding="utf-8")
        for mot in ("subprocess", "os.system", "open(", "Popen", "socket", "urllib", "os.environ", "import os"):
            self.assertNotIn(mot, source, f"le validateur ne lit rien et ne lance rien : {mot}")

    def test_affichage_de_la_liste(self):
        r = subprocess.run([sys.executable, str(BIN / "nc-energie-liste"), "--json"], capture_output=True, text=True, timeout=20)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('"cpu_epp"', r.stdout)


if __name__ == "__main__":
    unittest.main()
