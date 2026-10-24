"""nc-bt-appel (micro du casque Bluetooth en appel), nc-diag (constat, réparations, conseil MediaTek) et nc-reglages
(BT_APPEL_REPARE, BT_QUALITE_MUSIQUE).

Rien ne touche à la vraie session : HOME, XDG_CONFIG_HOME et PATH temporaires, faux pactl (subscribe qui émet des
événements, list cards/sources/source-outputs en JSON), bluetoothctl, journalctl, notify-send, wpctl et systemctl (chacun
note ses appels dans $FAKE/appels), faux /sys (NC_BT_SYS, NC_DIAG_SYS). Adresse fictive : 00:11:22:33:44:55."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_diag_json import Base as BaseDiag  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "home/.local/bin"
BT = BIN / "nc-bt-appel"
CARTE = "bluez_card.00_11_22_33_44_55"
MAC = "00:11:22:33:44:55"

PACTL = r"""#!/bin/sh
echo "pactl $*" >> "$FAKE/appels"
case "$*" in
  subscribe) cat "$FAKE/evenements" 2>/dev/null | while IFS= read -r l; do
               case "$l" in sleep*) sleep "${l#sleep }" ;; *) echo "$l" ;; esac; done
             sleep "$(cat "$FAKE/duree" 2>/dev/null || echo 3)" ;;
  "-f json list cards") cat "$FAKE/cartes.json" ;;
  "-f json list sources") cat "$FAKE/sources.json" 2>/dev/null || echo '[]' ;;
  "-f json list source-outputs") cat "$FAKE/sorties.json" 2>/dev/null || echo '[]' ;;
esac
exit 0
"""
BLUETOOTHCTL = '#!/bin/sh\necho "bluetoothctl $*" >> "$FAKE/appels"\nexit 0\n'
NOTIFY = '#!/bin/sh\necho "notify-send $*" >> "$FAKE/appels"\nexit 0\n'
JOURNALCTL = r"""#!/bin/sh
echo "journalctl $*" >> "$FAKE/appels"
case "$*" in
  *" -f "*) cat "$FAKE/noyau" 2>/dev/null; sleep "$(cat "$FAKE/duree" 2>/dev/null || echo 3)" ;;
  *) if [ -e "$FAKE/journal_refuse" ]; then echo "Hint: not seeing messages" >&2; exit 0; fi; echo "Linux version" ;;
