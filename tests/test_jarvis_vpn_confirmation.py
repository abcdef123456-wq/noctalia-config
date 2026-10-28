"""/nc : la confirmation appartient à (chat, utilisateur), les actions sensibles (VPN et écran) ne passent que dans la discussion
privée, les messages modifiés ne font rien, l'invite nomme l'action et l'état du kill switch, une nouvelle demande dit qu'elle
remplace l'ancienne. Faux executer qui note ses appels : jamais le vrai nc-vpn. UUID fictifs."""
import asyncio
import datetime
import json
import os
from pathlib import Path
import types
import unittest
from unittest import mock

from tests.test_jarvis_vpn import Base, SOURCE, U1, U2, conn

OK_CONNECTER = {"contrat": 1, "ok": True, "action": "connecter", "uuid": U1, "nom": "Labo", "actif": True, "deja": False}


def ks(actif):
    return {"contrat": 1, "installe": True, "voulu": True, "actif": actif, "refus_code": "", "refus": "", "limites": []}


class Invite(Base):
    def reponses(self, par_action):
        """Un executer qui répond selon la sous-commande de nc-vpn."""
        async def executer(argv, delai=20, limite=3000, fusion=True):
            self.appels.append((list(argv), delai, limite))
            return 0, json.dumps(par_action.get(argv[1], {}))
        self.m.executer = executer

    def test_invite_deconnecter_nomme_le_tunnel_et_le_killswitch_actif(self):
        self.reponses({"killswitch": ks(True)})
        r = self.nc("vpn deconnecter " + U1.upper())
        self.assertIn("couper le tunnel 11111111…", r)
        self.assertIn("kill switch est actif", r)
        self.assertIn("JARVIS perdra le réseau", r)
        self.assertEqual([a[0] for a in self.appels], [["nc-vpn", "killswitch", "etat-json"]], "rien d'autre avant le oui")

    def test_invite_killswitch_inactif_ou_inconnu(self):
        self.reponses({"killswitch": ks(False)})
        self.assertIn("kill switch est inactif", self.nc("vpn tout"))
        self.assertIn("couper TOUS les tunnels", self.nc("vpn tout", maintenant=2000))
        self.reponses({})                                    # réponse invalide : état inconnu
        self.assertIn("inconnu", self.nc("vpn deconnecter " + U1, maintenant=3000))

    def test_invite_connecter_sans_lecture_du_killswitch(self):
        r = self.nc("vpn connecter " + U1)
        self.assertIn("connecter le tunnel 11111111…", r)
        self.assertEqual(self.appels, [])

    def test_nouvelle_commande_dit_qu_elle_remplace(self):
        self.reponses({"killswitch": ks(False)})
        self.nc("vpn deconnecter " + U1, maintenant=1000)
        r = self.nc("vpn tout", maintenant=1010)
        self.assertIn("L'action en attente (couper le tunnel 11111111…) est remplacée", r)
        r = self.nc("vpn tout", maintenant=1010 + 500)       # l'ancienne a expiré : rien à remplacer
        self.assertNotIn("remplacée", r)


class Qui(Base):
    def test_un_autre_utilisateur_du_meme_chat_ne_confirme_pas(self):
        self.reponse = (0, json.dumps(OK_CONNECTER))
        self.assertTrue(self.nc_u("vpn connecter " + U1, user=1).startswith("⚠️"))
        self.assertIn("Rien à confirmer", self.nc_u("oui", user=2, maintenant=1001))
        self.assertEqual([a for a in self.appels if a[0][1] == "connecter"], [])
        self.assertTrue(self.nc_u("oui", user=1, maintenant=1002).startswith("✅"))
        self.assertEqual(len([a for a in self.appels if a[0][1] == "connecter"]), 1)

    def test_ecran_meme_correctif(self):
        self.assertTrue(self.nc_u("ecran externe", user=1).startswith("⚠️"))
        self.assertIn("Rien à confirmer", self.nc_u("oui", user=2, maintenant=1001))
        self.assertEqual([a for a in self.appels if a[0][0] == "nc-ecrans"], [])
        self.nc_u("oui", user=1, maintenant=1002)
        self.assertEqual(self.appels[-1][0], ["nc-ecrans", "externe"])

    def test_groupe_refuse_les_actions_sensibles(self):
        for texte in ("vpn connecter " + U1, "vpn tout", "vpn deconnecter " + U1, "ecran pc", "ecran externe"):
            r = self.nc_u(texte, prive=False)
            self.assertTrue(r.startswith("⛔"), (texte, r))
        self.assertIn("discussion privée", self.nc_u("oui", prive=False, maintenant=1001))
        self.assertEqual([a for a in self.appels if a[0][1:2] != ["killswitch"]], [])
        # une demande faite en privé ne se confirme pas depuis un groupe
        self.nc_u("ecran pc", user=1)
        self.assertIn("discussion privée", self.nc_u("oui", user=1, prive=False, maintenant=1001))
        # les lectures et actions non sensibles restent permises en groupe
        self.assertTrue(self.nc_u("ecran miroir", prive=False).startswith("✅"))

    def nc_u(self, texte, user=1, prive=True, chat=7, maintenant=1000.0):
        return asyncio.run(self.m.commande(texte, chat, maintenant, user, prive))


class Handler(Base):
    def monter(self, chat_type="private", modifie=False):
        reponses = []

        class Message:
            async def reply_text(self, texte):
                reponses.append(texte)
        update = types.SimpleNamespace(effective_user=types.SimpleNamespace(id=42),
                                       effective_chat=types.SimpleNamespace(id=7, type=chat_type), message=Message(),
                                       edited_message=Message() if modifie else None)
        tb = types.SimpleNamespace(_is_allowed=lambda uid: uid == 42)
        return self.m.handler(tb), update, reponses

    def lancer(self, handler, update, *args):
        asyncio.run(handler(update, types.SimpleNamespace(args=list(args))))

    def test_message_modifie_ne_fait_rien(self):
        h, update, reponses = self.monter(modifie=True)
        self.lancer(h, update, "energie", "eco")
        self.lancer(h, update, "oui")
        self.assertEqual((reponses, self.appels), ([], []))

    def test_groupe_et_privee_par_le_handler(self):
        h, update, reponses = self.monter(chat_type="supergroup")
        self.lancer(h, update, "ecran", "pc")
        self.assertTrue(reponses[-1].startswith("⛔ Action sensible refusée"), reponses[-1])
        self.assertEqual(self.appels, [])
        h, update, reponses = self.monter(chat_type="private")
        self.lancer(h, update, "ecran", "pc")
        self.assertTrue(reponses[-1].startswith("⚠️"))
        h, update, reponses = self.monter(chat_type=None)          # type absent : refusé par prudence
        self.lancer(h, update, "ecran", "pc")
        self.assertTrue(reponses[-1].startswith("⛔"))


if __name__ == "__main__":
    unittest.main()
