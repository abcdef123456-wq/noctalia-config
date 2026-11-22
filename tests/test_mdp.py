"""« mdp 20 » : le script nc-mdp avec un FAUX wl-copy (argv, stdin, environnement, TMPDIR et âge de la marque notés ;
jamais le vrai presse-papiers), sous une garde (crochet d'audit Python) qui refuse et note toute écriture de fichier,
tout programme lancé autre que wl-copy, tout syslog et toute socket ; la capture de l'île (nc-presse-capture) avec un
faux wl-paste ; la source ; puis Recherche.qml réel hors écran avec un faux nc-mdp."""
from tests import _isolation  # noqa: F401
import collections
import os
from pathlib import Path
import re
import runpy
import shutil
import signal
import string
import subprocess
import sys
import tempfile
import time
import unittest

REPO = Path(__file__).resolve().parents[1]
QML = REPO / "home/.config/quickshell/nc-ile"
SCRIPT_MDP = REPO / "home/.local/bin/nc-mdp"
CAPTURE = REPO / "home/.local/bin/nc-presse-capture"
RECHERCHE = (QML / "Recherche.qml").read_text(encoding="utf-8")
SOURCE = SCRIPT_MDP.read_text(encoding="utf-8")
TYPE = ["--type", "text/plain;charset=utf-8"]   # wl-copy ne devine pas le type sur le fichier du mot de passe
SYMBOLES = "-_.,:;+=@#%!?"
CLASSES = (string.ascii_lowercase, string.ascii_uppercase, string.digits, SYMBOLES)

# Faux wl-copy : « aide » = avec ou sans --sensitive dans --help. Note argv, environnement, mode de son TMPDIR, âge de
# la marque au moment où il lit son entrée, l'entrée, puis lance la VRAIE capture de l'île comme si la sélection
# venait d'apparaître (faux wl-paste qui rend cette entrée). « lent » : attend avant de lire ; « bloque » : ne finit pas.
FAUX = '''#!/bin/sh
if [ "$1" = "--help" ]; then
  printf '%s\\n' "Usage: wl-copy [options]"
  [ -f "$FAUX_DIR/sensible" ] && printf '%s\\n' "    --sensitive    Hint that the content is sensitive."
  exit 0
fi
printf '%s\\n' "$$" > "$FAUX_DIR/debut"
n=$(ls "$FAUX_DIR" | grep -c '^appel-.*\\.argv$')
m="$XDG_RUNTIME_DIR/nc-secret-copie"
# Lent : « lent » demi-secondes d'attente, l'âge de la marque (en secondes, à la nanoseconde) noté à chacune
if [ -f "$FAUX_DIR/lent" ]; then
  i=0
  while [ "$i" -lt "$(cat "$FAUX_DIR/lent")" ]; do
    sleep 0.5
    "$FAUX_PY" -I -c 'import os, sys, time; print(time.time() - os.stat(sys.argv[1]).st_mtime)' "$m" >> "$FAUX_DIR/ages" 2>&1
    i=$((i + 1))
  done
fi
printf '%s\\n' "$@" > "$FAUX_DIR/appel-$n.argv"
env > "$FAUX_DIR/appel-$n.env"
stat -c %a "$TMPDIR" > "$FAUX_DIR/appel-$n.tmpdir" 2>/dev/null
[ -f "$m" ] && printf '%s\\n' "$(( $(date +%s) - $(stat -c %Y "$m") ))" > "$FAUX_DIR/appel-$n.age"
cat > "$FAUX_DIR/appel-$n.stdin"
FAUX_COURANT="$FAUX_DIR/appel-$n.stdin" PATH="$FAUX_PASTE:/usr/bin:/bin" sh "$FAUX_CAPTURE" > "$FAUX_DIR/appel-$n.capture" 2>&1
date +%s.%N > "$FAUX_DIR/appel-$n.fin"
[ -f "$FAUX_DIR/bloque" ] && exec sleep 30
[ -f "$FAUX_DIR/echec" ] && exit 1
exit 0
'''
FAUX_PASTE = '#!/bin/sh\ncase "$*" in *list-types*) printf "%s\\n" text/plain;; *) cat "$FAUX_COURANT";; esac\n'

