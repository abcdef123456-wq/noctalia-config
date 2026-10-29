"""nc-energie : la fiche matériel anonyme, les profils par règles (IA_MODE=non), les profils de l'IA (faux nc-ia), l'aperçu,
l'application tout ou rien avec retour arrière, « revenir ». Tout est isolé : HOME et dossiers XDG dans un dossier
temporaire, faux /sys (NC_SYSFS), faux /proc, faux outils (nc-reglages, nc-brightness, powerprofilesctl, hyprctl, iw,
nvidia-smi, nc-gpu-mode, nc-limite-charge) qui notent leurs arguments, et le VRAI assistant root lancé dans son mode d'essai
sur le même faux /sys. Aucun réseau, aucune vraie IA, aucun vrai outil du système."""
import json
import os
import re
import stat
import subprocess
import unittest

from tests.test_energie_root import Base, REPO, ecrire

SCRIPT = REPO / "home/.local/bin/nc-energie"
ROOT = REPO / "system/nc-energie-root"

MONITEURS = json.dumps([{"name": "eDP-1", "availableModes": ["2560x1600@165.00Hz", "2560x1600@60.00Hz", "1920x1080@60.00Hz"]}])
DEFAUTS_REGLAGES = {"FOND_ANIME": "aurore", "HZ_ECO": "max", "HZ_BALANCED_BAT": "max", "HZ_PERFORMANCE": "max",
                    "EFFETS": "tous", "FENETRES_OMBRE": "22", "ECO_AUTO": "0", "ILE_ANIM_BATTERIE": "douces"}


class Energie(Base):
    def setUp(self):
        super().setUp()
        self.machine()
        self.home = self.tmp / "home"
        self.etat = self.tmp / "etat"
        self.etat.mkdir()
        for nom, v in (("lum", "70"), ("profil", "balanced"), ("wifi", "off"), ("limite", "0")):
            (self.etat / nom).write_text(v + "\n")
        for d in ("config", "state", "cache", "data", "run", "tmp"):
            (self.tmp / d).mkdir()
        # Compléments du faux portable : pilote, plateforme, batterie, écran, Bluetooth, /proc
        ecrire(self.sys / "devices/system/cpu/cpufreq/policy0/scaling_driver", "amd-pstate-epp")
        for n in range(4):
            (self.sys / f"devices/system/cpu/cpu{n}").mkdir(parents=True, exist_ok=True)
        ecrire(self.sys / "firmware/acpi/platform_profile_choices", "low-power balanced performance")
        b = self.sys / "class/power_supply/BAT0"
        ecrire(b / "type", "Battery")
        ecrire(b / "energy_full", "45000000")
        ecrire(b / "energy_full_design", "50000000")
        ecrire(b / "serial_number", "SERIE-SECRET-1234")
        ecrire(b / "model_name", "MODELE-SECRET")
        ecrire(self.sys / "class/backlight/amdgpu_bl1/brightness", "50")
        (self.sys / "class/bluetooth/hci0").mkdir(parents=True)
        ecrire(self.sys / "class/net/wlan0/address", "aa:bb:cc:dd:ee:ff")
        ecrire(self.sys / "class/leds/platform::kbd_backlight/brightness", "2")
        ecrire(self.sys / "class/dmi/id/product_serial", "SERIE-SECRET-5678")
        ecrire(self.sys / "class/dmi/id/product_name", "MODELE-PC-SECRET")
        self.proc = self.tmp / "proc"
        ecrire(self.proc / "cpuinfo", "processor\t: 0\nvendor_id\t: AuthenticAMD\nmodel name\t: AMD MODELE-CPU-SECRET")
        self.outils = self.tmp / "outils"
        self.outils.mkdir()
        self.installer_faux_outils()
        self.env = {"PATH": f"{self.outils}:/usr/bin:/bin", "HOME": str(self.home), "XDG_CONFIG_HOME": str(self.tmp / "config"),
                    "XDG_STATE_HOME": str(self.tmp / "state"), "XDG_CACHE_HOME": str(self.tmp / "cache"),
                    "XDG_DATA_HOME": str(self.tmp / "data"), "XDG_RUNTIME_DIR": str(self.tmp / "run"), "TMPDIR": str(self.tmp / "tmp"),
                    "NC_SYSFS": str(self.sys), "NC_PROC": str(self.proc), "NC_ENERGIE_OUTILS": str(self.outils),
                    "NC_ENERGIE_ROOT": str(ROOT), "NC_ENERGIE_RACINE": str(self.sys), "NC_ENERGIE_BIN": str(self.bin),
                    "NC_LIMITE_CHARGE": str(self.outils / "nc-limite-charge"), "NC_IA": str(self.outils / "absent"), "NC_LANGUE": "fr"}

    def outil(self, nom, corps):
        f = self.outils / nom
        f.write_text("#!/bin/sh\n" + corps)
        f.chmod(0o755)

    def installer_faux_outils(self):
        e, j = self.etat, self.journal
        defauts = "\n".join(f"  {k}) echo {v} ;;" for k, v in DEFAUTS_REGLAGES.items())
        self.outil("nc-reglages", f'''echo "nc-reglages $*" >> "{j}"
case "$1" in
  get) if [ -f "{e}/reg_$2" ]; then cat "{e}/reg_$2"; else case "$2" in
{defauts}
  *) echo oui ;; esac; fi ;;
  set) [ -f "{e}/echec_$2" ] && exit 1; echo "$3" > "{e}/reg_$2" ;;
esac
''')
        self.outil("nc-brightness", f'''echo "nc-brightness $*" >> "{j}"
case "$1" in get) cat "{e}/lum" 2>/dev/null || echo 70 ;; set) [ -f "{e}/echec_lum" ] && exit 1; echo "$2" > "{e}/lum" ;; esac
''')
        self.outil("powerprofilesctl", f'''echo "powerprofilesctl $*" >> "{j}"
case "$1" in
  list) printf '* balanced:\\n    Driver: x\\n\\n  power-saver:\\n    Driver: x\\n\\n  performance:\\n    Driver: x\\n' ;;
  get) cat "{e}/profil" 2>/dev/null || echo balanced ;;
  set) echo "$2" > "{e}/profil" ;;
esac
''')
        self.outil("hyprctl", f'''echo "hyprctl $*" >> "{j}"
case "$*" in "monitors all -j") cat <<'FIN'
{MONITEURS}
FIN
;; *) echo '[]' ;; esac
''')
        self.outil("nc-gpu-mode", 'echo hybride\n')
        self.outil("iw", f'''case "$*" in *get*) echo "Power save: $(cat "{e}/wifi" 2>/dev/null || echo off)" ;; esac
''')
        self.outil("nc-limite-charge", f'''echo "nc-limite-charge $*" >> "{j}"
case "$1" in etat) cat "{e}/limite" 2>/dev/null || echo 0 ;; on) echo 1 > "{e}/limite" ;; off) echo 0 > "{e}/limite" ;; esac
''')
        # Le wifi : l'assistant lance « iw dev wlan0 set power_save V » (le faux iw de la base le note) ; on suit son état
        self.outil("iw", f'''case "$*" in
  *get*) echo "Power save: $(cat "{e}/wifi" 2>/dev/null || echo off)" ;;
  *set*) echo "iw $*" >> "{j}"; echo "$5" > "{e}/wifi" ;;
esac
''')
        # Les mêmes faux iw et nvidia-smi pour nc-energie (PATH) et pour l'assistant (NC_ENERGIE_BIN) : un seul état
        nvidia = ('echo "nvidia-smi $*" >> "' + str(j) + '"\ncase "$*" in\n  *power.limit*) echo "50.00, 140.00, 140.00" ;;\n'
                  '  *query*) echo "50.00, 140.00" ;;\nesac\n')
        self.outil("nvidia-smi", nvidia)
        for nom in ("iw", "nvidia-smi"):
            copie = self.bin / nom
            copie.write_text((self.outils / nom).read_text())
            copie.chmod(0o755)

    def nc(self, *args, env=None, entree=None):
        e = dict(self.env)
        e.update(env or {})
        return subprocess.run([str(SCRIPT), *args], env=e, capture_output=True, text=True, timeout=120, input=entree)

    def json(self, *args, env=None, code=0):
        r = self.nc(*args, "--json", env=env)
        self.assertEqual(r.returncode, code, r.stdout + r.stderr)
        return json.loads(r.stdout)

    def reglage(self, cle):
        f = self.etat / f"reg_{cle}"
        return f.read_text().strip() if f.exists() else None

    def journal_lignes(self):
        return self.journal.read_text().splitlines()

    def ia(self, reponse, code=0):
        """Un faux nc-ia : note la question reçue, répond ce texte."""
        q = self.tmp / "question"
        r = self.tmp / "reponse"
        r.write_text(reponse if isinstance(reponse, str) else json.dumps(reponse))
        self.outil("nc-ia", f'echo "nc-ia $*" >> "{self.journal}"\ncat > "{q}"\ncat "{r}"\nexit {code}\n')
        self.env["NC_IA"] = str(self.outils / "nc-ia")
        return q

    def coupe_ia(self):
        d = self.home / ".config/nc"
        d.mkdir(parents=True, exist_ok=True)
        (d / "reglages.conf").write_text('IA_MODE="non"\n')

    def sauver_profils(self, profils):
        d = self.tmp / "config/nc"
        d.mkdir(parents=True, exist_ok=True)
        (d / "profils-energie.json").write_text(json.dumps({"version": 1, "profils": profils}))


