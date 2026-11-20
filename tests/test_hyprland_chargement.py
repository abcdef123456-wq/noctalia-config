"""hyprland.lua : chaque module passe par nc.charger (une erreur n'arrête pas les suivants, elle est signalée une fois),
et les écrans réglés dans perso.lua ne sont pas écrasés par nc/ecrans.lua. Faux `hl`, jamais le vrai Hyprland."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

HYPR = Path(__file__).resolve().parents[1] / "home/.config/hypr"

# Faux hl : MODE_BIND=casse fait lever hl.bind ; NOTIF=exec retire hl.notification (cas sans l'API)
ENTETE = r'''
package.path = os.getenv("CFG") .. "/?.lua;" .. package.path
local proxy; proxy = setmetatable({}, { __index = function() return proxy end, __call = function() return proxy end })
local mons = {
  { name = "DP-1", width = 3840, height = 2160, scale = 1, x = 0, y = 0, description = "a", physical_width = 600, physical_height = 340 },
  { name = "HDMI-A-1", width = 3840, height = 2160, scale = 1, x = 3840, y = 0, description = "b", physical_width = 600, physical_height = 340 },
}
last, specs, handlers, notifs, execs, nbinds = {}, {}, {}, {}, {}, 0
hl = {
  version = function() return "0.55.2" end, config = function() end, env = function() end,
  on = function(e, f) handlers[e] = handlers[e] or {}; table.insert(handlers[e], f) end,
  exec_cmd = function(c) execs[#execs + 1] = c end,
  bind = function(k)
    if os.getenv("MODE_BIND") == "casse" or (type(k) == "string" and k:find("BIDON")) then error("invalid modifier") end
    nbinds = nbinds + 1
    return {}
  end,
  monitor = function(s) if s.output == "PIEGE" then error("spec invalide") end last[s.output] = s.scale; specs[s.output] = s end,
  get_monitors = function() return mons end, get_active_monitor = function() return mons[1] end,
  get_windows = function() return {} end, get_active_window = function() end, get_active_workspace = function() end,
  get_config = function() return nil end, curve = function() end, animation = function() end, window_rule = function() end,
  layer_rule = function() end, workspace_rule = function() end, gesture = function() end, device = function() end,
  define_submap = function(n, f) f() end, timer = function() end, dsp = proxy, dispatch = function() end,
  get_cursor_pos = function() end,
  notification = { create = function(t) notifs[#notifs + 1] = t end },
}
if os.getenv("NOTIF") == "exec" then hl.notification = nil end
'''


@unittest.skipUnless(shutil.which("lua"), "Lua requis")
class Chargement(unittest.TestCase):
    def lancer(self, apres, perso=None, env=None, conf=None, ecrans=None):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            cfg = home / ".config/hypr"
            cfg.mkdir(parents=True)
            (cfg / "hyprland.lua").symlink_to(HYPR / "hyprland.lua")
            (cfg / "nc").symlink_to(HYPR / "nc")
            if conf:
                (home / ".config/nc").mkdir(parents=True, exist_ok=True)
                (home / ".config/nc/raccourcis.conf").write_text(conf)
            if ecrans:
                (home / ".config/nc").mkdir(parents=True, exist_ok=True)
                (home / ".config/nc/ecrans.conf").write_text(ecrans)
            if perso:
                (cfg / "perso.lua").write_text(perso)
            e = dict(os.environ, HOME=str(home), CFG=str(cfg), XDG_CONFIG_HOME=str(home / ".config"), NC_LANGUE="fr")
            e.update(env or {})
            code = ENTETE + f'dofile("{cfg}/hyprland.lua")\n' + apres
            r = subprocess.run(["lua", "-"], input=code, text=True, capture_output=True, timeout=30, env=e)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            return r.stdout

    def test_statique_aucun_require_nu(self):
        src = (HYPR / "hyprland.lua").read_text()
        self.assertIsNone(re.search(r'^\s*require\(', src, re.M), "tout passe par nc.charger")
        self.assertIn('nc.charger("perso")', src)
        self.assertIn("nc.signaler_echecs()", src)

    def test_module_en_echec_n_arrete_pas_les_suivants(self):
        out = self.lancer('print("suite", nc.mode_jeu ~= nil, #notifs, notifs[1] and (notifs[1].text:gsub("\\n", " ")))',
                          env={"MODE_BIND": "casse"})
        ligne = out.strip().splitlines()[-1].split("\t")
        self.assertEqual(ligne[1], "true", "un module après nc.raccourcis est quand même chargé : " + out)
        self.assertEqual(ligne[2], "1", "une seule notification")
        self.assertIn("nc.raccourcis", ligne[3])

    def test_sans_echec_pas_de_notification(self):
        out = self.lancer('print("n", #notifs, #nc.echecs)')
        self.assertEqual(out.strip().splitlines()[-1].split("\t")[1:], ["0", "0"], out)

    def test_repli_notify_send(self):
        out = self.lancer('local n = 0 for _, c in ipairs(execs) do if c:find("notify%-send") then n = n + 1 end end print("n", n)',
                          env={"MODE_BIND": "casse", "NOTIF": "exec"})
        self.assertEqual(out.strip().splitlines()[-1].split("\t")[1], "1", out)

    def test_perso_en_echec_signale(self):
        out = self.lancer('print("n", #notifs, notifs[1] and (notifs[1].text:gsub("\\n", " ")))', perso='error("boum")')
        l = out.strip().splitlines()[-1].split("\t")
        self.assertEqual(l[1], "1", out)
        self.assertIn("perso", l[2])

    def test_ecran_de_perso_garde_son_echelle(self):
        perso = 'hl.monitor({ output = "HDMI-A-1", mode = "preferred", position = "auto", scale = 1 })\n'
        # l'échelle calculée ne vaut 1 pour personne : on force un écran 4K de 27" -> échelle > 1 hors perso
        apres = r'''
for _, m in ipairs(hl.get_monitors()) do m.physical_width = 600 end
last["HDMI-A-1"] = nil; last["DP-1"] = nil
nc.ecrans_infos_poser({ ["HDMI-A-1"] = { modes = { "3840x2160@60.00Hz" }, pw = 600, ph = 340, reserved = {} } })
print("a", last["HDMI-A-1"], last["DP-1"])
last["HDMI-A-1"] = nil
for _, f in ipairs(handlers["monitor.added"]) do f() end
print("b", last["HDMI-A-1"], last["DP-1"], nc.ecrans_perso["HDMI-A-1"] ~= nil, hl.monitor ~= nil)
'''
        out = self.lancer(apres, perso=perso).strip().splitlines()
        a = out[-2].split("\t"); b = out[-1].split("\t")
        self.assertEqual(a[1], "nil", "ecrans_infos_poser ne réapplique pas l'écran de perso")
        self.assertNotEqual(a[2], "nil", "les autres écrans sont réappliqués")
        self.assertEqual(b[1], "nil", "monitor.added non plus")
        self.assertEqual(b[3], "true")

    def test_ecran_virtuel_ne_relance_pas_le_verrou(self):
        apres = r'''
local function n_verrou()
  local n = 0 for _, c in ipairs(execs) do if c:find("nc%-verrou%-place") then n = n + 1 end end return n
end
local function ajout(m) local avant = n_verrou() for _, f in ipairs(handlers["monitor.added"]) do f(m) end return n_verrou() - avant end
print("v", ajout({ name = "HEADLESS-2" }), ajout({ name = "FALLBACK" }), ajout({ name = "DP-1" }), ajout(nil))
'''
        v = self.lancer(apres).strip().splitlines()[-1].split("\t")
        self.assertEqual(v[1:], ["0", "0", "1", "1"], "écran virtuel : rien ; écran réel ou inconnu : relancé")

    def test_ecran_de_perso_en_prefixe_desc(self):
        # Hyprland compare « desc:… » au DÉBUT de la description (CMonitor::matchesStaticSelector)
        perso = 'hl.monitor({ output = "desc:b", scale = 1 })\n'
        apres = r'''
last["HDMI-A-1"] = nil; last["DP-1"] = nil
nc.ecrans_infos_poser({})
print("a", last["HDMI-A-1"], last["DP-1"] ~= nil)
'''
        a = self.lancer(apres, perso=perso).strip().splitlines()[-1].split("\t")
        self.assertEqual(a[1:], ["nil", "true"], "description « b » : préfixe de la description de HDMI-A-1")

    def test_hl_monitor_qui_leve_ne_bloque_pas_la_regle(self):
        perso = 'hl.monitor({ output = "PIEGE" })\n'   # le faux hl.monitor lève pour PIEGE
        out = self.lancer('print("n", nc.ecrans_perso["PIEGE"], #nc.echecs)', perso=perso).strip().splitlines()[-1].split("\t")
        self.assertEqual(out[1], "nil", "sortie non notée quand hl.monitor lève")
        apres = r'''
last["HDMI-A-1"] = nil
nc.ecrans_infos_poser({})
print("a", last["HDMI-A-1"] ~= nil)
'''
        perso2 = 'pcall(hl.monitor, { output = "HDMI-A-1", scale = 1, bidon = true }) pcall(function() hl.monitor({ output = "PIEGE" }) end)\n'
        out = self.lancer(apres, perso=perso2).strip().splitlines()[-1].split("\t")
        self.assertEqual(out[1], "false", "contrôle : HDMI-A-1 posé par perso est bien sauté")

    # ── perso.lua garde le matériel, la projection (ecrans.conf) garde le placement ──
    PERSO_HW = 'hl.monitor({ output = "%s", mode = "1920x1080@60", position = "9999x9999", scale = 1.5, transform = 1 })\n'
    SPEC = 'local s = specs["HDMI-A-1"] print("s", s.mode, s.scale, s.transform, s.position, s.mirror, s.disabled, s.output)'

    def spec_hdmi(self, perso, ecrans, apres=""):
        out = self.lancer(apres + 'print("fin")\nnc.ecrans_infos_poser({})\n' + self.SPEC, perso=perso, ecrans=ecrans)
        return out.strip().splitlines()[-1].split("\t")[1:]

    def test_projection_sur_ecran_de_perso_chaque_cote_et_mode(self):
        for cote, auto in (("droite", "auto-right"), ("gauche", "auto-left"), ("haut", "auto-up"), ("bas", "auto-down")):
            with self.subTest(cote=cote):
                s = self.spec_hdmi(self.PERSO_HW % "HDMI-A-1", f"ECRAN\tetendre\t{cote}\tb\n")
                self.assertEqual(s, ["1920x1080@60", "1.5", "1", auto, "nil", "nil", "HDMI-A-1"])
        s = self.spec_hdmi(self.PERSO_HW % "HDMI-A-1", "ECRAN\tmiroir\tdroite\tb\n")
        self.assertEqual(s[:3] + s[4:], ["1920x1080@60", "1.5", "1", "DP-1", "nil", "HDMI-A-1"])
        self.assertNotEqual(s[3], "9999x9999")
        s = self.spec_hdmi(self.PERSO_HW % "HDMI-A-1", "ECRAN\tpc\tdroite\tb\n")
        self.assertEqual(s[4:], ["nil", "true", "HDMI-A-1"], "éteint : plus de matériel")

    def test_projection_reconnait_nom_et_desc_dans_les_deux_sens(self):
        for sortie in ("HDMI-A-1", "desc:b"):
            with self.subTest(sortie=sortie):    # ecrans.conf retient par description (b)
                s = self.spec_hdmi(self.PERSO_HW % sortie, "ECRAN\tetendre\tgauche\tb\n")
                self.assertEqual(s[:4], ["1920x1080@60", "1.5", "1", "auto-left"])

    def test_projection_par_nom_quand_pas_de_description(self):
        apres = 'for _, m in ipairs(hl.get_monitors()) do m.description = "" end\n'
        s = self.spec_hdmi(self.PERSO_HW % "HDMI-A-1", "ECRAN\tetendre\tbas\tHDMI-A-1\n", apres)
        self.assertEqual(s[:4], ["1920x1080@60", "1.5", "1", "auto-down"])

    def test_sans_entree_perso_passe_tel_quel_position_comprise(self):
        s = self.spec_hdmi(self.PERSO_HW % "HDMI-A-1", "ECRAN\tetendre\tbas\tautre\n")
        self.assertEqual(s[:4], ["1920x1080@60", "1.5", "1", "9999x9999"])
        s = self.spec_hdmi(self.PERSO_HW % "HDMI-A-1", None)
        self.assertEqual(s[:4], ["1920x1080@60", "1.5", "1", "9999x9999"])

    def test_meme_resultat_au_premier_chargement_et_au_rechargement(self):
        perso = self.PERSO_HW % "HDMI-A-1"
        ecrans = "ECRAN\tetendre\thaut\tb\n"
        premier = self.spec_hdmi(perso, ecrans)
        recharge = self.spec_hdmi(perso, ecrans, 'for k in pairs(package.loaded) do if k:match("^nc%.") or k == "perso" then package.loaded[k] = nil end end\n'
                                   'last, specs = {}, {}\ndofile(os.getenv("CFG") .. "/hyprland.lua")\n')
        self.assertEqual(premier, recharge)
        self.assertEqual(premier[3], "auto-up")

    def test_spec_invalide_de_perso_ne_note_rien_et_la_projection_s_applique(self):
        s = self.spec_hdmi('hl.monitor({ output = "PIEGE" })\n', "ECRAN\tetendre\thaut\tb\n")
        self.assertEqual(s[3], "auto-up")
        self.assertEqual(self.lancer('print("n", next(nc.ecrans_perso))', perso='pcall(hl.monitor, { output = "PIEGE" })\n')
                         .strip().splitlines()[-1].split("\t")[1], "nil")

    def test_change_invalide_ne_casse_pas_raccourcis(self):
        conf = "change\t64:code:36\tBIDON + x\n"
        out = self.lancer('local n = 0 for _, e in ipairs(nc.echecs) do n = n + 1 end print("n", n, nbinds, #notifs)',
                          conf=conf).strip().splitlines()[-1].split("\t")
        self.assertEqual(out[1], "0", "nc.raccourcis ne figure pas dans nc.echecs")
        self.assertGreater(int(out[2]), 20, "les autres raccourcis sont posés")
        self.assertEqual(out[3], "0")

    def test_coupe_du_message_sur_un_caractere_entier(self):
        perso = 'error(string.rep("a", 159) .. "éé fin", 0)'
        out = self.lancer('print("n", notifs[1].text)', perso=perso)
        texte = out.split("\t", 1)[1] if "\t" in out else out
        texte.encode("utf-8")            # lève si un octet est coupé en deux
        self.assertIn("\n" + "a" * 159, texte)
        self.assertNotIn("\ufffd", texte)

    def test_sans_perso_les_ecrans_sont_reappliques(self):
        apres = 'last["HDMI-A-1"] = nil nc.ecrans_infos_poser({}) print("a", last["HDMI-A-1"] ~= nil, next(nc.ecrans_perso))'
        out = self.lancer(apres).strip().splitlines()[-1].split("\t")
        self.assertEqual(out[1], "true")


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(shutil.which("lua"), "Lua requis")
class PleinEcranEpinglee(unittest.TestCase):
    """Super + F sur une fenêtre flottante (épinglée ou non) : elle passe en plein écran, puis retrouve sa place et sa
    taille exactes (Hyprland ne garde que la taille) ; une épinglée est permise (binds.allow_pin_fullscreen)."""
    def test_super_f_garde_puis_rend_la_place(self):
        entete = ENTETE.replace(
            "  bind = function(k)\n",
            "  bind = function(k, f) touches = touches or {}; touches[k] = f\n").replace(
            "dsp = proxy, dispatch = function() end,",
            "dsp = setmetatable({ window = setmetatable({"
            " fullscreen_state = function(t) return { 'plein', t.action } end,"
            " resize = function(t) return { 'taille', t.x, t.y } end,"
            " move = function(t) return { 'place', t.x, t.y } end }, { __index = function() return proxy end }) },"
            " { __index = function() return proxy end }),"
            " dispatch = function(a) if type(a) == 'table' and a[1] then faits[#faits + 1] = table.concat(a, ' ', 1, #a) end end,")
        entete = entete.replace("last, specs, handlers, notifs, execs, nbinds = {}, {}, {}, {}, {}, 0", "last, handlers, notifs, execs, nbinds, faits = {}, {}, {}, {}, 0, {}")
        apres = r'''
local f = touches["SUPER + code:41"]
assert(type(f) == "function", "Super + F est une fonction")
local fen = { address = "0xabc", floating = true, pinned = true, fullscreen = 0, at = { x = 300, y = 200 }, size = { x = 800, y = 500 } }
hl.get_active_window = function() return fen end
f()
fen.fullscreen = 2; fen.at = { x = 0, y = 0 }; fen.size = { x = 3840, y = 2160 }
f()
for _, l in ipairs(faits) do print(l) end
for _, h in ipairs(handlers["window.close"] or {}) do h({ address = "0xabc" }) end
print("reste", nc.places_plein_ecran["0xabc"] == nil)
'''
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            cfg = home / ".config/hypr"
            cfg.mkdir(parents=True)
            (cfg / "hyprland.lua").symlink_to(HYPR / "hyprland.lua")
            (cfg / "nc").symlink_to(HYPR / "nc")
            e = dict(os.environ, HOME=str(home), CFG=str(cfg), XDG_CONFIG_HOME=str(home / ".config"), NC_LANGUE="fr")
            r = subprocess.run(["lua", "-"], input=entete + f'dofile("{cfg}/hyprland.lua")\n' + apres, text=True,
                               capture_output=True, timeout=30, env=e)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        lignes = r.stdout.strip().splitlines()
        self.assertEqual(lignes[-5:], ["plein toggle", "plein toggle", "taille 800 500", "place 300 200", "reste\ttrue"])
        self.assertIn("allow_pin_fullscreen = true", (HYPR / "nc/apparence.lua").read_text())


@unittest.skipUnless(shutil.which("lua"), "Lua requis")
class BindsSouris(unittest.TestCase):
    """Forme des raccourcis souris : jamais mouse = true avec click, drag, release, repeating ou locked. Hyprland 0.57 le
    refuse (« hl.bind: mouse is exclusive », signalé dans le bandeau d'erreurs même sous pcall), 0.56 l'ignore en Lua.
    Le faux hl.bind refuse comme 0.57 ; les vrais déplacements et redimensionnements gardent mouse = true."""
    APRES = r'''
for _, b in ipairs(vus) do print(b) end
for _, r in ipairs(refus) do print("REFUS " .. r) end
'''

    def lancer(self, saisie):
        entete = ENTETE.replace("last, specs, handlers, notifs, execs, nbinds = {}, {}, {}, {}, {}, 0",
                                "last, handlers, notifs, execs, nbinds, vus, refus = {}, {}, {}, {}, 0, {}, {}").replace(
            "  bind = function(k)\n",
            "  bind = function(k, f, o)\n"
            "    o = o or {}\n"
            "    if o.mouse and (o.click or o.drag or o.release or o.repeating or o.locked) then\n"
            "      refus[#refus + 1] = tostring(k); error('hl.bind: mouse is exclusive')\n"
            "    end\n"
            "    local d = {}\n"
            "    for _, n in ipairs({ 'mouse', 'click', 'drag' }) do if o[n] then d[#d + 1] = n end end\n"
            "    if (o.click or o.release) and tostring(k):find('mouse:27[2-6]') then\n"
            "      print('RELACHEMENT', tostring(k), o.click and 'click' or 'release', o.mouse and 'mouse' or '-', o.transparent and 'transparent' or 'masque')\n"
            "    end\n"
            "    if tostring(k):find('mouse:27[2-6]') then vus[#vus + 1] = tostring(k) .. ' ' .. table.concat(d, ',') end\n").replace(
            "    return {}\n  end,", "    return { click = o.click == true, drag = o.drag == true, remove = function() end }\n  end,")
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            cfg = home / ".config/hypr"
            cfg.mkdir(parents=True)
            (cfg / "hyprland.lua").symlink_to(HYPR / "hyprland.lua")
            (cfg / "nc").symlink_to(HYPR / "nc")
            (home / ".config/nc").mkdir(parents=True)
            (home / ".config/nc/reglages.conf").write_text(f"SAISIE={saisie}\n")
            e = dict(os.environ, HOME=str(home), CFG=str(cfg), XDG_CONFIG_HOME=str(home / ".config"), NC_LANGUE="fr")
            r = subprocess.run(["lua", "-"], input=entete + f'dofile("{cfg}/hyprland.lua")\n' + self.APRES, text=True,
                               capture_output=True, timeout=30, env=e)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout.strip().splitlines()

    def test_aucun_refus_quelle_que_soit_la_saisie(self):
        for saisie in ("clavier", "souris", "les-deux"):
            with self.subTest(saisie=saisie):
                lignes = self.lancer(saisie)
                self.assertEqual([l for l in lignes if l.startswith("REFUS")], [])
                self.assertIn("SUPER + mouse:272 mouse", lignes, "le vrai déplacement garde mouse = true")

    def test_chaque_relachement_souris_est_transparent_sans_mouse(self):
        """Hyprland 0.57 : l'appui consommé par le déplacement masque tout raccourci de relâchement sur la même touche, sauf
        transparent (shadowBinds). Le bouton Précédent / Suivant (click) et le rangement de l'aimant (release) seraient morts."""
        lignes = [l.split("\t")[1:] for l in self.lancer("les-deux") if l.startswith("RELACHEMENT")]
        attendus = [["mouse:275", "click", "-", "transparent"], ["mouse:276", "click", "-", "transparent"],
                    ["mouse:275", "release", "-", "transparent"], ["SUPER + mouse:272", "release", "-", "transparent"]]
        for attendu in attendus:
            self.assertIn(attendu, lignes)
        self.assertEqual([l for l in lignes if l[3] != "transparent"], [])

    def test_boutons_lateraux_clic_et_glisser_sans_mouse(self):
        lignes = self.lancer("les-deux")
        # l'aimantation (nc/aimant.lua) : un raccourci à l'appui et un au relâchement (tests/test_aimant.py), sans drag
        for attendu in ("mouse:275 mouse", "mouse:276 mouse", "mouse:275 click", "mouse:276 click", "mouse:275 ",
                        "SUPER + mouse:272 "):
            self.assertIn(attendu, lignes)

    def test_statique_mouse_toujours_litteral_et_seul(self):
        # Une table d'options qui pose mouse ne pose ni click, ni drag, ni release, ni repeating, ni locked, et mouse
        # vaut toujours le littéral true (« mouse = drapeau == "click" » a causé l'erreur en 0.57)
        for f in sorted((HYPR / "nc").glob("*.lua")) + [HYPR / "hyprland.lua"]:
            for t in re.findall(r"\{[^{}]*\bmouse\s*=[^{}]*\}", f.read_text(encoding="utf-8")):
                with self.subTest(fichier=f.name, table=t):
                    self.assertRegex(t, r"\bmouse\s*=\s*true\s*[,}]")
                    self.assertNotRegex(t, r"\b(click|drag|release|repeating|locked)\s*=")
