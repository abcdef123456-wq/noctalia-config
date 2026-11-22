#!/usr/bin/env python3
"""Schéma de la disposition d'un thème : un PNG dessiné à l'échelle, PAS une capture d'écran.

  outils/schema-theme.py --sortie DOSSIER [--themes DOSSIER] [--palettes DOSSIER] [--largeur 1600] [--planche FICHIER.png] NOM...

Un PNG par thème : DOSSIER/NOM.png (16:10). --planche ajoute une grille de tous les thèmes demandés, 4 par ligne.
--themes : dossier des thèmes (défaut : celui du dépôt). --palettes : dossier de palettes <Nom>.json lu en premier
(sinon celles du dépôt, puis celles de Noctalia si elles existent). Palette introuvable (fond d'écran, builtin absent) :
gris neutres, écrit « couleurs neutres » sur l'image.

Les valeurs sont les valeurs EFFECTIVES, calculées comme le système : les réglages du thème par-dessus les défauts de
nc-reglages (PAR_CLE), la table « noctalia » du thème par-dessus home/.config/noctalia/config.toml.

Fidèle : position, épaisseur et marge de la barre, capsules, style des bureaux, rayon et contour de l'île, disposition des
fenêtres (spirale, principale, colonnes), espaces, bordure, arrondi, ombre, dock (taille, position, caché), couleurs de la palette.
Approximé : les blocs de la barre sont des rectangles gris (pas les vrais widgets), l'espace entre deux fenêtres vaut
2 x gaps_in, l'ombre est un flou simple, la bordure en dégradé va de l'accent au second accent, les tailles sont celles d'un
écran 2560 x 1600 ramenées à la largeur demandée, le fond est une teinte unie (pas le fond d'écran).
Python 3.8 compatible (sans tomllib : valeurs de la barre en dur, signalé par un avertissement)."""
import argparse
import importlib.util
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
from unittest import mock

DEPOT = Path(__file__).resolve().parents[1]
BIN = DEPOT / "home/.local/bin/nc-reglages"
THEMES = DEPOT / "home/.local/share/nc/themes"
PALETTES_DEPOT = DEPOT / "home/.config/noctalia/palettes"
CONFIG_TOML = DEPOT / "home/.config/noctalia/config.toml"
LOGIQUE = (2560, 1600)  # écran de référence : toutes les mesures sont en pixels de cet écran
DEFAUT_NOCT = {"bar": {"default": {"position": "top", "thickness": 36, "margin_edge": 6, "capsule": True}},
               "widget": {"workspaces": {"style": "regular", "show_labels": True}},
               "dock": {"radius": 26, "margin_edge": 10}}


def dans_le_depot(chemin):
    c = Path(os.path.realpath(str(chemin)))
    return c == DEPOT or DEPOT in c.parents


def charger_reglages(themes_dir, tmp):
    """Importe nc-reglages dans un HOME temporaire (rien du vrai dossier personnel n'est lu)."""
    env = {"HOME": str(tmp), "XDG_CONFIG_HOME": str(tmp / "config"), "XDG_DATA_HOME": str(tmp / "data"),
           "XDG_CACHE_HOME": str(tmp / "cache"), "XDG_STATE_HOME": str(tmp / "state"), "TMPDIR": str(tmp),
           "NC_THEMES_DIR": str(themes_dir), "NC_LANGUE": "fr"}
    for d in ("config", "data", "cache", "state"):
        (tmp / d).mkdir(exist_ok=True)
    with mock.patch.dict(os.environ, env):
        loader = SourceFileLoader("nc_reglages_schema", str(BIN))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        mod = importlib.util.module_from_spec(spec)
        loader.exec_module(mod)
        themes, refuses = mod.charger_themes()
    return mod, themes, refuses


def lire_noctalia_defaut():
    """config.toml du dépôt sans ses @MARQUEURS@ (valeur nue : false ; dans une chaîne ou une liste : vide)."""
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            print("schema-theme : tomllib absent (Python < 3.11), valeurs de la barre en dur", file=sys.stderr)
            return json.loads(json.dumps(DEFAUT_NOCT))
    txt = CONFIG_TOML.read_text(encoding="utf-8")
    txt = re.sub(r"(=\s*)@\w+@", r"\1false", txt)
    txt = re.sub(r"@\w+@", "", txt)
    return tomllib.loads(txt)