class Fiche(Energie):
    def test_fiche_complete_et_anonyme(self):
        f = self.json("fiche")
        self.assertEqual(f["cpu"]["marque"], "AMD")
        self.assertEqual(f["cpu"]["pilote"], "amd-pstate-epp")
        self.assertEqual(f["cpu"]["coeurs"], 4)
        self.assertEqual(f["cpu"]["epp_disponibles"], ["performance", "balance_performance", "balance_power", "power"])
        self.assertTrue(f["cpu"]["boost"])
        self.assertEqual(f["gpu"], {"integree": "AMD", "nvidia": True, "mux": "hybride"})
        self.assertEqual(f["batterie"], {"presente": True, "sante_pct": 90})
        self.assertEqual(f["ecran"], {"resolution": "2560x1600", "hz_max": 165})
        self.assertEqual(f["profils"], {"service": "power-profiles-daemon", "disponibles": ["power-saver", "balanced", "performance"]})
        self.assertEqual(f["plateforme"]["choix"], ["low-power", "balanced", "performance"])
        self.assertEqual(f["clavier"]["max"], 2)
        for c in ("profil", "luminosite", "ecran", "batterie", "bluetooth", "epp", "boost", "freqmax", "platform", "nvidia_pm",
                  "nvidia_pl", "wifi", "usb", "audio", "clavier"):
            self.assertIn(c, f["capacites"])
        self.assertNotIn("limite_charge", f["capacites"], "pas de seuil de charge sur ce faux PC")
        self.assertTrue(f["assistant_root"])
        # Anonyme : ni numéro de série, ni modèle, ni MAC, ni nom de machine, ni chemin du HOME
        brut = json.dumps(f)
        for secret in ("SERIE-SECRET", "MODELE-SECRET", "MODELE-PC", "MODELE-CPU", "aa:bb:cc", "/home", str(self.tmp)):
            self.assertNotIn(secret, brut)
        self.assertNotIn(os.uname().nodename + '"', brut)

    def test_limite_de_charge_detectee(self):
        ecrire(self.sys / "class/power_supply/BAT0/charge_control_end_threshold", "100")
        self.assertIn("limite_charge", self.json("fiche")["capacites"])

    def test_carte_nvidia_endormie_jamais_reveillee(self):
        ecrire(self.sys / "bus/pci/devices/0000:01:00.0/power/runtime_status", "suspended")
        f = self.json("fiche")
        self.assertIn("nvidia_pm", f["capacites"])
        self.assertNotIn("nvidia_pl", f["capacites"])
        self.assertNotIn("nvidia-smi", self.journal.read_text(), "nvidia-smi n'est jamais lancé devant une carte endormie")

    def test_pc_sans_rien(self):
        import shutil
        shutil.rmtree(self.sys)
        for d in self.outils.iterdir():
            if d.name in ("powerprofilesctl", "hyprctl", "nc-brightness", "iw"):
                d.unlink()
        (self.sys / "devices/system/cpu").mkdir(parents=True)
        f = self.json("fiche")
        self.assertEqual(f["capacites"], [])
        self.assertEqual(f["profils"]["service"], "aucun")
        self.assertEqual(f["gpu"], {"integree": "aucune", "nvidia": False, "mux": "sans-objet"})
        self.assertEqual(f["batterie"], {"presente": False, "sante_pct": None})
        self.assertEqual(f["ecran"], {"resolution": None, "hz_max": None})
        r = self.nc("proposer", "--regles")
        self.assertEqual(r.returncode, 1)
        self.assertIn("rien à régler", r.stderr)

    def test_tuned_sans_power_profiles_daemon(self):
        (self.outils / "powerprofilesctl").unlink()
        self.outil("tuned-adm", f'''echo "tuned-adm $*" >> "{self.journal}"
case "$1" in
  list) printf 'Available profiles:\\n- balanced - Balanced\\n- powersave - Power\\n- throughput-performance - Perf\\n' ;;
  active) echo "Current active profile: $(cat "{self.etat}/tuned" 2>/dev/null || echo balanced)" ;;
  profile) echo "$2" > "{self.etat}/tuned" ;;
esac
''')
        f = self.json("fiche")
        self.assertEqual(f["profils"]["service"], "tuned")
        self.assertEqual(f["profils"]["disponibles"], ["power-saver", "balanced", "performance"])
        self.sauver_profils([{"nom": "T", "id": "t", "description": "d", "reglages": {"profil": "power-saver"}, "source": "regles"}])
        self.assertEqual(self.nc("appliquer", "t", "--oui").returncode, 0)
        self.assertEqual((self.etat / "tuned").read_text().strip(), "powersave")
        self.assertEqual(self.nc("revenir").returncode, 0)
        self.assertEqual((self.etat / "tuned").read_text().strip(), "balanced")