# Garde : nc-mdp tourne sous un crochet d'audit qui REFUSE (avant qu'elle ait lieu) et note toute action hors de ses
# promesses : écrire un fichier autre que la marque, créer un dossier autre que son TMPDIR privé, lancer autre chose
# que wl-copy, syslog, socket. Rien ne sort donc du dossier de test, même pour un mutant.
GARDE = r'''
import os, runpy, sys
script, journal, marque, wl = sys.argv[1], os.environ["NC_TEST_GARDE"], os.environ["NC_TEST_MARQUE"], os.environ["NC_TEST_WL"]
fd = os.open(journal, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
run = os.path.dirname(marque)
ECRIT = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC
INTERDITS = ("socket.connect", "socket.sendto", "socket.sendmsg", "socket.bind", "os.system", "os.exec",
             "os.spawn", "os.fork", "os.forkpty", "os.rename", "os.remove", "os.symlink", "os.link", "os.truncate", "ctypes.dlopen",
             "os.putenv", "os.chmod", "shutil.copyfile")
def garde(ev, a):
    mal = None
    if ev == "open" and isinstance(a[0], (str, bytes, os.PathLike)) and (a[2] or 0) & ECRIT:
        if os.path.abspath(os.fsdecode(a[0])) not in (marque, os.devnull):
            mal = "écrit " + os.fsdecode(a[0])
    elif ev in ("os.mkdir", "os.rmdir"):
        c = os.path.abspath(os.fsdecode(a[0]))
        if os.path.dirname(c) != run or not os.path.basename(c).startswith("nc-mdp-"):
            mal = ev + " " + c
    elif ev in ("subprocess.Popen", "os.posix_spawn"):           # Python 3.13+ : Popen passe par posix_spawn
        prog = os.fsdecode(a[0] if a[0] else a[1][0])
        if prog != wl:
            mal = "lance " + prog
    elif ev.startswith("syslog.") or ev in INTERDITS:
        mal = ev
    if mal:
        os.write(fd, (mal + "\n").encode("utf-8", "replace"))
        raise PermissionError("garde du test : " + mal)
sys.addaudithook(garde)
sys.argv = sys.argv[1:]
runpy.run_path(script, run_name="__main__")
'''


class Faux:
    """Un PATH de test avec un faux wl-copy (ou sans), un XDG_RUNTIME_DIR, dans un dossier jetable."""

    def __init__(self, test, sensible=True, present=True, echec=False):
        self.test = test
        self.d = Path(tempfile.mkdtemp(prefix="nc-mdp-"))
        test.addCleanup(shutil.rmtree, str(self.d), True)
        self.bin = self.d / "bin"
        self.bin.mkdir()
        self.etat = self.d / "etat"
        self.etat.mkdir()
        self.paste = self.d / "paste"
        self.paste.mkdir()
        (self.paste / "wl-paste").write_text(FAUX_PASTE)
        (self.paste / "wl-paste").chmod(0o755)
        self.run = self.d / "run"
        self.run.mkdir(mode=0o700)
        self.marque = self.run / "nc-secret-copie"
        self.garde = self.d / "garde"
        if present:
            (self.bin / "wl-copy").write_text(FAUX)
            (self.bin / "wl-copy").chmod(0o755)
        if sensible:
            (self.etat / "sensible").write_text("")
        if echec:
            (self.etat / "echec").write_text("")
        # PATH réduit au faux dossier + les outils de base du faux shell, par des liens
        for o in ("sh", "ls", "grep", "cat", "env", "stat", "date", "sleep"):
            chemin = shutil.which(o)
            if not chemin:
                test.skipTest(o + " absent")
            (self.bin / o).symlink_to(chemin)

    def environnement(self, env_plus=None):
        env = {"PATH": str(self.bin), "FAUX_DIR": str(self.etat), "FAUX_PASTE": str(self.paste), "FAUX_CAPTURE": str(CAPTURE),
               "HOME": str(self.d), "TMPDIR": str(self.d), "XDG_RUNTIME_DIR": str(self.run), "LC_ALL": "C.UTF-8",
               "PYTHONIOENCODING": "utf-8", "NC_TEST_GARDE": str(self.garde), "NC_TEST_MARQUE": str(self.marque),
               "NC_TEST_WL": str(self.bin / "wl-copy"), "FAUX_PY": sys.executable}
        for k, v in (env_plus or {}).items():
            if v is None:
                env.pop(k, None)
            else:
                env[k] = v
        return env

    def lancer(self, *args, env_plus=None, timeout=30):
        env = self.environnement(env_plus)
        r = subprocess.run([sys.executable, "-I", "-B", "-c", GARDE, str(SCRIPT_MDP), *args], env=env, capture_output=True, text=True,
                           timeout=timeout)
        self.test.assertEqual(self.garde.read_text() if self.garde.exists() else "", "", "action refusée par la garde")
        self.test.assertNotIn("Traceback", r.stderr)
        return r

    def appels(self):
        return sorted(self.etat.glob("appel-*.stdin"))

    def lire(self, quoi, i=0):
        return (self.etat / ("appel-%d.%s" % (i, quoi))).read_text(encoding="utf-8")

    def wl_copy_arrete(self):
        """Le faux wl-copy (pid noté au début) ne tourne plus ; s'il tourne encore, il est tué par ce pid."""
        pid = int((self.etat / "debut").read_text())
        vivant = os.path.exists("/proc/%d" % pid)
        if vivant:
            os.kill(pid, signal.SIGKILL)
        return not vivant

    def mot(self, i=0):
        return self.lire("stdin", i)

    def argv(self, i=0):
        return [a for a in self.lire("argv", i).splitlines() if a]


