"""Messages Telegram reçus pendant que le PC est éteint (gateway en mode polling, TELEGRAM_WEBHOOK_URL vide).

Le bot upstream (gateway/bots/telegram_bot.py, révision 9c12e00) démarre son polling par
``delete_webhook(drop_pending_updates=True)`` et repart sans offset : tout message envoyé au bot pendant que le PC qui
l'héberge est éteint est jeté au démarrage suivant. Ici, sans toucher à upstream (nc_gateway remplace seulement le nom
``start_telegram_polling`` que son lifespan appelle) :
  - les messages en attente sont gardés (``drop_pending_updates=False``) et traités dans l'ordre d'arrivée, par les
    handlers upstream, avant de reprendre le polling normal ; pour chacun, un mot au chat (« Reçu pendant l'arrêt à
    HH:MM ») et le même préfixe devant le texte transmis au modèle (pas devant une commande /…) ; tout est journalisé ;
  - l'offset Telegram (numéro du dernier message traité + 1) est gardé sur disque, nc-telegram-offset.json à côté du
    main.py du gateway (NC_TELEGRAM_OFFSET_FILE pour le déplacer), écrit après chaque message : un message déjà traité
    avant un arrêt brutal n'est pas rejoué.
Limites : Telegram ne garde un message non récupéré que 24 heures (rien à rattraper au-delà) et en rend au plus 100 par
appel (plusieurs appels sont faits). En mode webhook (TELEGRAM_WEBHOOK_URL renseignée), Telegram rejoue lui-même les
messages non livrés quand le serveur revient : ce module ne s'en mêle pas.

Aussi, dans le même overlay (installer) :
  - rappels « toutes les N heures » (every:hours:N) en plus des récurrences upstream (jour, semaine, mois), pour
    /rappel de Telegram comme pour l'API ; alias /supprimer de /annuler_rappel ;
  - diffuser(texte) : un message Telegram aux chats connus du bot (alertes machine, op notify de /api/nc/manage) ;
  - les commandes /nc de réglage du PC (nc_noctalia), seulement en déploiement local.
"""
import asyncio
import datetime
import importlib
import json
import logging
import os
from pathlib import Path
import re
import threading
import time

logger = logging.getLogger("nc_telegram")
_avec_suivi = set()     # id() des applications où le handler d'offset est déjà posé (relance du polling après une erreur)


def fichier_offset(upstream=None):
    """Où l'offset est gardé : NC_TELEGRAM_OFFSET_FILE, sinon à côté du main.py du gateway (comme reminders.db)."""
    perso = os.environ.get("NC_TELEGRAM_OFFSET_FILE", "").strip()
    if perso:
        return Path(perso)
    source = getattr(upstream, "__file__", None) if upstream is not None else None
    return (Path(source).resolve().parent if source else Path.cwd()) / "nc-telegram-offset.json"


def lire_offset(chemin):
    """L'offset gardé (0 : aucun, ou fichier illisible : Telegram donne alors tout ce qui n'est pas confirmé)."""
    try:
        d = json.loads(Path(chemin).read_text(encoding="utf-8"))
        offset = int(d.get("offset", 0)) if isinstance(d, dict) else 0
        return offset if offset > 0 else 0
    except (OSError, ValueError, TypeError):
        return 0


def ecrire_offset(chemin, offset):
    """Écriture atomique ; une erreur de disque est journalisée, jamais fatale pour le bot."""
    chemin = Path(chemin)
    try:
        tmp = chemin.with_name(chemin.name + ".tmp")
        tmp.write_text(json.dumps({"offset": int(offset), "date": datetime.datetime.now().astimezone().isoformat(timespec="seconds")}),
                       encoding="utf-8")
        os.replace(tmp, chemin)
    except (OSError, ValueError) as exc:
        logger.warning("Offset Telegram non enregistré dans %s : %s", chemin, exc)


def quand(date, maintenant=None):
    """« HH:MM » du message en heure locale, avec le jour s'il ne date pas d'aujourd'hui."""
    maintenant = maintenant or datetime.datetime.now().astimezone()
    if not isinstance(date, datetime.datetime):
        date = datetime.datetime.fromtimestamp(float(date), datetime.timezone.utc)
    if date.tzinfo is None:
        date = date.replace(tzinfo=datetime.timezone.utc)
    locale = date.astimezone(maintenant.tzinfo)
    return locale.strftime("%H:%M") if locale.date() == maintenant.date() else locale.strftime("%d/%m %H:%M")


def _horodatage(date):
    if isinstance(date, datetime.datetime):
        return (date if date.tzinfo else date.replace(tzinfo=datetime.timezone.utc)).timestamp()
    return float(date)