def valeurs_effectives(mod, theme, noct_defaut):
    """(réglages effectifs {CLE: valeur}, noctalia effectif {bar, widget, dock}) d'un thème chargé : règle de nc-reglages."""
    reg, noct = mod.valeurs_theme(theme, noct_defaut)
    return reg, {"bar": noct.get("bar", {}).get("default", {}), "bs": noct.get("widget", {}).get("workspaces", {}),
                 "dock": noct.get("dock", {})}


def entier(v, defaut):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return defaut


def palette_du_theme(mod, theme, dossier_palettes):
    """(couleurs {primary, secondary, tertiary, surface, onSurface, outline}, neutre?)."""
    src, nom = (list(theme.get("palette") or []) + ["", ""])[:2]
    neutre = dict(mod.COULEURS_NEUTRES)
    neutre.setdefault("outline", "#5a5c66")
    if src in ("custom", "builtin") and nom:
        cand = []
        if dossier_palettes:
            cand.append(os.path.join(dossier_palettes, nom + ".json"))
        cand.append(str(PALETTES_DEPOT / (nom + ".json")))
        if src == "builtin":
            cand += mod.palettes_noctalia("builtin", nom)
        for f in cand:
            try:
                d = mod.lire_palette(f)
            except (OSError, ValueError, KeyError):
                continue
            c = {k: d.get("m" + k[0].upper() + k[1:], neutre[k]) for k in neutre}
            if all(re.fullmatch(r"#[0-9a-fA-F]{6}", str(v)) for v in c.values()):
                return c, False
    return neutre, True


# --- dessin -----------------------------------------------------------------------------------------------------

def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def melange(a, b, t):
    return tuple(int(round(x + (y - x) * t)) for x, y in zip(rgb(a), rgb(b)))


def hexa(t):
    return "#%02x%02x%02x" % t


def police(taille):
    from PIL import ImageFont
    for nom in ("Inter-Regular.ttf", "DejaVuSans.ttf", "NotoSans-Regular.ttf", "LiberationSans-Regular.ttf",
                "Cantarell-Regular.otf", "FreeSans.ttf"):  # une police avec les accents ; sinon celle de Pillow
        try:
            return ImageFont.truetype(nom, taille)
        except OSError:
            continue
    try:
        return ImageFont.load_default(taille)
    except TypeError:  # Pillow < 10.1 : police fixe
        return ImageFont.load_default()


def rayon_ile(reg):
    r = reg.get("ILE_RAYON", "auto")
    noms = {"auto": 100, "normal": 100, "carre": 0, "doux": 50, "rond": 200}
    if r in noms:
        return noms[r]
    n = int(r) if re.fullmatch(r"[0-9]+", r) else 100
    return n if n <= 200 else 100


