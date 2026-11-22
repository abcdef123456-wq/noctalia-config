"""Fonds d'écran du dépôt (home/Pictures/Wallpapers) : taille minimale, crédits des fonds de thème, anciens fonds figés.

- Sans dépendance : la taille est lue dans l'en-tête (JPEG SOFn, PNG IHDR, WebP VP8 / VP8L / VP8X).
- Règles : toute image fait au moins 2560 x 1600 ; une image d'un sous-dossier (fond de thème) a sa ligne dans
  CREDITS.tsv avec les 4 champs et une licence connue ; une image à la racine est un ancien fond sans crédit,
  listé ici ; chaque ligne de CREDITS.tsv désigne un fichier existant.
- Le lecteur d'en-tête est vérifié sur de petits fichiers fabriqués à la main, dans un dossier temporaire.
"""
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FONDS = REPO / "home/Pictures/Wallpapers"
CREDITS = "CREDITS.tsv"
ENTETE = "fichier\tsource\tauteur\tlicence"
MIN_LARGEUR, MIN_HAUTEUR = 2560, 1600
EXTENSIONS_IMAGE = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".avif", ".jxl")
LICENCES = {"CC0-1.0", "CC-BY-4.0", "CC-BY-SA-4.0", "Unsplash", "Pexels", "Pixabay", "généré par noctalia-config"}
# Les 14 anciens fonds à la racine : sans crédit, hors des thèmes. Liste figée : un ajout ou un retrait se fait ici.
ANCIENS_SANS_CREDIT = [
    "astronaut-dark-5120x2880-22768.jpg",
    "bmw-m4-coupe-8k-7680x4320-24121.jpg",
    "ctr-ferrari-458-7680x4320-27340.jpg",
    "desert-doom-sand-dunes-dark-background-monochrome-landscape-3840x2160-6409.jpg",
    "macos-mojave-sand-dunes-mojave-desert-california-night-dark-5120x2880-4051.jpg",
    "mclaren-788hs-coupe-11520x6480-26955.jpg",
    "mountain-landscape-5120x2880-24317.jpg",
    "porsche-911-gt3-rs-3840x2160-25139.jpg",
    "porsche-911-turbo-s-black-background-amoled-pitch-black-3840x2160-7730.jpg",
    "porsche-taycan-3840x2160-26875.jpg",
    "snow-mountains-5120x2880-25876.jpg",
    "spider-man-dark-cyan-minimal-3840x2160-170.jpg",
    "thorfinn-vinland-saga-5k-3840x2160-14948.jpg",
    "tiger-dope-amoled-3840x2160-18370.jpg",
]


def taille(octets):
    """(largeur, hauteur) lues dans l'en-tête. ValueError si ce n'est ni JPEG, ni PNG, ni WebP (VP8, VP8L, VP8X)."""
    if octets[:8] == b"\x89PNG\r\n\x1a\n" and octets[12:16] == b"IHDR":
        return struct.unpack(">II", octets[16:24])
    if octets[:3] == b"\xff\xd8\xff":
        i = 2
        while i + 4 <= len(octets):
            if octets[i] != 0xFF:
                break
            m = octets[i + 1]
            if m == 0xFF:                                   # bourrage avant un marqueur
                i += 1
                continue
            if 0xC0 <= m <= 0xCF and m not in (0xC4, 0xC8, 0xCC):   # SOFn, sauf DHT, JPG, DAC
                h, w = struct.unpack(">HH", octets[i + 5:i + 9])
                return w, h
            if m == 0xD8 or m == 0x01 or 0xD0 <= m <= 0xD7:  # SOI, TEM, RSTn : sans longueur
                i += 2
                continue
            i += 2 + struct.unpack(">H", octets[i + 2:i + 4])[0]
        raise ValueError("JPEG sans marqueur SOF lisible")
    if octets[:4] == b"RIFF" and octets[8:12] == b"WEBP":
        morceau = octets[12:16]
        if morceau == b"VP8X":
            return (1 + int.from_bytes(octets[24:27], "little"), 1 + int.from_bytes(octets[27:30], "little"))
        if morceau == b"VP8L":
            v = int.from_bytes(octets[21:25], "little")
            return (v & 0x3FFF) + 1, ((v >> 14) & 0x3FFF) + 1
        if morceau == b"VP8 ":
            larg, haut = struct.unpack("<HH", octets[26:30])
            return larg & 0x3FFF, haut & 0x3FFF
    raise ValueError("format non lu par le test (JPEG, PNG ou WebP seulement)")