async def rattraper(app, chemin, demarrage=None, reconstruire=None):
    """Traite, dans l'ordre, les messages en attente chez Telegram depuis l'offset gardé ; renvoie combien étaient
    arrivés pendant l'arrêt. Le dernier appel (liste vide) confirme le tout à Telegram ; ``reconstruire(dict, bot)``
    (telegram.Update.de_json) sert à préfixer le texte d'un message en attente."""
    demarrage = time.time() if demarrage is None else demarrage
    offset = lire_offset(chemin)
    retard = 0
    while True:
        updates = await app.bot.get_updates(offset=offset if offset > 0 else None, timeout=0, limit=100)
        if not updates:
            return retard
        for u in updates:
            numero = u.update_id
            if numero < offset:
                continue    # déjà traité avant un arrêt brutal
            message = getattr(u, "message", None)
            texte = getattr(message, "text", None) if message is not None else None
            if message is not None and getattr(message, "date", None) is not None and _horodatage(message.date) < demarrage:
                heure = quand(message.date)
                retard += 1
                logger.info("Telegram : message %d reçu pendant l'arrêt à %s, traité maintenant", numero, heure)
                try:
                    await app.bot.send_message(chat_id=message.chat.id, text="⏱ Reçu pendant l'arrêt à " + heure + " : traité maintenant.")
                except Exception as exc:
                    logger.warning("Telegram : avertissement de retard non envoyé (%s)", exc)
                if reconstruire is not None and isinstance(texte, str) and texte.strip() and not texte.lstrip().startswith("/"):
                    try:
                        donnees = u.to_dict()
                        donnees["message"]["text"] = "[Reçu pendant l'arrêt à " + heure + "] " + texte
                        u = reconstruire(donnees, app.bot)
                    except Exception as exc:
                        logger.warning("Telegram : préfixe de retard non posé (%s)", exc)
            try:
                await app.process_update(u)
            except Exception as exc:
                logger.error("Telegram : message %d en attente non traité : %s", numero, exc)
            offset = numero + 1
            ecrire_offset(chemin, offset)


def noter_offset(chemin):
    """Handler (groupe -100, avant tout autre) qui garde l'offset de chaque message traité en polling normal."""
    async def handler(update, context):
        ecrire_offset(chemin, update.update_id + 1)
    return handler


HEURES = re.compile(r"^\s*(?:toutes\s+les|tous\s+les|chaque)\s+(\d{1,3})\s+heures?\b[,\s]*|^\s*(?:toutes\s+les|chaque)\s+heures?\b[,\s]*", re.IGNORECASE)


def etendre_rappels(reminders, tb=None):
    """Récurrence « toutes les N heures » (every:hours:N) dans le module reminders upstream : le préfixe de /rappel, la
    prochaine occurrence (le planificateur) et le libellé. Les autres règles passent aux fonctions d'origine."""
    if getattr(reminders, "_nc_heures", False):
        return
    origine_prefixe, origine_suivante, origine_libelle = reminders.strip_recurrence_prefix, reminders.compute_next_occurrence, reminders.recurrence_label

    def strip_recurrence_prefix(text):
        m = HEURES.match(text or "")
        if m:
            return "every:hours:%d" % max(1, int(m.group(1) or 1)), text[m.end():].strip()
        return origine_prefixe(text)

    def compute_next_occurrence(current, recurrence):
        m = re.fullmatch(r"every:hours:(\d+)", recurrence or "")
        if m:
            return current + datetime.timedelta(hours=max(1, int(m.group(1))))
        return origine_suivante(current, recurrence)

    def recurrence_label(recurrence):
        m = re.fullmatch(r"every:hours:(\d+)", recurrence or "")
        if m:
            n = int(m.group(1))
            return "Toutes les heures" if n == 1 else "Toutes les %d heures" % n
        return origine_libelle(recurrence)

    reminders.strip_recurrence_prefix, reminders.compute_next_occurrence, reminders.recurrence_label = strip_recurrence_prefix, compute_next_occurrence, recurrence_label
    if tb is not None and hasattr(tb, "recurrence_label"):
        tb.recurrence_label = recurrence_label      # importé par son nom dans le module du bot
    reminders._nc_heures = True


async def diffuser(texte, tb=None):
    """Un message Telegram à tous les chats que le bot connaît (ceux qui lui ont écrit) ; {sent, error?}."""
    if not isinstance(texte, str) or not 1 <= len(texte.strip()) <= 4000:
        return dict(sent=False, error="Texte vide ou trop long (4 000 caractères)")
    if tb is None:
        try:
            tb = importlib.import_module("bots.telegram_bot")
        except ImportError:
            return dict(sent=False, error="Bot Telegram absent de ce gateway")
    if not getattr(tb, "TELEGRAM_TOKEN", ""):
        return dict(sent=False, error="Telegram non configuré (TELEGRAM_TOKEN)")
    try:
        envoye = await tb.send_broadcast_message(texte.strip())
    except Exception as exc:
        logger.warning("Diffusion Telegram impossible : %s", exc)
        return dict(sent=False, error="Envoi Telegram impossible")
    return dict(sent=bool(envoye)) if envoye else dict(sent=False, error="Aucun chat Telegram connu : écris d'abord au bot")


