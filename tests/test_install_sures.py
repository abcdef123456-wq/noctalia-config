"""install.sh, étapes sensibles : --restore déplace sans rien supprimer, sources épinglées par commit et vérifiées,
empreinte de la clé du dépôt Noctalia (Debian) vérifiée avant toute installation, dépôts tiers (COPR, zypper) annoncés.
Morceaux d'install.sh extraits et lancés avec de faux outils (git, gpg, dpkg-deb, sudo) ; faux HOME ; rien de réel."""
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
SOURCE = (REPO / "install.sh").read_text()
PREAMBULE = r'''
set -euo pipefail
NC_LANGUE=fr
t() { printf '%s' "$1"; }
info() { printf '   %s\n' "$*"; }
warn() { printf '   ! %s\n' "$*"; }
ok() { printf '   ok %s\n' "$*"; }
die() { printf 'ERREUR %s\n' "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }
'''


def entre(debut, fin):
    return SOURCE[SOURCE.index(debut):SOURCE.index(fin)]


def faux(dossier, nom, corps):
    p = Path(dossier) / nom
    p.write_text("#!/usr/bin/env bash\n" + corps + "\n")
    p.chmod(p.stat().st_mode | stat.S_IEXEC)


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="nc-sures-")
        self.addCleanup(self._tmp.cleanup)
        self.r = Path(self._tmp.name)
        self.home = self.r / "home/user"
        self.home.mkdir(parents=True)
        self.bin = self.r / "bin"
        self.bin.mkdir()
        self.journal = self.r / "journal.txt"
        for nom in ("systemctl", "sudo"):
            faux(self.bin, nom, f'echo "{nom} $*" >> "{self.journal}"')
        (self.r / "run").mkdir()
        self.env = {"HOME": str(self.home), "XDG_CONFIG_HOME": str(self.home / ".config"), "XDG_DATA_HOME": str(self.home / ".local/share"),
                    "XDG_STATE_HOME": str(self.home / ".local/state"), "XDG_CACHE_HOME": str(self.home / ".cache"),
                    "XDG_RUNTIME_DIR": str(self.r / "run"), "TMPDIR": str(self.r), "PATH": f"{self.bin}:/usr/bin:/bin", "NC_LANGUE": "fr"}

    def bash(self, script, **extra):
        return subprocess.run(["bash", "-c", script], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                              start_new_session=True, env=dict(self.env, **extra), timeout=30)

    def log(self):
        return self.journal.read_text() if self.journal.exists() else ""


class Restauration(Base):
    BLOC = entre("# ── Retour arrière", "# ── Vérifications")

    def prepare(self):
        self.state = self.home / ".local/state/noctalia-config"
        self.sauv = self.state / "backup-20260101-000000"
        (self.sauv / ".config/hypr").mkdir(parents=True)
        (self.sauv / ".config/hypr/hyprland.lua").write_text("ancien\n")
        (self.sauv / "system").mkdir()
        (self.sauv / "system/sudo.conf").write_text("systeme\n")
        (self.sauv / "silencieux").mkdir()
        (self.sauv / "silencieux/resume.txt").write_text("resume\n")
        # fichiers ajoutés par l'installation, puis modifiés par l'utilisateur
        (self.home / ".config/nc").mkdir(parents=True)
        (self.home / ".config/nc/travail.conf").write_text("mon travail\n")
        (self.home / ".config/hypr").mkdir(parents=True)
        (self.home / ".config/hypr/hyprland.lua").write_text("nouveau\n")
        (self.home / "dossier-ajoute/sous").mkdir(parents=True)
        (self.home / "dossier-ajoute/sous/a.txt").write_text("a\n")
        (self.sauv / ".created").write_text(".config/nc/travail.conf\ndossier-ajoute\n../dehors\n/etc/passwd\n.config/inexistant\n")
        (self.r / "dehors").write_text("ne pas toucher\n")

    def lance(self):
        script = (PREAMBULE + f'STATE="{self.state}"; OLD_STATE="{self.home}/.local/state/legion-dotfiles"; ANNULE=10; MODE=restore\n'
                  'ask() { return 0; }; say() { printf "== %s\\n" "$*"; }\n' + self.BLOC)
        return self.bash(script)

    def test_restore_deplace_sans_rien_supprimer(self):
        self.prepare()
        r = self.lance()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        # le fichier ajouté n'est plus à sa place mais n'est pas perdu : mis de côté, avec son chemin, dans la sauvegarde
        self.assertFalse((self.home / ".config/nc/travail.conf").exists())
        self.assertFalse((self.home / "dossier-ajoute").exists())
        ecartes = sorted(self.sauv.glob("ecarte-*"))
        self.assertEqual(len(ecartes), 1)
        self.assertEqual((ecartes[0] / ".config/nc/travail.conf").read_text(), "mon travail\n")
        self.assertEqual((ecartes[0] / "dossier-ajoute/sous/a.txt").read_text(), "a\n")
        # l'ancien fichier est remis, la sauvegarde reste intacte
        self.assertEqual((self.home / ".config/hypr/hyprland.lua").read_text(), "ancien\n")
        self.assertEqual((self.sauv / ".config/hypr/hyprland.lua").read_text(), "ancien\n")
        # les chemins dangereux sont ignorés
        self.assertEqual((self.r / "dehors").read_text(), "ne pas toucher\n")
        self.assertIn("chemin ignoré", r.stdout)
        # ni le dossier mis de côté, ni system/, ni le résumé ne sont recopiés dans le HOME
        self.assertFalse(list(self.home.glob("ecarte-*")))
        self.assertFalse((self.home / "system").exists())
        self.assertFalse((self.home / "silencieux").exists())
        self.assertIn("mis de côté (pas supprimés)", r.stdout)

    def test_aucun_rm_rf_dans_la_restauration(self):
        self.assertNotIn("rm -rf", self.BLOC)
        self.assertNotIn("rm -r", self.BLOC)

    def test_refus_ne_touche_a_rien(self):
        self.prepare()
        script = (PREAMBULE + f'STATE="{self.state}"; OLD_STATE="/x"; ANNULE=10; MODE=restore\nask() {{ return 1; }}; say() {{ :; }}\n' + self.BLOC)
        r = self.bash(script)
        self.assertEqual(r.returncode, 10)
        self.assertEqual((self.home / ".config/nc/travail.conf").read_text(), "mon travail\n")
        self.assertFalse(list(self.sauv.glob("ecarte-*")))


