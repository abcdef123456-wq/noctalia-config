"""Miniatures du carrousel (nc-carousel-thumbs) : surveillance du vrai dossier des fonds (drop-in du .path), image
illisible non retraitée, restes .tmp.webp nettoyés, hyprctl en échec = rien de régénéré.
Tout se passe dans un dossier temporaire : HOME et XDG_* y pointent, faux magick, hyprctl et systemctl devant dans le PATH."""
import os
import re
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests import _isolation  # noqa: F401

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "home/.local/bin/nc-carousel-thumbs"
PANEL = REPO / "home/.local/share/noctalia/plugins/nc-carousel/panel.luau"
LUA = shutil.which("lua") or shutil.which("lua5.4")
UNITE = REPO / "home/.config/systemd/user/nc-carousel-thumbs.path"

MONITEURS = '[{"width":1920,"height":1080,"scale":1.0}]'


class Miniatures(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="nc-carrousel-")
        self.addCleanup(d.cleanup)
        self.r = Path(d.name)
        self.home = self.r / "home/user"
        self.bin = self.r / "bin"
        self.bin.mkdir()
        self.home.mkdir(parents=True)
        self.journal = self.r / "journal"
        self.journal.touch()
        self.fonds = self.home / "Pictures/Wallpapers"
        self.fonds.mkdir(parents=True)
        self.racine = self.home / ".cache/nc/carousel"
        self.sortie = self.cache(self.fonds)
        # faux magick : écrit la sortie (dernier argument) ; « casse » dans le nom de l'entrée = échec, avec un reste .tmp
        self.faux("magick", 'echo "magick $1" >> "$NC_JOURNAL"\n'
                  'for a; do last="$a"; done\n'
                  'case "$1" in *casse*) echo x > "$last"; exit 1 ;; esac\n'
                  'echo x > "$last"\n')
        self.faux("hyprctl", '[ -e "$NC_SANS_HYPR" ] && exit 1\necho \'' + MONITEURS + "'\n")
        self.faux("systemctl", 'echo "systemctl $*" >> "$NC_JOURNAL"\n'
                  '[ "$2" = is-active ] && exit 0\nexit 0\n')
        self.env = dict(os.environ, HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / ".config"),
                        XDG_STATE_HOME=str(self.home / ".local/state"), XDG_CACHE_HOME=str(self.home / ".cache"),
                        TMPDIR=str(self.r), PATH=f"{self.bin}:{os.environ['PATH']}",
                        NC_JOURNAL=str(self.journal), NC_SANS_HYPR=str(self.r / "sans-hypr"))
        self.env.pop("NOCTALIA_CONFIG_HOME", None)
        self.env.pop("HYPRLAND_INSTANCE_SIGNATURE", None)

    def cache(self, dossier):
        # le sous-dossier du cache d'un dossier de fonds : chaque octet hors [A-Za-z0-9._-] écrit %XX
        return self.racine / "".join(chr(b) if re.match(r"[A-Za-z0-9._-]", chr(b)) else "%%%02X" % b
                                     for b in str(dossier).rstrip("/").encode())

    def faux(self, nom, corps):
        f = self.bin / nom
        f.write_text("#!/bin/sh\n" + corps)
        f.chmod(f.stat().st_mode | stat.S_IEXEC)

    def lance(self, *args):
        return subprocess.run([str(SCRIPT), *args], env=self.env, capture_output=True, text=True, timeout=60, check=False)

    def config(self, dossier, nom="zy-reglages.toml"):
        c = self.home / ".config/noctalia"
        c.mkdir(parents=True, exist_ok=True)
        (c / nom).write_text(f'[wallpaper]\ndirectory = "{dossier}"\n')

    @property
    def dropin(self):
        return self.home / ".config/systemd/user/nc-carousel-thumbs.path.d/dossier.conf"

    # surveillance du vrai dossier

    def test_unite_sans_chemin_de_noctalia_v4(self):
        texte = UNITE.read_text()
        self.assertNotIn("wallpaperCarousel", texte)
        self.assertIn("PathChanged=%h/Pictures/Wallpapers", texte)

    def test_dropin_avec_espace_et_pour_cent(self):
        dossier = self.home / "Mes fonds 100% beaux"
        dossier.mkdir()
        self.config(dossier)
        r = self.lance("--surveillance")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.dropin.read_text(),
                         f"[Path]\nPathChanged=\nPathChanged={self.home}/Mes fonds 100%% beaux\n")
        j = self.journal.read_text()
        self.assertIn("systemctl --user daemon-reload", j)
        self.assertIn("systemctl --user restart nc-carousel-thumbs.path", j)

    def test_dropin_inchange_ne_recharge_pas(self):
        dossier = self.home / "Images"
        dossier.mkdir()
        self.config(dossier)
        self.lance("--surveillance")
        self.journal.write_text("")
        self.lance("--surveillance")
        j = self.journal.read_text()
        self.assertNotIn("daemon-reload", j)
        self.assertNotIn("restart", j)
        self.assertIn("start --no-block nc-carousel-thumbs.service", j)     # les miniatures sont quand même relancées

    def test_dropin_retire_pour_le_defaut(self):
        dossier = self.home / "Images"
        dossier.mkdir()
        self.config(dossier)
        self.lance("--surveillance")
        self.assertTrue(self.dropin.exists())
        self.config(self.home / "Pictures/Wallpapers")
        self.lance("--surveillance")
        self.assertFalse(self.dropin.exists())

    def test_defaut_sans_config_pas_de_dropin(self):
        self.lance("--surveillance")
        self.assertFalse(self.dropin.exists())
        self.assertNotIn("daemon-reload", self.journal.read_text())

    def test_zy_reglages_l_emporte_sur_config(self):
        a = self.home / "A"
        b = self.home / "B"
        a.mkdir()
        b.mkdir()
        self.config(a, "config.toml")
        self.config(b, "zy-reglages.toml")
        self.lance("--surveillance")
        self.assertIn(f"PathChanged={b}\n", self.dropin.read_text())

    # miniatures

    def image(self, nom, mtime=None):
        f = self.fonds / nom
        f.write_text("img")
        if mtime:
            os.utime(f, (mtime, mtime))
        return f

    def test_echec_marque_et_pas_retraite(self):
        self.image("casse.png", 1000)
        self.image("bon.png", 1000)
        self.assertEqual(self.lance().returncode, 0)
        self.assertEqual((self.sortie / "casse.png.echec").read_text().strip(), "1000")
        self.assertFalse((self.sortie / "casse.png.W.webp").exists())
        self.assertTrue((self.sortie / "bon.png.W.webp").exists())
        self.assertFalse(list(self.sortie.glob("*.tmp.webp")))       # reste de l'échec nettoyé
        self.journal.write_text("")
        self.lance()
        self.assertNotIn("casse.png", self.journal.read_text())      # pas de nouvel essai
        self.image("casse.png", 2000)                                # l'image a changé : nouvel essai
        self.lance()
        self.assertIn("casse.png", self.journal.read_text())
        self.assertEqual((self.sortie / "casse.png.echec").read_text().strip(), "2000")

    def test_echec_efface_si_l_image_disparait(self):
        f = self.image("casse.png", 1000)
        self.lance()
        f.unlink()
        self.lance()
        self.assertFalse((self.sortie / "casse.png.echec").exists())

    def test_restes_tmp_nettoyes_au_debut(self):
        self.sortie.mkdir(parents=True)
        (self.sortie / "vieux.png.W.tmp.webp").write_text("x")
        self.lance()
        self.assertFalse(list(self.sortie.glob("*.tmp.webp")))

    def test_hyprctl_en_echec_ne_regenere_rien(self):
        self.image("bon.png")
        self.lance()
        self.assertEqual((self.racine / ".dpr").read_text().strip(), "1.080")
        signature = (self.sortie / ".size").read_text()
        avant = (self.sortie / "bon.png.W.webp").stat().st_mtime_ns
        (self.r / "sans-hypr").touch()
        self.journal.write_text("")
        self.assertEqual(self.lance().returncode, 0)
        self.assertEqual((self.sortie / ".size").read_text(), signature)
        self.assertEqual((self.sortie / "bon.png.W.webp").stat().st_mtime_ns, avant)
        self.assertEqual(self.journal.read_text(), "")

    def test_hyprctl_en_echec_sans_dpr_connu_prend_1_sans_le_garder(self):
        # Première installation hors session : des miniatures quand même (facteur 1), et le vrai facteur plus tard
        self.image("bon.png")
        (self.r / "sans-hypr").touch()
        self.assertEqual(self.lance().returncode, 0)
        self.assertTrue((self.sortie / "bon.png.W.webp").exists())
        self.assertFalse((self.racine / ".dpr").exists())

    def test_hyprctl_en_echec_garde_le_dpr_pour_les_nouvelles_images(self):
        self.image("a.png", 1000)
        self.lance()
        (self.r / "sans-hypr").touch()
        self.image("b.png", 1000)
        self.lance()
        self.assertTrue((self.sortie / "b.png.W.webp").exists())
        self.assertTrue((self.sortie / "a.png.W.webp").exists())

    # B1 : la surveillance et les miniatures suivent le dossier réel à chaque application

    def test_retour_au_defaut_retire_le_dropin_et_fait_les_miniatures(self):
        autre = self.home / "Fonds du thème"
        autre.mkdir()
        (autre / "t.png").write_text("img")
        self.config(autre)
        self.lance("--surveillance")
        self.assertTrue(self.dropin.exists())
        self.lance()
        self.assertTrue((self.cache(autre) / "t.png.W.webp").exists())
        self.image("d.png")
        self.config(self.fonds)                       # un thème sans fonds : retour au dossier par défaut
        self.lance("--surveillance")
        self.assertFalse(self.dropin.exists())
        self.assertFalse(self.dropin.parent.exists())
        self.lance()
        self.assertTrue((self.cache(self.fonds) / "d.png.W.webp").exists())

    def test_surveillance_relance_le_service_meme_sans_changement(self):
        self.lance("--surveillance")
        self.assertIn("start --no-block nc-carousel-thumbs.service", self.journal.read_text())

    def test_reglages_lance_surveillance_a_chaque_application(self):
        src = (REPO / "home/.local/bin/nc-reglages").read_text(encoding="utf-8")
        i = src.index('"--surveillance"')
        self.assertNotIn("FONDS_DOSSIER", src[src.rindex("\n", 0, src.rindex("\n", 0, i - 120)):i])

    # B2 : un cache par dossier

    def test_dossiers_distincts_meme_nom_de_fichier_sans_melange(self):
        a = self.home / "Fonds A"
        b = self.home / "Fonds é/B"
        a.mkdir()
        b.mkdir(parents=True)
        (a / "x.png").write_text("a")
        (b / "x.png").write_text("b")
        self.config(a)
        self.lance()
        self.config(b)
        self.lance()
        self.assertTrue((self.cache(a) / "x.png.W.webp").exists())       # changer de dossier n'efface pas l'autre
        self.assertTrue((self.cache(b) / "x.png.W.webp").exists())
        self.assertNotEqual(self.cache(a), self.cache(b))
        self.assertIn("%C3%A9", str(self.cache(b)))

    def test_aller_retour_sans_regeneration(self):
        a = self.home / "Fonds A"
        a.mkdir()
        (a / "x.png").write_text("a")
        self.image("d.png")
        self.config(a)
        self.lance()
        self.config(self.fonds)
        self.lance()
        self.config(a)
        self.journal.write_text("")
        self.lance()
        self.config(self.fonds)
        self.lance()
        self.assertNotIn("magick", self.journal.read_text())

    def test_ancien_cache_plat_efface_une_fois(self):
        self.racine.mkdir(parents=True)
        for n in ("vieux.png.W.webp", "vieux.png.N.webp", "vieux.png.echec", ".size"):
            (self.racine / n).write_text("x")
        self.image("a.png")
        self.lance()
        self.assertEqual(sorted(p.name for p in self.racine.iterdir() if p.is_file()), [".dpr"])

    def test_orphelins_effaces_dans_le_bon_dossier_seulement(self):
        a = self.home / "Fonds A"
        a.mkdir()
        (a / "x.png").write_text("a")
        self.config(a)
        self.lance()
        self.config(self.fonds)
        self.image("d.png")
        self.lance()
        (self.fonds / "d.png").unlink()
        self.lance()
        self.assertFalse((self.sortie / "d.png.W.webp").exists())
        self.assertTrue((self.cache(a) / "x.png.W.webp").exists())

    def test_borne_de_32_dossiers_efface_les_plus_anciens(self):
        self.racine.mkdir(parents=True)
        for i in range(40):
            d = self.racine / f"vieux{i:02d}"
            d.mkdir()
            os.utime(d, (1000 + i, 1000 + i))         # comparés entre eux, jamais à l'horloge
        self.image("a.png")
        self.lance()
        restes = sorted(p.name for p in self.racine.iterdir() if p.is_dir())
        self.assertEqual(len(restes), 32)
        self.assertEqual(self.sortie.name in restes, True)
        self.assertNotIn("vieux00", restes)
        self.assertIn("vieux39", restes)

    # clé identique en bash et en Luau

    CHEMINS = ["/home/user/Pictures/Wallpapers", "/home/user/Mes fonds 100% beaux", "/home/user/Fonds é à/ü",
               "/home/user/a.b-c_d", "/", "/home/user/a%2Fb", "/home/user/guillemet'et\"deux"]

    def cles_bash(self):
        bloc = SCRIPT.read_text(encoding="utf-8").split("# -- DEBUT cle", 1)[1].split("# -- FIN cle", 1)[0]
        prog = bloc + 'while IFS= read -r l; do cle_dossier "$l"; printf "\\n"; done\n'
        r = subprocess.run(["bash", "-c", prog], input="\n".join(self.CHEMINS) + "\n", capture_output=True,
                           text=True, check=True, env=dict(self.env, LC_ALL="C.UTF-8"))
        return r.stdout.split("\n")[:-1]

    def test_cle_bash_regle(self):
        cles = self.cles_bash()
        self.assertEqual(cles[0], "%2Fhome%2Fuser%2FPictures%2FWallpapers")
        self.assertEqual(cles[1], "%2Fhome%2Fuser%2FMes%20fonds%20100%25%20beaux")
        self.assertEqual(cles[2], "%2Fhome%2Fuser%2FFonds%20%C3%A9%20%C3%A0%2F%C3%BC")
        self.assertEqual(cles[3], "%2Fhome%2Fuser%2Fa.b-c_d")
        self.assertEqual(cles[5], "%2Fhome%2Fuser%2Fa%252Fb")
        self.assertEqual(len(set(cles)), len(cles))

    @unittest.skipUnless(LUA, "lua absent")
    def test_cle_luau_identique_a_bash(self):
        bloc = PANEL.read_text(encoding="utf-8").split("-- DEBUT cle", 1)[1].split("-- FIN cle", 1)[0].split("\n", 1)[1]
        # le Luau ne prend que le dossier tel quel ; les chemins arrivent un par ligne
        prog = bloc + 'for l in io.lines() do io.write(cleDossier(l), "\\n") end\n'
        f = self.r / "cle.lua"
        f.write_text(prog, encoding="utf-8")
        r = subprocess.run([LUA, str(f)], input="\n".join(self.CHEMINS) + "\n", capture_output=True, text=True, check=True)
        self.assertEqual(r.stdout.split("\n")[:-1], self.cles_bash())

    @unittest.skipUnless(LUA, "lua absent")
    def test_fenetre_des_tranches_sans_doublon(self):
        bloc = PANEL.read_text(encoding="utf-8").split("-- DEBUT cle", 1)[1].split("-- FIN cle", 1)[0].split("\n", 1)[1]
        prog = bloc + r"""
local function err(m) error(m, 0) end
for _, reach in ipairs({ 3, 4 }) do
  for _, n in ipairs({ 1, 2, 3, 4, 5, 8, 9, 10, 15 }) do
    for c = -20, 20 do
      for _, frac in ipairs({ 0, 1 }) do
        local fl = c - frac
        local lo, hi = fenetre(n, c, fl, reach)
        local vus = {}
        for i = lo, hi do
          local k = ((i % n) + n) % n
          if vus[k] then err("doublon n=" .. n .. " c=" .. c .. " reach=" .. reach) end
          vus[k] = true
        end
        if not (lo <= c and c <= hi) then err("centre absent n=" .. n) end
        if n >= 2 and not (lo <= fl and fl + 1 <= hi) then err("interpolation absente n=" .. n .. " c=" .. c) end
        if n >= 2 * reach + 2 and (lo ~= c - reach or hi ~= c + reach + 1) then err("fenetre pleine n=" .. n) end
      end
    end
  end
end
io.write("ok")
"""
        f = self.r / "fen.lua"
        f.write_text(prog, encoding="utf-8")
        r = subprocess.run([LUA, str(f)], capture_output=True, text=True, check=False)
        self.assertEqual(r.stdout, "ok", r.stderr)

    # B5 : dans un thème, les fonds du thème PUIS ceux de l'utilisateur

    def theme(self, dossier_theme, utilisateur=None):
        # Noctalia lit le dossier du thème ; style.conf pose FONDS_DOSSIER ; reglages.conf : le dossier de l'utilisateur
        self.config(dossier_theme)
        nc = self.home / ".config/nc"
        nc.mkdir(parents=True, exist_ok=True)
        (nc / "style.conf").write_text(f'FONDS_DOSSIER="{dossier_theme}"\n')
        if utilisateur:
            (nc / "reglages.conf").write_text(f'FONDS_DOSSIER="{utilisateur}/"\n')

    def dossier_theme(self, nom="Fonds du thème"):
        d = self.home / nom
        d.mkdir()
        (d / "t.png").write_text("img")
        return d

    def test_theme_surveille_les_deux_dossiers(self):
        t = self.dossier_theme()
        self.image("u.png")
        self.theme(t)
        self.lance("--surveillance")
        self.assertEqual(self.dropin.read_text(), f"[Path]\nPathChanged=\nPathChanged={t}\nPathChanged={self.fonds}\n")

    def test_theme_dossier_de_l_utilisateur_des_reglages(self):
        t = self.dossier_theme()
        u = self.home / "Mes fonds"
        u.mkdir()
        self.theme(t, u)
        self.lance("--surveillance")
        self.assertEqual(self.dropin.read_text(), f"[Path]\nPathChanged=\nPathChanged={t}\nPathChanged={u}\n")

    def test_theme_sans_doublon_si_meme_dossier(self):
        u = self.home / "Mes fonds"
        u.mkdir()
        self.theme(u, u)                            # le dossier de Noctalia est celui de l'utilisateur : pas dans un thème
        self.lance("--surveillance")
        self.assertEqual(self.dropin.read_text(), f"[Path]\nPathChanged=\nPathChanged={u}\n")
        (u / "a.png").write_text("img")
        self.lance()
        self.assertEqual(self.journal.read_text().count("magick"), 3)       # un seul passage, pas deux

    def test_retour_a_noctalia_retire_le_dropin(self):
        t = self.dossier_theme()
        self.image("u.png")
        self.theme(t)
        self.lance("--surveillance")
        self.assertTrue(self.dropin.exists())
        (self.home / ".config/nc/style.conf").write_text("")      # plus de thème
        self.config(self.fonds)
        self.lance("--surveillance")
        self.assertFalse(self.dropin.exists())

    def test_theme_dossier_absent_sans_erreur_ni_ligne(self):
        t = self.dossier_theme()
        self.theme(t, self.home / "Absent")
        r = self.lance("--surveillance")
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(self.dropin.read_text(), f"[Path]\nPathChanged=\nPathChanged={t}\n")
        r = self.lance()
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertTrue((self.cache(t) / "t.png.W.webp").exists())

    def test_theme_vignettes_des_deux_dossiers(self):
        t = self.dossier_theme()
        self.image("u.png")
        self.theme(t)
        self.lance()
        self.assertTrue((self.cache(t) / "t.png.W.webp").exists())
        self.assertTrue((self.cache(self.fonds) / "u.png.W.webp").exists())
        self.assertFalse((self.cache(t) / "u.png.W.webp").exists())
        j = self.journal.read_text()
        self.assertIn(f"magick {t}/t.png[0]", j)
        self.assertIn(f"magick {self.fonds}/u.png[0]", j)
        self.assertEqual(j.count("magick"), 6)

    def test_borne_de_32_garde_les_deux_dossiers_du_theme(self):
        t = self.dossier_theme()
        self.image("u.png")
        self.theme(t)
        self.lance()
        for i in range(40):
            d = self.racine / f"vieux{i}"
            d.mkdir()
            os.utime(d, (1000 + i, 1000 + i))
        os.utime(self.cache(t), (10, 10))             # les plus anciens, mais en cours
        os.utime(self.cache(self.fonds), (11, 11))
        self.lance()
        self.assertTrue(self.cache(t).exists() and self.cache(self.fonds).exists())

    def test_aide_rotation_dans_un_theme(self):
        src = (REPO / "home/.local/bin/nc-reglages").read_text(encoding="utf-8")
        self.assertIn("la rotation ne tourne que dans", src)
        self.assertIn("les fonds du thème", src)
        self.assertIn("peut être remplacé à la rotation suivante", src)
        self.assertIn("the rotation only cycles", src)

    def lance_liste(self, dir_, reglages="", style="", home="/h/u/"):
        # la logique pure du panneau (bloc « cle »), avec une fausse API de Noctalia ; renvoie « chemin|vignette »
        bloc = PANEL.read_text(encoding="utf-8").split("-- DEBUT cle", 1)[1].split("-- FIN cle", 1)[0].split("\n", 1)[1]
        prog = (f"local DIR, REGLAGES, STYLE, HOME = [==[{dir_}]==], [==[{reglages}]==], [==[{style}]==], [==[{home}]==]\n"
                + bloc + r"""
local fichiers = {
  ["/h/u/Theme"] = { "b.png", "A.jpg", "note.txt" },
  ["/h/u/Pictures/Wallpapers"] = { "z.png" },
  ["/h/u/Mes fonds"] = { "m.png" },
}
local api = {
  listDir = function(d) local l = fichiers[(d:gsub("/$", ""))]; if not l then return nil end
    local c = {} for i, f in ipairs(l) do c[i] = f end return c end,
  fileInfo = function() return { isDir = false } end,
  fileExists = function() return true end,
}
local out = {}
local dossiers = dossiersDuCarrousel(DIR, REGLAGES, STYLE, HOME)
for _, w in ipairs(listerFonds(dossiers, "/c/", api, { png = true, jpg = true })) do out[#out + 1] = w.path .. "|" .. w.thumbW end
io.write(table.concat(out, "\n"))
""")
        f = self.r / "liste.lua"
        f.write_text(prog, encoding="utf-8")
        r = subprocess.run([LUA, str(f)], capture_output=True, text=True, check=False)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.split("\n") if r.stdout else []

    @unittest.skipUnless(LUA, "lua absent")
    def test_liste_theme_puis_utilisateur(self):
        l = self.lance_liste("/h/u/Theme/", 'FONDS_DOSSIER="~/Pictures/Wallpapers/"\n', 'FONDS_DOSSIER="/h/u/Theme"\n')
        self.assertEqual([x.split("|")[0] for x in l], ["/h/u/Theme/A.jpg", "/h/u/Theme/b.png", "/h/u/Pictures/Wallpapers/z.png"])
        self.assertIn("Theme", l[0].split("|")[1])
        self.assertIn("Pictures", l[2].split("|")[1])
        self.assertNotIn("Theme", l[2].split("|")[1])

    @unittest.skipUnless(LUA, "lua absent")
    def test_liste_dossier_des_reglages_et_tilde(self):
        l = self.lance_liste("/h/u/Theme", 'FONDS_DOSSIER="~/Mes fonds/"\n', 'FONDS_DOSSIER="/h/u/Theme"\n')
        self.assertEqual(l[-1].split("|")[0], "/h/u/Mes fonds/m.png")

    @unittest.skipUnless(LUA, "lua absent")
    def test_liste_sans_doublon_ni_theme(self):
        # même dossier des deux côtés, ou pas de thème : un seul passage
        l = self.lance_liste("/h/u/Pictures/Wallpapers", "", 'FONDS_DOSSIER="/h/u/Pictures/Wallpapers"\n')
        self.assertEqual([x.split("|")[0] for x in l], ["/h/u/Pictures/Wallpapers/z.png"])
        l = self.lance_liste("/h/u/Theme", "", "")
        self.assertEqual([x.split("|")[0] for x in l], ["/h/u/Theme/A.jpg", "/h/u/Theme/b.png"])

    # B3 : jamais l'image brute

    def test_panneau_n_affiche_jamais_l_original(self):
        src = PANEL.read_text(encoding="utf-8")
        self.assertNotIn("thumbW = tw or ", src)
        self.assertNotRegex(src, r"thumbW\s*=\s*tw\s+or\s")
        self.assertNotRegex(src, r"thumbN\s*=\s*tn\s+or\s")

    # B6 : réparation à la mise à jour et à l'ouverture de session

    def test_maj_lance_surveillance_en_fond_et_basse_priorite(self):
        src = (REPO / "home/.local/bin/nc-maj").read_text(encoding="utf-8")
        lignes = [l for l in src.splitlines() if "nc-carousel-thumbs" in l and "--surveillance" in l]
        self.assertTrue(lignes)
        for l in lignes:
            self.assertIn("nice -n 19", l)
            self.assertTrue(l.rstrip().endswith("&"), l)

    def test_session_lance_surveillance_en_fond_et_basse_priorite(self):
        src = (REPO / "home/.config/hypr/nc/session.lua").read_text(encoding="utf-8")
        lignes = [l for l in src.splitlines() if "nc-carousel-thumbs" in l]
        self.assertTrue(lignes)
        self.assertIn("exec_cmd", lignes[0])
        self.assertIn("nice -n 19", lignes[0])
        self.assertIn("--surveillance", lignes[0])


@unittest.skipUnless(shutil.which("systemd-analyze"), "systemd-analyze absent")
class Verification(unittest.TestCase):
    def test_unite_et_dropin_valides(self):
        with tempfile.TemporaryDirectory(prefix="nc-carrousel-unite-") as d:
            d = Path(d)
            shutil.copy(UNITE, d / "nc-carousel-thumbs.path")
            shutil.copy(REPO / "home/.config/systemd/user/nc-carousel-thumbs.service", d / "nc-carousel-thumbs.service")
            (d / "nc-carousel-thumbs.path.d").mkdir()
            (d / "nc-carousel-thumbs.path.d/dossier.conf").write_text("[Path]\nPathChanged=\nPathChanged=/tmp/a b/100%%\n")
            r = subprocess.run(["systemd-analyze", "--user", "verify", str(d / "nc-carousel-thumbs.path")],
                               capture_output=True, text=True, check=False,
                               env=dict(os.environ, HOME=str(d), XDG_CONFIG_HOME=str(d)))
            for mot in ("Unknown", "Invalid", "not valid", "Failed", "Bad"):
                self.assertNotIn(mot, r.stderr, r.stderr)


if __name__ == "__main__":
    unittest.main()