class Regles(Energie):
    def test_trois_profils_de_base(self):
        r = self.json("proposer", "--regles")
        self.assertEqual(r["source"], "regles")
        self.assertEqual([p["nom"] for p in r["profils"]], ["Cours / bureautique", "Jeu", "Film sur batterie"])
        self.assertEqual(r["rejets"], [])
        self.assertEqual([p["film_batterie"] for p in r["profils"]], [False, False, True])
        gardes = json.loads((self.tmp / "config/nc/profils-energie.json").read_text())["profils"]
        film = next(p for p in gardes if p["id"] == "film-sur-batterie")
        self.assertEqual(film["reglages"]["HZ_ECO"], "60")
        self.assertEqual(film["reglages"]["profil"], "power-saver")
        self.assertEqual(film["reglages"]["platform_profile"], "low-power")
        self.assertEqual(film["reglages"]["clavier_retro"], "0")
        cours = next(p for p in gardes if p["id"] == "cours-bureautique")
        self.assertEqual(cours["reglages"]["HZ_BALANCED_BAT"], "max", "le cours garde la fréquence maximale")
        self.assertNotIn("HZ_ECO", cours["reglages"])
        self.assertEqual(stat.S_IMODE((self.tmp / "config/nc/profils-energie.json").stat().st_mode), 0o600)
        self.assertEqual(r["profils"][2]["materiel"], True)

    def test_ecran_sans_haute_frequence_pas_de_60hz(self):
        self.outil("hyprctl", 'echo \'[{"name":"eDP-1","availableModes":["1920x1080@60.00Hz"]}]\'\n')
        r = self.json("proposer", "--regles")
        film = next(p for p in r["profils"] if p["nom"] == "Film sur batterie")
        self.assertFalse(film["film_batterie"], "pas de baisse de fréquence à proposer sur un écran de 60 Hz")
        gardes = json.loads((self.tmp / "config/nc/profils-energie.json").read_text())["profils"]
        self.assertNotIn("60", [p["reglages"].get("HZ_ECO") for p in gardes])

    def test_seulement_ce_qui_existe(self):
        import shutil
        shutil.rmtree(self.sys / "bus/pci")
        shutil.rmtree(self.sys / "class/leds")
        shutil.rmtree(self.sys / "module")
        r = self.json("proposer", "--regles")
        self.assertEqual(len(r["profils"]), 3)
        for p in json.loads((self.tmp / "config/nc/profils-energie.json").read_text())["profils"]:
            for cle in ("nvidia_pm", "nvidia_pl", "clavier_retro", "audio_power_save"):
                self.assertNotIn(cle, p["reglages"], f"{cle} n'existe pas sur ce PC")

    def test_ia_mode_non_aucun_appel_a_l_ia(self):
        self.coupe_ia()
        self.ia({"profils": []})
        r = self.json("proposer")
        self.assertEqual(r["source"], "regles")
        self.assertIn("IA coupée", r["raison"])
        self.assertFalse(any(l.startswith("nc-ia") for l in self.journal_lignes()), "nc-ia n'est pas appelé")
        r = self.nc("proposer", "--ia", "--json")
        self.assertEqual(r.returncode, 3, r.stdout)
        self.assertIn("IA_MODE=non", json.loads(r.stdout)["erreur"])
        self.assertFalse(any(l.startswith("nc-ia") for l in self.journal_lignes()))
        self.assertFalse(self.json("liste")["ia"], "l'île cache l'IA")

    def test_aucun_reseau(self):
        for nom in ("nc-energie", "nc-energie-liste"):
            source = (REPO / "home/.local/bin" / nom).read_text(encoding="utf-8")
            for mot in ("urllib", "http.client", "socket", "requests", "curl", "wget"):
                self.assertNotIn(mot, source, f"{nom} : {mot}")
        ia = self.tmp / "ia-jamais"
        self.assertFalse(ia.exists())