class Script(unittest.TestCase):
    def test_copie_sensible(self):
        f = Faux(self)
        r = f.lancer("20")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(f.appels()), 1)
        self.assertEqual(f.argv(), TYPE + ["--sensitive"])
        self.assertEqual(len(f.mot()), 20, "pas de retour à la ligne ajouté")

    def test_copie_sans_option_si_wl_copy_ancien(self):
        f = Faux(self, sensible=False)
        r = f.lancer("20")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(f.argv(), TYPE)
        self.assertEqual(len(f.mot()), 20)

    def test_longueurs_et_classes(self):
        for n in (8, 9, 20, 33, 64):
            f = Faux(self)
            self.assertEqual(f.lancer(str(n)).returncode, 0)
            m = f.mot()
            self.assertEqual(len(m), n)
            self.assertTrue(set(m) <= set(string.ascii_letters + string.digits + SYMBOLES), m)
            self.assertTrue(all(any(c in k for c in m) for k in CLASSES), m)

    def test_bornes_et_refus(self):
        for arg in ("7", "65", "0", "-5", "abc", "", "20 ", "2e1", "٢٠", "9" * 40, "9" * 5000, "008"):
            f = Faux(self)
            r = f.lancer(arg)
            self.assertEqual(r.returncode, 2, "refusé : %r" % arg[:50])
            self.assertIn("nc-mdp", r.stderr)
            self.assertEqual(f.appels(), [], "rien copié pour %r" % arg[:50])
            self.assertEqual(r.stdout, "")
        for args in ((), ("20", "30")):
            f = Faux(self)
            self.assertEqual(f.lancer(*args).returncode, 2)
            self.assertEqual(f.appels(), [])
        for n in ("8", "64"):
            self.assertEqual(Faux(self).lancer(n).returncode, 0)

    def test_mot_de_passe_jamais_en_argv_ni_en_sortie(self):
        f = Faux(self)
        r = f.lancer("32")
        m = f.mot()
        self.assertNotIn(m, " ".join(f.argv()))
        self.assertEqual(f.argv(), TYPE + ["--sensitive"])
        self.assertEqual(r.stdout + r.stderr, "")

    def test_environnement_et_tmpdir_prive_de_wl_copy(self):
        """Le secret n'est pas dans l'environnement de wl-copy ; son TMPDIR est un dossier 0700 sous XDG_RUNTIME_DIR,
        retiré après la copie (wl-copy y recopie son entrée)."""
        f = Faux(self)
        self.assertEqual(f.lancer("40").returncode, 0)
        m, env = f.mot(), f.lire("env")
        self.assertNotIn(m, env)
        tmp = dict(l.split("=", 1) for l in env.splitlines() if "=" in l)["TMPDIR"]
        self.assertEqual(os.path.dirname(tmp), str(f.run))
        self.assertTrue(os.path.basename(tmp).startswith("nc-mdp-"), tmp)
        self.assertEqual(f.lire("tmpdir").strip(), "700")
        self.assertEqual(sorted(p.name for p in f.run.iterdir()), ["nc-secret-copie"], "TMPDIR privé retiré")

    def test_sans_xdg_runtime_dir_rien_n_est_copie(self):
        f = Faux(self)
        r = f.lancer("20", env_plus={"XDG_RUNTIME_DIR": None})
        self.assertEqual(r.returncode, 1)
        self.assertIn("XDG_RUNTIME_DIR", r.stderr)
        self.assertEqual(f.appels(), [])

    def test_wl_copy_absent(self):
        f = Faux(self, present=False)
        r = f.lancer("20")
        self.assertEqual(r.returncode, 1)
        self.assertIn("wl-copy", r.stderr)
        self.assertEqual(f.appels(), [])
        self.assertEqual(list(f.run.iterdir()), [], "rien d'écrit")
        self.assertEqual([p.name for p in f.etat.iterdir()], ["sensible"], "seul mon marqueur de test")

    def test_echec_de_wl_copy_donne_un_code_non_nul(self):
        f = Faux(self, echec=True)
        r = f.lancer("20")
        self.assertEqual(r.returncode, 1)
        self.assertIn("échoué", r.stderr)
        self.assertNotIn(f.mot(), r.stdout + r.stderr)

    def test_deux_appels_deux_mots_differents(self):
        f = Faux(self)
        f.lancer("24")
        f.lancer("24")
        self.assertEqual(len(f.appels()), 2)
        self.assertNotEqual(f.mot(0), f.mot(1))

    def test_rien_sur_disque(self):
        f = Faux(self)
        f.lancer("20")
        self.assertEqual(sorted(p.name for p in f.d.iterdir()), ["bin", "etat", "garde", "paste", "run"])
        self.assertEqual([p.name for p in f.run.iterdir()], ["nc-secret-copie"])
        self.assertEqual(f.marque.read_bytes(), b"")

    def test_marque_fraiche_quand_wl_copy_lit_et_capture_vide(self):
        """Ordre : la marque existe et a moins d'une seconde quand wl-copy lit le mot de passe ; la capture de l'île,
        lancée à cet instant, ne garde rien — même sans --sensitive (Debian 13, wl-clipboard 2.2.1)."""
        f = Faux(self, sensible=False)
        r = f.lancer("20")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(f.argv(), TYPE)
        self.assertIn(f.lire("age").strip(), ("0", "1"))
        self.assertEqual(f.lire("capture"), "")
        self.assertEqual(f.marque.stat().st_mode & 0o777, 0o600)
        # Deux heures de fichiers (même horloge du noyau, précise à quelques ms) : jamais une heure de fichier contre
        # celle de « date », plus fine, qui a donné 0,3 ms d'écart sur openSUSE
        self.assertGreaterEqual(f.marque.stat().st_mtime_ns, (f.etat / "appel-0.fin").stat().st_mtime_ns,
                                "marque rafraîchie après la fin de wl-copy")
        # Contrôle du contrôle : la même capture, marque périmée, garde la copie
        vieux = time.time() - 30
        os.utime(str(f.marque), (vieux, vieux))
        env = dict(HOME=str(f.d), XDG_RUNTIME_DIR=str(f.run), FAUX_COURANT=str(f.appels()[0]), PATH=str(f.paste) + ":/usr/bin:/bin")
        sortie = subprocess.run(["sh", str(CAPTURE)], env=env, capture_output=True, text=True, timeout=10).stdout
        self.assertEqual(sortie, "T:" + f.mot() + "\n")

    def test_copie_lente_puis_delai_depasse(self):
        """wl-copy lent (6 s avant de lire) : la marque est restée fraîche. wl-copy qui ne finit pas : tué au bout de
        10 s, code 1, jamais « copié », message sans le secret, marque encore fraîche après."""
        f = Faux(self, sensible=False)
        (f.etat / "lent").write_text("12")
        (f.etat / "bloque").write_text("")
        t0 = time.monotonic()
        r = f.lancer("20", timeout=40)
        duree = time.monotonic() - t0
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertLess(duree, 14, "délai de wl-copy : 10 s")
        self.assertGreater(duree, 9)
        self.assertIn(f.lire("age").strip(), ("0", "1"))
        ages = [float(a) for a in (f.etat / "ages").read_text().split()]
        self.assertEqual(len(ages), 12)
        self.assertTrue(all(0 <= a < 1.5 for a in ages), "marque fraîche à chaque demi-seconde : %s" % ages)
        self.assertEqual(f.lire("capture"), "")
        self.assertNotIn(f.mot(), r.stdout + r.stderr)
        self.assertLess(time.time() - f.marque.stat().st_mtime, 2)
        self.assertTrue(f.wl_copy_arrete(), "wl-copy tué au délai")

    def test_sigterm_pendant_la_copie_ne_laisse_rien(self):
        """SIGTERM (et SIGINT, SIGHUP) pendant un wl-copy lent : sortie par les finally, aucun dossier nc-mdp-* laissé."""
        f = Faux(self)
        (f.etat / "lent").write_text("20")
        p = subprocess.Popen([sys.executable, "-I", "-B", "-c", GARDE, str(SCRIPT_MDP), "20"], env=f.environnement(),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: p.poll() is None and p.kill())
        fin = time.monotonic() + 10
        while not (f.etat / "debut").exists() and time.monotonic() < fin:
            time.sleep(0.05)
        self.assertTrue(list(f.run.glob("nc-mdp-*")), "TMPDIR privé présent pendant la copie")
        p.send_signal(signal.SIGTERM)          # pid mémorisé de ce nc-mdp
        sortie, erreur = p.communicate(timeout=10)
        self.assertEqual(p.returncode, 128 + signal.SIGTERM, erreur)
        self.assertNotIn("Traceback", erreur)
        self.assertEqual(list(f.run.glob("nc-mdp-*")), [], "aucun dossier laissé")
        self.assertTrue(f.wl_copy_arrete(), "wl-copy arrêté avec nc-mdp")
        self.assertEqual(f.garde.read_text() if f.garde.exists() else "", "")
        self.assertLess(time.time() - f.marque.stat().st_mtime, 2, "marque rafraîchie à la sortie")

    def test_marque_fifo_ne_bloque_pas(self):
        f = Faux(self)
        os.mkfifo(str(f.marque))
        r = f.lancer("20", timeout=10)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(f.appels(), [], "pas de marque : rien copié")
        # Avec un lecteur, l'ouverture réussit : refusée quand même (pas un fichier ordinaire)
        lecteur = os.open(str(f.marque), os.O_RDONLY | os.O_NONBLOCK)
        self.addCleanup(os.close, lecteur)
        r = f.lancer("20", timeout=10)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(f.appels(), [])

    def test_marque_lien_symbolique_refuse(self):
        f = Faux(self)
        cible = f.d / "cible"
        cible.write_text("intact")
        os.utime(str(cible), (1000000000, 1000000000))
        f.marque.symlink_to(cible)
        r = f.lancer("20")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(f.appels(), [])
        self.assertEqual(cible.read_text(), "intact")
        self.assertEqual(cible.stat().st_mtime, 1000000000, "la marque ne suit jamais un lien (O_NOFOLLOW)")