def images(dossier):
    """Toutes les images du dossier, sous-dossiers compris, triées."""
    return sorted(p for p in Path(dossier).rglob("*") if p.is_file() and p.suffix.lower() in EXTENSIONS_IMAGE)


def lire_credits(dossier):
    """Lignes de CREDITS.tsv (sans l'en-tête) sous forme de listes de 4 champs."""
    lignes = (Path(dossier) / CREDITS).read_text(encoding="utf-8").splitlines()
    return [ligne.split("\t") for ligne in lignes[1:] if ligne != ""]


def manque_taille(dossier):
    """Images trop petites ou illisibles : une ligne par problème."""
    problemes = []
    for p in images(dossier):
        try:
            larg, haut = taille(p.read_bytes())
        except ValueError as e:
            problemes.append(f"{p.relative_to(dossier)} : {e}")
            continue
        if larg < MIN_LARGEUR or haut < MIN_HAUTEUR:
            problemes.append(f"{p.relative_to(dossier)} : {larg}x{haut}, minimum {MIN_LARGEUR}x{MIN_HAUTEUR}")
    return problemes


def sans_credit(dossier):
    """Images des sous-dossiers sans ligne complète (4 champs non vides, licence connue) dans CREDITS.tsv."""
    dossier = Path(dossier)
    lignes = {}
    for champs in lire_credits(dossier):
        lignes.setdefault(champs[0], []).append(champs)
    problemes = []
    for p in images(dossier):
        rel = p.relative_to(dossier).as_posix()
        if "/" not in rel:
            continue
        ok = [c for c in lignes.get(rel, []) if len(c) == 4 and all(c) and c[3] in LICENCES]
        if not ok:
            problemes.append(f"{rel} : pas de ligne complète dans {CREDITS}")
    return problemes


def racine_hors_liste(dossier):
    """Images à la racine absentes de ANCIENS_SANS_CREDIT, ou entrées de la liste qui n'existent plus."""
    dossier = Path(dossier)
    racine = sorted(p.name for p in dossier.iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONS_IMAGE)
    problemes = [f"{nom} : image à la racine hors de la liste figée" for nom in racine if nom not in ANCIENS_SANS_CREDIT]
    problemes += [f"{nom} : dans la liste figée, mais absente" for nom in ANCIENS_SANS_CREDIT if nom not in racine]
    return problemes


def credits_fantomes(dossier):
    """Lignes de CREDITS.tsv qui désignent un fichier absent (ou mal formées)."""
    dossier = Path(dossier)
    problemes = []
    if (dossier / CREDITS).read_text(encoding="utf-8").splitlines()[:1] != [ENTETE]:
        problemes.append("en-tête de CREDITS.tsv différent de « " + ENTETE.replace("\t", " / ") + " »")
    for champs in lire_credits(dossier):
        if len(champs) != 4:
            problemes.append(f"ligne à {len(champs)} champs au lieu de 4 : {champs}")
        elif not (dossier / champs[0]).is_file():
            problemes.append(f"{champs[0]} : fichier absent du dossier")
    return problemes


def jpeg(w, h):
    app0 = b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00" + bytes(9)
    dht = b"\xff\xc4" + struct.pack(">H", 3) + b"\x00"
    sof = b"\xff\xc0" + struct.pack(">H", 17) + b"\x08" + struct.pack(">HH", h, w) + b"\x03" + b"\x01\x22\x00" * 3
    return b"\xff\xd8" + app0 + dht + sof + b"\xff\xd9"