def commandes_nc(app, tb, chemin_offset=None):
    """Handlers de l'overlay sur l'application upstream : /supprimer (alias de /annuler_rappel) et /nc (nc_noctalia)."""
    from telegram import BotCommand
    from telegram.ext import CommandHandler
    if hasattr(tb, "cmd_annuler_rappel"):
        app.add_handler(CommandHandler(["supprimer"], tb.cmd_annuler_rappel))
    try:
        import nc_noctalia
        app.add_handler(CommandHandler(["nc", "pc"], nc_noctalia.handler(tb)))
        descriptions = [("nc", "Réglages du PC Noctalia (/nc aide)"), ("supprimer", "Supprimer un rappel : /supprimer <id>")]
    except ImportError as exc:
        logger.warning("Commandes /nc indisponibles : %s", exc)
        descriptions = [("supprimer", "Supprimer un rappel : /supprimer <id>")]
    existantes = {getattr(c, "command", None) for c in tb.BOT_COMMANDS}
    for nom, description in descriptions:
        if nom not in existantes:
            tb.BOT_COMMANDS.append(BotCommand(nom, description))


def demarrer_polling(tb, chemin):
    """Même thread et même boucle que start_telegram_polling upstream, sans jeter les messages en attente."""
    if not tb.TELEGRAM_TOKEN:
        logger.warning("TELEGRAM_TOKEN non défini — bot Telegram non démarré.")
        return
    tb._stop_event.clear()

    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        app = tb.get_application()

        async def _async_polling():
            from telegram import Update
            from telegram.ext import TypeHandler
            tb._TELEGRAM_LOOP = asyncio.get_running_loop()
            demarrage = time.time()
            await app.initialize()
            # Le webhook est retiré pour le polling, mais les messages reçus pendant l'arrêt sont gardés
            await app.bot.delete_webhook(drop_pending_updates=False)
            if id(app) not in _avec_suivi:
                app.add_handler(TypeHandler(Update, noter_offset(chemin)), group=-100)
                _avec_suivi.add(id(app))
                try:
                    commandes_nc(app, tb)
                except Exception as exc:     # le bot démarre quand même, sans /nc ni /supprimer
                    logger.warning("Commandes de l'overlay non ajoutées : %s", exc)
            try:
                await app.bot.set_my_commands(tb.BOT_COMMANDS)
                logger.info("Commandes Telegram enregistrées avec succès (autocomplétion active).")
            except Exception as exc:
                logger.warning("Impossible d'enregistrer les commandes Telegram: %s", exc)
            await app.start()
            retard = await rattraper(app, chemin, demarrage, Update.de_json)
            logger.info("Telegram : %d message(s) reçu(s) pendant l'arrêt traité(s) ; offset gardé dans %s", retard, chemin)
            await app.updater.start_polling()
            logger.info("Bot Telegram démarré en mode POLLING (local), messages en attente conservés.")
            while not tb._stop_event.is_set():
                await asyncio.sleep(1)
            await app.updater.stop()
            await app.stop()
            await app.shutdown()

        while not tb._stop_event.is_set():
            try:
                loop.run_until_complete(_async_polling())
                break
            except Exception as exc:
                if tb._stop_event.is_set():
                    break
                logger.error("Erreur dans le polling Telegram: %s. Nouvelle tentative dans 5s...", exc)
                time.sleep(5)
        loop.close()

    tb._polling_thread = threading.Thread(target=_run, name="telegram-polling", daemon=True)
    tb._polling_thread.start()
    logger.info("Thread de polling Telegram lancé (overlay nc : messages en attente conservés).")


def installer(upstream, tb=None, chemin=None):
    """Branche l'overlay : le lifespan upstream appelle start_telegram_polling() par le nom importé dans main, c'est lui
    qui est remplacé ; stop_telegram_polling upstream (il lève _stop_event) convient tel quel. Renvoie le fichier d'offset,
    ou None si le module du bot n'est pas là (gateway sans bots)."""
    if tb is None:
        try:
            tb = importlib.import_module("bots.telegram_bot")
        except ImportError as exc:
            logger.warning("Bot Telegram upstream introuvable, messages reçus pendant l'arrêt non rattrapés : %s", exc)
            return None
    chemin = Path(chemin) if chemin else fichier_offset(upstream)
    upstream.start_telegram_polling = lambda: demarrer_polling(tb, chemin)
    try:
        etendre_rappels(importlib.import_module("reminders"), tb)
    except ImportError as exc:
        logger.warning("Rappels « toutes les N heures » indisponibles : %s", exc)
    return chemin