class Tirage(unittest.TestCase):
    """generer() chargé du script lui-même (sans lancer main) : beaucoup de tirages."""

    @classmethod
    def setUpClass(cls):
        cls.generer = staticmethod(runpy.run_path(str(SCRIPT_MDP), run_name="nc_mdp")["generer"])

    def test_chaque_classe_a_chaque_position(self):
        vus = collections.defaultdict(set)
        for _ in range(1500):
            for i, c in enumerate(self.generer(8)):
                vus[i].update(k for k in range(4) if c in CLASSES[k])
        self.assertEqual({i: sorted(v) for i, v in vus.items()}, {i: [0, 1, 2, 3] for i in range(8)})

    def test_repartition_des_caracteres(self):
        """Khi-deux contre la loi attendue : un de chaque classe (uniforme dans la classe) + n-4 tirés sur les 75."""
        tout, n, tirages = "".join(CLASSES), 64, 3000
        compte = collections.Counter()
        for _ in range(tirages):
            m = self.generer(n)
            self.assertTrue(all(any(c in k for c in m) for k in CLASSES))
            compte.update(m)
        khi2 = 0.0
        for k in CLASSES:
            for c in k:
                attendu = tirages * (1 / len(k) + (n - 4) / len(tout))
                khi2 += (compte[c] - attendu) ** 2 / attendu
        self.assertLess(khi2, 160, "74 degrés de liberté : ~74 attendu, 160 a une chance sur dix millions environ")


