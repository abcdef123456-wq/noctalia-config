"""install.sh en mode UI (NC_UI=1) : JSON lignes sur le fd 3, réponses sur une FIFO, sudo -A, --graphique.

Vrai install.sh, faux outils dans le PATH (modèle de test_install_nixos.py), HOME et XDG_* isolés.
Un « répondeur » lit la sortie JSON et écrit les réponses dans la FIFO. Aucun vrai sudo.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_install_nixos import BASE, OUTILS, REPO, outil  # noqa: E402


class Banc:
    def __init__(self, famille="arch", sudo=True):
        self.d = Path(tempfile.mkdtemp(prefix="nc-ui-"))
        self.home = self.d / "home"
        self.bin = self.d / "bin"
        self.journal = self.d / "appels"
        self.sortie = self.d / "sortie.jsonl"
        self.entree = self.d / "entree"
        self.home.mkdir()
        self.bin.mkdir()
        (self.d / "osr").write_text(f'ID={famille}\nNAME={famille}\nVERSION_ID="25.11"\n')
        for n in OUTILS:
            outil(self.bin, n, 'case "$1" in --version) echo "Hyprland v0.55.1"; echo "Tag: v0.55.1";; esac')
        if sudo:  # faux sudo : note ses arguments et SUDO_ASKPASS, ne fait rien
            outil(self.bin, "sudo", f'echo "sudo $* ASKPASS=${{SUDO_ASKPASS:-}}" >> "{self.journal}"; exit 0')
        for n in ["curl", "wget", "chsh", "dnf", "apt-get", "pacman", "zypper"]:
            outil(self.bin, n, f'echo "{n} $*" >> "{self.journal}"; exit 1')
        outil(self.bin, "git", 'for a in "$@"; do case "$a" in rev-parse) echo 0123456789abcdef0123456789abcdef01234567; exit 0;; '
                               'log|diff|ls-files|status|show) exit 0;; esac; done; '
                               f'echo "git $*" >> "{self.journal}"; exit 1')
        outil(self.bin, "fc-match", 'echo "MaterialSymbolsRounded.ttf: Material Symbols Rounded"')
        for n in BASE:
            w = shutil.which(n)
            if w and not (self.bin / n).exists():
                (self.bin / n).symlink_to(w)

    def env(self, ui=True, entree="fifo"):
        e = {"HOME": str(self.home), "PATH": str(self.bin), "TMPDIR": str(self.d), "LANG": "C",
             "XDG_CONFIG_HOME": str(self.home / ".config"), "XDG_DATA_HOME": str(self.home / ".local/share"),
             "XDG_STATE_HOME": str(self.home / ".local/state"), "XDG_CACHE_HOME": str(self.home / ".cache"),
             "NC_INSTALLER_TEST": "1", "NC_OS_RELEASE": str(self.d / "osr"), "NC_LANGUE": "fr",
             "NC_UI_SORTIE": str(self.sortie), "NC_UI_ATTENTE": "1"}
        if ui:
            e["NC_UI"] = "1"
        if entree == "fifo":
            os.mkfifo(self.entree)
            e["NC_UI_ENTREE"] = str(self.entree)
        elif entree == "absente":
            e["NC_UI_ENTREE"] = str(self.d / "nexiste-pas")
        return e

    def lance(self, *args, repond=None, ui=True, entree="fifo", env_plus=None):
        """repond(evenement) -> texte de réponse ou None. Retourne (code, stdout, evenements)."""
        e = self.env(ui, entree)
        e.update(env_plus or {})
        p = subprocess.Popen(["bash", str(REPO / "install.sh"), *args], stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True, env=e, text=True)
        stop = threading.Event()
        t = None
        if repond and entree == "fifo":
            def boucle():
                fd = os.open(self.entree, os.O_RDWR)
                vu = 0
                while not stop.is_set():
                    lignes = self.sortie.read_text().splitlines() if self.sortie.exists() else []
                    for l in lignes[vu:]:
                        try:
                            ev = json.loads(l)
                        except ValueError:
                            continue
                        if ev.get("type") in ("question", "choix", "saisie"):
                            r = repond(ev)
                            if r is not None:
                                os.write(fd, r.encode() + b"\n")
                    vu = len(lignes)
                    time.sleep(0.05)
                os.close(fd)
            t = threading.Thread(target=boucle, daemon=True)
            t.start()
        try:
            sortie, _ = p.communicate(timeout=60)
        except subprocess.TimeoutExpired:
            os.kill(p.pid, 9)
            sortie, _ = p.communicate()
        stop.set()
        if t:
            t.join(2)
        return p.returncode, sortie, self.evenements()

    def evenements(self):
        if not self.sortie.exists():
            return []
        return [json.loads(l) for l in self.sortie.read_text().splitlines() if l.strip()]

    def appels(self):
        return self.journal.read_text() if self.journal.exists() else ""

    def fin(self):
        shutil.rmtree(self.d, ignore_errors=True)


def echappe(texte):
    """Appelle la vraie fonction nc_json_echappe de install.sh (extraite, pas copiée)."""
    src = (REPO / "install.sh").read_text()
    debut = src.index("nc_json_echappe() {")
    fin = src.index("\nnc_ui_ev()", debut)
    r = subprocess.run(["bash", "-c", src[debut:fin] + '\nnc_json_echappe "$1"; printf %s "$NC_J"', "x", texte],
                       capture_output=True, text=True)
    return r.stdout


class UiTest(unittest.TestCase):
    def banc(self, **kw):
        b = Banc(**kw)
        self.addCleanup(b.fin)
        return b

    def oui(self, ev):
        return f"{ev['id']} o" if ev["type"] == "question" else None

    def test_chaque_ligne_est_du_json_avec_etape_ok_question_fin(self):
        b = self.banc()
        code, sortie, evs = b.lance("--files-only", repond=lambda ev: f"{ev['id']} o" if ev["type"] == "question" else None)
        self.assertEqual(code, 0, sortie)
        types = {e["type"] for e in evs}
        for t in ("etape", "ok", "fin"):
            self.assertIn(t, types, sortie)
        self.assertEqual(evs[-1], {"type": "fin", "code": 0})
        self.assertEqual(sum(e["type"] == "fin" for e in evs), 1)
        for l in b.sortie.read_text().splitlines():
            json.loads(l)

    def test_stdout_sans_json(self):
        b = self.banc()
        code, sortie, evs = b.lance("--files-only", repond=self.oui)
        self.assertEqual(code, 0, sortie)
        self.assertNotIn('{"type"', sortie)

    def test_question_reponses(self):
        b = self.banc()
        src = (REPO / "install.sh").read_text()
        d = src.index("nc_json_echappe() {")
        f = src.index("\nsay()", d)
        a = src.index("ask() {")
        z = src.index("\nANNULE=10", a)
        fonctions = src[d:f] + "\nsans_tty() { true; }\n" + src[a:z]
        cas = [("o", True), ("n", False), ("oui", False), ("o sans id", False), ("", False)]
        for rep, attendu in cas:
            with self.subTest(rep):
                e = b.env(entree=None)
                e["NC_UI_ENTREE"] = str(b.entree)
                b.entree.unlink(missing_ok=True)
                os.mkfifo(b.entree)
                fd = os.open(b.entree, os.O_RDWR)
                texte = "o" if rep == "o sans id" else f"1 {rep}"
                os.write(fd, (texte + "\n").encode())
                r = subprocess.run(["bash", "-c", f"NC_UI=1; NC_UI_ID=0; NC_UI_IN=1; OUI=0; t(){{ echo \"$1\"; }}\n"
                                    'exec 3>>"$NC_UI_SORTIE"; exec 4<>"$NC_UI_ENTREE"\n' + fonctions +
                                    '\nif ask "Q ?" n; then echo OUI; else echo NON; fi'],
                                   env=e, capture_output=True, text=True, timeout=10)
                os.close(fd)
                self.assertEqual(r.stdout.strip(), "OUI" if attendu else "NON", r.stderr)

    def test_question_mauvais_id_vaut_non(self):
        b = self.banc()
        src = (REPO / "install.sh").read_text()
        d = src.index("nc_json_echappe() {")
        f = src.index("\nsay()", d)
        a = src.index("ask() {")
        z = src.index("\nANNULE=10", a)
        e = b.env(entree=None)
        e["NC_UI_ENTREE"] = str(b.entree)
        os.mkfifo(b.entree)
        fd = os.open(b.entree, os.O_RDWR)
        os.write(fd, b"7 o\n")
        r = subprocess.run(["bash", "-c", "NC_UI=1; NC_UI_ID=0; NC_UI_IN=1; OUI=0\n"
                            'exec 3>>"$NC_UI_SORTIE"; exec 4<>"$NC_UI_ENTREE"\n' + src[d:f] + "\nsans_tty() { true; }\n" + src[a:z] +
                            '\nif ask "Q ?" n; then echo OUI; else echo NON; fi'],
                           env={**e, "NC_UI": "1"}, capture_output=True, text=True, timeout=10)
        os.close(fd)
        self.assertEqual(r.stdout.strip(), "NON", r.stderr)

    def test_entree_absente_ou_sans_ecrivain_ne_bloque_pas(self):
        for mode in ("absente", "fifo"):
            with self.subTest(mode):
                b = self.banc()
                t0 = time.monotonic()
                code, sortie, evs = b.lance("--files-only", entree=mode)
                self.assertEqual(code, 10, sortie)  # « On y va ? » sans réponse vaut non
                self.assertLess(time.monotonic() - t0, 50)
                self.assertTrue(any(e["type"] == "question" for e in evs))
                self.assertEqual(evs[-1]["type"], "fin")

    def test_choix_numero_valide_sinon_defaut(self):
        b = self.banc()
        src = (REPO / "install.sh").read_text()
        d = src.index("nc_json_echappe() {")
        f = src.index("\nsay()", d)
        a = src.index("choisir() {")
        z = src.index("\n# Longue étape", a)
        fonctions = src[d:f] + "\nsans_tty() { true; }\n" + src[a:z]
        for rep, attendu in [("2", "2"), ("3", "3"), ("9", "1"), ("0", "1"), ("abc", "1")]:
            with self.subTest(rep):
                e = b.env(entree=None)
                e["NC_UI_ENTREE"] = str(b.entree)
                b.entree.unlink(missing_ok=True)
                os.mkfifo(b.entree)
                fd = os.open(b.entree, os.O_RDWR)
                os.write(fd, f"1 {rep}\n".encode())
                r = subprocess.run(["bash", "-c", "NC_UI=1; NC_UI_ID=0; NC_UI_IN=1; t(){ echo \"$1\"; }\n"
                                    'exec 3>>"$NC_UI_SORTIE"; exec 4<>"$NC_UI_ENTREE"\n' + fonctions +
                                    '\nchoisir "Q ?" "a\\"b" "B" "C"; echo "$CHOIX"'],
                                   env=e, capture_output=True, text=True, timeout=10)
                os.close(fd)
                self.assertEqual(r.stdout.strip(), attendu, r.stderr)
        ev = [json.loads(l) for l in b.sortie.read_text().splitlines()][0]
        self.assertEqual((ev["type"], ev["options"], ev["defaut"]), ("choix", ['a"b', "B", "C"], 1))

    def test_echappement(self):
        self.assertEqual(echappe('a"b\\c'), 'a\\"b\\\\c')
        self.assertEqual(echappe("a\tb\nc"), "a\\u0009b\\u000ac")
        self.assertEqual(echappe("\033[1;35mrose\033[0m"), "rose")
        self.assertEqual(echappe("é ✓ 日本"), "é ✓ 日本")
        self.assertEqual(json.loads('"' + echappe('x"\\\x01\x7f') + '"'), 'x"\\\x01\x7f')

    def test_sudo_recoit_dash_A_et_askpass(self):
        b = self.banc()
        # un sous-script qui appelle sudo : il doit passer par l'enveloppe du PATH
        src = (REPO / "install.sh").read_text()
        self.assertIn('exec "%s" -A "$@"', src)
        # l'enveloppe est testée en vrai : extraire le bloc, lancer un sous-script qui appelle « sudo »
        d = src.index("    NC_VRAI_SUDO=")
        f = src.index("    # Pièges précoces")
        sous = b.d / "sous.sh"
        sous.write_text("#!/bin/sh\nsudo tee /x\n")
        sous.chmod(0o755)
        script = f'REPO=/depot; NC_UI_BIN=""\n{src[d:f]}\nbash {sous}\nls "$NC_UI_BIN" >/dev/null; rm -rf "$NC_UI_BIN"'
        e = b.env(entree=None)
        r = subprocess.run(["bash", "-c", script], env=e, capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("sudo -A tee /x ASKPASS=/depot/installeur/nc-askpass", b.appels())

    def test_sans_nc_ui_rien(self):
        b = self.banc()
        code, sortie, evs = b.lance("--files-only", ui=False, entree=None)
        self.assertEqual(code, 0, sortie)
        self.assertFalse(b.sortie.exists() and b.sortie.read_text(), "écriture sur NC_UI_SORTIE sans NC_UI")
        self.assertNotIn("-A", b.appels())
        self.assertNotIn("ASKPASS=/", b.appels())

    def test_enveloppe_effacee_a_la_fin(self):
        b = self.banc()
        code, sortie, evs = b.lance("--files-only", repond=self.oui)
        self.assertEqual(code, 0, sortie)
        restes = [p.name for p in b.d.iterdir() if p.name.startswith("tmp") or p.name.startswith("tmp.")]
        self.assertEqual(restes, [], "dossier de l'enveloppe sudo resté")

    def test_graphique_sans_session_reste_au_terminal(self):
        b = self.banc()
        code, sortie, evs = b.lance("--files-only", "--graphique", ui=False, entree=None)
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("Erreur", sortie)

    def test_graphique_avec_session_lance_nc_installeur(self):
        b = self.banc()
        # le worktree n'a pas forcément installeur/ : on copie install.sh dans un faux dépôt
        faux = b.d / "depot"
        faux.mkdir()
        shutil.copy(REPO / "install.sh", faux / "install.sh")
        for dossier in ("home", "system", "applications", "scripts"):
            if (REPO / dossier).exists():
                shutil.copytree(REPO / dossier, faux / dossier, symlinks=True)
        (faux / "installeur").mkdir()
        (faux / "installeur/nc-installeur").write_text("# faux\n")
        (b.bin / "python3").unlink(missing_ok=True)
        outil(b.bin, "python3", f'case "$1" in -c) exit 0;; esac; echo "python3 $*" >> "{b.journal}"; exit 0')
        e = b.env(ui=False, entree=None)
        e["WAYLAND_DISPLAY"] = "wayland-0"
        r = subprocess.run(["bash", str(faux / "install.sh"), "--graphique", "--oui", "--files-only"], env=e,
                           stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        ligne = [l for l in b.appels().splitlines() if l.startswith("python3 ")]
        self.assertEqual(len(ligne), 1, b.appels())
        self.assertIn("installeur/nc-installeur", ligne[0])
        self.assertIn("--oui --files-only", ligne[0])
        self.assertNotIn("--graphique", ligne[0])


if __name__ == "__main__":
    unittest.main()
