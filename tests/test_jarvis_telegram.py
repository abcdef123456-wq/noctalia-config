"""Messages Telegram reçus pendant l'arrêt du PC : rattrapage au démarrage et offset gardé sur disque (nc_telegram).

Faux Telegram (bot, application, mises à jour) et faux module bots.telegram_bot : aucun réseau, aucune dépendance,
HOME et fichiers temporaires.
"""
import asyncio
import datetime
import json
import logging
from pathlib import Path
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "home/.local/share/nc-jarvis/server/nc_telegram.py"
UTC = datetime.timezone.utc


def module():
    m = types.ModuleType("nc_telegram_test")
    m.__file__ = str(SOURCE)
    exec(compile(SOURCE.read_text(), str(SOURCE), "exec"), m.__dict__)
    return m


class Chat:
    def __init__(self, id):
        self.id = id


class Message:
    def __init__(self, text, date, chat=42, auteur=None):
        self.text, self.date, self.chat = text, date, Chat(chat)
        self.from_user = types.SimpleNamespace(id=auteur) if auteur is not None else None


class Update:
    def __init__(self, update_id, message=None):
        self.update_id, self.message = update_id, message

    def to_dict(self):
        m = self.message
        return {"update_id": self.update_id, "message": None if m is None else {"text": m.text, "date": m.date.timestamp(), "chat": {"id": m.chat.id}}}

    @staticmethod
    def de_json(data, bot):
        m = data["message"]
        return Update(data["update_id"], None if m is None else Message(m["text"], datetime.datetime.fromtimestamp(m["date"], UTC), m["chat"]["id"]))


class Bot:
    """Faux Telegram : les mises à jour non confirmées, rendues par get_updates selon l'offset ; un appel avec un offset
    plus grand confirme les précédentes."""
    def __init__(self, en_attente):
        self.en_attente = list(en_attente)
        self.appels = []
        self.envoyes = []
        self.webhook = None
        self.commandes = None

    async def get_updates(self, offset=None, timeout=0, limit=100):
        self.appels.append(offset)
        if offset:
            self.en_attente = [u for u in self.en_attente if u.update_id >= offset]
        return self.en_attente[:limit]

    async def send_message(self, chat_id, text, **kwargs):
        self.envoyes.append((chat_id, text))

    async def delete_webhook(self, drop_pending_updates):
        self.webhook = dict(drop_pending_updates=drop_pending_updates)

    async def set_my_commands(self, commandes):
        self.commandes = commandes


class Application:
    def __init__(self, bot, echecs=()):
        self.bot, self.echecs = bot, set(echecs)
        self.traites = []
        self.handlers = []
        self.etapes = []
        self.updater = types.SimpleNamespace(start_polling=self._etape("polling"), stop=self._etape("updater.stop"))
        self.initialize, self.start, self.stop, self.shutdown = (self._etape(n) for n in ("initialize", "start", "stop", "shutdown"))

    def _etape(self, nom):
        async def f(*a, **k):
            self.etapes.append(nom)
        return f

    def add_handler(self, handler, group=0):
        self.handlers.append((handler, group))

    async def process_update(self, u):
        if u.update_id in self.echecs:
            raise RuntimeError("handler cassé")
        self.traites.append(u.message.text if u.message else None)
        for handler, _ in sorted(self.handlers, key=lambda h: h[1]):
            await handler.callback(u, None)


class Offset(unittest.TestCase):
    def setUp(self):
        self.m = module()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.chemin = Path(self.tmp.name) / "nc-telegram-offset.json"

    def test_lecture_ecriture_atomique(self):
        self.assertEqual(self.m.lire_offset(self.chemin), 0)
        self.m.ecrire_offset(self.chemin, 1234)
        self.assertEqual(self.m.lire_offset(self.chemin), 1234)
        self.assertEqual(sorted(p.name for p in self.chemin.parent.iterdir()), ["nc-telegram-offset.json"], "pas de .tmp qui traîne")
        self.assertIn("date", json.loads(self.chemin.read_text()))
        self.chemin.write_text("{corrompu")
        self.assertEqual(self.m.lire_offset(self.chemin), 0)
        self.chemin.write_text(json.dumps({"offset": -5}))
        self.assertEqual(self.m.lire_offset(self.chemin), 0)

    def test_emplacement(self):
        faux = types.SimpleNamespace(__file__="/srv/jarvis/gateway/main.py")
        self.assertEqual(self.m.fichier_offset(faux), Path("/srv/jarvis/gateway/nc-telegram-offset.json"))
        with mock.patch.dict(self.m.os.environ, NC_TELEGRAM_OFFSET_FILE=str(self.chemin)):
            self.assertEqual(self.m.fichier_offset(faux), self.chemin)

    def test_heure_locale(self):
        maintenant = datetime.datetime(2026, 10, 20, 18, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=2)))
        self.assertEqual(self.m.quand(datetime.datetime(2026, 10, 20, 6, 12, tzinfo=UTC), maintenant), "08:12")
        self.assertEqual(self.m.quand(datetime.datetime(2026, 10, 19, 21, 30, tzinfo=UTC), maintenant), "19/10 23:30")