class Capture(unittest.TestCase):
    """nc-presse-capture : fenêtre des marques, et sélection déjà là au démarrage de la veille."""

    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="nc-cap-"))
        self.addCleanup(shutil.rmtree, str(self.d), True)
        self.dossier_run = self.d / "run"
        self.dossier_run.mkdir(mode=0o700)
        self.bin = self.d / "bin"
        self.bin.mkdir()
        # Faux wl-paste : --watch lance la commande (fork, comme wl-paste) pour chaque fichier sel-* de FAUX_SEL (le premier
        # = sélection déjà là), après FAUX_PAUSE secondes ; note son pid ; FAUX_PREP prépare d'abord son fichier de veille
        (self.bin / "wl-paste").write_text('''#!/bin/sh
case "$1" in
  --watch)
    shift
    printf '%s\\n' "$$" > "$FAUX_SEL/pid"
    v="$XDG_RUNTIME_DIR/nc-presse-veille.$$"
    case "${FAUX_PREP:-}" in
      fausse) printf '%s\\n' 1 > "$v" ;;
      dossier) mkdir "$v" ;;
      lien:*) ln -s "${FAUX_PREP#lien:}" "$v" ;;
    esac
    for s in "$FAUX_SEL"/sel-*; do
      [ -n "${FAUX_PAUSE:-}" ] && sleep "$FAUX_PAUSE"
      FAUX_COURANT="$s" "$@" < "$s"
    done ;;
  --list-types) printf '%s\\n' text/plain ;;
  *) cat "${FAUX_COURANT:-$FAUX_DIR/courant}" ;;
esac
''')
        (self.bin / "wl-paste").chmod(0o755)
        (self.d / "courant").write_text("copie")

    def env(self, **plus):
        e = dict(HOME=str(self.d), XDG_RUNTIME_DIR=str(self.dossier_run), FAUX_DIR=str(self.d), PATH=str(self.bin) + ":/usr/bin:/bin")
        e.update(plus)
        return {k: v for k, v in e.items() if v is not None}

    def capturer(self):
        return subprocess.run(["sh", str(CAPTURE)], env=self.env(), capture_output=True, text=True, timeout=10).stdout

    def test_fenetre_de_0_a_4_s_pour_les_deux_marques(self):
        for nom in ("nc-secret-copie", "nc-dictee-copie"):
            m = self.dossier_run / nom
            m.write_bytes(b"")
            for age, garde in ((0, False), (3.5, False), (5.5, True), (-3600, True)):
                t = time.time() - age
                os.utime(str(m), (t, t))
                self.assertEqual(self.capturer(), "T:copie\n" if garde else "", "%s âgée de %s s" % (nom, age))
            m.unlink()

    def lancer_veille(self, selections, **env):
        sel = Path(tempfile.mkdtemp(prefix="sel-", dir=str(self.d)))
        for i, s in enumerate(selections):
            (sel / ("sel-%d" % i)).write_text(s)
        p = subprocess.Popen([str(self.bin / "wl-paste"), "--watch", str(CAPTURE)], env=self.env(NC_PRESSE_VEILLE="1", FAUX_SEL=str(sel), **env),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: p.poll() is None and p.kill())
        return p, sel

    def veille(self, *selections, **env):
        p, sel = self.lancer_veille(selections, **env)
        sortie, _ = p.communicate(timeout=20)
        self.pid_veille = int((sel / "pid").read_text())
        return sortie

    def fichiers_veille(self):
        return sorted(p.name for p in self.dossier_run.iterdir() if p.name.startswith("nc-presse-veille"))

    def test_deux_veilles_vivantes_en_meme_temps(self):
        """Deux veilles entrelacées : chacune ignore SA première sélection et garde les suivantes."""
        a, _ = self.lancer_veille(["deja-la-a", "a1", "a2", "a3"], FAUX_PAUSE="0.3")
        time.sleep(0.15)
        b, _ = self.lancer_veille(["deja-la-b", "b1", "b2", "b3"], FAUX_PAUSE="0.3")
        self.assertEqual(a.communicate(timeout=20)[0], "T:a1\nT:a2\nT:a3\n")
        self.assertEqual(b.communicate(timeout=20)[0], "T:b1\nT:b2\nT:b3\n")

    def test_heure_de_depart_lue_apres_la_derniere_parenthese(self):
        """Nom de processus avec espaces et parenthèses : l'heure notée est bien le champ 22 de /proc/<pid>/stat."""
        drole = self.bin / "wl) (paste x"
        shutil.copy2(str(self.bin / "wl-paste"), str(drole))
        sel = Path(tempfile.mkdtemp(prefix="sel-", dir=str(self.d)))
        for i, t in enumerate(("deja-la", "copie")):
            (sel / ("sel-%d" % i)).write_text(t)
        p = subprocess.Popen([str(drole), "--watch", str(CAPTURE)], env=self.env(NC_PRESSE_VEILLE="1", FAUX_SEL=str(sel), FAUX_PAUSE="0.5"),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: p.poll() is None and p.kill())
        fin = time.monotonic() + 10
        while not (sel / "pid").exists() and time.monotonic() < fin:
            time.sleep(0.02)
        stat = Path("/proc/%d/stat" % p.pid).read_text()
        self.assertIn(") (", stat, "le nom du processus contient bien des parenthèses")
        heure = stat[stat.rindex(")") + 2:].split()[19]
        self.assertEqual(p.communicate(timeout=20)[0], "T:copie\n")
        self.assertEqual((self.dossier_run / ("nc-presse-veille.%d" % p.pid)).read_text(), heure + "\n")

    def test_pid_reutilise_premiere_selection_quand_meme_ignoree(self):
        """Le fichier de ce pid existe déjà (pid réutilisé, autre heure de départ) : la première sélection n'entre pas."""
        self.assertEqual(self.veille("mot de passe", "ma copie", FAUX_PREP="fausse"), "T:ma copie\n")
        heure = (self.dossier_run / ("nc-presse-veille.%d" % self.pid_veille)).read_text().strip()
        self.assertRegex(heure, r"^\d+$")
        self.assertNotEqual(heure, "1")

    def test_menage_des_veilles_mortes(self):
        mort = subprocess.Popen(["true"])
        mort.wait()
        (self.dossier_run / ("nc-presse-veille.%d" % mort.pid)).write_text("123\n")
        (self.dossier_run / "nc-presse-veille.abc").write_text("123\n")
        self.assertEqual(self.veille("deja la", "copie"), "T:copie\n")
        self.assertEqual(self.fichiers_veille(), ["nc-presse-veille.%d" % self.pid_veille, "nc-presse-veille.abc"],
                         "fichier du pid mort retiré, nom non numérique laissé")

    def test_selection_deja_la_au_demarrage_jamais_gardee(self):
        # Toute première veille après la connexion : aucun fichier nc-presse-veille encore
        self.assertEqual(self.fichiers_veille(), [])
        self.assertEqual(self.veille("mot de passe", "ma copie"), "T:ma copie\n", "la première sélection n'entre pas")
        self.assertEqual(self.veille("ma copie", "autre", "encore"), "T:autre\nT:encore\n", "veille relancée : pareil")
        self.assertEqual(self.veille("a", "b", XDG_RUNTIME_DIR=None), "", "sans XDG_RUNTIME_DIR : rien gardé")
        (self.d / "courant").write_text("hors veille")
        self.assertEqual(self.capturer(), "T:hors veille\n", "lancée à la main (sans NC_PRESSE_VEILLE) : comme avant")

    def test_fichier_de_veille_atomique_sans_suivre_de_lien(self):
        cible = self.d / "cible"
        cible.write_text("intact")
        self.assertEqual(self.veille("deja la", "copie", FAUX_PREP="lien:" + str(cible)), "T:copie\n")
        v = self.dossier_run / ("nc-presse-veille.%d" % self.pid_veille)
        self.assertEqual(cible.read_text(), "intact", "le lien n'est jamais suivi")
        self.assertFalse(v.is_symlink())
        self.assertEqual(v.stat().st_mode & 0o777, 0o600)
        self.assertRegex(v.read_text(), r"^\d+\n$")
        self.assertEqual(self.fichiers_veille(), [v.name], "aucun fichier temporaire laissé")
        # un dossier à la place : rien n'y est écrit, rien n'est gardé, aucune erreur
        self.assertEqual(self.veille("deja la", "copie", FAUX_PREP="dossier"), "")
        d = self.dossier_run / ("nc-presse-veille.%d" % self.pid_veille)
        self.assertTrue(d.is_dir())
        self.assertEqual(list(d.iterdir()), [])
        self.assertEqual([n for n in self.fichiers_veille() if "tmp" in n], [], "aucun fichier temporaire laissé")

    def test_l_ile_pose_la_variable_de_la_veille(self):
        pp = (QML / "PressePapiers.qml").read_text(encoding="utf-8")
        self.assertRegex(pp, r'command: \["wl-paste", "--watch", pp\.bin \+ "nc-presse-capture"\]\n(?:\s*//[^\n]*\n)?'
                             r'\s*environment: \(\{ "NC_PRESSE_VEILLE": "1" \}\)')


