"""Transport en http:// (nc-assistant adresse_fixee, nc-noeud) : la règle se vérifie sur les adresses RÉSOLUES, et la
connexion va à l'adresse contrôlée, jamais à une seconde résolution. Sans réseau ni vrai DNS : socket.getaddrinfo est
remplacé ; un faux serveur en boucle locale compte ses connexions. HOME, XDG_* et TMPDIR pointent vers un dossier
jetable avant le chargement des modules."""
import asyncio
import http.server
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import socket
import tempfile
import threading
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "home/.local/bin"
VRAI_GETADDRINFO = socket.getaddrinfo
VRAIE_CONNEXION = socket.create_connection


def charger(nom, fichier):
    l = importlib.machinery.SourceFileLoader(nom, str(BIN / fichier))
    m = importlib.util.module_from_spec(importlib.util.spec_from_loader(nom, l))
    l.exec_module(m)
    return m


class Faux(http.server.BaseHTTPRequestHandler):
    recus = []

    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(n)
        Faux.recus.append((self.path, self.headers.get("Host"), self.headers.get("X-Secret-Key")))
        corps = json.dumps({"ok": True}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)


class Compteur(http.server.ThreadingHTTPServer):
    connexions = 0

    def get_request(self):
        Compteur.connexions += 1
        return super().get_request()


def resolveur(table):
    """getaddrinfo de test : les noms de la table rendent leurs adresses ; une adresse numérique passe telle quelle ;
    tout autre nom est introuvable. Aucune requête DNS."""
    def faux(hote, port, family=0, type=0, proto=0, flags=0):
        if hote in table:
            return [(socket.AF_INET6 if ":" in a else socket.AF_INET, socket.SOCK_STREAM, 6, "", (a, port))
                    for a in table[hote]]
        try:
            return VRAI_GETADDRINFO(hote, port, family, type, proto, flags | socket.AI_NUMERICHOST)
        except socket.gaierror:
            raise socket.gaierror(socket.EAI_NONAME, "introuvable") from None
    return faux


