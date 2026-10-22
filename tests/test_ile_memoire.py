"""La mémoire de l'île au démarrage (mesurée sur l'île Quickshell, 30 s après son lancement, un écran) :
- qs alloue avec jemalloc, qui ouvre quatre arènes par cœur (64 sur 16 cœurs) : chaque fil en entame une. Deux suffisent
  (nc-ile.service, MALLOC_CONF=narenas:2) : environ 50 Mo de mémoire anonyme en moins.
- L'emblème animé de JARVIS (LogoAssistant, atlas PNG de 1024 x 704) n'est créé que quand il se montre : dans la pilule,
  toujours chargée, il était décodé dès le démarrage, pilule JARVIS cachée."""
from pathlib import Path
import re
import unittest

RACINE = Path(__file__).resolve().parents[1]
QML = RACINE / "home/.config/quickshell/nc-ile"
SERVICE = RACINE / "home/.config/systemd/user/nc-ile.service"


class Memoire(unittest.TestCase):
    def test_service_deux_arenes(self):
        service = SERVICE.read_text()
        bloc = service[service.index("[Service]"):]
        self.assertRegex(bloc, r"(?m)^Environment=MALLOC_CONF=narenas:2$",
                         "nc-ile.service : sans narenas:2, jemalloc garde 64 arènes à moitié vides")

    def test_logo_assistant_charge_a_la_demande(self):
        # Fichiers toujours chargés (l'île fermée) : l'emblème n'y est créé que par un Loader (sourceComponent)
        for nom in ("Ile.qml", "Compact.qml", "Etincelle.qml"):
            with self.subTest(nom):
                source = (QML / nom).read_text()
                for m in re.finditer(r"\bLogoAssistant\s*\{", source):
                    avant = source[:m.start()]
                    i = avant.rfind("sourceComponent:")
                    # Encore dans le composant du Loader : ses accolades ouvertes ne sont pas toutes refermées
                    dedans = i >= 0 and (avant[i:].rstrip().endswith("sourceComponent:")
                                         or avant[i:].count("{") > avant[i:].count("}"))
                    self.assertTrue(dedans, nom + " : LogoAssistant créé au démarrage (atlas PNG décodé pour rien) ; "
                                                  "le mettre dans un Loader actif seulement quand il se montre")



class PasPourLesEnfants(unittest.TestCase):
    """MALLOC_CONF (2 arènes) ne vaut que pour l'île : les applis lancées par nc-launch, nvidia-run ou nc-apps n'en
    héritent pas (un programme très multithreadé avec jemalloc serait ralenti, sans lien visible avec l'île)."""
    def test_nc_launch_retire_la_variable(self):
        import os, subprocess, tempfile
        racine = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run([str(racine / "home/.local/bin/nc-launch"), "sh", "-c", 'echo "[${MALLOC_CONF-absent}]"'],
                               env=dict(os.environ, HOME=d, XDG_RUNTIME_DIR=d, MALLOC_CONF="narenas:2"),
                               capture_output=True, text=True, timeout=10)
            self.assertEqual(r.stdout.strip(), "[absent]", r.stderr)

    def test_lanceurs(self):
        racine = Path(__file__).resolve().parents[1] / "home/.local/bin"
        for nom, motif in (("nc-launch", "unset MALLOC_CONF"), ("nvidia-run", "unset MALLOC_CONF"),
                           ("nc-apps", 'os.environ.pop("MALLOC_CONF", None)')):
            with self.subTest(nom):
                self.assertIn(motif, (racine / nom).read_text())


if __name__ == "__main__":
    unittest.main()