class Source(unittest.TestCase):
    def test_secrets_seul(self):
        self.assertRegex(SOURCE, r"(?m)^import secrets$")
        self.assertNotRegex(SOURCE, r"(?m)^\s*(import|from)\s+random\b")
        self.assertNotIn("random.", SOURCE.replace("SystemRandom", ""))

    def test_copie_par_stdin_sans_shell(self):
        self.assertNotIn("shell=True", SOURCE)
        self.assertNotIn("os.system", SOURCE)
        self.assertIn('"--sensitive"', SOURCE)
        self.assertIn('"--help"', SOURCE)
        self.assertNotRegex(SOURCE, r"\bprint\([^)]*(generer|mot)\b")
        self.assertNotRegex(SOURCE, r"\b(logging|syslog)\b")

    def test_historique_ignore_la_marque(self):
        # --sensitive pose x-kde-passwordManagerHint, que la capture de l'île ignore (voir aussi test_presse)
        self.assertRegex(CAPTURE.read_text(encoding="utf-8"), r"x-kde-passwordManagerHint\*\|")


class Recherche(unittest.TestCase):
    def test_commande_en_liste_avec_seulement_n(self):
        self.assertIn('copieurMdp.command = [Etat.bin + "nc-mdp", String(n)]', RECHERCHE)
        bloc = RECHERCHE[RECHERCHE.index("function copierMdp"):RECHERCHE.index("function nomGuillemets")]
        self.assertNotIn("console.log", bloc)
        self.assertNotIn("sh -c", bloc)
        self.assertNotIn("bash", bloc)
        self.assertIn("code === 0", bloc, "« copié » seulement si le code est 0")
        self.assertIn("Copie impossible", bloc)

    def test_pas_de_console_log_ni_de_nouveau_composant(self):
        self.assertNotRegex(RECHERCHE, r"console\.log\([^)]*(mdp|retourMdp)")
        # Valeurs FIXES (rechargement à chaud : aucun nouveau component inline ni import dans un .qml existant)
        for texte, composants, imports in ((RECHERCHE, 0, 7), ((QML / "PressePapiers.qml").read_text(encoding="utf-8"), 0, 4)):
            self.assertEqual(len(re.findall(r"(?m)^\s*component\s", texte)), composants)
            self.assertEqual(len(re.findall(r"(?m)^import\s", texte)), imports)

    def test_rien_n_est_genere_en_tapant(self):
        i = RECHERCHE.index("mdp|password)(?:")
        bloc = RECHERCHE[i:i + 1800]
        self.assertIn("garder: true, f: () => r.copierMdp(nm)", bloc)
        self.assertNotIn("copierMdp(nm)\n", RECHERCHE[:i].split("function chercher")[-1])
        self.assertEqual(RECHERCHE.count("copierMdp("), 2, "définition + un seul appel (dans la ligne)")