PROFIL_IA = {"nom": "Cours / bureautique", "description": "Sobre pour la journée.",
             "reglages": {"profil": "balanced", "cpu_epp": "balance_power", "wifi_power_save": "on", "HALO_BATTERIE": "non"}}


class AvecIA(Energie):
    def test_cle_en_double_dans_la_reponse_de_l_ia_refusee(self):
        """Relecture : avec une clé en double, la dernière gagnerait en silence ; la réponse entière est refusée."""
        self.ia('{"profils": [{"nom": "A", "description": "x", "reglages": {"luminosite": "40", "luminosite": "100"}}]}')
        r = self.nc("proposer", "--ia", "--json")
        self.assertNotEqual(r.returncode, 0, r.stdout)

    def test_profils_de_l_ia_valides(self):
        q = self.ia("Voilà :\n" + json.dumps({"profils": [PROFIL_IA, {
            "nom": "Film sur batterie", "description": "Autonomie.", "film_batterie": True,
            "reglages": {"profil": "power-saver", "HZ_ECO": "60", "luminosite": 40}}]}) + "\nBonne journée")
        r = self.json("proposer", "--ia")
        self.assertEqual(r["source"], "ia")
        self.assertEqual([p["nom"] for p in r["profils"]], ["Cours / bureautique", "Film sur batterie"])
        self.assertEqual(self.journal_lignes()[-1] if self.journal_lignes() else "", self.journal_lignes()[-1])
        self.assertIn("nc-ia demander --usage question -", self.journal_lignes())
        question = q.read_text()
        # La question : la fiche anonyme et la liste blanche de CE PC, rien d'autre
        self.assertIn("LISTE BLANCHE", question)
        self.assertIn('"cpu_epp"', question)
        self.assertIn('"HZ_ECO": ["max", "60"]', question)
        for secret in ("SERIE-SECRET", "MMODELE", "aa:bb:cc", "/home", str(self.tmp), "MODELE-CPU"):
            self.assertNotIn(secret, question)

    def test_profil_refuse_avec_la_raison(self):
        self.ia({"profils": [
            PROFIL_IA,
            {"nom": "Pirate", "description": "x", "reglages": {"render:direct_scanout": "0"}},
            {"nom": "Libre", "description": "x", "reglages": {"cpu_epp": "n'importe"}},
            {"nom": "Commande", "description": "x", "reglages": {"cpu_boost": "off; rm -rf ~"}},
            {"nom": "Sournois", "description": "x", "reglages": {"HZ_ECO": "60"}},
            {"nom": "Mal\nécrit", "description": "x", "reglages": {"profil": "balanced"}}]})
        r = self.json("proposer", "--ia")
        self.assertEqual([p["nom"] for p in r["profils"]], ["Cours / bureautique"])
        raisons = {x["nom"]: x["raison"] for x in r["rejets"]}
        self.assertIn("interdite", raisons["Pirate"])
        self.assertIn("hors liste", raisons["Libre"])
        self.assertIn("Commande", raisons)
        self.assertIn("film sur batterie", raisons["Sournois"])
        self.assertTrue(any("nom" in v for k, v in raisons.items() if k.startswith("Mal")))

    def test_ia_seule_tout_refuse(self):
        self.ia({"profils": [{"nom": "Pirate", "description": "x", "reglages": {"cm_enabled": "0"}}]})
        r = self.nc("proposer", "--ia", "--json")
        self.assertEqual(r.returncode, 1)
        self.assertIn("interdite", json.loads(r.stdout)["erreur"])
        self.assertFalse((self.tmp / "config/nc/profils-energie.json").exists(), "rien de refusé n'est gardé")

    def test_repli_sur_les_regles(self):
        for reponse, code in (("pas du json", 0), ({"profils": [{"nom": "X", "description": "x", "reglages": {"zzz": "1"}}]}, 0), ("{}", 1)):
            self.ia(reponse, code)
            r = self.json("proposer")
            self.assertEqual(r["source"], "regles", reponse)
            self.assertTrue(r["raison"])
            self.assertEqual(len(r["profils"]), 3)

    def test_nc_ia_absent(self):
        r = self.json("proposer")                                   # NC_IA pointe vers un fichier qui n'existe pas
        self.assertEqual(r["source"], "regles")


