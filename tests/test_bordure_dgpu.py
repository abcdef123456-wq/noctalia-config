"""hypr/nc/energie.lua : la bordure ne tourne en continu (Performance, secteur) que si la session est rendue par une
carte graphique dédiée. Sur une carte intégrée (Radeon 610M à 165 Hz), elle faisait redessiner tout l'écran à chaque
image : environ la moitié du GPU (mesuré : Hyprland 65 % → 18 %, figée). Hors Hyprland, avec un faux hl et un faux /sys."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ENERGIE = Path(__file__).resolve().parents[1] / "home/.config/hypr/nc/energie.lua"
LUA = shutil.which("lua5.4") or shutil.which("lua")

HARNAIS = r'''
local profil, batterie = arg[2], arg[3] == "1"
nc = { profil = { profil = profil, batterie = batterie }, reglage = function(_, d) return d end,
       t = function(fr) return fr end, guillemets = function(s) return "'" .. s .. "'" end }
local bordure
hl = { config = function() end, exec_cmd = function() end,
       animation = function(a) if a.leaf == "borderangle" then bordure = a end end }
local dpms = os.getenv("NC_TEST_DPMS")      -- « true,false » : un écran par valeur ; absent : pas d'API
if dpms then
    hl.get_monitors = function()
        local l = {}
        for v in dpms:gmatch("[a-z]+") do l[#l + 1] = { name = "X", dpms_status = v == "true" } end
        return l
    end
end
dofile(arg[1])
print(bordure.style == "loop" and "tourne" or "figee")
if arg[4] then
    nc.bordure(arg[4] == "eteint")
    local apres = bordure
    print((apres.style == "loop" and "tourne" or "figee") .. " " .. tostring(apres.speed))
end
'''


@unittest.skipUnless(LUA, "lua requis")
class BordureSurCarteDediee(unittest.TestCase):
    def bordure(self, cartes, profil="performance", batterie=False, aq=None, ecran=None, marque=False, jeu=False, dpms=None):
        """cartes : {"card1": {"vendor": "0x1002", "vram": 512 Mio, "prises": {"eDP-1": "connected"}}}"""
        with tempfile.TemporaryDirectory(prefix="nc-bordure-") as d:
            sysfs = Path(d) / "sys"
            for carte, c in cartes.items():
                dev = sysfs / "class/drm" / carte / "device"
                dev.mkdir(parents=True)
                (dev / "vendor").write_text(c["vendor"] + "\n")
                if "vram" in c:
                    (dev / "mem_info_vram_total").write_text(str(c["vram"]) + "\n")
                if "pcie" in c:   # lien PCIe propre (pp_dpm_pcie) : une vraie carte AMD, pas un APU
                    (dev / "pp_dpm_pcie").write_text(c["pcie"])
                for prise, etat in c.get("prises", {}).items():
                    p = sysfs / "class/drm" / f"{carte}-{prise}"
                    p.mkdir(parents=True)
                    (p / "status").write_text(etat + "\n")
            (Path(d) / "harnais.lua").write_text(HARNAIS)
            env = dict(os.environ, NC_SYSFS=str(sysfs), XDG_RUNTIME_DIR=d)
            env.pop("AQ_DRM_DEVICES", None)
            if aq:
                env["AQ_DRM_DEVICES"] = aq
            if marque:
                (Path(d) / "nc-ecran-eteint").write_text("")
            if jeu:
                (Path(d) / "nc-mode-jeu").write_text("")
            if dpms is not None:
                env["NC_TEST_DPMS"] = dpms
            args = [ecran] if ecran else []
            r = subprocess.run([LUA, str(Path(d) / "harnais.lua"), str(ENERGIE), profil, "1" if batterie else "0", *args],
                               env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(r.returncode, 0, r.stderr)
            return r.stdout.strip() if ecran is None else r.stdout.strip().splitlines()

    # Le portable de l'utilisateur : Radeon 610M (512 Mio) et RTX
    HYBRIDE = {"card1": {"vendor": "0x1002", "vram": 512 * 2 ** 20, "prises": {"eDP-1": "connected"}},
               "card0": {"vendor": "0x10de", "prises": {"eDP-2": "disconnected"}}}
    DEDIEE = {"card1": {"vendor": "0x1002", "vram": 512 * 2 ** 20, "prises": {"eDP-1": "disconnected"}},
              "card0": {"vendor": "0x10de", "prises": {"eDP-2": "connected"}}}

    def test_hybride_figee(self):
        self.assertEqual(self.bordure(self.HYBRIDE), "figee")
        self.assertEqual(self.bordure(self.HYBRIDE, aq="/dev/dri/card1:/dev/dri/card0"), "figee")

    def test_dediee_tourne(self):
        self.assertEqual(self.bordure(self.DEDIEE), "tourne")
        self.assertEqual(self.bordure(self.HYBRIDE, aq="/dev/dri/card0"), "tourne")
        # PC fixe, carte AMD de 8 Gio, écran sur la prise DisplayPort
        fixe = {"card0": {"vendor": "0x1002", "vram": 8 * 2 ** 30, "pcie": "0: 2.5GT/s, x8\n1: 16.0GT/s, x16 *\n",
                          "prises": {"DP-1": "connected"}}}
        self.assertEqual(self.bordure(fixe), "tourne")

    def test_batterie_et_economie_figee(self):
        self.assertEqual(self.bordure(self.DEDIEE, batterie=True), "figee")
        self.assertEqual(self.bordure(self.DEDIEE, profil="power-saver"), "figee")
        self.assertEqual(self.bordure(self.DEDIEE, profil="balanced"), "figee")

    def test_ecran_eteint_pas_de_boucle(self):
        # Écran éteint : calme (vitesse 8), puis la boucle repart au rallumage
        self.assertEqual(self.bordure(self.DEDIEE, ecran="eteint"), ["tourne", "figee 8"])
        self.assertEqual(self.bordure(self.DEDIEE, ecran="allume"), ["tourne", "tourne 100"])
        # Boucle jamais permise : rien ne la lance au rallumage
        self.assertEqual(self.bordure(self.DEDIEE, batterie=True, ecran="allume"), ["figee", "figee 8"])
        self.assertEqual(self.bordure(self.HYBRIDE, ecran="allume"), ["figee", "figee 8"])

    def test_mode_jeu_rallumage_ne_relance_pas_la_boucle(self):
        # Mode jeu : bordure coupée au chargement, et le rallumage de l'écran (nc-ecran on) n'y touche pas
        self.assertEqual(self.bordure(self.DEDIEE, jeu=True, ecran="allume"), ["figee", "figee nil"])
        self.assertEqual(self.bordure(self.DEDIEE, jeu=True, ecran="eteint"), ["figee", "figee nil"])

    def test_rechargement_ecran_eteint_sans_marque(self):
        # Écran éteint par un autre chemin que nc-ecran (pas de marque) : le chargement lit dpms_status de Hyprland
        self.assertEqual(self.bordure(self.DEDIEE, dpms="false"), "figee")
        self.assertEqual(self.bordure(self.DEDIEE, dpms="false,false"), "figee")
        # Un écran encore allumé, aucun écran connu (démarrage) : la boucle reste
        self.assertEqual(self.bordure(self.DEDIEE, dpms="false,true"), "tourne")
        self.assertEqual(self.bordure(self.DEDIEE, dpms=""), "tourne")
        self.assertEqual(self.bordure(self.DEDIEE, dpms="true"), "tourne")

    def test_rechargement_ecran_eteint_ne_relance_pas_la_boucle(self):
        # La marque de nc-ecran existe : le chargement de la config donne tout de suite la version calme
        self.assertEqual(self.bordure(self.DEDIEE, marque=True), "figee")
        self.assertEqual(self.bordure(self.DEDIEE, marque=False), "tourne")

    def test_apu_amd_avec_vram_reservee_figee(self):
        # APU AMD qui réserve 2 Gio ou plus : pas de lien PCIe propre (fichier absent, ou vide), donc pas une carte dédiée
        for pcie in ({}, {"pcie": ""}):
            apu = {"card0": {"vendor": "0x1002", "vram": 4 * 2 ** 30, "prises": {"eDP-1": "connected"}, **pcie}}
            self.assertEqual(self.bordure(apu), "figee", pcie)
            self.assertEqual(self.bordure(apu, aq="/dev/dri/card0"), "figee", pcie)
        # La même quantité de mémoire sur une vraie carte AMD (portable à MUX, écran interne sur la dGPU) : la boucle tourne
        dgpu = {"card0": {"vendor": "0x1002", "vram": 4 * 2 ** 30, "pcie": "1: 16.0GT/s, x16 *\n",
                          "prises": {"eDP-1": "connected"}}}
        self.assertEqual(self.bordure(dgpu), "tourne")

    def test_doute_figee(self):
        self.assertEqual(self.bordure({}), "figee")
        intel = {"card0": {"vendor": "0x8086", "prises": {"eDP-1": "connected"}}}
        self.assertEqual(self.bordure(intel), "figee")


if __name__ == "__main__":
    unittest.main()
