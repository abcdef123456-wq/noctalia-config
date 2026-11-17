"""Carte Proton du panneau « Réseau privé » : « vérification en cours… » (jamais « bientôt » puis « indisponible »),
et une lecture automatique périmée ne remet pas l'ancien état. Hors écran, vrai qs, faux nc-vpn à réponse et délai par appel."""
import json
import unittest
from unittest import mock

from tests import test_vpn_qml as T


def proton(etat, pays=()):
    return dict(id="proton", nom="Proton VPN", etat=etat, message="", pays=[dict(code=c, nom=n) for c, n in pays], pays_actif="",
                connecte=False, peut_login=False, probleme="", pilotage="direct", pays_probleme="")


def nord(etat):
    return dict(id="nord", nom="NordVPN", etat=etat, message="", pays=[], pays_actif="", connecte=False, peut_login=False,
                probleme="", pilotage="direct", pays_probleme="")


PAYS = (("fr", "France"), ("de", "Allemagne"))
# Seul changement du faux nc-vpn : « fournisseurs-json » répond selon SC["auto-N"] / SC["verif-N"] (à défaut, la dernière entrée précédente) = {"delai": s, "rep": [fournisseurs]}
BLOC = '''SC = json.loads(%r)
if a[:1] == ["fournisseurs-json"]:
    k = "verif" if "--verifier-proton" in a else "auto"
    n = sum(1 for l in open(H + "/appels") if json.loads(l)[:1] == ["fournisseurs-json"] and ("--verifier-proton" in json.loads(l)) == (k == "verif")) - 1
    s = next((SC[x] for x in ("%%s-%%d" %% (k, i) for i in range(n, -1, -1)) if x in SC), None)
    if s:
        time.sleep(s["delai"])
        print(json.dumps(dict(contrat=1, fournisseurs=s["rep"])))
    sys.exit(0)
'''
ENTREE = 'if a[:1] == ["etat-json"]:'
ETAT = dict(disponible=True, connexions=[], actives=[])


def faux(scenario, source=None):
    source = source or T.FAUX_NC_VPN
    return source.replace(ENTREE, BLOC % json.dumps(scenario) + ENTREE, 1)


# Ouvre le panneau, va sur l'onglet Proton, puis attend `attente` dixièmes de seconde avant de contrôler
OUVRIR = '''
    Timer { interval: 100; running: true; repeat: true; onTriggered: {
        ticks++
        if (etape === 0) { var k = Qt.createComponent("Vpn.qml"); verifier(k.status === Component.Ready, k.errorString()); fen = k.createObject(racine); etape++; return }
        if (etape === 1) { if (!VpnEtat.lu || ticks < 6) return
            t.mouseClick(trouver(fen.contentItem, "nc-vpn-filtre-proton")); etape++; ticks = 0; return }
        if (etape === 2) { if (ticks < @ATTENTE@) return
            var zone = textes(trouver(fen.contentItem, "nc-vpn-liste-zone")).join("|")
            var pr = VpnEtat.externe.proton, nd = VpnEtat.externe.nord
            @CONTROLES@
            console.log("FINI"); Qt.exit(0) }
    } }
'''


@T.unittest.skipUnless(T.shutil.which("qs"), "Quickshell requis")
class ProtonAttente(T.HorsEcran):
    # On hérite de lancer() mais pas des tests : on ne garde que les nôtres
    def run_scenario(self, scenario, attente, controles):
        corps = OUVRIR.replace("@ATTENTE@", str(attente)).replace("@CONTROLES@", controles)
        with mock.patch.object(T, "FAUX_NC_VPN", faux(scenario)):
            return self.lancer(corps, etats={0: dict(ETAT, fournisseurs=[])})

    def test_a_affichage_initial_verification_en_cours_sans_bientot_ni_bouton(self):
        lent = dict(delai=3, rep=[proton("pret", PAYS)])
        self.run_scenario({"auto-0": lent, "verif-0": lent}, 8, '''
            verifier(zone.indexOf("Proton VPN · vérification en cours…") >= 0, "titre : " + zone)
            verifier(zone.indexOf("bientôt") < 0, "pas de bientôt : " + zone)
            for (var n of ["login", "installer", "ouvrir"]) {
                var b = trouver(fen.contentItem, "nc-vpn-fournisseur-" + n)
                verifier(b === null || !b.visible, "bouton " + n + " caché")
            }''')

    def test_b_resultat_valide_donne_la_liste_des_pays(self):
        vite = dict(delai=0, rep=[proton("pret", PAYS)])
        self.run_scenario({"auto-0": vite, "verif-0": vite}, 25, '''
            verifier(zone.indexOf("vérification en cours") < 0 && zone.indexOf("bientôt") < 0, "plus d'attente : " + zone)
            verifier(zone.indexOf("France") >= 0 && zone.indexOf("Allemagne") >= 0, "pays : " + zone)''')

    def test_c_vrai_sans_compte_reste_affiche(self):
        vite = dict(delai=0, rep=[proton("sans_compte")])
        self.run_scenario({"auto-0": vite, "verif-0": vite}, 25, '''
            verifier(pr.etat === "sans_compte", "état : " + JSON.stringify(pr))
            verifier(zone.indexOf("vérification en cours") < 0 && zone.indexOf("bientôt") < 0, "plus d'attente : " + zone)''')

    def test_d_verification_explicite_finie_avant_une_lecture_automatique_plus_ancienne(self):
        # auto-0 (lente, lancée avant) porte l'ancien état Proton et un NordVPN à jour ; verif-0 (rapide) porte le bon état Proton
        sc = {"auto-0": dict(delai=2.5, rep=[proton("sans_compte"), nord("sans_compte")]), "verif-0": dict(delai=0.3, rep=[proton("pret", PAYS)])}
        self.run_scenario(sc, 40, '''
            verifier(pr && pr.etat === "pret", "l'ancien état Proton est revenu : " + JSON.stringify(pr))
            verifier(nd && nd.etat === "sans_compte", "l'autre fournisseur de la lecture automatique est pris en compte : " + JSON.stringify(nd))''')

    def test_e_pas_de_lecture_automatique_pendant_la_verification_explicite(self):
        lent = dict(delai=2, rep=[proton("pret", PAYS)])
        _, appels, _ = self.run_scenario({"auto-0": dict(delai=0, rep=[proton("sans_compte")]), "verif-0": lent}, 12, '''
            VpnEtat.relire()              // en pleine vérification : reportée, rien ne démarre''')
        i = appels.index(["fournisseurs-json", "--verifier-proton"])
        self.assertNotIn(["fournisseurs-json"], appels[i + 1:], "aucune lecture automatique pendant la vérification explicite")


# Les tests hérités de HorsEcran ne sont pas à relancer ici
for _n in [n for n in dir(T.HorsEcran) if n.startswith("test_")]:
    setattr(ProtonAttente, _n, None)

if __name__ == "__main__":
    unittest.main()
