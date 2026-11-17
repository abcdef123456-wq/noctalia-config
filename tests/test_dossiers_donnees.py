"""Dossiers de données (XDG_DATA_DIRS) : une petite fonction par langage, et plus aucun /usr/share en dur dans les scripts.

Sur NixOS, /usr/share n'existe presque pas : les données système sont dans XDG_DATA_DIRS. Sans cette variable (ou vide),
le défaut XDG est /usr/local/share puis /usr/share. Chaque recherche passe par la liste, la première trouvée gagne."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "home/.local/bin"
QML = REPO / "home/.config/quickshell"
SH = BIN / "nc-plateforme-root"
REGLE = BIN / "nc-gpu-regle"
PYTHON = ["nc-apps", "nc-ia", "nc-icones", "nc-logiciels", "nc-navigateurs", "nc-reglages", "nc-rtx-veille"]
DEFAUT = ["/usr/local/share", "/usr/share"]
CAS = [   # (XDG_DATA_DIRS ou None = non défini, liste attendue)
    (None, DEFAUT),
    ("", DEFAUT),
    ("/a:/b", ["/a", "/b"]),
    ("/a/:/b//", ["/a", "/b"]),
    ("/a:rel:/b:./c::/a", ["/a", "/b"]),
    ("/a:/b:/a/:/b", ["/a", "/b"]),
    ("rel:autre", DEFAUT),
    (":::", DEFAUT),
    ("/", DEFAUT),
    ("/nix/profile/share:/usr/share", ["/nix/profile/share", "/usr/share"]),
]


def fonction_python(script):
    src = (BIN / script).read_text(encoding="utf-8")
    m = re.search(r"^def dossiers_donnees\(\):\n(?:(?:    .*)?\n)+", src, re.M)
    assert m, f"{script} : pas de dossiers_donnees()"
    ns = {"os": os}
    exec(m.group(0), ns)
    return ns["dossiers_donnees"]


def liste_sh(xdg):
    env = {k: v for k, v in os.environ.items() if k != "XDG_DATA_DIRS"}
    if xdg is not None:
        env["XDG_DATA_DIRS"] = xdg
    r = subprocess.run(["sh", "-c", f'. "{SH}"; nc_dossiers_donnees'], env=env, capture_output=True, text=True, timeout=30)
    return r.stdout.splitlines()


class Fonctions(unittest.TestCase):
    def test_sh(self):
        for xdg, attendu in CAS:
            self.assertEqual(liste_sh(xdg), attendu, repr(xdg))

    def test_python(self):
        for script in PYTHON:
            f = fonction_python(script)
            for xdg, attendu in CAS:
                env = {k: v for k, v in os.environ.items() if k != "XDG_DATA_DIRS"}
                if xdg is not None:
                    env["XDG_DATA_DIRS"] = xdg
                with mock.patch.dict(os.environ, env, clear=True):
                    self.assertEqual(f(), attendu, f"{script} {xdg!r}")


class Sources(unittest.TestCase):
    def test_aucun_usr_share_en_dur(self):
        """Pas de /usr/share en dur hors commentaires et hors des fonctions elles-mêmes."""
        # nc-paquets, nc-diag : hors lot (nc-diag est codé à part, nc-paquets lit le gestionnaire de paquets du système)
        exceptions = {"nc-paquets", "nc-diag"}
        fichiers = [p for p in BIN.iterdir() if p.is_file() and p.name not in exceptions]
        fichiers += [p for p in QML.rglob("*.qml")]
        fautes = []
        for p in fichiers:
            try:
                src = p.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            src = re.sub(r"^def dossiers_donnees\(\):\n(?:(?:    .*)?\n)+", "", src, flags=re.M)
            src = re.sub(r"^nc_dossiers_donnees\(\) \{\n(?:.*\n)*?\}\n", "", src, flags=re.M)
            for n, l in enumerate(src.splitlines(), 1):
                code = re.sub(r"(^|\s)(#|//) .*$|^\s*(#|//).*$", "", l)
                # vk=${vk:-…} : repli quand aucun fichier Vulkan n'est trouvé (rien à chercher)
                # une ligne qui lit déjà XDG_DATA_DIRS avec le défaut XDG est juste
                # nc-navigateurs : les dossiers standard ajoutés EN PLUS de XDG_DATA_DIRS (un XDG_DATA_DIRS partiel ne les cache pas)
                repli = "vk=${vk:-" in code or "if p not in dirs" in code
                if "/usr/share" in code and "XDG_DATA_DIRS" not in code and not repli and not l.lstrip().startswith(("#", "//")):
                    # un message ou un commentaire de fin de ligne n'est pas une recherche
                    if re.search(r"""(T\(|print\(|echo |printf |notify|"""  # noqa
                                 r"""message|text:|ToolTip)""", code):
                        continue
                    fautes.append(f"{p.relative_to(REPO)}:{n}: {l.strip()[:90]}")
        self.maxDiff = None; self.assertEqual(fautes, [])


class Integration(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="nc-donnees-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.xdg = self.tmp / "nix/share"
        self.xdg.mkdir(parents=True)
        self.home = self.tmp / "home"
        (self.home / ".local/bin").mkdir(parents=True)

    def env(self, **e):
        base = {k: v for k, v in os.environ.items() if k not in ("XDG_DATA_DIRS", "NC_EGL_DIR", "NC_PCI_IDS")}
        base.update(HOME=str(self.home), NC_LANGUE="fr", XDG_DATA_DIRS=str(self.xdg))
        base.update(e)
        return base

    def test_sysinfo_pci_ids(self):
        sys_ = self.tmp / "sys"
        (sys_ / "firmware/acpi").mkdir(parents=True)
        d = sys_ / "bus/pci/devices/0000:01:00.0"
        d.mkdir(parents=True)
        for nom, v in (("class", "0x030000"), ("vendor", "0x10de"), ("device", "0x2d59"), ("revision", "0xa1")):
            (d / nom).write_text(v + "\n")
        (self.xdg / "hwdata").mkdir()
        (self.xdg / "hwdata/pci.ids").write_text("10de  NVIDIA Corporation\n\t2d59  GB206M [GeForce RTX 9999 Max-Q / Mobile]\n")
        r = subprocess.run(["bash", str(BIN / "nc-sysinfo"), "gpu"], env=self.env(NC_SYSFS=str(sys_)),
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.stdout.strip(), "RTX 9999", r.stderr)

    def test_term_logo_svg_systeme(self):
        (self.xdg / "pixmaps").mkdir()
        (self.xdg / "pixmaps/zzz-logo.svg").write_text("<svg/>")
        src = (BIN / "nc-term-logo").read_text(encoding="utf-8")
        m = re.search(r"^svg_systeme\(\) \{\n(?:.*\n)*?\}\n", src, re.M)
        code = f'. "{SH}"\nID=zzz\nLOGO=\n{m.group(0)}svg_systeme'
        r = subprocess.run(["bash", "-c", code], env=self.env(), capture_output=True, text=True, timeout=30)
        self.assertEqual(r.stdout.strip(), str(self.xdg / "pixmaps/zzz-logo.svg"), r.stderr)

    def test_gpu_regle_glvnd(self):
        sys_ = self.tmp / "sys"
        for i, v in enumerate(("0x10de", "0x8086")):
            d = sys_ / f"bus/pci/devices/0000:0{i}:00.0"
            d.mkdir(parents=True)
            (d / "class").write_text("0x030000\n")
            (d / "vendor").write_text(v + "\n")
        egl = self.xdg / "glvnd/egl_vendor.d"
        egl.mkdir(parents=True)
        for f in ("10_nvidia.json", "50_mesa.json"):
            (egl / f).write_text("{}")
        code = f'. "{SH}"; . "{REGLE}"; nc_pc_hybride'
        r = subprocess.run(["sh", "-c", code], env=self.env(NC_SYSFS=str(sys_)), capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        # sans le fichier mesa dans le dossier XDG, pas hybride même si le système en a un
        (egl / "50_mesa.json").unlink()
        r = subprocess.run(["sh", "-c", code], env=self.env(NC_SYSFS=str(sys_)), capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 1)
        (egl / "50_mesa.json").write_text("{}")
        # NC_EGL_DIR reste prioritaire : un dossier vide donne « pas hybride »
        vide = self.tmp / "vide"
        vide.mkdir()
        r = subprocess.run(["sh", "-c", code], env=self.env(NC_SYSFS=str(sys_), NC_EGL_DIR=str(vide)),
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 1)

    def test_reglages_xkb(self):
        (self.xdg / "X11/xkb/rules").mkdir(parents=True)
        (self.xdg / "X11/xkb/rules/evdev.lst").write_text("! variant\n  zzvar  us: Une variante\n! option\n  grp  Groupe\n")
        src = (BIN / "nc-reglages").read_text(encoding="utf-8")
        ns = {"os": os}
        for nom in ("dossiers_donnees", "variantes_xkb_connues"):
            m = re.search(rf"^def {nom}\(.*?\):\n(?:(?:    .*)?\n)+", src, re.M)
            exec(m.group(0), ns)
        with mock.patch.dict(os.environ, {"XDG_DATA_DIRS": str(self.xdg)}):
            self.assertTrue(ns["variantes_xkb_connues"]("zzvar"))
            self.assertFalse(ns["variantes_xkb_connues"]("inconnue"))


if __name__ == "__main__":
    unittest.main()