SCRIPT = '''import QtQuick
import Quickshell
ShellRoot {
 id: racine
 property int etape: 0
 property int attente: 0
 function trouver(item,nom){if(item.objectName===nom)return item;for(var i=0;i<item.children.length;i++){var r=trouver(item.children[i],nom);if(r)return r}return null}
 function verifier(ok,message){if(!ok){console.error(message);Qt.exit(2);throw new Error(message)}}
 function titres(){ return spot.resultats.map(x => x.titre) }
 FloatingWindow { id: fen; visible: true; implicitWidth: 700; implicitHeight: 600
  Recherche { id: spot; width: 700; actif: true } }
 Timer { interval: 100; running: true; repeat: true; onTriggered: {
  var champ = trouver(spot, "nc-spotlight-champ")
  if (etape === 0) { if (spot.nomIA === "") return
   champ.text = "mdp"; etape++; return }
  if (etape === 1) {
   verifier(titres().length === 1 && titres()[0].indexOf("Copier un mot de passe de 20 caractères") === 0, "mdp seul : " + JSON.stringify(titres()))
   champ.text = "password 12"; etape++; return }
  if (etape === 2) {
   verifier(titres().length === 1 && titres()[0].indexOf("de 12 caractères") > 0, "password 12 : " + JSON.stringify(titres()))
   champ.text = "mdp 7"; etape++; return }
  if (etape === 3) {
   verifier(titres().length === 1 && titres()[0].indexOf("Longueur") === 0, "mdp 7 : " + JSON.stringify(titres()))
   spot.valider(0, false)      // ligne d'erreur : rien ne doit partir
   champ.text = "mdp 65"; etape++; return }
  if (etape === 4) {
   verifier(titres()[0].indexOf("Longueur") === 0, "mdp 65 : " + JSON.stringify(titres()))
   spot.valider(0, false)
   champ.text = "mdp 20"; etape++; return }
  if (etape === 5) {
   verifier(titres().length === 1 && titres()[0] === "Copier un mot de passe de 20 caractères", "mdp 20 : " + JSON.stringify(titres()))
   attente++; if (attente < 10) return      // laisser le temps à un lancement fautif de se montrer
   verifier(Etat.fermetures === 0, "pas de fermeture avant Entrée")
   spot.valider(0, false)
   verifier(Etat.fermetures === 0, "Entrée garde le Spotlight ouvert pour dire « copié »")
   etape++; return }
  if (etape === 6) {
   if (titres()[0].indexOf("copié") < 0) { attente++; verifier(attente < 60, "jamais « copié » : " + JSON.stringify(titres())); return }
   verifier(titres()[0] === "Mot de passe de 20 caractères copié", "retour : " + JSON.stringify(titres()))
   champ.text = "mdp 21"; etape++; return }
  if (etape === 7) {
   verifier(titres()[0].indexOf("Copier") === 0, "le retour disparaît à la frappe : " + JSON.stringify(titres()))
   Qt.quit() }
 } }
 Timer { interval: 25000; running: true; onTriggered: Qt.exit(9) }
}'''


