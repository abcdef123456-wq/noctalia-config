"""Thèmes : aller sur N'IMPORTE QUEL thème puis revenir à « noctalia » remet à l'octet près tous les fichiers générés
(style.conf, zy-reglages.toml, couleurs de nc-theme-sync…). Liste des thèmes lue dans le dossier, pas en dur : les futurs
thèmes sont couverts. Faux HOME, faux noctalia ; jamais le vrai HOME."""
import hashlib
import json
import os
from pathlib import Path
import unittest

from tests import test_themes as tt

THEMES, ThemeSync = tt.THEMES, tt.ThemeSync

# Mémoire voulue : la palette d'avant le premier thème, gardée pour la remettre. Elle n'existe qu'après un thème à palette.
MEMOIRE = {".config/nc/style-avant"}


def empreintes(racine):
    return {str(p.relative_to(racine)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(racine.rglob("*")) if p.is_file() and not p.is_symlink()}


class Retour(tt.Base):
    def setUp(self):
        super().setUp()
        faux = Path(self.env["PATH"].split(":")[0])
        for n, corps in (("noctalia", 'case "$*" in *color-scheme-get*) printf "wallpaper vibrant\\n";; esac\nexit 0\n'),
                         ("fc-list", "exit 0\n")):
            (faux / n).write_text("#!/bin/sh\n" + corps)
            (faux / n).chmod(0o755)
        (self.home / ".config/noctalia").mkdir(parents=True, exist_ok=True)      # nc-theme-sync lit colors.json
        (self.home / ".config/noctalia/colors.json").write_text(json.dumps(ThemeSync.COULEURS))

    def aller_retour(self, nom):
        r = self.nc("set", "STYLE", "noctalia")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        avant = empreintes(self.home)
        for m in MEMOIRE:                       # présente ou non selon les thèmes déjà essayés : hors comparaison
            avant.pop(m, None)
        self.assertIn(".config/nc/style.conf", avant)
        # Le HOME sert à tous les thèmes de la boucle : chaque « avant » doit égaler le tout premier (HOME neuf + noctalia),
        # sinon le reste laissé par un thème précédent deviendrait la référence du suivant et passerait inaperçu
        ref = getattr(self, "_reference", None)
        if ref is None:
            self._reference = dict(avant)
        else:
            self.assertEqual(avant, ref, f"état noctalia différent du premier avant {nom} (reste d'un thème précédent)")
        r = self.nc("set", "STYLE", nom)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = self.nc("set", "STYLE", "noctalia")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        apres = empreintes(self.home)
        for m in MEMOIRE:
            apres.pop(m, None)
        self.assertEqual(sorted(apres), sorted(avant))
        for f in avant:
            self.assertEqual(apres[f], avant[f], f"{f} change après {nom} puis noctalia")

    def test_chaque_theme(self):
        for p in sorted(THEMES.glob("*.json")):
            with self.subTest(theme=p.stem):
                self.aller_retour(p.stem)

    def test_theme_fabrique_barre_et_dock(self):
        """Le cas de la tranche A : un thème qui retouche [bar.default] et [dock] ; le retour doit tout défaire."""
        self.ecrire_theme("zzz-essai", noctalia={"bar.default": {"position": "bottom", "thickness": 40, "margin_edge": 8},
                                                  "dock": {"radius": 20}})
        self.nc("set", "STYLE", "zzz-essai")
        toml = (Path(self.env.get("XDG_CONFIG_HOME") or self.home / ".config") / "noctalia/zy-reglages.toml").read_text(encoding="utf-8")
        self.assertIn("thickness = 40", toml)             # le thème fabriqué est bien appliqué
        self.assertIn("radius = 20", toml)
        self.aller_retour("zzz-essai")

    def test_theme_fabrique_qui_compose_sa_barre(self):
        """A9 : listes start, center et end, instances t-heure et t-texte, un groupe, une seconde barre bar.bas ; avec ou sans
        BARRE_SYSTEME=non et la pilule VPN de la personne. Le retour à noctalia remet zy-reglages.toml à l'octet, sans bar.bas."""
        from tests import test_barre_composition as tb
        conf = self.home / ".config/noctalia/config.toml"
        conf.write_text(tb.config_installee("plugin"), encoding="utf-8")
        self.ecrire_theme("zzz-barre", noctalia=tb.COMPOSE)
        toml = self.home / ".config/noctalia/zy-reglages.toml"
        for reglages in ({}, {"BARRE_SYSTEME": "non", "VPN_PILULE_BARRE": "oui"}):
            with self.subTest(reglages=reglages):
                for k, v in reglages.items():
                    self.assertEqual(self.nc("set", k, v).returncode, 0)
                self.nc("set", "STYLE", "noctalia")
                self.__dict__.pop("_reference", None)       # réglages changés : nouvelle référence « noctalia »
                avant = toml.read_bytes() if toml.exists() else b""
                r = self.nc("set", "STYLE", "zzz-barre")
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                t = toml.read_text(encoding="utf-8")
                self.assertIn("[bar.bas]", t)                     # le thème fabriqué est bien appliqué
                self.assertIn('"t-heure"', t)
                self.assertEqual("nc/vpn:vpn" in t, bool(reglages))
                self.aller_retour("zzz-barre")
                self.assertEqual(toml.read_bytes() if toml.exists() else b"", avant)
                self.assertNotIn("[bar.bas]", toml.read_text(encoding="utf-8") if toml.exists() else "")