def png(w, h):
    corps = struct.pack(">II", w, h) + b"\x08\x02\x00\x00\x00"
    ihdr = struct.pack(">I", 13) + b"IHDR" + corps + struct.pack(">I", zlib.crc32(b"IHDR" + corps))
    fin = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", zlib.crc32(b"IEND"))
    return b"\x89PNG\r\n\x1a\n" + ihdr + fin


def webp(morceau, w, h):
    if morceau == b"VP8X":
        corps = b"\x00\x00\x00\x00" + (w - 1).to_bytes(3, "little") + (h - 1).to_bytes(3, "little")
    elif morceau == b"VP8L":
        v = (w - 1) | ((h - 1) << 14)
        corps = b"\x2f" + v.to_bytes(4, "little")
    else:
        corps = b"\x00\x00\x00\x9d\x01\x2a" + struct.pack("<HH", w, h)
    bloc = morceau + struct.pack("<I", len(corps)) + corps
    return b"RIFF" + struct.pack("<I", 4 + len(bloc)) + b"WEBP" + bloc


class FondsDuDepot(unittest.TestCase):
    def test_toutes_les_images_font_au_moins_2560_par_1600(self):
        self.assertEqual(manque_taille(FONDS), [])

    def test_chaque_image_de_sous_dossier_a_son_credit(self):
        self.assertEqual(sans_credit(FONDS), [])

    def test_anciens_fonds_de_la_racine_figes(self):
        self.assertEqual(racine_hors_liste(FONDS), [])

    def test_chaque_ligne_de_credits_designe_un_fichier(self):
        self.assertEqual(credits_fantomes(FONDS), [])


class LecteurEtControle(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="nc-fonds-")
        self.addCleanup(self._tmp.cleanup)
        self.d = Path(self._tmp.name)

    def test_lecteur_jpeg_png_webp(self):
        cas = {
            "a.jpg": (jpeg(2560, 1600), (2560, 1600)),
            "b.png": (png(3840, 2160), (3840, 2160)),
            "c-vp8x.webp": (webp(b"VP8X", 5120, 2880), (5120, 2880)),
            "d-vp8l.webp": (webp(b"VP8L", 1920, 1080), (1920, 1080)),
            "e-vp8.webp": (webp(b"VP8 ", 2561, 1601), (2561, 1601)),
        }
        for nom, (octets, attendu) in cas.items():
            with self.subTest(nom=nom):
                self.assertEqual(taille(octets), attendu)

    def test_format_inconnu_refuse(self):
        with self.assertRaises(ValueError):
            taille(b"GIF89a" + bytes(20))

    def test_controle_voit_une_image_1920x1080(self):
        (self.d / "petite.png").write_bytes(png(1920, 1080))
        (self.d / "ok.jpg").write_bytes(jpeg(2560, 1600))
        self.assertEqual(len(manque_taille(self.d)), 1)
        self.assertIn("petite.png", manque_taille(self.d)[0])

    def test_controle_voit_un_sous_dossier_sans_credit(self):
        (self.d / "theme").mkdir()
        (self.d / "theme" / "f.webp").write_bytes(webp(b"VP8L", 2560, 1600))
        (self.d / CREDITS).write_text(ENTETE + "\n", encoding="utf-8")
        self.assertEqual(sans_credit(self.d), ["theme/f.webp : pas de ligne complète dans CREDITS.tsv"])
        (self.d / CREDITS).write_text(ENTETE + "\ntheme/f.webp\tsrc\tauteur\tPexels\n", encoding="utf-8")
        self.assertEqual(sans_credit(self.d), [])
        (self.d / CREDITS).write_text(ENTETE + "\ntheme/f.webp\tsrc\t\tPexels\n", encoding="utf-8")
        self.assertEqual(len(sans_credit(self.d)), 1)


if __name__ == "__main__":
    unittest.main()