class Rattrapage(unittest.TestCase):
    def setUp(self):
        self.m = module()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.chemin = Path(self.tmp.name) / "offset.json"
        self.demarrage = time.time()
        self.avant = datetime.datetime.fromtimestamp(self.demarrage - 3600, UTC)      # pendant l'arrêt
        self.pendant = datetime.datetime.fromtimestamp(self.demarrage + 5, UTC)       # arrivé pendant le rattrapage

    def rattraper(self, bot, app=None, offset=None):
        if offset:
            self.m.ecrire_offset(self.chemin, offset)
        app = app or Application(bot)
        n = asyncio.run(self.m.rattraper(app, self.chemin, self.demarrage, Update.de_json))
        return n, app

    def test_messages_en_attente_traites_dans_l_ordre_avec_prefixe(self):
        bot = Bot([Update(10, Message("déjà traité", self.avant)), Update(11, Message("bonjour jarvis", self.avant)),
                   Update(12, Message("/rappels", self.avant)), Update(13, None), Update(14, Message("tout neuf", self.pendant))])
        with self.assertLogs("nc_telegram", level="INFO") as journal, \
                mock.patch.dict("os.environ", {"TELEGRAM_ALLOWED_USER_IDS": "", "ALLOW_ALL_USERS": "true"}):
            n, app = self.rattraper(bot, offset=11)
        self.assertEqual(n, 2, "deux messages arrivés pendant l'arrêt (la commande comprise, pas celui déjà traité ni le nouveau)")
        heure = self.m.quand(self.avant)
        self.assertEqual(app.traites, ["[Reçu pendant l'arrêt à " + heure + "] bonjour jarvis", "/rappels", None, "tout neuf"],
                         "ordre d'arrivée, préfixe sur le texte mais pas sur la commande ni sur le message arrivé après le démarrage")
        self.assertEqual(bot.envoyes, [(42, "⏱ Reçu pendant l'arrêt à " + heure + " : traité maintenant.")] * 2)
        self.assertEqual(bot.appels, [11, 15], "repris à l'offset gardé, puis un dernier appel qui confirme tout à Telegram")
        self.assertEqual(self.m.lire_offset(self.chemin), 15)
        self.assertTrue(any("reçu pendant l'arrêt" in l for l in journal.output))

    def test_sans_offset_et_sans_attente(self):
        bot = Bot([])
        n, app = self.rattraper(bot)
        self.assertEqual((n, app.traites, bot.appels), (0, [], [None]), "sans offset gardé, Telegram donne tout ce qui n'est pas confirmé")
        self.assertFalse(self.chemin.exists())

    def test_lots_de_cent_et_handler_casse(self):
        bot = Bot([Update(i, Message("m" + str(i), self.avant)) for i in range(1, 151)])
        with self.assertLogs("nc_telegram", level="ERROR"):
            n, app = self.rattraper(bot, app=Application(bot, echecs={7}))
        self.assertEqual(n, 150)
        self.assertEqual(len(app.traites), 149, "le message dont le handler échoue ne bloque pas les suivants")
        self.assertEqual(bot.appels, [None, 101, 151], "au plus 100 par appel, puis confirmation")
        self.assertEqual(self.m.lire_offset(self.chemin), 151)

    def test_avis_de_retard_seulement_aux_autorises(self):
        """Revue SRV-02 : un inconnu qui avait écrit pendant l'arrêt recevait « ⏱ Reçu pendant l'arrêt »."""
        bot = Bot([Update(1, Message("moi", self.avant, chat=7, auteur=7)), Update(2, Message("inconnu", self.avant, chat=8, auteur=8))])
        with mock.patch.dict("os.environ", {"TELEGRAM_ALLOWED_USER_IDS": "7, 9"}):
            n, app = self.rattraper(bot)
        self.assertEqual([c for c, _ in bot.envoyes], [7])
        self.assertEqual(len(app.traites), 2, "le message de l'inconnu passe quand même à upstream, qui décide")
        # Liste vide : personne, comme le bot upstream (fail-closed), sauf ALLOW_ALL_USERS
        bot = Bot([Update(1, Message("moi", self.avant, chat=7, auteur=7))])
        with mock.patch.dict("os.environ", {"TELEGRAM_ALLOWED_USER_IDS": "", "ALLOW_ALL_USERS": ""}):
            self.chemin.unlink(missing_ok=True)
            self.rattraper(bot)
        self.assertEqual(bot.envoyes, [])

    def test_ordres_du_pc_recus_pendant_l_arret_ignores(self):
        """Revue SRV-03 : « /nc ecran externe » puis « /nc oui » envoyés PC éteint étaient exécutés au démarrage."""
        bot = Bot([Update(1, Message("/nc ecran externe", self.avant, chat=7, auteur=7)), Update(2, Message("/nc oui", self.avant, chat=7, auteur=7)),
                   Update(3, Message("/PC@MonBot energie performance", self.avant, chat=8, auteur=8)),
                   Update(4, Message("/rappels", self.avant, chat=7, auteur=7)), Update(5, Message("/nc etat", self.pendant, chat=7, auteur=7))])
        app = Application(bot)
        n = asyncio.run(self.m.rattraper(app, self.chemin, self.demarrage, Update.de_json, lambda uid: uid == 7))
        self.assertEqual(app.traites, ["/rappels", "/nc etat"], "ni les ordres d'avant, ni leur confirmation ; le récent passe")
        heure = self.m.quand(self.avant)
        self.assertEqual(bot.envoyes[:2], [(7, "⏱ Commande ignorée : reçue pendant l'arrêt à " + heure + ". Renvoie-la si tu la veux toujours.")] * 2)
        self.assertNotIn(8, [c for c, _ in bot.envoyes], "l'inconnu n'a pas d'avis (liste blanche du bot)")
        self.assertEqual((n, self.m.lire_offset(self.chemin)), (4, 6))

    def test_attend_que_le_runner_ecoute(self):
        """Revue SRV-01 : au démarrage du PC, le runner écoutait parfois après le rattrapage (messages perdus)."""
        import http.server, socket
        s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
        url = "http://127.0.0.1:%d" % port
        self.assertFalse(asyncio.run(self.m.attendre_runner(url, delai=0.5, pas=0.1)), "personne n'écoute")

        class R(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(404); self.end_headers()

            def log_message(self, *a):
                pass

        def plus_tard():
            time.sleep(0.8)
            serveur = http.server.HTTPServer(("127.0.0.1", port), R)
            self.addCleanup(serveur.server_close)
            serveur.handle_request()
        threading.Thread(target=plus_tard, daemon=True).start()
        debut = time.monotonic()
        self.assertTrue(asyncio.run(self.m.attendre_runner(url, delai=10, pas=0.1)), "une réponse, même 404, suffit")
        self.assertGreater(time.monotonic() - debut, 0.5)
        self.assertTrue(asyncio.run(self.m.attendre_runner("", delai=0)), "sans runner configuré : rien à attendre")

    def test_offset_garde_en_polling_normal(self):
        app = Application(Bot([]))
        handler = self.m.noter_offset(self.chemin)
        asyncio.run(handler(Update(77, Message("x", self.pendant)), None))
        self.assertEqual(self.m.lire_offset(self.chemin), 78)


class Demarrage(unittest.TestCase):
    """demarrer_polling : même cycle qu'upstream, sans jeter les messages en attente ; stop par _stop_event."""
    def setUp(self):
        self.m = module()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.chemin = Path(self.tmp.name) / "offset.json"
        faux_telegram = types.ModuleType("telegram")
        faux_telegram.Update = Update
        faux_telegram.BotCommand = lambda command, description: types.SimpleNamespace(command=command, description=description)
        faux_ext = types.ModuleType("telegram.ext")
        class TypeHandler:
            def __init__(self, type_, callback):
                self.type_, self.callback = type_, callback
        class CommandHandler:
            def __init__(self, commands, callback):
                self.commands, self.callback = commands, callback
            async def callback(self, update, context):
                pass
        faux_ext.TypeHandler, faux_ext.CommandHandler = TypeHandler, CommandHandler
        self.anciens = {k: sys.modules.get(k) for k in ("telegram", "telegram.ext")}
        sys.modules.update({"telegram": faux_telegram, "telegram.ext": faux_ext})
        def restaurer():
            for k, v in self.anciens.items():
                if v is None:
                    sys.modules.pop(k, None)
                else:
                    sys.modules[k] = v
        self.addCleanup(restaurer)

    def faux_bot_module(self, app, token="123:abc"):
        async def annuler(update, context):
            pass
        return types.SimpleNamespace(TELEGRAM_TOKEN=token, BOT_COMMANDS=["start"], _stop_event=threading.Event(),
                                     _polling_thread=None, _TELEGRAM_LOOP=None, get_application=lambda: app, cmd_annuler_rappel=annuler)

    def test_demarrage_garde_les_messages_en_attente_puis_polling_puis_arret(self):
        avant = datetime.datetime.fromtimestamp(time.time() - 60, UTC)
        bot = Bot([Update(5, Message("reçu hors ligne", avant))])
        app = Application(bot)
        tb = self.faux_bot_module(app)
        upstream = types.SimpleNamespace(__file__=str(Path(self.tmp.name) / "main.py"), start_telegram_polling="upstream")
        chemin = self.m.installer(upstream, tb=tb)
        self.assertEqual(chemin, Path(self.tmp.name) / "nc-telegram-offset.json")
        self.assertNotEqual(upstream.start_telegram_polling, "upstream", "start_telegram_polling remplacé dans main")
        upstream.start_telegram_polling()
        for _ in range(100):
            if "polling" in app.etapes:
                break
            time.sleep(0.05)
        self.assertEqual(bot.webhook, dict(drop_pending_updates=False), "les messages en attente ne sont plus jetés")
        self.assertEqual([getattr(c, "command", c) for c in bot.commandes], ["start", "supprimer"], "les commandes de l'overlay sont déclarées à Telegram")
        self.assertEqual(app.etapes, ["initialize", "start", "polling"], "rattrapage entre start et le polling")
        self.assertEqual(len(app.traites), 1)
        self.assertTrue(app.traites[0].startswith("[Reçu pendant l'arrêt à "))
        self.assertEqual([g for _, g in app.handlers], [-100, 0], "handler d'offset avant tout autre, puis /supprimer")
        self.assertEqual(getattr(app.handlers[1][0], "commands", None), ["supprimer"])
        self.assertEqual([getattr(c, "command", c) for c in tb.BOT_COMMANDS], ["start", "supprimer"], "sans nc_noctalia sur le chemin : /supprimer seulement")
        self.assertEqual(self.m.lire_offset(chemin), 6)
        self.assertIsNotNone(tb._TELEGRAM_LOOP)
        tb._stop_event.set()
        tb._polling_thread.join(5)
        self.assertFalse(tb._polling_thread.is_alive())
        self.assertEqual(app.etapes, ["initialize", "start", "polling", "updater.stop", "stop", "shutdown"])

    def test_sans_token_ni_module_bot(self):
        tb = self.faux_bot_module(Application(Bot([])), token="")
        with self.assertLogs("nc_telegram", level="WARNING"):
            self.m.demarrer_polling(tb, self.chemin)
        self.assertIsNone(tb._polling_thread)
        upstream = types.SimpleNamespace(start_telegram_polling="upstream")
        with self.assertLogs("nc_telegram", level="WARNING"):
            self.assertIsNone(self.m.installer(upstream))
        self.assertEqual(upstream.start_telegram_polling, "upstream", "sans bots.telegram_bot, rien n'est remplacé")


if __name__ == "__main__":
    unittest.main()


class Extensions(unittest.TestCase):
    """Rappels « toutes les N heures », diffusion aux chats connus, commandes ajoutées au bot."""
    def setUp(self):
        self.m = module()

    def faux_reminders(self):
        r = types.ModuleType("reminders")
        r.strip_recurrence_prefix = lambda text: ("daily", text[15:].strip()) if text.startswith("tous les jours ") else (None, text.strip())
        r.compute_next_occurrence = lambda current, recurrence: current + datetime.timedelta(days=1) if recurrence == "daily" else None
        r.recurrence_label = lambda recurrence: "Tous les jours" if recurrence == "daily" else (recurrence or "")
        return r

    def test_toutes_les_n_heures(self):
        r = self.faux_reminders()
        tb = types.SimpleNamespace(recurrence_label=r.recurrence_label)
        self.m.etendre_rappels(r, tb)
        self.m.etendre_rappels(r, tb)      # idempotent
        self.assertEqual(r.strip_recurrence_prefix("toutes les 3 heures boire"), ("every:hours:3", "boire"))
        self.assertEqual(r.strip_recurrence_prefix("Chaque heure, respirer"), ("every:hours:1", "respirer"))
        self.assertEqual(r.strip_recurrence_prefix("tous les jours 8h pain"), ("daily", "8h pain"), "les autres règles passent à upstream")
        self.assertEqual(r.strip_recurrence_prefix("8h pain"), (None, "8h pain"))
        t = datetime.datetime(2026, 10, 20, 8, 0, tzinfo=UTC)
        self.assertEqual(r.compute_next_occurrence(t, "every:hours:3"), t + datetime.timedelta(hours=3))
        self.assertEqual(r.compute_next_occurrence(t, "daily"), t + datetime.timedelta(days=1))
        self.assertEqual(r.recurrence_label("every:hours:3"), "Toutes les 3 heures")
        self.assertEqual(r.recurrence_label("every:hours:1"), "Toutes les heures")
        self.assertEqual(tb.recurrence_label("daily"), "Tous les jours", "le nom importé dans le module du bot est remplacé aussi")

    def test_diffusion(self):
        envoyes = []
        async def send_broadcast_message(texte):
            envoyes.append(texte)
            return bool(envoyes) and texte != "personne"
        tb = types.SimpleNamespace(TELEGRAM_TOKEN="123:abc", send_broadcast_message=send_broadcast_message)
        self.assertEqual(asyncio.run(self.m.diffuser("🔋 Batterie à 15 %", tb)), dict(sent=True))
        self.assertEqual(envoyes, ["🔋 Batterie à 15 %"])
        self.assertFalse(asyncio.run(self.m.diffuser("personne", tb))["sent"])
        self.assertFalse(asyncio.run(self.m.diffuser("", tb))["sent"])
        self.assertFalse(asyncio.run(self.m.diffuser("x" * 4001, tb))["sent"])
        self.assertIn("TELEGRAM_TOKEN", asyncio.run(self.m.diffuser("x", types.SimpleNamespace(TELEGRAM_TOKEN="")))["error"])
        self.assertEqual(envoyes, ["🔋 Batterie à 15 %", "personne"])

    def test_commandes_ajoutees_au_bot(self):
        faux_telegram = types.ModuleType("telegram")
        class BotCommand:
            def __init__(self, command, description):
                self.command, self.description = command, description
        faux_telegram.BotCommand = BotCommand
        faux_ext = types.ModuleType("telegram.ext")
        class CommandHandler:
            def __init__(self, commands, callback, filters=None):
                self.commands, self.callback, self.filters = commands, callback, filters
        faux_ext.CommandHandler = CommandHandler
        class Filtre:
            def __invert__(self):
                return "pas-modifie"
        faux_ext.filters = types.SimpleNamespace(UpdateType=types.SimpleNamespace(EDITED_MESSAGE=Filtre()))
        faux_noctalia = types.ModuleType("nc_noctalia")
        faux_noctalia.handler = lambda tb: "handler-nc"
        anciens = {k: sys.modules.get(k) for k in ("telegram", "telegram.ext", "nc_noctalia")}
        sys.modules.update({"telegram": faux_telegram, "telegram.ext": faux_ext, "nc_noctalia": faux_noctalia})
        try:
            app = Application(Bot([]))
            async def annuler(update, context):
                pass
            tb = types.SimpleNamespace(cmd_annuler_rappel=annuler, BOT_COMMANDS=[BotCommand("rappel", "x")])
            self.m.commandes_nc(app, tb)
            self.assertEqual([(h.commands, h.callback) for h, _ in app.handlers], [(["supprimer"], annuler), (["nc", "pc"], "handler-nc")])
            self.assertEqual([h.filters for h, _ in app.handlers], [None, "pas-modifie"], "/nc ignore les messages modifiés")
            self.assertEqual([c.command for c in tb.BOT_COMMANDS], ["rappel", "nc", "supprimer"])
            self.m.commandes_nc(app, tb)
            self.assertEqual([c.command for c in tb.BOT_COMMANDS], ["rappel", "nc", "supprimer"], "pas de doublon")
        finally:
            for k, v in anciens.items():
                if v is None:
                    sys.modules.pop(k, None)
                else:
                    sys.modules[k] = v