class CommitsEpingles(Base):
    FONCTION = entre("verifier_commit() {", "# Debian / Ubuntu : Quickshell n'est pas dans les dépôts")

    def test_les_deux_sources_sont_epinglees(self):
        self.assertRegex(SOURCE, r"(?m)^QS_COMMIT=[0-9a-f]{40}$")
        self.assertRegex(SOURCE, r"(?m)^SDDM_ASTRO_COMMIT=[0-9a-f]{40}$")
        # Quickshell : chaque clone est suivi de la vérification
        for m in re.finditer(r'git clone [^\n]*quickshell\.git "\$wd/qs"', SOURCE):
            self.assertIn('verifier_commit "$wd/qs" "$QS_COMMIT"', SOURCE[m.end():m.end() + 120])
        # sddm : récupéré par son empreinte, vérifié, et plus de « git clone --depth 1 » non épinglé
        self.assertIn('fetch -q --depth 1 origin "$SDDM_ASTRO_COMMIT"', SOURCE)
        self.assertIn('verifier_commit "$T" "$SDDM_ASTRO_COMMIT" sudo', SOURCE)
        self.assertNotIn("sudo git clone", SOURCE)
        # le compilateur n'est lancé qu'après les clones vérifiés
        i = SOURCE.index('verifier_commit "$wd/qs" "$QS_COMMIT"; }; } &&')
        self.assertLess(i, SOURCE.index('cmake -S "$wd/qs"'))

    def lance(self, vu, voulu, sudo=""):
        faux(self.bin, "git", 'if [ "$1" = -C ] && [ "$3" = rev-parse ]; then echo "$FAUX_SHA"; fi')
        faux(self.bin, "sudo", 'echo "sudo $*" >> "' + str(self.journal) + '"; exec "$@"')
        return self.bash(PREAMBULE + self.FONCTION + f'verifier_commit /faux "{voulu}" {sudo}', FAUX_SHA=vu)

    def test_commit_conforme_accepte(self):
        sha = "4f508be500dea6e5732cc3d50382a0048b17e7b1"
        self.assertEqual(self.lance(sha, sha).returncode, 0)
        self.assertEqual(self.lance(sha, sha, "sudo").returncode, 0)
        self.assertIn("sudo git -C /faux rev-parse HEAD", self.log())

    def test_commit_different_refuse(self):
        r = self.lance("0" * 40, "4f508be500dea6e5732cc3d50382a0048b17e7b1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("Commit inattendu", r.stdout)
        self.assertIn("rien n'est compilé ni installé", r.stdout)

    def test_pas_de_commit_refuse(self):
        self.assertEqual(self.lance("", "4f508be500dea6e5732cc3d50382a0048b17e7b1").returncode, 1)


class EmpreinteDebian(Base):
    FONCTIONS = entre("NOCT_DEB_EMPREINTE=", "# Fedora (COPR) et openSUSE")
    BONNE = "C2A7E07FB3D746BDF2A245CD683B67D7BC99A9B7"

    def lance(self, sortie_gpg):
        faux(self.bin, "dpkg-deb", 'mkdir -p "$3" && : > "$3/cle.gpg"')
        faux(self.bin, "gpg", 'printf "%s" "$FAUX_GPG"')
        deb = self.r / "keyring.deb"
        deb.write_text("faux")
        return self.bash(PREAMBULE + self.FONCTIONS + f'verifier_empreinte_cle "{deb}" "$NOCT_DEB_EMPREINTE"', FAUX_GPG=sortie_gpg)

    @staticmethod
    def cles(*fprs):
        # sortie « --with-colons » : une clé principale, sa sous-clé (qui a sa propre empreinte), puis l'identité
        return "".join(f"pub:-:4096:1:AAAA:1:2::-:::scSC::::::23::0:\nfpr:::::::::{f}:\nuid:-::::1::HASH::Nom::::::::::0:\n"
                       f"sub:-:4096:1:BBBB:1:2:::::s::::::23:\nfpr:::::::::{'E' * 40}:\n" for f in fprs)

    def test_la_bonne_empreinte_est_acceptee(self):
        r = self.lance(self.cles(self.BONNE))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_une_autre_empreinte_est_refusee(self):
        r = self.lance(self.cles("D" * 40))
        self.assertEqual(r.returncode, 1)
        self.assertIn("Empreinte de la clé du dépôt différente", r.stdout)
        self.assertIn(self.BONNE, r.stdout)
        self.assertIn("D" * 40, r.stdout)

    def test_la_sous_cle_ne_remplace_pas_la_cle_principale(self):
        # une sous-clé portant la bonne empreinte ne suffit pas : seule la clé principale compte
        sortie = f"pub:-:4096:1:AAAA:1:2::-:::scSC::::::23::0:\nfpr:::::::::{'D' * 40}:\nsub:-:4096:1:BBBB:1:2:::::s::::::23:\nfpr:::::::::{self.BONNE}:\n"
        self.assertEqual(self.lance(sortie).returncode, 1)

    def test_une_cle_en_plus_est_refusee(self):
        self.assertEqual(self.lance(self.cles(self.BONNE, "D" * 40)).returncode, 1)

    def test_aucune_cle_est_refusee(self):
        r = self.lance("")
        self.assertEqual(r.returncode, 1)
        self.assertIn("aucune", r.stdout)

    def test_la_cle_est_verifiee_avant_toute_installation(self):
        bloc = SOURCE[SOURCE.index("empreinte attendue de la clé"):SOURCE.index("have noctalia || die")]
        self.assertLess(bloc.index("verifier_empreinte_cle"), bloc.index("sudo dpkg -i"))
        self.assertLess(bloc.index("verifier_empreinte_cle"), bloc.index("sudo install -Dm0644"))
        # en cas d'écart : die, avant dpkg -i
        self.assertLess(bloc.index("die "), bloc.index("sudo dpkg -i"))
        self.assertNotIn("sudo wget", bloc)                  # le fichier de source n'est plus écrit sans contrôle
        self.assertRegex(SOURCE, r"(?m)^NOCT_DEB_EMPREINTE=[0-9A-F]{40}$")


class DepotsTiers(Base):
    def test_annonce_avant_chaque_question(self):
        for question, motif in (("Activer ce dépôt et installer Hyprland", "dnf -y copr enable"),
                                ("Activer ce dépôt pour l'île dynamique", "dnf -y copr enable"),
                                ("Ajouter ce dépôt et installer Noctalia ?\" \"Add this repository and install Noctalia?\")\" o || die \"$(t \"Noctalia v5 est nécessaire : $NOCT_DOCS\" \"Noctalia v5 is required: $NOCT_DOCS\")\"\n        sudo zypper",
                                 "zypper --gpg-auto-import-keys")):
            i = SOURCE.index(question)
            avant = SOURCE[max(0, i - 400):i]
            self.assertIn("avertir_depot_tiers", avant, question)
            self.assertIn(motif, avant, question)

    def test_message_dit_la_cle_et_le_depot(self):
        fonction = entre("avertir_depot_tiers() {", "# Debian 13 (trixie) : Hyprland 0.55+")
        r = self.bash(PREAMBULE + fonction + 'avertir_depot_tiers "COPR exemple/depot" "dnf -y copr enable"')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("COPR exemple/depot", r.stdout)
        self.assertIn("communautaire", r.stdout)
        self.assertIn("clé GPG sera importée automatiquement (dnf -y copr enable)", r.stdout)
        self.assertEqual(self.log(), "")                # rien n'est fait, seulement dit


if __name__ == "__main__":
    unittest.main()