class Transport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dossier = tempfile.mkdtemp(prefix="nc-transport-")
        h = Path(cls.dossier) / "home"
        h.mkdir()
        cls.env = mock.patch.dict(os.environ, {"HOME": str(h), "XDG_CONFIG_HOME": str(h / ".config"),
                                               "XDG_STATE_HOME": str(h / ".local/state"), "XDG_DATA_HOME": str(h / ".local/share"),
                                               "XDG_CACHE_HOME": str(h / ".cache"), "TMPDIR": cls.dossier, "NC_LANGUE": "fr"})
        cls.env.start()
        cls.A = charger("nc_assistant_transport", "nc-assistant")
        cls.srv = Compteur(("127.0.0.1", 0), Faux)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.env.stop()
        import shutil
        shutil.rmtree(cls.dossier, ignore_errors=True)

    def setUp(self):
        Faux.recus = []
        Compteur.connexions = 0
        self.connexions = []

        def connexion(adresse, *a, **kw):
            # Toute connexion est notée, puis envoyée au faux serveur local (aucune vraie adresse n'est jointe)
            self.connexions.append(adresse[0])
            return VRAIE_CONNEXION(("127.0.0.1", self.port), *a, **kw)
        p = mock.patch.object(socket, "create_connection", connexion)
        p.start()
        self.addCleanup(p.stop)

    def resoudre(self, table):
        p = mock.patch.object(socket, "getaddrinfo", resolveur(table))
        p.start()
        self.addCleanup(p.stop)

    def envoyer(self, url):
        c = {"URL": url, "SECRET_KEY": "cle-de-test-0123456789", "USER_ID": "u", "TIMEOUT": 5.0}
        adresse = self.A.adresse_fixee(url)
        return self.A.api(c, "/api/ask", {"q": 1}, sans_proxy=True, adresse=adresse)

    def test_ts_net_vers_une_adresse_publique_refuse_rien_n_est_envoye(self):
        self.resoudre({"pc.tail1.ts.net": ["203.0.113.7"]})
        with self.assertRaises(self.A.TransportRefuse) as e:
            self.envoyer(f"http://pc.tail1.ts.net:{self.port}")
        self.assertIn("HTTP en clair", str(e.exception))
        self.assertEqual((self.connexions, Compteur.connexions, Faux.recus), ([], 0, []))
        self.assertFalse(self.A.transport_sur(f"http://pc.tail1.ts.net:{self.port}"))

    def test_ts_net_vers_tailscale_accepte_connexion_a_cette_adresse(self):
        self.resoudre({"pc.tail1.ts.net": ["100.64.1.2"]})
        self.assertEqual(self.envoyer(f"http://pc.tail1.ts.net:{self.port}"), {"ok": True})
        self.assertEqual(self.connexions, ["100.64.1.2"])
        self.assertEqual(Faux.recus[0][1], f"pc.tail1.ts.net:{self.port}")      # le nom reste dans Host

    def test_local_vers_une_adresse_privee_accepte(self):
        self.resoudre({"mon-pi.local": ["192.168.1.20"]})
        self.assertEqual(self.A.adresse_fixee("http://mon-pi.local:8000"), ["192.168.1.20"])
        self.resoudre({"mon-pi.local": ["8.8.8.8"]})
        with self.assertRaises(self.A.TransportRefuse):
            self.A.adresse_fixee("http://mon-pi.local:8000")

    def test_deux_adresses_dont_une_publique_seule_la_permise_est_jointe(self):
        self.resoudre({"pc.tail1.ts.net": ["203.0.113.7", "100.64.1.2"], "nas.lan": ["2001:db8::1", "10.0.0.4"]})
        self.assertEqual(self.A.adresse_fixee("http://pc.tail1.ts.net"), ["100.64.1.2"])
        self.assertEqual(self.A.adresse_fixee("http://nas.lan"), ["10.0.0.4"])
        self.assertEqual(self.envoyer(f"http://nas.lan:{self.port}"), {"ok": True})
        self.assertEqual(self.connexions, ["10.0.0.4"])           # jamais l'IPv6 publique

    def test_localhost_essaie_chaque_adresse_dans_l_ordre(self):
        self.resoudre({"localhost": ["::1", "127.0.0.1"]})
        refusees = []

        def connexion(adresse, *a, **kw):
            self.connexions.append(adresse[0])
            if adresse[0] == "::1":                 # le serveur n'écoute qu'en 127.0.0.1
                refusees.append(adresse[0])
                raise ConnectionRefusedError("::1")
            return VRAIE_CONNEXION(("127.0.0.1", self.port), *a, **kw)
        with mock.patch.object(socket, "create_connection", connexion):
            self.assertEqual(self.envoyer(f"http://localhost:{self.port}"), {"ok": True})
        self.assertEqual((self.connexions, refusees), (["::1", "127.0.0.1"], ["::1"]))

    def test_lien_local_avec_zone_refuse_clairement(self):
        self.resoudre({})
        with self.assertRaises(self.A.TransportRefuse) as e:
            self.A.adresse_fixee("http://[fe80::1%25eth0]:8000")
        self.assertIn("zone", str(e.exception))

    def test_point_final_refuse(self):
        self.resoudre({})
        for url in ("http://127.0.0.1.:8000", "http://localhost.", "http://pc.tail1.ts.net.", "http://nas.local."):
            with self.subTest(url=url), self.assertRaises(self.A.TransportRefuse):
                self.A.adresse_fixee(url)

    def test_nom_introuvable_hors_ligne(self):
        self.resoudre({})
        with self.assertRaises(self.A.HoteIntrouvable):
            self.A.adresse_fixee("http://pc.tail1.ts.net:8000")
        self.assertEqual(self.connexions, [])

    def test_inchange_https_et_boucle_locale(self):
        self.resoudre({})
        self.assertIsNone(self.A.adresse_fixee("https://jarvis.example.com"))
        self.assertEqual(self.A.adresse_fixee("http://127.0.0.1:8000"), ["127.0.0.1"])
        self.assertEqual(self.A.adresse_fixee("http://[::1]:8000"), ["::1"])
        self.assertEqual(self.envoyer(f"http://127.0.0.1:{self.port}"), {"ok": True})
        for url in ("http://203.0.113.5", "http://exemple.test", "http://172.32.0.1", "http://100.128.0.1",
                    "http://[::ffff:8.8.8.8]", "ftp://127.0.0.1"):
            with self.subTest(url=url), self.assertRaises(self.A.TransportRefuse):
                self.A.adresse_fixee(url)

    def test_localhost_seulement_en_boucle_locale(self):
        self.resoudre({"localhost": ["192.168.1.9"]})
        with self.assertRaises(self.A.TransportRefuse):
            self.A.adresse_fixee("http://localhost:8000")

    # ── T2 : tous les appels au serveur (api() sans fichier, nc-dictee) ──

    def api(self, url):
        c = {"URL": url, "SECRET_KEY": "cle-de-test-0123456789", "USER_ID": "u", "TIMEOUT": 5.0}
        return self.A.api(c, "/api/status", {"q": 1})

    def test_api_sans_fichier_suit_les_adresses_verifiees(self):
        self.resoudre({"pc.tail1.ts.net": ["203.0.113.7"], "nas.lan": ["2001:db8::9", "10.0.0.4"]})
        with self.assertRaises(self.A.TransportRefuse):
            self.api(f"http://pc.tail1.ts.net:{self.port}")              # DNS hostile : rien ne part
        self.assertEqual((self.connexions, Compteur.connexions), ([], 0))
        self.assertEqual(self.api(f"http://nas.lan:{self.port}"), {"ok": True})
        self.assertEqual(self.connexions, ["10.0.0.4"])
        with self.assertRaises(self.A.TransportRefuse):
            self.api(f"http://nas.lan.:{self.port}")

    def test_aucun_proxy_de_l_environnement(self):
        proxy = Compteur(("127.0.0.1", 0), Faux)
        threading.Thread(target=proxy.serve_forever, daemon=True).start()
        self.addCleanup(proxy.server_close)
        self.addCleanup(proxy.shutdown)
        adresse = "http://127.0.0.1:%d" % proxy.server_address[1]
        self.resoudre({})
        with mock.patch.dict(os.environ, {k: adresse for k in ("http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY", "all_proxy")}):
            for url in (f"http://10.1.2.3:{self.port}", f"http://203.0.113.5:{self.port}"):
                with self.subTest(url=url):
                    self.assertEqual(self.api(url), {"ok": True})
            o = self.A.ouvreur("https://jarvis.example.com")
        self.assertEqual(Faux.recus and [r[1] for r in Faux.recus], [f"10.1.2.3:{self.port}", f"203.0.113.5:{self.port}"])
        # https : aucun proxy non plus (ProxyHandler({}) remplace celui de l'environnement et n'ouvre rien)
        self.assertFalse(any(isinstance(h, self.A.urllib.request.ProxyHandler) and h.proxies for h in o.handlers))
        self.assertFalse(any(hasattr(h, "https_open") and type(h).__name__ == "ProxyHandler" for h in o.handlers))

    def test_adresse_publique_en_http_avertie_une_fois(self):
        import io
        self.A._AVERTI.clear()
        erreur = io.StringIO()
        self.resoudre({})
        with mock.patch.object(self.A.sys, "stderr", erreur):
            for _ in range(3):
                self.assertEqual(self.api(f"http://203.0.113.5:{self.port}"), {"ok": True})
            self.api(f"http://127.0.0.1:{self.port}")
        self.assertEqual(erreur.getvalue().count("HTTP en clair"), 1, erreur.getvalue())

    def test_dictee_passe_par_le_meme_ouvreur(self):
        source = (BIN / "nc-dictee").read_text()
        self.assertIn('m.ouvreur(c["URL"])', source)
        self.assertNotIn("build_opener", source)

    def test_delai_reparti_sur_les_adresses(self):
        parts = []
        horloge = [100.0]           # horloge simulée : chaque essai lent consomme toute sa part

        def connexion(adresse, delai, *a, **kw):
            parts.append(delai)
            if len(parts) < 3:
                horloge[0] += delai
                raise socket.timeout("lent")
            return VRAIE_CONNEXION(("127.0.0.1", self.port), *a, **kw)
        c = self.A.ConnexionFixee("nas.lan", 8000, adresse=["10.0.0.1", "10.0.0.2", "10.0.0.3"], timeout=6.0)
        with mock.patch.object(socket, "create_connection", connexion), \
                mock.patch.object(self.A.time, "monotonic", lambda: horloge[0]):
            c.connect()
        self.addCleanup(c.close)
        self.assertEqual(len(parts), 3)
        self.assertLessEqual(sum(parts), 6.0)
        self.assertAlmostEqual(parts[0], 2.0, delta=0.1)
        self.assertEqual(c.sock.gettimeout(), 6.0)          # la suite garde le délai demandé

    def test_noeud_ip_ecrite_hors_plage_arret_definitif(self):
        m = charger("nc_noeud_transport_ip", "nc-noeud")
        m.A = self.A
        for url in ("http://203.0.113.5:8000", "http://198.18.0.1:8000", "http://0.0.0.0:8000", "http://240.0.0.1:8000"):
            with self.subTest(url=url), self.assertRaises(m.Definitif):
                m.adresse_ws({"URL": url})
        self.assertEqual(m.adresse_ws({"URL": "http://192.168.1.20:8000"})[2], False)

    def test_noeud_delai_total_reparti(self):
        import time
        m = charger("nc_noeud_transport_delai", "nc-noeud")
        m.A = self.A
        m.DELAI_CONNEXION = 0.6
        essais = []

        async def ouvrir(hote, port, **kw):
            essais.append(hote)
            await asyncio.sleep(10)
        self.resoudre({"nas.local": ["192.168.1.4", "192.168.1.5", "192.168.1.6"]})
        debut = time.monotonic()
        with mock.patch.object(asyncio, "open_connection", ouvrir), self.assertRaises(asyncio.TimeoutError):
            asyncio.run(m.connecter({"URL": "http://nas.local:8000", "SECRET_KEY": "k"}))
        self.assertEqual(essais, ["192.168.1.4", "192.168.1.5", "192.168.1.6"])
        self.assertLess(time.monotonic() - debut, 1.5)

    def test_noeud_ws_vers_une_adresse_resolue_publique(self):
        m = charger("nc_noeud_transport", "nc-noeud")
        m.A = self.A
        ouverts = []

        async def ouvrir(hote, port, **kw):
            ouverts.append(hote)
            raise ConnectionRefusedError("essai")
        self.resoudre({"pc.tail1.ts.net": ["203.0.113.7"], "nas.local": ["192.168.1.4", "192.168.1.5"]})
        with mock.patch.object(asyncio, "open_connection", ouvrir):
            # Résolu hors plage (portail captif) : pas un arrêt définitif, une longue attente, et rien n'est ouvert
            with self.assertRaises(m.AttenteLongue):
                asyncio.run(m.connecter({"URL": "http://pc.tail1.ts.net:8000", "SECRET_KEY": "k"}))
            self.assertFalse(issubclass(m.AttenteLongue, m.Definitif))
            self.assertEqual(m.ATTENTE_LONGUE, 300)
            self.assertEqual(ouverts, [])
            with self.assertRaises(ConnectionError):
                asyncio.run(m.connecter({"URL": "http://nas.local:8000", "SECRET_KEY": "k"}))
            self.assertEqual(ouverts, ["192.168.1.4", "192.168.1.5"])      # chaque adresse, dans l'ordre
            self.resoudre({})
            with self.assertRaises(ConnectionError):       # introuvable : nouvel essai plus tard, pas un arrêt
                asyncio.run(m.connecter({"URL": "http://pc.tail1.ts.net:8000", "SECRET_KEY": "k"}))
        with self.assertRaises(m.Definitif):
            m.adresse_ws({"URL": "http://nas.local.:8000"})


if __name__ == "__main__":
    unittest.main()