class Apercu(Energie):
    def setUp(self):
        super().setUp()
        self.sauver_profils([
            {"nom": "Cours / bureautique", "id": "cours-bureautique", "description": "Sobre.", "film_batterie": False, "source": "regles",
             "reglages": {"profil": "power-saver", "cpu_epp": "power", "cpu_boost": "off", "cpu_freq_max": "80", "wifi_power_save": "on",
                          "luminosite": "40", "HALO_BATTERIE": "oui", "FOND_ANIME": "non", "audio_power_save": "off"}},
            {"nom": "Film sur batterie", "id": "film-sur-batterie", "description": "Autonomie.", "film_batterie": True, "source": "ia",
             "reglages": {"profil": "power-saver", "HZ_ECO": "60"}}])

    def test_avant_apres_en_francais(self):
        ap = self.json("apercu", "cours-bureautique")
        c = {x["cle"]: x for x in ap["changements"]}
        self.assertEqual(c["profil"]["avant"], "Équilibré")
        self.assertEqual(c["profil"]["apres"], "Économie")
        self.assertEqual(c["cpu_epp"]["avant"], "balance_performance")
        self.assertEqual(c["cpu_boost"]["avant"] + c["cpu_boost"]["apres"], "activécoupé")
        self.assertEqual(c["cpu_freq_max"]["apres"], "80 %")
        self.assertEqual(c["luminosite"]["avant"], "70 %")
        self.assertEqual(c["FOND_ANIME"]["avant"], "aurore")
        self.assertEqual(ap["inchanges"], 2, "HALO_BATTERIE=oui et l'audio coupé étaient déjà comme voulu")
        self.assertTrue(ap["applicable"])
        self.assertFalse(ap["demande_hz"])
        self.assertEqual([x["niveau"] for x in ap["changements"]], sorted((x["niveau"] for x in ap["changements"]), reverse=True),
                         "le matériel d'abord")
        txt = self.nc("apercu", "Cours / bureautique").stdout
        self.assertIn("Fréquence maximale du processeur (%) : 100 % → 80 %", txt)
        self.assertIn("Profil d'énergie : Équilibré → Économie", txt)
        # Rien n'a bougé
        self.assertEqual(self.lire("devices/system/cpu/cpufreq/policy0/scaling_max_freq"), "4000000")
        self.assertFalse(any("set" in l for l in self.journal_lignes() if l.startswith("nc-reglages")))

    def test_film_demande_la_confirmation_du_60_hz(self):
        ap = self.json("apercu", "film-sur-batterie")
        self.assertTrue(ap["demande_hz"])
        self.assertIn("60 Hz au lieu de 165 Hz", ap["texte_hz"])
        self.assertIn("60 Hz", {x["cle"]: x for x in ap["changements"]}["HZ_ECO"]["apres"])

    def test_profil_inconnu_et_profil_devenu_invalide(self):
        r = self.nc("apercu", "n'existe pas")
        self.assertEqual(r.returncode, 2)
        # Un fichier modifié à la main : 60 Hz hors profil film, option de rendu, ou clé inconnue → refusé à chaque lecture
        self.sauver_profils([
            {"nom": "Faux film", "id": "faux-film", "description": "x", "film_batterie": False, "reglages": {"HZ_ECO": "60"}},
            {"nom": "Rendu", "id": "rendu", "description": "x", "reglages": {"render:new_render_scheduling": "1"}},
            {"nom": "Inconnu", "id": "inconnu", "description": "x", "reglages": {"truc": "1"}}])
        for nom, mot in (("faux-film", "film sur batterie"), ("rendu", "interdite"), ("inconnu", "inconnue")):
            r = self.nc("apercu", nom)
            self.assertEqual(r.returncode, 2, r.stdout)
            self.assertIn(mot, r.stderr)
            r = self.nc("appliquer", nom, "--oui", "--oui-hz")
            self.assertEqual(r.returncode, 2)
        liste = self.json("liste")["profils"]
        self.assertEqual([p["valide"] for p in liste], [False, False, False])
        self.assertEqual(self.journal.read_text().count("set"), 0)

    def lire(self, chemin):
        return (self.sys / chemin).read_text().strip()