def dessiner(theme_nom, theme, reg, noct, couleurs, neutre, largeur):
    from PIL import Image, ImageDraw
    s = largeur / LOGIQUE[0]
    W, H = largeur, int(round(LOGIQUE[1] * s))
    LEG = int(round(150 * s))  # bandeau de légende sous le schéma
    img = Image.new("RGB", (W, H + LEG))
    d = ImageDraw.Draw(img, "RGBA")

    def p(v):
        return int(round(v * s))

    def rr(box, rad, **kw):
        d.rounded_rectangle([int(box[0]), int(box[1]), int(box[2]) - 1, int(box[3]) - 1], radius=max(0, int(rad)), **kw)

    surf, prim, sec = couleurs["surface"], couleurs["primary"], couleurs["secondary"]
    fond = "#000000" if reg.get("FENETRES_FOND") == "noir" else hexa(melange(surf, "#0b1226", 0.5))
    d.rectangle([0, 0, W, H], fill=fond)

    # barre
    b = noct["bar"]
    pos = b.get("position", "top")
    ep, marge = p(entier(b.get("thickness"), 36)), p(entier(b.get("margin_edge"), 0))
    bout = p(entier(b.get("margin_ends"), 10))
    horiz = pos in ("top", "bottom")
    if pos == "top":
        zone = (bout, marge, W - bout, marge + ep)
    elif pos == "bottom":
        zone = (bout, H - marge - ep, W - bout, H - marge)
    elif pos == "left":
        zone = (marge, bout, marge + ep, H - bout)
    else:
        zone = (W - marge - ep, bout, W - marge, H - bout)
    reserve = ep + marge
    # zone utile pour les fenêtres : écran moins la barre, moins le dock s'il réserve de la place (il flotte : non)
    go = p(entier(reg.get("FENETRES_MARGE"), 10))
    gi = p(entier(reg.get("FENETRES_ESPACE"), 4)) * 2
    x0, y0, x1, y1 = 0, 0, W, H
    if pos == "top":
        y0 = reserve
    elif pos == "bottom":
        y1 = H - reserve
    elif pos == "left":
        x0 = reserve
    else:
        x1 = W - reserve
    x0, y0, x1, y1 = x0 + go, y0 + go, x1 - go, y1 - go
    fenetres(d, img, reg, couleurs, (x0, y0, x1, y1), gi, s)

    # dock
    dessiner_dock(d, reg, noct, couleurs, W, H, s, pos, reserve)

    # la barre puis l'île sont des couches au-dessus des fenêtres et du dock : dessinées en dernier
    if marge == 0:
        d.rectangle(list(zone), fill=hexa(melange(surf, "#000000", 0.2)) + "e0")
    capsule = bool(b.get("capsule", True))
    gris = hexa(melange(surf, couleurs["onSurface"], 0.25))
    gris_cap = gris if capsule else None
    pad = p(8)
    # trois blocs : début (long), centre (court), fin (long)
    z0, z1 = (zone[0], zone[2]) if horiz else (zone[1], zone[3])
    fr = [(0.0, 0.30), (0.40, 0.60), (0.68, 1.0)]
    for i, (a, c) in enumerate(fr):
        a0, a1 = z0 + (z1 - z0) * a + (pad if a == 0 else 0), z0 + (z1 - z0) * c - (pad if c == 1.0 else 0)
        if i == 1:
            continue  # le centre est la place de l'île : laissé vide
        cross0 = (zone[1] if horiz else zone[0]) + int(ep * 0.07)
        cross1 = (zone[3] if horiz else zone[2]) - int(ep * 0.07)
        box = (a0, cross0, a1, cross1) if horiz else (cross0, a0, cross1, a1)
        if gris_cap:
            rr(box, ep, fill=gris_cap + "70")
        else:
            rr(box, ep // 3, fill=gris + "30")
        # petits rectangles de widgets
        n = 4 if i == 0 else 5
        for k in range(n):
            u0 = a0 + (a1 - a0) * (0.06 + 0.9 * k / n)
            u1 = u0 + (a1 - a0) * 0.9 / n * 0.6
            if i == 0 and k == 1:
                continue  # les bureaux sont dessinés à part
            wb = (u0, cross0 + ep * 0.3, u1, cross1 - ep * 0.3) if horiz else (cross0 + ep * 0.3, u0, cross1 - ep * 0.3, u1)
            rr(wb, ep // 6, fill=couleurs["onSurface"] + "55")
        if i == 0:
            pastilles_bureaux(d, noct["bs"], couleurs, horiz, a0, a1, cross0, cross1, ep, s)

    # île : pilule en haut au centre, quelle que soit la barre
    iw, ih = p(380), p(46)
    ix, iy = (W - iw) // 2, p(8) + (marge if pos == "top" else 0)
    base = ih / 2.0
    ray = min(base * rayon_ile(reg) / 100.0, min(iw, ih) / 2.0)
    noire = reg.get("ILE_STYLE") == "noir"
    fond_ile = "#000000" if noire else couleurs["surface"]
    verre = max(0, min(100, entier(reg.get("ILE_VERRE"), 100)))
    d.rounded_rectangle([ix, iy, ix + iw - 1, iy + ih - 1], radius=int(ray),
                        fill=fond_ile + "%02x" % int(255 * verre / 100.0) if verre < 100 else fond_ile)
    epc = entier(reg.get("ILE_CONTOUR_EPAISSEUR"), 2)
    contour = reg.get("ILE_CONTOUR", "degrade")
    if epc > 0 and contour != "aucun" and (reg.get("ILE_CONTOUR_FERMEE") == "oui" or True):
        col = hexa(melange(prim, sec, 0.5)) if contour == "degrade" else couleurs["outline"]
        d.rounded_rectangle([ix, iy, ix + iw - 1, iy + ih - 1], radius=int(ray), outline=col, width=max(1, p(epc)))
    ft = police(max(8, p(15)))
    d.text((ix + iw // 2, iy + ih // 2), "île", font=ft, fill=couleurs["onSurface"], anchor="mm")

    # légende
    d.rectangle([0, H, W, H + LEG], fill="#101114")
    legende(d, theme_nom, theme, reg, noct, neutre, W, H, LEG, s)
    return img


def pastilles_bureaux(d, bs, couleurs, horiz, a0, a1, c0, c1, ep, s):
    style = bs.get("style", "regular")
    labels = bool(bs.get("show_labels", True))
    n = 5
    taille = max(4, int(ep * 0.18))
    cx0 = a0 + (a1 - a0) * 0.30
    cy = (c0 + c1) / 2.0
    pas = taille * 3.2
    from PIL import ImageDraw  # noqa: F401  (PIL déjà vérifié par l'appelant)
    f = police(max(7, int(ep * 0.36)))
    for k in range(n):
        actif = k == 1
        if style == "minimal":
            lg = taille * (3.0 if actif else 1.6)
            col = couleurs["primary"] if actif else couleurs["outline"]
            box = (cx0 + k * pas, cy - taille / 4, cx0 + k * pas + lg, cy + taille / 4)
            d.rounded_rectangle([int(v) for v in box], radius=int(taille / 4), fill=col)
            continue
        if style == "focus_hint" and not actif:
            continue
        lg = taille * (2.6 if actif else 1.0)
        x = cx0 + k * pas + (taille * 0.8 if k > 1 else 0)
        col = couleurs["primary"] if actif else couleurs["secondary" if k < 3 else "outline"]
        if horiz:
            box = (x, cy - taille / 2, x + lg, cy + taille / 2)
        else:
            box = (cy - taille / 2, x, cy + taille / 2, x + lg)
        d.rounded_rectangle([int(v) for v in box], radius=int(taille / 2), fill=col)
        if labels and style != "focus_hint" and not actif and k < 3:
            d.text(((box[0] + box[2]) / 2, box[1] - taille * 1.1) if horiz else (box[0] - taille * 1.1, (box[1] + box[3]) / 2),
                   str(k + 1), font=f, fill=couleurs["onSurface"], anchor="mm")
        elif labels and actif:
            d.text(((box[0] + box[2]) / 2, box[1] - taille * 1.1) if horiz else (box[0] - taille * 1.1, (box[1] + box[3]) / 2),
                   "2", font=f, fill=couleurs["primary"], anchor="mm")


def fenetres(d, img, reg, couleurs, aire, gi, s):
    from PIL import Image, ImageDraw, ImageFilter
    x0, y0, x1, y1 = aire
    disp = reg.get("FENETRES_DISPOSITION", "dwindle")
    ori = reg.get("FENETRES_MAITRE_ORIENTATION", "auto")
    w, h = x1 - x0, y1 - y0
    if disp == "master":
        if ori in ("auto", "gauche", ""):
            r = [(x0, y0, x0 + (w - gi) * 0.55, y1), (x0 + (w - gi) * 0.55 + gi, y0, x1, y1)]
        elif ori == "droite":
            r = [(x0 + (w - gi) * 0.45 + gi, y0, x1, y1), (x0, y0, x0 + (w - gi) * 0.45, y1)]
        elif ori == "haut":
            r = [(x0, y0, x1, y0 + (h - gi) * 0.6), (x0, y0 + (h - gi) * 0.6 + gi, x1, y1)]
        elif ori == "bas":
            r = [(x0, y0 + (h - gi) * 0.4 + gi, x1, y1), (x0, y0, x1, y0 + (h - gi) * 0.4)]
        else:  # centre : la principale au milieu, la pile à droite (une seule autre fenêtre)
            r = [(x0 + w * 0.2, y0, x0 + w * 0.8, y1), (x0 + w * 0.8 + gi, y0, x1, y1)]
    elif disp == "scrolling":
        cw = (w - gi) * 0.62
        r = [(x0, y0, x0 + cw, y1), (x0 + cw + gi, y0, x0 + 2 * cw + gi, y1)]  # la seconde dépasse de l'aire utile : coupée
    else:  # dwindle : deux moitiés
        r = [(x0, y0, x0 + (w - gi) / 2.0, y1), (x0 + (w - gi) / 2.0 + gi, y0, x1, y1)]
    rad = int(entier(reg.get("FENETRES_ARRONDI"), 14) * s)
    bord = int(round(entier(reg.get("FENETRES_BORDURE"), 2) * s * 1.5)) if entier(reg.get("FENETRES_BORDURE"), 2) > 0 else 0
    ombre = int(entier(reg.get("FENETRES_OMBRE"), 22) * s * 1.5)
    dec = {"auto": (0, 4), "aucun": (0, 0), "bas": (0, 8), "dure": (8, 8)}.get(reg.get("FENETRES_OMBRE_DECALAGE", "auto"), (0, 4))
    dure = reg.get("FENETRES_OMBRE_DECALAGE") == "dure"
    degrade = None
    clip = (0, 0, img.width, img.height - 0)
    for i, box in enumerate(r):
        bx = (int(box[0]), int(box[1]), int(min(box[2], x1)), int(box[3]))
        coupee = box[2] > x1
        # ombre
        if ombre > 0:
            couche = Image.new("RGBA", img.size, (0, 0, 0, 0))
            cd = ImageDraw.Draw(couche)
            ox, oy = int(dec[0] * s * 1.5), int(dec[1] * s * 1.5)
            cd.rounded_rectangle([bx[0] + ox, bx[1] + oy, bx[2] + ox, bx[3] + oy], radius=rad, fill=(0, 0, 0, 200 if dure else 150))
            if not dure:
                couche = couche.filter(ImageFilter.GaussianBlur(max(1, ombre / 2.0)))
            img.paste(Image.alpha_composite(img.convert("RGBA"), couche).convert("RGB"))
        d = ImageDraw.Draw(img, "RGBA")
        fen = hexa(melange(couleurs["surface"], couleurs["onSurface"], 0.06 if i == 0 else 0.02))
        d.rounded_rectangle([bx[0], bx[1], bx[2] - 1, bx[3] - 1], radius=rad, fill=fen)
        # barre de titre et lignes de texte factices
        tb = int(40 * s)
        d.line([bx[0] + rad // 2, bx[1] + tb, bx[2] - rad // 2, bx[1] + tb], fill=couleurs["outline"] + "60", width=max(1, int(s * 2)))
        for k in range(5):
            yy = bx[1] + tb + int(30 * s) + k * int(34 * s)
            if yy < bx[3] - int(30 * s):
                d.rounded_rectangle([bx[0] + int(30 * s), yy, bx[0] + int((70 + 40 * ((k * 7) % 5)) * s * 3), yy + int(10 * s)],
                                    radius=int(5 * s), fill=couleurs["onSurface"] + "30")
        if bord:
            if i == 0:
                masque = Image.new("L", img.size, 0)
                md = ImageDraw.Draw(masque)
                md.rounded_rectangle([bx[0], bx[1], bx[2] - 1, bx[3] - 1], radius=rad, outline=255, width=bord)
                if degrade is None:
                    degrade = couleurs
                grad = Image.new("RGB", img.size)
                gd = ImageDraw.Draw(grad)
                for xx in range(bx[0], bx[2] + 1):
                    gd.line([xx, 0, xx, img.height], fill=melange(couleurs["primary"], couleurs["secondary"], (xx - bx[0]) / float(max(1, bx[2] - bx[0]))))
                img.paste(grad, (0, 0), masque)
            else:
                d.rounded_rectangle([bx[0], bx[1], bx[2] - 1, bx[3] - 1], radius=rad, outline=couleurs["outline"], width=bord)
        if coupee:
            pass
    return clip


def dessiner_dock(d, reg, noct, couleurs, W, H, s, pos_barre, reserve):
    if reg.get("DOCK", "oui") != "oui":
        return
    dock = noct["dock"]
    pos = reg.get("DOCK_POSITION", "bottom")
    taille = max(16, int(entier(reg.get("DOCK_TAILLE"), 48) * s * 1.4))
    marge = int(entier(dock.get("margin_edge"), 10) * s)
    ray = int(entier(dock.get("radius"), 26) * s)
    n = 5
    esp = int(10 * s)
    long_ = n * taille + (n + 1) * esp
    court = taille + int(16 * s)
    surf = couleurs["surface"]
    if pos in ("bottom", "top"):
        cx = W // 2
        if pos == "bottom":
            y = H - marge - court - (reserve if pos_barre == "bottom" else 0)
        else:
            y = marge + (reserve if pos_barre == "top" else 0)
        box = [cx - long_ // 2, y, cx + long_ // 2, y + court]
    else:
        cy = H // 2
        if pos == "left":
            x = marge + (reserve if pos_barre == "left" else 0)
        else:
            x = W - marge - court - (reserve if pos_barre == "right" else 0)
        box = [x, cy - long_ // 2, x + court, cy + long_ // 2]
    if reg.get("DOCK_AUTO", "oui") == "oui":
        # caché : un fin trait au bord de l'écran
        ep = max(2, int(3 * s))
        if pos == "bottom":
            t = [W // 2 - long_ // 4, H - ep, W // 2 + long_ // 4, H - 1]
        elif pos == "top":
            t = [W // 2 - long_ // 4, 0, W // 2 + long_ // 4, ep]
        elif pos == "left":
            t = [0, H // 2 - long_ // 4, ep, H // 2 + long_ // 4]
        else:
            t = [W - ep, H // 2 - long_ // 4, W - 1, H // 2 + long_ // 4]
        d.rounded_rectangle(t, radius=ep // 2, fill=couleurs["onSurface"] + "b0")
        return
    d.rounded_rectangle(box, radius=min(ray, min(box[2] - box[0], box[3] - box[1]) // 2), fill=surf + "c8",
                        outline=couleurs["outline"] + "50", width=1)
    for k in range(n):
        o = esp + k * (taille + esp)
        if pos in ("bottom", "top"):
            ic = [box[0] + o, box[1] + (court - taille) // 2, box[0] + o + taille, box[1] + (court - taille) // 2 + taille]
        else:
            ic = [box[0] + (court - taille) // 2, box[1] + o, box[0] + (court - taille) // 2 + taille, box[1] + o + taille]
        col = couleurs[("primary", "secondary", "tertiary")[k % 3]]
        d.rounded_rectangle(ic, radius=taille // 4, fill=col + "c0")


def legende(d, nom, theme, reg, noct, neutre, W, H, LEG, s):
    ft = police(max(10, int(24 * s * 1.0)))
    pt = police(max(8, int(17 * s)))
    marge = int(26 * s)
    b = noct["bar"]
    libelle = theme.get("libelle", "")
    titre = (libelle.get("fr") or libelle.get("en") if isinstance(libelle, dict) else str(libelle)) or nom
    pos = {"top": "en haut", "bottom": "en bas", "left": "à gauche", "right": "à droite"}.get(b.get("position", "top"), "?")
    flottante = "flottante" if entier(b.get("margin_edge"), 0) > 0 else "collée"
    cap = "capsules" if b.get("capsule", True) else "sans capsules"
    barre = "Barre : %s, %s, %s, %d px" % (pos, flottante, cap, entier(b.get("thickness"), 36))
    sty = {"regular": "pilule + points", "minimal": "petits traits", "focus_hint": "un repère"}.get(noct["bs"].get("style", "regular"), "?")
    bur = "Bureaux : %s%s" % (sty, ", chiffres" if noct["bs"].get("show_labels", True) else "")
    disp = {"dwindle": "spirale", "master": "principale", "scrolling": "colonnes"}.get(reg.get("FENETRES_DISPOSITION"), "?")
    if reg.get("FENETRES_DISPOSITION") == "master":
        disp += " (" + {"auto": "gauche"}.get(reg.get("FENETRES_MAITRE_ORIENTATION"), reg.get("FENETRES_MAITRE_ORIENTATION", "gauche")) + ")"
    dock = "Dock : " + ("non" if reg.get("DOCK") != "oui" else "%s, %s px, %s" % (
        reg.get("DOCK_POSITION", "bottom"), reg.get("DOCK_TAILLE"), "caché" if reg.get("DOCK_AUTO") == "oui" else "visible"))
    coins = "Fenêtres : %s, coins %s px, bordure %s px, ombre %s px" % (disp, reg.get("FENETRES_ARRONDI"), reg.get("FENETRES_BORDURE"),
                                                                       reg.get("FENETRES_OMBRE"))
    anim = "Animations : %s   Île : police %s, coins %s, %s" % (reg.get("FENETRES_CARACTERE"), reg.get("ILE_POLICE"),
                                                               reg.get("ILE_RAYON"), "noire" if reg.get("ILE_STYLE") == "noir" else "couleurs du terminal")
    y = H + int(12 * s)
    d.text((marge, y), titre, font=ft, fill="#ffffff")
    if neutre:
        d.text((W - marge, y), "couleurs neutres", font=pt, fill="#e0b050", anchor="ra")
    lignes = [barre + "   |   " + bur, coins, dock + "   |   " + anim]
    for i, t in enumerate(lignes):
        d.text((marge, y + int(40 * s) + i * int(27 * s)), t, font=pt, fill="#c8c8d0")
    d.text((W - marge, H + LEG - int(10 * s)), "schéma (pas une capture)", font=police(max(8, int(14 * s))), fill="#808088", anchor="rd")


def planche(images, colonnes=4):
    from PIL import Image
    if not images:
        return None
    w, h = images[0].size
    g = max(8, w // 40)
    lignes = (len(images) + colonnes - 1) // colonnes
    pl = Image.new("RGB", (colonnes * w + (colonnes + 1) * g, lignes * h + (lignes + 1) * g), "#08080a")
    for i, im in enumerate(images):
        pl.paste(im, (g + (i % colonnes) * (w + g), g + (i // colonnes) * (h + g)))
    return pl


def main(argv=None):
    a = argparse.ArgumentParser(description="Schéma (pas une capture) de la disposition d'un thème.")
    a.add_argument("themes_demandes", nargs="+", metavar="THEME")
    a.add_argument("--themes", default=str(THEMES), help="dossier des thèmes (défaut : celui du dépôt)")
    a.add_argument("--sortie", required=True, help="dossier des PNG (hors du dépôt)")
    a.add_argument("--palettes", help="dossier de palettes <Nom>.json lu en premier")
    a.add_argument("--largeur", type=int, default=1600, help="largeur de l'image en pixels (défaut 1600, 16:10)")
    a.add_argument("--planche", help="fichier PNG : grille de tous les thèmes demandés, 4 par ligne")
    o = a.parse_args(argv)
    try:
        import PIL  # noqa: F401
    except ImportError:
        print("schema-theme : Pillow (PIL) est absent : pip install pillow, ou le paquet python-pillow de la distribution", file=sys.stderr)
        return 2
    if dans_le_depot(o.sortie) or (o.planche and dans_le_depot(os.path.dirname(os.path.abspath(o.planche)))):
        print("schema-theme : la sortie ne doit pas être dans le dépôt", file=sys.stderr)
        return 2
    if not 400 <= o.largeur <= 8000:
        print("schema-theme : --largeur doit être entre 400 et 8000", file=sys.stderr)
        return 2
    if not os.path.isdir(o.themes):
        print("schema-theme : dossier de thèmes introuvable : " + o.themes, file=sys.stderr)
        return 2
    os.makedirs(o.sortie, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="nct-schema-"))
    code, images = 0, []
    try:
        mod, themes, refuses = charger_reglages(o.themes, tmp)
        noct_defaut = lire_noctalia_defaut()
        for nom in o.themes_demandes:
            if nom not in themes:
                print("schema-theme : thème inconnu ou refusé : %s (%s)" % (nom, refuses.get(nom, "absent")), file=sys.stderr)
                code = 1
                continue
            th = themes[nom]
            reg, noct = valeurs_effectives(mod, th, noct_defaut)
            coul, neutre = palette_du_theme(mod, th, o.palettes)
            img = dessiner(nom, th, reg, noct, coul, neutre, o.largeur)
            chemin = os.path.join(o.sortie, nom + ".png")
            img.save(chemin)
            images.append(img)
            print(chemin)
        if o.planche and images:
            planche(images).save(o.planche)
            print(o.planche)
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)
    return code


if __name__ == "__main__":
    sys.exit(main())
