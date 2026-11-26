"""Mode jeu : « ne pas déranger » revient à l'état d'avant la partie (fichier nc-mode-jeu-dnd dans XDG_RUNTIME_DIR).
Les lignes de shell que energie.lua passe à hl.exec_cmd sont rejouées sous sh avec un faux qs, sans Hyprland."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

NC = Path(__file__).resolve().parents[1] / "home/.config/hypr/nc"
LUA = shutil.which("lua5.4") or shutil.which("lua")

# Le jeu est « en place » (fichier nc-mode-jeu) quand arg[3] vaut « sortie » : nc.mode_jeu() sort alors du jeu.
HARNAIS = r'''
nc = { profil = { profil = "balanced", batterie = false }, t = function(fr) return fr end,
       reglage = function(cle, d) if cle == "JEU_PERFORMANCE" then return false end return d end,
       guillemets = function(s) return "'" .. s .. "'" end }
hl = { config = function() end, animation = function() end, gesture = function() end, device = function() end,
       exec_cmd = function(c) print(c) end }
dofile(arg[1] .. "/clavier.lua")
dofile(arg[1] .. "/energie.lua")
nc.mode_jeu()
'''

FAUX_QS = '''#!/bin/sh
# faux qs : état dans $DND_ETAT, appels notés dans $JOURNAL ; QS_MUET=1 : l'île ne répond pas
echo "$*" >> "$JOURNAL"
[ -n "$QS_MUET" ] && exit 1
case "$*" in
  *concentrationEtat*) cat "$DND_ETAT" ;;
  *"concentrationRegler true"*) echo oui > "$DND_ETAT" ;;
  *"concentrationRegler false"*) echo non > "$DND_ETAT" ;;
esac
'''


@unittest.skipUnless(LUA and all(shutil.which(cmd) for cmd in ("sh", "timeout", "flock")), "lua, sh, timeout et flock requis")
class DndEnModeJeu(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory(prefix="nc-jeu-dnd-")
        self.d = Path(self._t.name)
        self.addCleanup(self._t.cleanup)
        (self.d / "bin").mkdir()
        (self.d / "harnais.lua").write_text(HARNAIS)
        for nom, corps in (("qs", FAUX_QS), ("hyprctl", "#!/bin/sh\n"), ("notify-send", "#!/bin/sh\n"),
                           ("sleep", "#!/bin/sh\n"), ("noctalia", '#!/bin/sh\necho "noctalia $*" >> "$JOURNAL"\n')):
            p = self.d / "bin" / nom
            p.write_text(corps)
            p.chmod(0o755)
        self.etat = self.d / "etat"
        self.env = dict(os.environ, HOME=str(self.d), XDG_RUNTIME_DIR=str(self.d), XDG_CONFIG_HOME=str(self.d),
                        XDG_STATE_HOME=str(self.d), TMPDIR=str(self.d), PATH=f"{self.d / 'bin'}:{os.environ['PATH']}",
                        JOURNAL=str(self.d / "journal"), DND_ETAT=str(self.etat))
        self.env.pop("QS_MUET", None)

    def passer(self, jeu_en_place):
        """Une bascule du mode jeu : la ligne de shell de energie.lua, rejouée."""
        marque = self.d / "nc-mode-jeu"
        marque.write_text("") if jeu_en_place else marque.unlink(missing_ok=True)
        r = subprocess.run([LUA, str(self.d / "harnais.lua"), str(NC)], env=self.env, capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 0, r.stderr)
        cmd = r.stdout.strip()
        r = subprocess.run(["sh", "-c", cmd], env=self.env, capture_output=True, text=True, timeout=20)
        self.assertEqual(r.stderr, "")

    def entrer(self):
        self.passer(False)

    def sortir(self):
        self.passer(True)

    def test_actif_avant_reste_actif_apres(self):
        self.etat.write_text("oui\n")
        self.entrer()
        self.sortir()
        self.assertEqual(self.etat.read_text().strip(), "oui")
        self.assertFalse((self.d / "nc-mode-jeu-dnd").exists())

    def test_inactif_avant_inactif_apres(self):
        self.etat.write_text("non\n")
        self.entrer()
        self.assertEqual(self.etat.read_text().strip(), "oui")
        self.sortir()
        self.assertEqual(self.etat.read_text().strip(), "non")
        self.assertFalse((self.d / "nc-mode-jeu-dnd").exists())

    def test_sortie_pendant_la_notification_annule_la_pause(self):
        self.etat.write_text("non\n")
        # Rejoue la sortie entière avant de rendre la main à l'entrée différée, sans attente réelle.
        (self.d / "bin" / "sleep").write_text(
            '#!/bin/sh\ncmd=$("$LUA" "$XDG_RUNTIME_DIR/harnais.lua" "$NC") && sh -c "$cmd"\n'
        )
        self.env.update(LUA=LUA, NC=str(NC))
        self.entrer()
        self.assertFalse((self.d / "nc-mode-jeu").exists())
        self.assertEqual(self.etat.read_text().strip(), "non")
        self.assertFalse((self.d / "nc-mode-jeu-dnd").exists())
        self.assertNotIn("concentrationRegler true", (self.d / "journal").read_text())
        self.assertNotIn("notification-dnd-set on", (self.d / "journal").read_text())

    def test_entree_deux_fois_ne_crase_pas_letat_davant(self):
        self.etat.write_text("oui\n")
        self.entrer()
        self.entrer()
        self.sortir()
        self.assertEqual(self.etat.read_text().strip(), "oui")
        # et à l'inverse : inactif avant, le second passage (où l'île dit « oui ») ne le change pas
        self.etat.write_text("non\n")
        self.entrer()
        self.entrer()
        self.sortir()
        self.assertEqual(self.etat.read_text().strip(), "non")

    def test_ile_muette_comme_avant(self):
        self.env["QS_MUET"] = "1"
        self.entrer()
        self.assertFalse((self.d / "nc-mode-jeu-dnd").exists())
        self.sortir()
        journal = (self.d / "journal").read_text()
        self.assertIn("noctalia msg notification-dnd-set on", journal)
        self.assertIn("noctalia msg notification-dnd-set off", journal)


if __name__ == "__main__":
    unittest.main()