esac
exit 0
"""
WPCTL = r"""#!/bin/sh
echo "wpctl $*" >> "$FAKE/appels"
[ -e "$FAKE/wpctl_sans_settings" ] && exit 1
exit 0
"""
PROFILS = {"off": {}, "a2dp-sink-sbc": {}, "a2dp-sink-sbc_xq": {}, "a2dp-sink": {}, "a2dp-sink-aac": {},
           "headset-head-unit-cvsd": {}, "headset-head-unit": {}}


def carte(nom=CARTE, actif="headset-head-unit-cvsd", profils=None):
    return {"name": nom, "active_profile": actif, "profiles": PROFILS if profils is None else profils}


class Base(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-bt-appel-")
        self.addCleanup(d.cleanup)
        self.racine = Path(d.name)
        self.home = self.racine / "home"
        (self.home / ".config/nc").mkdir(parents=True)
        (self.home / ".local/bin").mkdir(parents=True)
        (self.home / ".local/bin/nc-bt-appel").symlink_to(BT)
        self.sys = self.racine / "sys"
        (self.sys / "class/bluetooth/hci0").mkdir(parents=True)
        self.fake = self.racine / "fake"
        self.fake.mkdir()
        self.bin = self.racine / "bin"
        self.bin.mkdir()
        for nom, corps in (("pactl", PACTL), ("bluetoothctl", BLUETOOTHCTL), ("notify-send", NOTIFY),
                           ("journalctl", JOURNALCTL), ("wpctl", WPCTL)):
            (self.bin / nom).write_text(corps)
            (self.bin / nom).chmod(0o755)
        (self.fake / "appels").touch()
        self.msbc(True)
        self.cartes([carte()])

    def msbc(self, v):
        d = self.home / ".config/wireplumber/wireplumber.conf.d"
        d.mkdir(parents=True, exist_ok=True)
        (d / "51-nc-airpods.conf").write_text("monitor.bluez.properties = {\n  bluez5.enable-msbc = %s\n}\n" % ("true" if v else "false"))

    def cartes(self, liste):
        (self.fake / "cartes.json").write_text(json.dumps(liste))

    def evenements(self, n, ecart=0.3):
        lignes = []
        for i in range(n):
            lignes += ["sleep %s" % (ecart if i else 0.3), "Event 'change' on card #5"]
        (self.fake / "evenements").write_text("\n".join(lignes) + "\n")

    def appel(self, en_cours=True):
        (self.fake / "sources.json").write_text(json.dumps([{"index": 7, "name": "bluez_input.00_11_22_33_44_55.0"},
                                                            {"index": 8, "name": "bluez_output.00_11_22_33_44_55.1.monitor"}]))
        sorties = [{"index": 3, "source": 7, "properties": {"application.name": "Discord"}}] if en_cours else []
        (self.fake / "sorties.json").write_text(json.dumps(sorties))

    def env(self, **plus):
        env = dict(os.environ, HOME=str(self.home), FAKE=str(self.fake), NC_LANGUE="fr",
                   XDG_CONFIG_HOME=str(self.home / ".config"), PATH=f"{self.bin}:{os.environ['PATH']}",
                   NC_BT_SYS=str(self.sys), NC_BT_PAUSE="0", NC_BT_GARDE="2", NC_BT_CALME="0.1")
        env.update(plus)
        return env

    def service(self, **plus):
        return subprocess.run([sys.executable, str(BT)], env=self.env(**plus), capture_output=True, text=True, timeout=30)

    def appels(self):
        return (self.fake / "appels").read_text().splitlines()

    def n(self, debut):
        return sum(1 for l in self.appels() if l.startswith(debut))


class Service(Base):
    def test_repli_cvsd_une_reconnexion_sans_appel(self):
        self.evenements(1)
        r = self.service()
        self.assertEqual(r.returncode, 1, r.stderr)     # pactl subscribe fini : systemd relance
        a = self.appels()
        self.assertEqual(self.n("bluetoothctl disconnect " + MAC), 1, a)
        self.assertEqual(self.n("bluetoothctl connect " + MAC), 1, a)
        self.assertLess(a.index("bluetoothctl disconnect " + MAC), a.index("bluetoothctl connect " + MAC))
        self.assertEqual(self.n("pactl set-card-profile"), 0, "aucun appel en cours : WirePlumber décide")
        self.assertEqual(self.n("notify-send"), 0)

    def test_appel_en_cours_remet_le_mode_appel_apres_la_reconnexion(self):
        self.appel(True)
        self.evenements(1)
        self.service()
        a = self.appels()
        self.assertIn(f"pactl set-card-profile {CARTE} headset-head-unit", a)
        self.assertLess(a.index("bluetoothctl connect " + MAC), a.index(f"pactl set-card-profile {CARTE} headset-head-unit"))

    def test_un_vumetre_n_est_pas_un_appel(self):
        (self.fake / "sources.json").write_text(json.dumps([{"index": 7, "name": "bluez_input.00_11_22_33_44_55.0"}]))
        (self.fake / "sorties.json").write_text(json.dumps([{"index": 3, "source": 7, "properties": {"media.name": "Peak detect"}}]))
        self.evenements(1)
        self.service()
        self.assertEqual(self.n("bluetoothctl connect"), 1)
        self.assertEqual(self.n("pactl set-card-profile"), 0)

    def test_deux_tentatives_par_deux_minutes_puis_une_notification(self):
        self.evenements(6)
        self.service()
        self.assertEqual(self.n("bluetoothctl disconnect"), 2, self.appels())
        self.assertEqual(self.n("notify-send"), 1, self.appels())
        self.assertIn("qualité réduite", " ".join(l for l in self.appels() if l.startswith("notify-send")))

    def test_fenetre_expiree_nouvelle_tentative(self):
        self.evenements(6, ecart=0.6)
        self.service(NC_BT_FENETRE="0.5")
        self.assertGreaterEqual(self.n("bluetoothctl disconnect"), 3, self.appels())

    def test_profil_normal_rien(self):
        self.cartes([carte(actif="a2dp-sink")])
        self.evenements(2)
        self.service()
        self.assertEqual(self.n("bluetoothctl"), 0)

    def test_cvsd_sans_msbc_propose_rien(self):
        self.cartes([carte(profils={"a2dp-sink": {}, "headset-head-unit-cvsd": {}})])
        self.evenements(2)
        self.service()
        self.assertEqual(self.n("bluetoothctl"), 0)

    def test_msbc_faux_ou_absent_aucune_action_aucun_pactl(self):
        self.msbc(False)
        self.evenements(2)
        r = self.service()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.appels(), [], "ni pactl, ni bluetoothctl : sortie immédiate")
        (self.home / ".config/wireplumber/wireplumber.conf.d/51-nc-airpods.conf").unlink()
        r = self.service()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.appels(), [])

    def test_sans_adaptateur_rien(self):
        (self.sys / "class/bluetooth/hci0").rmdir()
        self.evenements(2)
        r = self.service()
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.appels(), [])

    def test_reglage_non_rien(self):
        (self.home / ".config/nc/reglages.conf").write_text('BT_APPEL_REPARE="non"\n')
        self.evenements(2)
        r = self.service()
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.appels(), [])

    def test_mac_et_carte_invalides_ignores(self):
        for nom in ("bluez_card.00_11_22_33_44_5", "bluez_card.00_11_22_33_44_5g", "bluez_card.00_11_22_33_44_55;id",
                    "bluez_card.00_11_22_33_44_5a", "alsa_card.pci-0000", "bluez_card.00:11:22:33:44:55"):
            self.cartes([carte(nom=nom)])
            self.evenements(1)
            self.service()
            self.assertEqual(self.n("bluetoothctl"), 0, nom)

    def test_rafale_sco_en_mode_appel_une_reconnexion(self):
        self.cartes([carte(actif="headset-head-unit")])
        (self.fake / "noyau").write_text("Bluetooth: hci0: corrupted SCO packet\n" * 5)
        self.appel(True)
        self.service()
        self.assertEqual(self.n("bluetoothctl disconnect " + MAC), 1, self.appels())
        self.assertIn(f"pactl set-card-profile {CARTE} headset-head-unit", self.appels())

    def test_quatre_sco_ne_suffisent_pas(self):
        self.cartes([carte(actif="headset-head-unit")])
        (self.fake / "noyau").write_text("Bluetooth: hci0: corrupted SCO packet\n" * 4)
        self.service()
        self.assertEqual(self.n("bluetoothctl"), 0)

    def test_sco_hors_mode_appel_rien(self):
        self.cartes([carte(actif="a2dp-sink")])
        (self.fake / "noyau").write_text("Bluetooth: hci0: corrupted SCO packet\n" * 6)
        self.service()
        self.assertEqual(self.n("bluetoothctl"), 0)

    def test_journal_illisible_seul_le_repli_sans_bruit(self):
        (self.fake / "journal_refuse").touch()
        self.cartes([carte(actif="headset-head-unit")])
        (self.fake / "noyau").write_text("Bluetooth: hci0: corrupted SCO packet\n" * 6)
        r = self.service()
        self.assertEqual(self.n("bluetoothctl"), 0)
        self.assertEqual(self.n("journalctl -k -f"), 0, "le suivi du noyau n'est même pas lancé")
        self.assertEqual(r.stderr, "")
        # le déclencheur (a) marche toujours
        self.cartes([carte()])
        self.evenements(1)
        self.service()
        self.assertEqual(self.n("bluetoothctl disconnect"), 1)

    def test_reparer_carte_invalide_code_2(self):
        r = subprocess.run([sys.executable, str(BT), "reparer", "bluez_card.zz"], env=self.env(), capture_output=True, text=True, timeout=20)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(self.appels(), [])


class Diag(BaseDiag):
    def setUp(self):
        super().setUp()
        (self.home / ".local/bin/nc-bt-appel").symlink_to(BT)
        self.sys = self.racine / "sys"
        (self.sys / "class/bluetooth/hci0").mkdir(parents=True)
        for nom, corps in (("pactl", PACTL), ("bluetoothctl", BLUETOOTHCTL)):
            (self.bin / nom).write_text(corps)
            (self.bin / nom).chmod(0o755)
        self.cartes([carte()])

    def cartes(self, liste):
        (self.fake / "cartes.json").write_text(json.dumps(liste))

    def appel(self, en_cours):
        (self.fake / "sources.json").write_text(json.dumps([{"index": 7, "name": "bluez_input.00_11_22_33_44_55.0"}]))
        (self.fake / "sorties.json").write_text(json.dumps(
            [{"index": 3, "source": 7, "properties": {"application.name": "Discord"}}] if en_cours else []))

    def diag(self, *args, **plus):
        plus = {"NC_DIAG_SYS": str(self.sys), "NC_BT_PAUSE": "0", "NC_BT_GARDE": "2", "NC_BT_SYS": str(self.sys),
                "XDG_CONFIG_HOME": str(self.home / ".config"), **plus}
        return super().diag(*args, **plus)

    def constat(self, cle):
        return next((c for c in self.json()["constats"] if c["cle"] == cle), None)

    def test_constat_et_deux_reparations(self):
        self.appel(False)
        c = self.constat("bt_cvsd:" + CARTE)
        self.assertIsNotNone(c)
        self.assertEqual(c["niveau"], "avert")
        self.assertIn("son réduit", c["texte"])
        self.assertEqual(c["reparations"], ["bt_reconnecter:" + CARTE, "bt_musique:" + CARTE])
        rep = self.json()["reparations"]
        self.assertIn("bt_musique:" + CARTE, rep)
        self.assertFalse(rep["bt_musique:" + CARTE]["danger"])

    def test_pas_de_musique_si_une_appli_utilise_le_micro(self):
        self.appel(True)
        self.assertEqual(self.constat("bt_cvsd:" + CARTE)["reparations"], ["bt_reconnecter:" + CARTE])

    def test_pas_de_constat_hors_cvsd_ou_sans_msbc_ou_sans_adaptateur(self):
        self.cartes([carte(actif="headset-head-unit")])
        self.assertIsNone(self.constat("bt_cvsd:" + CARTE))
        self.cartes([carte(profils={"a2dp-sink": {}, "headset-head-unit-cvsd": {}})])
        self.assertIsNone(self.constat("bt_cvsd:" + CARTE))
        self.cartes([carte()])
        (self.sys / "class/bluetooth/hci0").rmdir()
        self.assertIsNone(self.constat("bt_cvsd:" + CARTE))

    def test_reparer_reconnecter(self):
        self.appel(False)
        r = self.diag("reparer", "bt_reconnecter:" + CARTE, "--json")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertEqual(json.loads(r.stdout)["resultat"], "fait")
        a = self.journal()
        self.assertIn("bluetoothctl disconnect " + MAC, a)
        self.assertIn("bluetoothctl connect " + MAC, a)

    def test_reparer_reconnecter_deja_si_plus_en_cvsd(self):
        self.cartes([carte(actif="a2dp-sink")])
        r = self.diag("reparer", "bt_reconnecter:" + CARTE, "--json")
        self.assertEqual(json.loads(r.stdout)["resultat"], "deja")
        self.assertFalse([l for l in self.journal() if l.startswith("bluetoothctl")])

    def test_reparer_musique_prend_le_meilleur_a2dp(self):
        self.appel(False)
        r = self.diag("reparer", "bt_musique:" + CARTE, "--json")
        self.assertEqual(json.loads(r.stdout)["resultat"], "fait", r.stdout + r.stderr)
        self.assertIn(f"pactl set-card-profile {CARTE} a2dp-sink-aac", self.journal())
        self.appels.write_text("")
        self.cartes([carte(profils={"a2dp-sink": {}, "a2dp-sink-sbc_xq": {}, "a2dp-sink-sbc": {}, "headset-head-unit": {},
                                    "headset-head-unit-cvsd": {}})])
        self.diag("reparer", "bt_musique:" + CARTE, "--json")
        self.assertIn(f"pactl set-card-profile {CARTE} a2dp-sink-sbc_xq", self.journal())

    def test_reparer_musique_refuse_pendant_un_appel(self):
        self.appel(True)
        r = self.diag("reparer", "bt_musique:" + CARTE, "--json")
        self.assertEqual(json.loads(r.stdout)["resultat"], "echec")
        self.assertFalse([l for l in self.journal() if "set-card-profile" in l])

    def test_ids_invalides_refuses_code_2_rien_lance(self):
        for ident in ("bt_reconnecter:bluez_card.00_11_22_33_44_5", "bt_musique:bluez_card.00_11_22_33_44_5a",
                      "bt_musique:bluez_card.00_11_22_33_44_55;id", "bt_reconnecter:bluez_card.00_11_22_33_44_55 x",
                      "bt_reconnecter:$(id)", "bt_autre:" + CARTE, "bt_musique:" + CARTE + "\n", "bt_musique:",
                      "bt_musique:bluez_card.00:11:22:33:44:55"):
            r = self.diag("reparer", ident)
            self.assertEqual(r.returncode, 2, ident)
        self.assertFalse([l for l in self.journal() if l.startswith(("bluetoothctl", "pactl"))])

    def mediatek(self, vendeur="0e8d", auto="Y", btusb=True):
        d = self.sys / "bus/usb/devices/1-3"
        d.mkdir(parents=True, exist_ok=True)
        (d / "idVendor").write_text(vendeur + "\n")
        if btusb:
            p = self.sys / "module/btusb/parameters"
            p.mkdir(parents=True, exist_ok=True)
            (p / "enable_autosuspend").write_text(auto + "\n")

    def test_conseil_mediatek_seulement_avec_mediatek_et_autosuspend(self):
        self.assertIsNone(self.constat("bt_mediatek_autosuspend"))
        self.mediatek()
        c = self.constat("bt_mediatek_autosuspend")
        self.assertIsNotNone(c)
        self.assertIn("enable_autosuspend=n", c["quoi"])
        self.assertEqual(c["reparations"], [], "un conseil : jamais appliqué")
        self.mediatek(auto="N")
        self.assertIsNone(self.constat("bt_mediatek_autosuspend"))
        self.mediatek(vendeur="8087")
        self.assertIsNone(self.constat("bt_mediatek_autosuspend"))


class Reglages(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-bt-reglages-")
        self.addCleanup(d.cleanup)
        self.racine = Path(d.name)
        self.home = self.racine / "home"
        (self.home / ".config/nc").mkdir(parents=True)
        (self.home / ".local/bin").mkdir(parents=True)
        (self.home / ".local/bin/nc-reglages").symlink_to(BIN / "nc-reglages")
        self.fake = self.racine / "fake"
        self.fake.mkdir()
        self.bin = self.racine / "bin"
        self.bin.mkdir()
        (self.fake / "appels").touch()
        for nom, corps in (("wpctl", WPCTL), ("systemctl", '#!/bin/sh\necho "systemctl $*" >> "$FAKE/appels"\n'),
                           ("hyprctl", "#!/bin/sh\nexit 0\n"), ("notify-send", NOTIFY)):
            (self.bin / nom).write_text(corps)
            (self.bin / nom).chmod(0o755)

    def lancer(self, *args):
        env = dict(os.environ, HOME=str(self.home), FAKE=str(self.fake), NC_LANGUE="fr", PATH=f"{self.bin}:{os.environ['PATH']}",
                   XDG_CONFIG_HOME=str(self.home / ".config"))
        return subprocess.run([sys.executable, str(BIN / "nc-reglages"), *args], env=env, capture_output=True, text=True, timeout=60)

    def appels(self):
        return (self.fake / "appels").read_text().splitlines()

    def conf(self):
        return self.home / ".config/wireplumber/wireplumber.conf.d/52-nc-bt-autoswitch.conf"

    def test_defauts(self):
        self.assertEqual(self.lancer("get", "BT_APPEL_REPARE").stdout.strip(), "oui")
        self.assertEqual(self.lancer("get", "BT_QUALITE_MUSIQUE").stdout.strip(), "oui")

    def test_appel_repare_active_ou_coupe_le_service(self):
        r = self.lancer("set", "BT_APPEL_REPARE", "non")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex((self.home / ".config/nc/reglages.conf").read_text(), r'BT_APPEL_REPARE="?non"?')
        self.assertIn("systemctl --user enable nc-bt-appel.service", self.appels())
        self.assertIn("systemctl --user restart nc-bt-appel.service", self.appels())

    def test_qualite_musique_par_wpctl(self):
        self.lancer("set", "BT_QUALITE_MUSIQUE", "non")
        self.assertIn("wpctl settings --save bluetooth.autoswitch-to-headset-profile false", self.appels())
        self.assertFalse(self.conf().exists())
        self.lancer("reset", "BT_QUALITE_MUSIQUE")
        self.assertIn("wpctl settings --save bluetooth.autoswitch-to-headset-profile true", self.appels())

    def test_qualite_musique_repli_conf_d_sans_wpctl_settings(self):
        (self.fake / "wpctl_sans_settings").touch()
        self.lancer("set", "BT_QUALITE_MUSIQUE", "non")
        self.assertIn("bluetooth.autoswitch-to-headset-profile = false", self.conf().read_text())
        self.lancer("reset", "BT_QUALITE_MUSIQUE")
        self.assertFalse(self.conf().exists())


if __name__ == "__main__":
    unittest.main()