@unittest.skipUnless(shutil.which("qs"), "Quickshell requis")
class RechercheHorsEcran(unittest.TestCase):
    def test_de_la_frappe_au_lancement(self):
        os.makedirs("/tmp/claude-1000", exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="ncm-", dir="/tmp/claude-1000") as d:
            root = Path(d)
            q = root / "qml"
            shutil.copytree(QML, q)
            for sous in ("run", "cache", "state", "data", "config", "tmp"):
                (root / sous).mkdir(mode=0o700)
            (q / "Reglages.qml").write_text('''pragma Singleton
import QtQuick
QtObject {
 property var v: ({})
 readonly property bool iaCoupee: true
 readonly property bool en: false
 function t(fr,en){return fr}
 function val(k,d){return v[k] !== undefined ? v[k] : d}
 function pageActive(n){return true}
}''')
            (q / "Etat.qml").write_text('''pragma Singleton
import QtQuick
import Quickshell
QtObject {
 property string saisie: ""
 property string texteIA: ""
 property bool recherche: true
 property bool nuit: false
 readonly property string bin: Quickshell.env("HOME") + "/.local/bin/"
 property int fermetures: 0
 signal validerRecherche()
 function faire(c) {} function fermer() { fermetures++ } function aller(p) {} function basculer(e, c) {}
}''')
            (q / "Partage.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject { property bool silence: false }')
            (q / "AssistantEtat.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject {function formater(t){return t} function sansReseau(t){return t}}')
            (q / "Etincelle.qml").write_text('import QtQuick\nItem {property real taille: 10; property bool tourne: false; property string agent: ""}')
            (q / "CloudEtat.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject { property bool actif: false; property bool associe: false }')
            (q / "Rappels.qml").write_text('pragma Singleton\nimport QtQuick\nQtObject { property var liste: []; property bool plein: false; function analyser(p) { return {ok: false, raison: "heure"} } function quand(d) { return "" } function creer(t, d) { return false } function supprimer(i) {} }')
            noms = ["Reglages", "Etat", "Partage", "AssistantEtat", "Couleurs", "Connexion", "Recherche", "Emoji", "Diagnostic", "Etincelle", "Texte", "Ico"]
            (q / "qmldir").write_text("\n".join(("singleton " if n in ("Reglages", "Etat", "Partage", "AssistantEtat", "Couleurs", "Connexion") else "") + n + " 1.0 " + n + ".qml" for n in noms) + "\nsingleton CloudEtat 1.0 CloudEtat.qml\nsingleton Rappels 1.0 Rappels.qml")
            b = root / ".local/bin"
            b.mkdir(parents=True)
            scripts = {
                "nc-apps": '#!/bin/sh\nprintf "%s\\n" "[]"\n',
                "hyprctl": "#!/bin/sh\nprintf '%s\\n' '[]'\n",
                "nc-aide-config": "#!/bin/sh\nexit 0\n",
                "nc-demander": '#!/bin/sh\ncase "$1" in --ia) printf "%s\\n" \'{"nom": "-", "agent": "claude", "coupee": true}\' ;; esac\n',
                # Faux nc-mdp : note seulement le nombre d'arguments et leur valeur ; ne copie rien
                "nc-mdp": '#!/bin/sh\nprintf "%s\\n" "nc-mdp $# $*" >> "$HOME/appels"\n',
                "wl-copy": '#!/bin/sh\nprintf "%s\\n" "wl-copy $*" >> "$HOME/appels-wl"\n',
            }
            for nom, code in scripts.items():
                (b / nom).write_text(code)
                (b / nom).chmod(0o755)
            (q / "shell.qml").write_text(SCRIPT)
            env = dict(os.environ, HOME=d, XDG_CONFIG_HOME=str(root / "config"), XDG_CACHE_HOME=str(root / "cache"),
                       XDG_STATE_HOME=str(root / "state"), XDG_DATA_HOME=str(root / "data"), XDG_RUNTIME_DIR=str(root / "run"),
                       TMPDIR=str(root / "tmp"), QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software",
                       PATH=str(b) + os.pathsep + os.environ["PATH"])
            for k in ("WAYLAND_DISPLAY", "HYPRLAND_INSTANCE_SIGNATURE", "DISPLAY"):
                env.pop(k, None)
            r = subprocess.run(["qs", "--no-color", "-p", str(q / "shell.qml")], env=env, text=True, capture_output=True, timeout=60,
                               stdin=subprocess.DEVNULL)
            sortie = r.stdout + r.stderr
            self.assertEqual(r.returncode, 0, sortie)
            for erreur in ("ReferenceError", "TypeError", "is not a type", "Binding loop"):
                self.assertNotIn(erreur, sortie)
            appels = (root / "appels").read_text(encoding="utf-8").splitlines()
            self.assertEqual(appels, ["nc-mdp 1 20"], "un seul lancement, après Entrée, avec seulement N")
            self.assertFalse((root / "appels-wl").exists(), "le Spotlight n'appelle jamais wl-copy lui-même")


if __name__ == "__main__":
    unittest.main()