class Appliquer(Energie):
    def setUp(self):
        super().setUp()
        self.profil = {"nom": "Cours / bureautique", "id": "cours-bureautique", "description": "Sobre.", "film_batterie": False,
                       "source": "regles",
                       "reglages": {"profil": "power-saver", "cpu_epp": "power", "cpu_boost": "off", "cpu_freq_max": "80",
                                    "platform_profile": "low-power", "nvidia_pm": "auto", "wifi_power_save": "on",
                                    "usb_autosuspend": "on", "audio_power_save": "on", "clavier_retro": "1", "luminosite": "40",
                                    "FOND_ANIME": "non", "limite_charge": "on"}}
        ecrire(self.sys / "class/power_supply/BAT0/charge_control_end_threshold", "100")
        self.sauver_profils([self.profil])

    def etat_materiel(self):
        s = self.lire
        return {"epp": s("devices/system/cpu/cpufreq/policy1/energy_performance_preference"),
                "boost": s("devices/system/cpu/cpufreq/boost"), "freq": s("devices/system/cpu/cpufreq/policy1/scaling_max_freq"),
                "plateforme": s("firmware/acpi/platform_profile"), "nvidia": s("bus/pci/devices/0000:01:00.0/power/control"),
                "usb": s("bus/usb/devices/1-1/power/control"), "audio": s("module/snd_hda_intel/parameters/power_save"),
                "kbd": s("class/leds/platform::kbd_backlight/brightness"),
                "wifi": (self.etat / "wifi").read_text().strip() if (self.etat / "wifi").exists() else None,
                "profil": (self.etat / "profil").read_text().strip() if (self.etat / "profil").exists() else None,
                "lum": (self.etat / "lum").read_text().strip() if (self.etat / "lum").exists() else None,
                "limite": (self.etat / "limite").read_text().strip() if (self.etat / "limite").exists() else "0",
                "anime": self.reglage("FOND_ANIME")}

    def test_confirmation_obligatoire(self):
        avant = self.etat_materiel()
        r = self.nc("appliquer", "cours-bureautique")          # pas de terminal, pas de --oui
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("pas confirmé", r.stderr)
        r = self.nc("appliquer", "cours-bureautique", entree="o\n")    # l'entrée standard n'est pas un terminal : refusé aussi
        self.assertEqual(r.returncode, 2)
        self.assertEqual(self.etat_materiel(), avant)
        self.assertFalse((self.tmp / "state/nc/energie-avant.json").exists())

    def test_appliquer_puis_revenir(self):
        avant = self.etat_materiel()
        r = self.json("appliquer", "Cours / bureautique", "--oui")
        self.assertTrue(r["applique"])
        apres = self.etat_materiel()
        self.assertEqual(apres["epp"], "power")
        self.assertEqual(apres["boost"], "0")
        self.assertEqual(apres["freq"], "3200000")
        self.assertEqual(apres["plateforme"], "low-power")
        self.assertEqual(apres["nvidia"], "auto")
        self.assertEqual(apres["usb"], "auto")
        self.assertEqual(apres["audio"], "1")
        self.assertEqual(apres["kbd"], "1")
        self.assertEqual((apres["wifi"], apres["profil"], apres["lum"], apres["limite"], apres["anime"]), ("on", "power-saver", "40", "1", "non"))
        fichier = self.tmp / "state/nc/energie-avant.json"
        self.assertEqual(stat.S_IMODE(fichier.stat().st_mode), 0o600)
        d = json.loads(fichier.read_text())
        self.assertEqual(d["profil"], "cours-bureautique")
        self.assertEqual(d["avant"]["cpu_epp"], "balance_performance")
        self.assertEqual(d["avant"]["luminosite"], "70")
        self.assertEqual(self.json("liste")["actif"], "cours-bureautique")
        # Les ordres du matériel sont partis un par un, avec des valeurs de la liste
        self.assertIn("iw dev wlan0 set power_save on", self.journal_lignes())
        # Revenir : tout est remis, le fichier d'avant disparaît
        r = self.json("revenir")
        self.assertTrue(r["revenu"])
        retour = self.etat_materiel()
        self.assertEqual({k: v for k, v in retour.items() if k not in ("wifi", "anime")},
                         {k: v for k, v in avant.items() if k not in ("wifi", "anime")})
        self.assertEqual((retour["wifi"], retour["anime"]), ("off", "aurore"))
        self.assertFalse(fichier.exists())
        self.assertIsNone(self.json("liste")["actif"])
        # Un deuxième « revenir » ne fait rien
        self.assertFalse(self.json("revenir")["revenu"])

    def test_echec_au_milieu_tout_est_remis(self):
        avant = self.etat_materiel()
        (self.etat / "echec_FOND_ANIME").write_text("")       # nc-reglages refuse : le niveau 1 vient après le matériel
        r = self.nc("appliquer", "cours-bureautique", "--oui", "--json")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("Tout a été remis comme avant", json.loads(r.stdout)["erreur"])
        retour = self.etat_materiel()
        self.assertEqual({k: v for k, v in retour.items() if k not in ("wifi",)}, {k: v for k, v in avant.items() if k not in ("wifi",)})
        self.assertEqual(retour["wifi"], "off")
        self.assertFalse((self.tmp / "state/nc/energie-avant.json").exists())

    def test_le_profil_logiciel_passe_avant_le_profil_de_la_plateforme(self):
        """Un service (tlp-pd, power-profiles-daemon) réécrit le profil de la plateforme en changeant de profil : celui-ci
        est donc posé APRÈS le profil du service, sinon il serait aussitôt remplacé."""
        j, e = self.journal, self.etat
        pf = self.sys / "firmware/acpi/platform_profile"
        self.outil("powerprofilesctl", f'''echo "powerprofilesctl $*" >> "{j}"
case "$1" in
  list) printf '* balanced:\\n    Driver: x\\n\\n  power-saver:\\n    Driver: x\\n\\n  performance:\\n    Driver: x\\n' ;;
  get) cat "{e}/profil" 2>/dev/null || echo balanced ;;
  set) echo "$2" > "{e}/profil"; echo balanced > "{pf}" ;;
esac
''')
        self.sauver_profils([dict(self.profil, reglages={"profil": "power-saver", "platform_profile": "low-power"})])
        r = self.json("appliquer", "cours-bureautique", "--oui")
        self.assertTrue(r["applique"])
        self.assertEqual(self.lire("firmware/acpi/platform_profile"), "low-power")
        ap = self.json("apercu", "cours-bureautique")
        self.assertEqual([c["cle"] for c in ap["changements"]], [])          # déjà comme voulu : plus rien à changer

    def test_ordre_des_changements_de_l_apercu(self):
        ap = self.json("apercu", "cours-bureautique")
        cles = [c["cle"] for c in ap["changements"]]
        self.assertLess(cles.index("profil"), cles.index("platform_profile"))
        self.assertLess(cles.index("cpu_epp"), cles.index("profil"))             # le matériel sans service d'abord
        self.assertLess(cles.index("platform_profile"), cles.index("luminosite"))

    def test_profil_materiel_reecrit_par_un_service_pas_de_faux_succes(self):
        pf = self.sys / "firmware/acpi/platform_profile"
        (self.bin / "sleep").write_text(f'#!/bin/sh\necho balanced > "{pf}"\n')
        (self.bin / "sleep").chmod(0o755)
        avant = self.etat_materiel()
        r = self.nc("appliquer", "cours-bureautique", "--oui", "--json")
        self.assertEqual(r.returncode, 1, r.stdout)
        msg = json.loads(r.stdout)["erreur"]
        self.assertIn("profil matériel « low-power » demandé", msg)
        self.assertIn("« balanced » relu", msg)
        self.assertIn("Tout a été remis comme avant", msg)
        self.assertEqual({k: v for k, v in self.etat_materiel().items() if k != "wifi"}, {k: v for k, v in avant.items() if k != "wifi"})

    def service_qui_reecrit(self, ecrit, epp=None):
        """Un faux powerprofilesctl dont « set » réécrit le profil de la plateforme (et l'EPP si demandé), comme le fait un
        service de profils en changeant de profil."""
        j, e, pf = self.journal, self.etat, self.sys / "firmware/acpi/platform_profile"
        action = f'echo {ecrit} > "{pf}"'
        if epp:
            for n in (0, 1):
                action += f'; echo {epp} > "{self.sys}/devices/system/cpu/cpufreq/policy{n}/energy_performance_preference"'
        lancement = action
        self.outil("powerprofilesctl", f'''echo "powerprofilesctl $*" >> "{j}"
case "$1" in
  list) printf '* balanced:\\n    Driver: x\\n\\n  power-saver:\\n    Driver: x\\n\\n  performance:\\n    Driver: x\\n' ;;
  get) cat "{e}/profil" 2>/dev/null || echo balanced ;;
  set) echo "$2" > "{e}/profil"; {lancement} ;;
esac
''')

    def test_revenir_remet_le_profil_du_service_avant_celui_de_la_plateforme(self):
        self.sauver_profils([dict(self.profil, reglages={"profil": "power-saver", "platform_profile": "low-power"})])
        self.assertEqual(self.lire("firmware/acpi/platform_profile"), "balanced")
        self.json("appliquer", "cours-bureautique", "--oui")
        self.assertEqual(self.lire("firmware/acpi/platform_profile"), "low-power")
        # Le service réécrit « performance » à chaque changement de profil : au retour, la plateforme passe donc après
        self.service_qui_reecrit("performance")
        r = self.json("revenir")
        self.assertTrue(r["ok"], r)
        self.assertEqual(self.lire("firmware/acpi/platform_profile"), "balanced")
        self.assertEqual((self.etat / "profil").read_text().strip(), "balanced")

    def test_annulation_apres_un_echec_meme_ordre(self):
        self.sauver_profils([dict(self.profil, reglages={"profil": "power-saver", "platform_profile": "low-power", "FOND_ANIME": "non"})])
        self.service_qui_reecrit("performance")
        (self.etat / "echec_FOND_ANIME").write_text("")
        r = self.nc("appliquer", "cours-bureautique", "--oui", "--json")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("Tout a été remis comme avant", json.loads(r.stdout)["erreur"])
        self.assertEqual(self.lire("firmware/acpi/platform_profile"), "balanced")
        self.assertEqual((self.etat / "profil").read_text().strip(), "balanced")

    def test_service_qui_reecrit_en_retard_pendant_la_pose(self):
        """Le service détaché réécrit la plateforme un instant après l'écriture (course) : relu en boucle, jamais un faux
        succès. Le faux « sleep » de l'assistant joue le service : à son 2e appel, il remet « performance »."""
        self.sauver_profils([dict(self.profil, reglages={"profil": "power-saver", "platform_profile": "low-power"})])
        n, pf = self.tmp / "n_sleep", self.sys / "firmware/acpi/platform_profile"
        n.write_text("0")
        (self.bin / "sleep").write_text(f'#!/bin/sh\nn=$(cat "{n}"); n=$((n+1)); echo $n > "{n}"\n'
                                       f'[ "$n" = 2 ] && echo performance > "{pf}"\nexit 0\n')
        (self.bin / "sleep").chmod(0o755)
        r = self.nc("appliquer", "cours-bureautique", "--oui", "--json")
        self.assertEqual(r.returncode, 1, r.stdout)
        msg = json.loads(r.stdout)["erreur"]
        self.assertIn("non confirmé", msg)
        self.assertIn("Tout a été remis comme avant", msg)

    def test_verification_finale_signale_un_reglage_reecrit(self):
        """L'EPP est posé AVANT le profil du service, qui le réécrit : la relecture finale le dit (code 4), pas de succès."""
        self.sauver_profils([dict(self.profil, reglages={"profil": "power-saver", "cpu_epp": "power"})])
        self.service_qui_reecrit("balanced", epp="balance_performance")
        r = self.nc("appliquer", "cours-bureautique", "--oui", "--json")
        self.assertEqual(r.returncode, 4, r.stdout)
        msg = json.loads(r.stdout)["erreur"]
        self.assertIn("réécrit par le service", msg)
        self.assertIn("cpu_epp", msg)
        self.assertTrue((self.tmp / "state/nc/energie-avant.json").exists(), "de quoi revenir")

    def test_controleur_different_message_a_part(self):
        d = self.sys / "class/platform-profile/platform-profile-0"
        ecrire(d / "name", "acer-wmi")
        ecrire(d / "profile", "balanced")
        ecrire(d / "choices", "low-power balanced performance")
        self.sauver_profils([dict(self.profil, reglages={"platform_profile": "low-power"})])
        r = self.nc("appliquer", "cours-bureautique", "--oui", "--json")
        self.assertEqual(r.returncode, 1, r.stdout)
        msg = json.loads(r.stdout)["erreur"]
        self.assertIn("un contrôleur de la plateforme a gardé un autre profil", msg)
        self.assertNotIn("relu « low-power » : un service", msg)

    def test_echec_du_materiel_rien_d_autre_n_a_bouge(self):
        avant = self.etat_materiel()
        # Le noyau ne propose plus « low-power » : l'assistant répond « rien de tel » (3) et tout s'arrête là
        ecrire(self.sys / "firmware/acpi/platform_profile_choices", "balanced performance")
        r = self.nc("appliquer", "cours-bureautique", "--oui", "--json")
        self.assertEqual(r.returncode, 2, "le profil n'est plus valable sur ce PC : refusé avant tout changement")
        self.assertEqual(self.etat_materiel(), avant)

    def test_limite_nvidia_refusee_sautee_le_reste_applique(self):
        """Beaucoup de cartes de portable refusent nvidia-smi -pl (relecture) : ce réglage est sauté et dit, le profil
        n'est pas annulé pour autant."""
        avant = self.etat_materiel()
        self.sauver_profils([dict(self.profil, reglages={"cpu_epp": "power", "nvidia_pl": "1", "luminosite": "40"})])
        ecrire(self.sys / "bus/pci/devices/0000:01:00.0/power/runtime_status", "active")
        self.faux("nvidia-smi", f'case "$*" in *query*) echo "50.00, 140.00, 140.00" ;; *) exit 1 ;; esac\n')
        r = self.nc("appliquer", "cours-bureautique", "--oui", "--json")
        self.assertEqual(r.returncode, 0, r.stdout)
        d = json.loads(r.stdout)
        self.assertTrue(d["sautes"])
        self.assertIn("Sautés", d["message"])
        self.assertNotEqual(self.etat_materiel(), avant)                                # l'EPP est bien passé

    def test_sans_assistant_refus_net(self):
        """Sans l'assistant (PC fixe, ou refusé), la fiche ne propose aucun réglage matériel (relecture) : un profil
        qui en contient est refusé avant tout changement."""
        avant = self.etat_materiel()
        e = {"NC_ENERGIE_ROOT": str(self.tmp / "absent")}
        f = self.json("fiche", env=e)
        self.assertFalse(f["assistant_root"])
        for cap in ("epp", "boost", "freqmax", "platform", "nvidia_pm", "nvidia_pl", "wifi", "usb", "audio", "clavier"):
            self.assertNotIn(cap, f["capacites"])
        r = self.nc("appliquer", "cours-bureautique", "--oui", env=e)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(self.etat_materiel(), avant)

    def test_profil_sans_materiel_marche_sans_assistant(self):
        self.sauver_profils([dict(self.profil, reglages={"profil": "power-saver", "FOND_ANIME": "non"})])
        r = self.json("appliquer", "cours-bureautique", "--oui", env={"NC_ENERGIE_ROOT": str(self.tmp / "absent")})
        self.assertTrue(r["applique"])

    def test_deja_comme_voulu(self):
        self.sauver_profils([dict(self.profil, reglages={"profil": "balanced"})])
        r = self.json("appliquer", "cours-bureautique", "--oui")
        self.assertFalse(r["applique"])
        self.assertFalse((self.tmp / "state/nc/energie-avant.json").exists())

    def test_le_film_demande_une_confirmation_en_clair(self):
        self.sauver_profils([{"nom": "Film sur batterie", "id": "film-sur-batterie", "description": "x", "film_batterie": True,
                              "reglages": {"profil": "power-saver", "HZ_ECO": "60"}}])
        r = self.nc("appliquer", "film-sur-batterie", "--oui", "--json")
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("60 Hz au lieu de 165 Hz", json.loads(r.stdout)["erreur"])
        self.assertIn("--oui-hz", json.loads(r.stdout)["erreur"])
        self.assertIsNone(self.reglage("HZ_ECO"))
        self.assertEqual(self.etat_materiel()["profil"], "balanced")
        r = self.nc("appliquer", "film-sur-batterie", "--oui-hz", "--json")           # --oui-hz seul ne confirme pas le reste
        self.assertEqual(r.returncode, 2)
        r = self.nc("appliquer", "film-sur-batterie", "--oui", "--oui-hz", "--json")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(self.reglage("HZ_ECO"), "60")
        self.assertTrue(self.json("revenir")["revenu"])
        self.assertEqual(self.reglage("HZ_ECO"), "max", "la fréquence d'avant revient")

    def test_deux_profils_de_suite_revenir_rend_l_etat_d_origine(self):
        origine = self.etat_materiel()
        self.json("appliquer", "cours-bureautique", "--oui")
        self.sauver_profils([dict(self.profil, nom="Autre", id="autre", reglages={"cpu_epp": "performance", "luminosite": "90"})])
        self.json("appliquer", "autre", "--oui")
        self.json("revenir")
        retour = self.etat_materiel()
        self.assertEqual(retour["epp"], origine["epp"])
        self.assertEqual(retour["lum"], origine["lum"])

    def test_interdits_jamais_ecrits(self):
        # Même un « avant » trafiqué dans le fichier d'état ne fait jamais écrire autre chose que la liste
        (self.tmp / "state/nc").mkdir(parents=True, exist_ok=True)
        (self.tmp / "state/nc/energie-avant.json").write_text(json.dumps({"avant": {
            "cpu_epp": "../../../etc/passwd", "cpu_boost": "off; id", "render:x": "1", "luminosite": "abc", "FOND_ANIME": "a b;c"}}))
        r = self.nc("revenir", "--json")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.lire("devices/system/cpu/cpufreq/policy0/energy_performance_preference"), "balance_performance")
        self.assertEqual(self.lire("devices/system/cpu/cpufreq/boost"), "1")
        self.assertFalse(any(re.search(r"etc/passwd|; id|a b", l) for l in self.journal_lignes()))

    def lire(self, chemin):
        return (self.sys / chemin).read_text().strip()


if __name__ == "__main__":
    unittest.main()
