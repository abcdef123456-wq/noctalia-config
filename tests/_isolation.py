"""Garde-fou des tests : aucun test ne touche la vraie session. Posé une seule fois, au chargement des tests
(tests/__init__.py pour python -m unittest, tests/conftest.py pour pytest), avant tout test.

1. Les dossiers XDG (cache, réglages, état, données, runtime) pointent vers un dossier temporaire.
   Un test qui passe dict(os.environ, HOME=…) à un script hérite alors de valeurs sûres, jamais de ~/.cache ni de
   ~/.config de la vraie session (un test de nc-maj avait écrit dans le vrai ~/.cache/nc/maj-annoncee).

2. Un dossier de faux programmes passe en TÊTE du PATH : notify-send, hyprctl, noctalia, wl-copy, wl-paste, wtype,
   grim, playerctl, wpctl, brightnessctl et systemctl (un relecteur avait vu de vraies notifications « Sessions »
   apparaître sur le bureau). Chaque faux écrit « nom arguments » dans le journal ($NC_TEST_JOURNAL) et sort avec 0.
   hyprctl répond « ok », et en JSON (-j) une liste vide ou un objet vide selon la question ; wl-paste ne colle rien.
   - Un test qui veut son propre faux le met devant, dans son PATH, comme avant : le sien passe en premier.
   - Un test qui se fait un PATH minimal (sans /usr/bin) ne voit pas ces faux : il a déjà les siens.
   - Les vrais outils (sh, bash, dash, python, git, flock, timeout…) ne sont pas remplacés.

3. qs (Quickshell) : certains tests ont besoin du vrai, pour charger un fichier QML hors écran (qs -p FICHIER).
   Le faux qs renvoie donc vers le vrai quand il y a -p ou --path, sauf pour l'ipc. Tout le reste (qs ipc …,
   qs -c nc-ile ipc …, qs -c nc-ile qui lancerait la vraie île, qs kill…) est seulement noté au journal.
   Sans vrai qs sur la machine, pas de faux qs : il n'y a pas d'île à protéger, et les tests marqués
   skipUnless(shutil.which("qs")) restent sautés.

4. Un test qui a besoin d'un vrai programme dans un cadre sûr le demande à vrai(nom) (le PATH d'avant le garde-fou) :
   test_notifs met le vrai notify-send devant, sur un bus de session privé (dbus-run-session).
   Un test qui veut la branche « sans session graphique » retire WAYLAND_DISPLAY et HYPRLAND_INSTANCE_SIGNATURE :
   avec le faux qs, l'île répond toujours.

Le dossier temporaire est effacé à la fin des tests."""
import atexit
import os
from pathlib import Path
import shlex
import shutil
import tempfile

# Les faux : nom -> ce qu'ils affichent (après avoir noté leurs arguments au journal)
FAUX = ("notify-send", "hyprctl", "noctalia", "wl-copy", "wl-paste", "wtype", "grim", "playerctl", "wpctl",
        "brightnessctl", "systemctl")

_HYPRCTL = """case " $* " in
  *" -j "*|*" --json "*)
    case " $* " in
      *" activewindow "*|*" activeworkspace "*|*" layers "*|*" devices "*|*" getoption "*|*" version "*|*" cursorpos "*|*" splash "*) echo '{}' ;;
      *) echo '[]' ;;
    esac ;;
  *) echo ok ;;
esac
"""


def vrai(nom):
    """Le vrai programme, cherché dans le PATH d'avant le garde-fou (None s'il manque) : pour un test qui en a besoin
    dans un cadre sûr, comme test_notifs avec notify-send sur un bus de session privé."""
    return shutil.which(nom, path=os.environ.get("NC_TEST_VRAI_PATH", os.environ.get("PATH")))


def _ecrire(chemin, corps):
    chemin.write_text(corps)
    chemin.chmod(0o755)


def _poser_faux(dossier, journal, vrai_qs):
    dossier.mkdir(mode=0o700)
    def note(nom):
        return f'printf "%s\\n" "{nom} $*" >> {shlex.quote(str(journal))}\n'
    for nom in FAUX:
        _ecrire(dossier / nom, "#!/bin/sh\n" + note(nom) + (_HYPRCTL if nom == "hyprctl" else "") + "exit 0\n")
    if vrai_qs:
        note_qs = note("qs")
        _ecrire(dossier / "qs", f"""#!/bin/sh
# Faux qs des tests : le vrai seulement pour un fichier QML (-p, --path), jamais pour l'ipc ni la vraie île
ipc=0; fichier=0
for a in "$@"; do
  case "$a" in
    ipc) ipc=1 ;;
    -p|--path|--path=*) fichier=1 ;;
  esac
done
if [ "$fichier" = 1 ] && [ "$ipc" = 0 ]; then
  exec {shlex.quote(vrai_qs)} "$@"
fi
{note_qs}exit 0
""")


if not os.environ.get("NC_TEST_ISOLE"):
    _racine = Path(tempfile.mkdtemp(prefix="nc-tests-"))
    atexit.register(shutil.rmtree, _racine, True)
    os.environ["NC_TEST_VRAI_RUNTIME"] = os.environ.get("XDG_RUNTIME_DIR", "")
    for _cle, _nom in (("XDG_CACHE_HOME", "cache"), ("XDG_CONFIG_HOME", "config"), ("XDG_STATE_HOME", "state"),
                       ("XDG_DATA_HOME", "data"), ("XDG_RUNTIME_DIR", "run")):
        (_racine / _nom).mkdir(mode=0o700)
        os.environ[_cle] = str(_racine / _nom)
    _vrai_qs = shutil.which("qs") or ""                  # cherché avant de poser les faux
    _faux, _journal = _racine / "faux-bin", _racine / "faux-appels"
    _journal.touch()
    _poser_faux(_faux, _journal, _vrai_qs)
    os.environ["NC_TEST_VRAI_PATH"] = os.environ.get("PATH", "")
    os.environ["PATH"] = str(_faux) + os.pathsep + os.environ.get("PATH", "")
    os.environ["NC_TEST_FAUX"] = str(_faux)
    os.environ["NC_TEST_JOURNAL"] = str(_journal)
    os.environ["NC_TEST_VRAI_QS"] = _vrai_qs
    os.environ["NC_TEST_ISOLE"] = str(_racine)
