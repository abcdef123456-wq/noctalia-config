"""export.sh reconstruit home/ depuis la seule liste HOME_FILES : un fichier de home/ qui n'y est pas serait supprimé
du dépôt au prochain export (revue EXP-01 : nc-ia, nc-session et 11 autres l'étaient)."""
from pathlib import Path
import os
import re
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]


class Export(unittest.TestCase):
    def test_tout_home_est_dans_home_files(self):
        texte = (REPO / "export.sh").read_text()
        # DEPOT_SEUL : suivis, jamais pris dans ~ (la photo de profil), mais gardés eux aussi
        liste = [e for nom in ("HOME_FILES", "DEPOT_SEUL")
                 for e in re.search(nom + r"=\((.*?)\n\)", texte, re.S)[1].split()]
        r = subprocess.run(["git", "-C", str(REPO), "ls-files", "-z", "--cached", "--others", "--exclude-standard", "home"],
                           capture_output=True, text=True)
        if r.returncode != 0:
            self.skipTest("pas un dépôt git")
        couvert = lambda f: any(f == e or f.startswith(e.rstrip("/") + "/") for e in liste)
        manque = [f[5:] for f in r.stdout.split("\0") if f and not couvert(f[5:])]
        self.assertEqual(manque, [], "à ajouter à HOME_FILES dans export.sh")


class ExportIsole(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="nc-export-")
        self.addCleanup(self.tmp.cleanup)
        self.racine = Path(self.tmp.name)
        self.depot, self.home, self.bin = [self.racine / n for n in ("depot", "utilisateur", "bin")]
        for p in (self.depot, self.home, self.bin):
            p.mkdir()
        self.env = dict(HOME=str(self.home), PATH=str(self.bin), NC_LANGUE="fr", LC_ALL="C",
                        GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        for nom in ("bash", "dirname", "mkdir", "mktemp", "find", "rm", "grep", "sed", "cp", "mv", "id", "git", "jq", "python3", "realpath", "readlink"):
            outil = shutil.which(nom)
            if not outil:
                self.skipTest(nom + " requis")
            (self.bin / nom).symlink_to(outil)
        # Le vrai Hyprland n'est jamais joint, même si la session de l'utilisateur est disponible.
        h = self.bin / "hyprctl"
        h.write_text('#!/bin/sh\necho "HYPRLAND_INSTANCE_SIGNATURE not set! (is hyprland running?)"\nexit 1\n')
        h.chmod(0o755)
        shutil.copy2(REPO / "export.sh", self.depot / "export.sh")
        (self.depot / "system").mkdir()
        fichiers = {
            ".config/hypr/nc/clavier.lua": 'kb_layout = "fr"\nkb_options = ""\n',
            ".config/noctalia/config.toml": 'center = []\n[lockscreen_widgets]\ncx = 800\ncy = 300\n[plugins]\nenabled = []\n',
            ".local/share/noctalia/plugins/nc-launcher/panel.luau": 'local navigateur = "firefox-developer-edition"\n',
            ".config/qt6ct/qt6ct.conf": 'style=Fusion\nicon_theme=Papirus\n',
            ".local/bin/nc-dictee": '#!/bin/sh\necho version-depot\n',
        }
        for rel, texte in fichiers.items():
            for base in (self.home, self.depot / "home"):
                p = base / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(texte)
        p = self.depot / "home/.local/bin/nc-ia"
        p.write_text('#!/bin/sh\necho nouveau-composant\n')
        p.chmod(0o755)
        qml = self.depot / "home/.config/quickshell/nc-ile/Nouveau.qml"
        qml.parent.mkdir(parents=True)
        qml.write_text('import QtQuick\nItem {}\n')
        for a in (("init", "-q"), ("add", "home"),
                  ("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "base")):
            subprocess.run(["git", "-C", str(self.depot), *a], env=self.env, capture_output=True, check=True)

    def exporter(self, *a):
        return subprocess.run([str(self.depot / "export.sh"), *a], env=self.env,
                              capture_output=True, text=True, timeout=20)

    def test_absents_du_pc_gardes_et_fichiers_installes_exportes(self):
        (self.home / ".local/bin/nc-dictee").write_text('#!/bin/sh\necho version-installee\n')
        r = self.exporter()
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        home = self.depot / "home"
        self.assertTrue((home / ".local/bin/nc-ia").exists(), "un composant non installé n'est pas supprimé du dépôt")
        self.assertTrue((home / ".config/quickshell/nc-ile/Nouveau.qml").exists())
        self.assertEqual((home / ".local/bin/nc-ia").stat().st_mode & 0o777, 0o755)
        self.assertIn("version-installee", (home / ".local/bin/nc-dictee").read_text())

    def test_nouveau_fichier_d_un_dossier_installe_garde(self):
        """Un ancien dossier installé (sans Nouveau.qml, suivi) n'efface pas les ajouts du dépôt ; son fichier pas encore
        suivi par git (Ancien.qml) est seulement signalé (E2)."""
        self.base_exportee()
        qml = self.home / ".config/quickshell/nc-ile"
        qml.mkdir(parents=True)
        (qml / "Ancien.qml").write_text('import QtQuick\nItem { width: 12 }\n')
        r = self.exporter()
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        resultat = self.depot / "home/.config/quickshell/nc-ile"
        self.assertTrue((resultat / "Nouveau.qml").exists(), "un ancien dossier installé n'efface pas les ajouts du dépôt")
        self.assertFalse((resultat / "Ancien.qml").exists(), "un nouveau fichier n'est pas publié sans le demander")
        self.assertIn("nouveau, pas publié : ~/.config/quickshell/nc-ile/Ancien.qml", r.stderr)
        self.assertIn("NC_EXPORT_NOUVEAUX=oui", r.stderr)
        self.assertEqual(self.etat(), "")

    def test_preview_ne_remplace_pas_le_depot(self):
        avant = (self.depot / "home/.local/bin/nc-dictee").read_bytes()
        (self.home / ".local/bin/nc-dictee").write_text('#!/bin/sh\necho version-installee\n')
        r = self.exporter("--preview")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertEqual((self.depot / "home/.local/bin/nc-dictee").read_bytes(), avant)
        self.assertFalse(list(self.depot.glob(".nc-export.*")))

    def test_dossier_installe_en_lien_symbolique(self):
        """A3-R2 : ~/.config/nvim lien vers un dossier faisait « type incompatible » et arrêtait tout l'export. Son
        contenu est publié, jamais le lien (sa cible contient le chemin du dossier personnel)."""
        (self.depot / "home/.config/nvim").mkdir(parents=True)
        (self.depot / "home/.config/nvim/depot.lua").write_text("-- seulement dans le dépôt\n")
        # Déjà suivis par git (sinon de nouveaux fichiers : pas publiés)
        (self.depot / "home/.config/nvim/lua").mkdir()
        (self.depot / "home/.config/nvim/init.lua").write_text("-- ancienne version\n")
        (self.depot / "home/.config/nvim/lua/reglages.lua").write_text("-- ancienne version\n")
        subprocess.run(["git", "-C", str(self.depot), "add", "home"], env=self.env, capture_output=True, check=True)
        subprocess.run(["git", "-C", str(self.depot), "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                        "commit", "-qm", "nvim"], env=self.env, capture_output=True, check=True)
        ailleurs = self.home / "ailleurs/nvim"
        (ailleurs / "lua").mkdir(parents=True)
        (ailleurs / "init.lua").write_text("vim.o.number = true\n")
        (ailleurs / "lua/reglages.lua").write_text("return {}\n")
        (self.home / ".config/nvim").symlink_to(ailleurs)
        (self.home / "ailleurs/p10k.zsh").write_text("# p10k\n")
        (self.home / ".p10k.zsh").symlink_to(self.home / "ailleurs/p10k.zsh")
        r = self.exporter()
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        nvim = self.depot / "home/.config/nvim"
        self.assertFalse(nvim.is_symlink(), "le lien lui-même n'est jamais publié")
        self.assertTrue(nvim.is_dir())
        self.assertEqual((nvim / "init.lua").read_text(), "vim.o.number = true\n")
        self.assertTrue((nvim / "lua/reglages.lua").exists())
        self.assertTrue((nvim / "depot.lua").exists(), "les fichiers du dépôt pas encore installés restent")
        p10k = self.depot / "home/.p10k.zsh"
        self.assertFalse(p10k.is_symlink(), "un lien vers un fichier : le fichier est publié")
        self.assertEqual(p10k.read_text(), "# p10k\n")

    def test_fichier_contre_dossier_refuse(self):
        (self.home / ".config/quickshell/nc-ile").parent.mkdir(parents=True)
        (self.home / ".config/quickshell/nc-ile").write_text("pas un dossier\n")
        r = self.exporter("--preview")
        self.assertEqual(r.returncode, 1)
        self.assertIn("type incompatible", r.stderr)
        self.assertFalse(list(self.depot.glob(".nc-export.*")))

    def etat(self):
        return subprocess.run(["git", "-C", str(self.depot), "status", "--porcelain", "--untracked-files=all", "--",
                               "home"], env=self.env, capture_output=True, text=True, check=True).stdout

    def base_exportee(self):
        """Le petit dépôt de setUp n'a pas ses repères (clavier, barre…) : un premier export, commité, sert de base,
        pour que git status ne montre ensuite que ce que le test change."""
        r = self.exporter()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.commit("base exportée")

    def commit(self, message):
        for a in (("add", "-A", "home"), ("-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                                          "commit", "-qm", message)):
            subprocess.run(["git", "-C", str(self.depot), *a], env=self.env, capture_output=True, check=True)

    def test_liens_dans_un_dossier_exporte(self):
        """P2-2 : un lien DANS un dossier exporté (fond d'écran -> /home/<nom>/…) était publié tel quel. Il est copié
        comme fichier s'il mène dans le même dossier, refusé sinon."""
        depot = self.depot / "home/Pictures/Wallpapers"           # déjà suivis par git
        depot.mkdir(parents=True)
        for nom in ("a.jpg", "copie.jpg", "perso.jpg"):
            (depot / nom).write_bytes(b"\xff\xd8ancienne")
        self.commit("fonds")
        fonds = self.home / "Pictures/Wallpapers"
        fonds.mkdir(parents=True)
        (fonds / "a.jpg").write_bytes(b"\xff\xd8image")
        (fonds / "copie.jpg").symlink_to("a.jpg")
        r = self.exporter()
        self.assertEqual(r.returncode, 0, r.stderr)
        copie = self.depot / "home/Pictures/Wallpapers/copie.jpg"
        self.assertFalse(copie.is_symlink(), "lien interne : copié comme fichier")
        self.assertEqual(copie.read_bytes(), b"\xff\xd8image")
        ailleurs = self.racine / "ailleurs.jpg"
        ailleurs.write_bytes(b"perso")
        (fonds / "perso.jpg").symlink_to(ailleurs)
        r = self.exporter("--preview")
        self.assertEqual(r.returncode, 1)
        self.assertIn("perso.jpg est un lien vers l'extérieur du dossier", r.stderr)

    def test_lien_interne_vers_un_dossier_refuse(self):
        """Un lien interne vers un dossier (ici son propre dossier : une boucle) : cp échouait sur le lien cyclique,
        l'erreur était ignorée (set -e coupé par « || return 1 ») et le dépôt recevait une copie entière du dossier."""
        self.base_exportee()
        depot = self.depot / "home/Pictures/Wallpapers"           # déjà suivis par git, comme fichiers
        depot.mkdir(parents=True)
        for nom in ("a.jpg", "boucle", "vers-sous"):
            (depot / nom).write_bytes(b"\xff\xd8image")
        self.commit("fonds")
        fonds = self.home / "Pictures/Wallpapers"
        (fonds / "sous").mkdir(parents=True)
        (fonds / "a.jpg").write_bytes(b"\xff\xd8image")
        for i in range(10):
            (fonds / f"copie{i}.jpg").symlink_to("a.jpg")
        for nom, cible in (("boucle", fonds), ("vers-sous", fonds / "sous")):
            with self.subTest(nom=nom):
                lien = fonds / nom
                lien.symlink_to(cible)
                for a in (("--preview",), ()):
                    r = self.exporter(*a)
                    self.assertEqual(r.returncode, 1, r.stderr)
                    self.assertIn(f"{nom} est un lien vers un dossier", r.stderr)
                self.assertEqual(self.etat(), "", "rien de copié dans le dépôt")
                self.assertFalse((self.depot / "home/Pictures/Wallpapers/sous").exists())
                lien.unlink()

    def test_dossier_lien_vers_le_dossier_personnel_refuse(self):
        """P3 : ~/.config/nvim -> ~ copiait tout le dossier personnel (clé .ssh, jetons) dans home/."""
        (self.home / ".ssh").mkdir()
        (self.home / ".ssh/id_test").write_text("-----BEGIN OPENSSH " + "PRIVATE KEY-----\nx\n")
        # Pas « / » dans le test : si le garde-fou cassait, tout le disque serait copié (« / » est vu comme parent de ~)
        for cible in (self.home, self.racine):
            with self.subTest(cible=cible.name):
                lien = self.home / ".config/nvim"
                lien.parent.mkdir(parents=True, exist_ok=True)
                if lien.is_symlink():
                    lien.unlink()
                lien.symlink_to(cible)
                r = self.exporter("--preview")
                self.assertEqual(r.returncode, 1)
                self.assertIn("mène à ton dossier personnel ou au-dessus", r.stderr)
        self.assertFalse((self.depot / "home/.config/nvim").exists())

    def test_fichier_suivi_hors_liste_garde(self):
        """P3 : un fichier suivi sous home/ mais absent de HOME_FILES disparaissait à l'export."""
        hors = self.depot / "home/.config/hors-liste/garde.conf"
        hors.parent.mkdir(parents=True)
        hors.write_text("x = 1\n")
        self.commit("hors liste")
        r = self.exporter()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(hors.read_text(), "x = 1\n")

    def test_lien_absolu_du_depot_refuse(self):
        lien = self.depot / "home/.local/share/nc/logos/lien.png"
        lien.parent.mkdir(parents=True)
        lien.symlink_to(self.racine / "logo.png")
        self.commit("lien")
        r = self.exporter("--preview")
        self.assertEqual(r.returncode, 1)
        self.assertIn("lien.png -> /", r.stderr)

    def test_jetons_refuses(self):
        for jeton in ("gho_" + "A" * 36, "ghs_" + "B" * 36, "github_pat_" + "C" * 40):
            with self.subTest(jeton=jeton[:6]):
                (self.home / ".local/bin/nc-dictee").write_text(f"#!/bin/sh\nJETON={jeton}\n")
                r = self.exporter("--preview")
                self.assertEqual(r.returncode, 1)
                self.assertIn("à vérifier avant de publier", r.stderr)
                self.assertIn("nc-dictee", r.stderr)

    def test_ancienne_version_du_depot_pas_publiee(self):
        """Un fichier de ~ égal à une version plus ancienne du dépôt (installation en retard) effacerait les derniers
        changements : il n'est pas publié, fichier par fichier ; les autres le sont. NC_EXPORT_MALGRE_TOUT=1 le publie."""
        dictee = self.depot / "home/.local/bin/nc-dictee"
        dictee.write_text("#!/bin/sh\necho version-2\n")       # ~ garde la version d'avant (celle de « base »)
        self.commit("version 2")
        (self.home / ".local/bin/nc-ia").parent.mkdir(parents=True, exist_ok=True)
        (self.home / ".local/bin/nc-ia").write_text("#!/bin/sh\necho retouche-dans-home\n")
        r = self.exporter("--preview")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("~/.local/bin/nc-dictee est une ancienne version du dépôt (commit ", r.stderr)
        self.assertIn("pas publié ; nc-maj pour te mettre à jour", r.stderr)
        self.assertNotIn("echo version-depot", r.stdout, "l'aperçu montre ce que fera l'export")
        self.assertIn("retouche-dans-home", r.stdout)
        r = self.exporter()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(dictee.read_text(), "#!/bin/sh\necho version-2\n", "le dépôt garde sa version récente")
        self.assertIn("retouche-dans-home", (self.depot / "home/.local/bin/nc-ia").read_text(), "les autres, publiés")
        self.commit("export")
        self.env["NC_EXPORT_MALGRE_TOUT"] = "1"
        r = self.exporter()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("publié quand même", r.stderr)
        self.assertIn("version-depot", dictee.read_text())

    def test_juste_apres_son_propre_export_rien_de_bloque(self):
        """Un export, son commit, puis une retouche dans ~ et un nouvel export : rien n'est pris pour une ancienne
        version (le commit vient justement de ~)."""
        (self.home / ".local/bin/nc-dictee").write_text("#!/bin/sh\necho retouche-1\n")
        self.assertEqual(self.exporter().returncode, 0)
        self.commit("export 1")
        r = self.exporter()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("ancienne version", r.stderr)
        (self.home / ".local/bin/nc-dictee").write_text("#!/bin/sh\necho retouche-2\n")
        r = self.exporter()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("ancienne version", r.stderr)
        self.assertIn("retouche-2", (self.depot / "home/.local/bin/nc-dictee").read_text())

    def test_zshrc_aucune_valeur_affichee(self):
        """L'écart du .zshrc ne montre que le premier mot de chaque ligne (s'il s'agit d'un mot-clé du shell ou d'une
        commande) et le nom affecté : aucune valeur, car un mot de passe ou un jeton peut se cacher n'importe où."""
        for nom in ("curl", "mysql"):                                      # de fausses commandes, jamais lancées
            (self.bin / nom).write_text("#!/bin/sh\nexit 0\n")
            (self.bin / nom).chmod(0o755)
        self.zshrc_ajoute()
        s = ["Sec" + str(i).zfill(2) + "x" for i in range(18)]            # 18 valeurs secrètes repérables
        lignes = [
            f'export OPENAI_API_KEY="sk-proj-{s[0]}"',
            f"GH_TOKEN=ghp_{s[1]} gh auth status",
            f'curl -H "Authorization: Bearer {s[2]}" https://exemple.invalid',
            f"curl -u nom:{s[3]} https://exemple.invalid",
            f"git clone https://nom:{s[4]}@exemple.invalid/depot",
            f"Motdepasse{s[17]}",                                          # un mot de passe collé seul
            f"https://nom:{s[5]}@exemple.invalid",
            f"mysql -p{s[6]} base",
            f"K+={s[7]}",
            f"typeset -gx K {s[8]}",
            f"export K {s[9]}",
            f"alias moi='mot={s[10]}'",
            f"sk-ant-{s[11]}",
            f"local mdp={s[12]}",
            f"PASS='{s[13]}' commande",
            f"echo {s[14]} | sudo -S true",
            f"source <(outil --jeton {s[15]})",
            f'export PATH="@HOME@/{s[16]}/bin:$PATH"',
        ]
        with open(self.home / ".zshrc", "a") as f:
            f.write("\n".join(lignes) + "\n")
        r = self.exporter("--preview")
        self.assertEqual(r.returncode, 0, r.stderr)
        sortie = r.stderr + r.stdout
        for v in s:
            self.assertNotIn(v, sortie)
        self.assertNotIn("Motdepasse", sortie)
        for attendu in ("+export OPENAI_API_KEY=…", "+GH_TOKEN=…", "+curl …", "+mysql …", "+K=…", "+typeset …",
                        "+export …", "+git …", "+export PATH=…", "\n  +…\n", "(19 lignes)"):
            self.assertIn(attendu, r.stderr)

    ZSHRC = '# géré par le dépôt\nexport EDITOR=nvim\n[[ -r ~/.zshrc.perso ]] && source ~/.zshrc.perso\n'

    def zshrc_ajoute(self):
        """Le .zshrc du dépôt, et dans ~ le même avec une ligne d'un installateur tiers (chemin du dossier perso)."""
        (self.depot / "home/.zshrc").write_text(self.ZSHRC)
        for a in (("add", "home"), ("-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                                    "commit", "-qm", "zshrc")):
            subprocess.run(["git", "-C", str(self.depot), *a], env=self.env, capture_output=True, check=True)
        installe = self.ZSHRC + f'export PATH="{self.home}/.tiers/bin:$PATH"\n'
        (self.home / ".zshrc").write_text(installe)
        return installe

    def test_zshrc_ajouts_tiers_pas_publies(self):
        """~/.zshrc reçoit des lignes d'installateurs tiers : l'export garde le .zshrc du dépôt, montre l'écart et ne
        modifie pas ~/.zshrc."""
        installe = self.zshrc_ajoute()
        for a in (("--preview",), ()):
            r = self.exporter(*a)
            self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
            self.assertEqual((self.depot / "home/.zshrc").read_text(), self.ZSHRC, f"export {a}")
            self.assertEqual((self.home / ".zshrc").read_text(), installe, "~/.zshrc n'est jamais modifié")
            self.assertIn("~/.zshrc diffère du dépôt", r.stderr)
            self.assertIn("+export PATH=…", r.stderr, "l'écart, valeur masquée")
            self.assertIn("~/.zshrc.perso", r.stderr)
            self.assertNotIn(".zshrc", r.stdout.replace("gardé depuis le dépôt", ""), "pas de diff du .zshrc")
        etat = subprocess.run(["git", "-C", str(self.depot), "status", "--porcelain", "--", "home/.zshrc"],
                              env=self.env, capture_output=True, text=True, check=True).stdout
        self.assertEqual(etat, "")

    def test_zshrc_secret_jamais_affiche(self):
        """L'écart du .zshrc s'affiche, et export.sh est aussi lancé par des assistants qui gardent tout : la valeur
        des affectations et tout ce qui ressemble à un jeton sont masqués."""
        self.zshrc_ajoute()
        secrets = ("sk-proj-" + "Faux" * 10, "ghp_" + "Z" * 36, "abc" * 14, "Pa55-mot-de-passe")
        with open(self.home / ".zshrc", "a") as f:
            f.write(f'export OPENAI_API_KEY="{secrets[0]}"\n')
            f.write(f"GH_TOKEN={secrets[1]} gh auth status\n")
            f.write(f'curl -H "Authorization: Bearer {secrets[2]}" https://exemple.invalid\n')
            f.write(f"alias moi='mot={secrets[3]}'\n")
        for a in (("--preview",), ()):
            r = self.exporter(*a)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("~/.zshrc diffère du dépôt", r.stderr)
            self.assertIn("+export OPENAI_API_KEY=…", r.stderr)
            for s in secrets:
                self.assertNotIn(s, r.stderr + r.stdout)
            self.assertNotIn("Faux" * 3, r.stderr)

    def test_zshrc_identique_apres_normalisation_sans_avertissement(self):
        (self.depot / "home/.zshrc").write_text(self.ZSHRC + 'export PATH="@HOME@/.local/bin:$PATH"\n')
        (self.home / ".zshrc").write_text(self.ZSHRC + f'export PATH="{self.home}/.local/bin:$PATH"\n')
        r = self.exporter("--preview")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertNotIn("diffère", r.stderr)

    # Revue « export » (E1 à E7). Clés factices évidentes, assemblées ici pour ne jamais figurer telles quelles.
    CLES = {
        "openai": "sk-proj-" + "FAUX" * 6,
        "google": "AIza" + "F" * 35,
        "groq": "gsk_" + "F" * 40,
        "aws": "AKIA" + "FAUX" * 4,
        "telegram": "123456789:AA" + "F" * 32,
        "slack": "xoxb-" + "1" * 12,
        "jeton google": "ya29." + "F" * 20,
        "refresh_token": '"refresh_token": "' + "F" * 12 + '"',
        "e-mail": "quelquun" + "@" + "courriel.invalid",
    }

    def test_e1_uwsm_env_garde_noms_seulement(self):
        """E1 : uwsm/env et env-hyprland (où l'on met ANTHROPIC_API_KEY…) étaient copiés en entier. La version du dépôt
        est gardée, seuls les noms des variables sont montrés."""
        self.base_exportee()
        base = "# session uwsm\nexport QT_QPA_PLATFORMTHEME=qt6ct\n"
        for nom in ("env", "env-hyprland"):
            for racine in (self.depot / "home", self.home):
                p = racine / ".config/uwsm" / nom
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(base)
        self.commit("uwsm")
        cle = "sk-ant-" + "FAUX" * 8
        for nom in ("env", "env-hyprland"):
            with open(self.home / ".config/uwsm" / nom, "a") as f:
                f.write(f'export ANTHROPIC_API_KEY="{cle}"\nexport OPENAI_API_KEY={self.CLES["openai"]}\n')
        for a in (("--preview",), ()):
            r = self.exporter(*a)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("~/.config/uwsm/env diffère du dépôt", r.stderr)
            self.assertIn("~/.config/uwsm/env-hyprland diffère du dépôt", r.stderr)
            self.assertIn("+export ANTHROPIC_API_KEY=…", r.stderr)
            self.assertNotIn("FAUX", r.stderr + r.stdout, "jamais une valeur à l'écran")
        self.assertEqual((self.depot / "home/.config/uwsm/env").read_text(), base)
        self.assertEqual(self.etat(), "")

    def test_e1_cles_et_adresses_nouvelles_refusees(self):
        """E1 : le contrôle final ne connaissait que gh*_, github_pat_, sk-ant-, MAC et clés privées."""
        self.base_exportee()
        avant = (self.depot / "home/.local/bin/nc-dictee").read_text()
        for genre, cle in self.CLES.items():
            with self.subTest(genre=genre):
                (self.home / ".local/bin/nc-dictee").write_text(f"#!/bin/sh\nVALEUR={cle}\n")
                for a in (("--preview",), ()):
                    r = self.exporter(*a)
                    self.assertEqual(r.returncode, 1, r.stderr)
                    self.assertIn("à vérifier avant de publier", r.stderr)
                    self.assertIn("home/.local/bin/nc-dictee, ligne 2 :", r.stderr)
                    self.assertNotIn(cle, r.stderr + r.stdout, "le fichier et la ligne, jamais la valeur")
                self.assertEqual((self.depot / "home/.local/bin/nc-dictee").read_text(), avant)
                self.assertEqual(self.etat(), "")

    def test_e1_lignes_deja_dans_le_depot_permises(self):
        """Faux positifs : nc-ia ou les tests contiennent ces motifs exprès. Une ligne déjà dans git passe ; seule une
        ligne nouvelle est refusée. Adresses permises : example.*, noreply, unités systemd, adresses déjà suivies."""
        self.base_exportee()
        connues = (f"MOTIF={self.CLES['openai']}\n"
                   "AUTEUR=" + "moi" + "@" + "projet.invalid\n")
        (self.depot / "home/.local/bin/nc-dictee").write_text("#!/bin/sh\n" + connues)
        self.commit("motifs connus")
        permis = ("A=test" + "@" + "example.com\n" + "B=noreply" + "@" + "github.com\n"
                  + "C=wayland-wm" + "@" + "hyprland.desktop.service\n" + "D=moi" + "@" + "projet.invalid\n")
        (self.home / ".local/bin/nc-dictee").write_text("#!/bin/sh\n" + connues + "echo modifie\n" + permis)
        r = self.exporter()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("echo modifie", (self.depot / "home/.local/bin/nc-dictee").read_text())
        self.commit("export")
        with open(self.home / ".local/bin/nc-dictee", "a") as f:
            f.write(f"NOUVELLE={self.CLES['groq']}\n")
        r = self.exporter()
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("home/.local/bin/nc-dictee, ligne 9 : clé Groq", r.stderr)
        self.assertNotIn("ligne 2", r.stderr, "la ligne déjà dans git n'est pas signalée")
        self.assertEqual(self.etat(), "")

    def ile(self):
        d = self.home / ".config/quickshell/nc-ile"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def test_e2_nouveaux_fichiers_d_un_dossier(self):
        """E2 : un dossier de la liste était copié en entier, tout nouveau fichier compris. Seuls les fichiers suivis
        sont publiés ; NC_EXPORT_NOUVEAUX=oui publie les nouveaux, sauf la liste noire, qui l'emporte toujours."""
        self.base_exportee()
        ile = self.ile()
        (ile / "Perso.qml").write_text("import QtQuick\nItem {}\n")
        noire = ["auth.json", ".env", "cle.env", ".netrwhist", "spell/fr.utf-8.add", "mon_token.txt", "SECRET.conf",
                 "cert.pem", "serveur.key", "id_ed25519", "zsh_history", "base.sqlite"]
        for nom in noire:
            (ile / nom).parent.mkdir(parents=True, exist_ok=True)
            (ile / nom).write_text("x = 1\n")
        prive = ile / "Prive.qml"
        prive.write_text("import QtQuick\nItem {}\n")
        prive.chmod(0o600)
        r = self.exporter()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("nouveau, pas publié : ~/.config/quickshell/nc-ile/Perso.qml (pas encore dans le dépôt)", r.stderr)
        self.assertIn("relance avec NC_EXPORT_NOUVEAUX=oui", r.stderr)
        self.assertEqual(self.etat(), "")
        self.env["NC_EXPORT_NOUVEAUX"] = "oui"
        r = self.exporter()
        self.assertEqual(r.returncode, 0, r.stderr)
        publie = self.depot / "home/.config/quickshell/nc-ile"
        self.assertTrue((publie / "Perso.qml").exists(), "demandé exprès : publié")
        self.assertIn("nouveau, publié (NC_EXPORT_NOUVEAUX) : ~/.config/quickshell/nc-ile/Perso.qml", r.stderr)
        for nom in noire:
            self.assertFalse((publie / nom).exists(), nom)
            self.assertIn(f"~/.config/quickshell/nc-ile/{nom} (liste noire)", r.stderr)
        self.assertFalse((publie / "Prive.qml").exists())
        self.assertIn("Prive.qml (fichier privé, lisible par toi seul)", r.stderr)
        self.assertEqual(self.etat(), "?? home/.config/quickshell/nc-ile/Perso.qml\n")

    def test_e2_page_de_l_ile_suivie_modifiee_publiee(self):
        """Nouvelle page de l'île déjà dans le dépôt (suivie), puis modifiée dans ~ : publiée."""
        self.base_exportee()
        (self.ile() / "Nouveau.qml").write_text("import QtQuick\nItem { width: 42 }\n")
        r = self.exporter()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("width: 42", (self.depot / "home/.config/quickshell/nc-ile/Nouveau.qml").read_text())
        self.assertNotIn("nouveau, pas publié", r.stderr)
        self.assertEqual(self.etat(), " M home/.config/quickshell/nc-ile/Nouveau.qml\n")

    def test_export_normal_passe(self):
        """Un export ordinaire : fichiers suivis modifiés, publiés, code 0."""
        self.base_exportee()
        (self.home / ".local/bin/nc-dictee").write_text("#!/bin/sh\necho retouche\n")
        (self.ile() / "Nouveau.qml").write_text("import QtQuick\nItem { width: 7 }\n")
        r = self.exporter()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Dépôt mis à jour depuis ce PC.", r.stdout)
        self.assertEqual(self.etat(), " M home/.config/quickshell/nc-ile/Nouveau.qml\n M home/.local/bin/nc-dictee\n")

    def test_e3_fonds_lien_vers_un_autre_dossier_de_home_refuse(self):
        """E3 : ~/Pictures/Wallpapers -> ~/Images faisait partir tout ~/Images. Un lien de dossier qui mène ailleurs
        dans ~ n'est permis que vers un dossier du même nom."""
        self.base_exportee()
        images = self.home / "Images"
        images.mkdir()
        (images / "notes.txt").write_text("privé\n")
        (self.home / "Pictures").mkdir()
        (self.home / "Pictures/Wallpapers").symlink_to(images)
        for a in (("--preview",), ()):
            r = self.exporter(*a)
            self.assertEqual(r.returncode, 1, r.stderr)
            self.assertIn("~/Pictures/Wallpapers mène ailleurs dans ton dossier personnel", r.stderr)
        self.assertEqual(self.etat(), "")
        (self.home / "Pictures/Wallpapers").unlink()
        (images / "Wallpapers").mkdir()
        (self.home / "Pictures/Wallpapers").symlink_to(images / "Wallpapers")
        r = self.exporter("--preview")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_e4_photo_de_profil_jamais_publiee(self):
        """E4 : ~/.face (photo de profil, EXIF compris) était publiée. Le dépôt garde son avatar par défaut."""
        self.base_exportee()
        (self.depot / "home/.face").write_bytes(b"\x89PNGavatar-du-depot")
        self.commit("avatar")
        (self.home / ".face").write_bytes(b"\x89PNGma-photo")
        r = self.exporter()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("jamais publié : ~/.face", r.stdout)
        self.assertEqual((self.depot / "home/.face").read_bytes(), b"\x89PNGavatar-du-depot")
        self.assertEqual(self.etat(), "")

    def test_e4_nouvelle_image_et_position_gps(self):
        """E4 : une nouvelle image acceptée (NC_EXPORT_NOUVEAUX=oui) est refusée si elle a une position GPS
        (exiftool), et toujours refusée sans exiftool."""
        self.base_exportee()
        self.env["NC_EXPORT_NOUVEAUX"] = "oui"
        fonds = self.home / "Pictures/Wallpapers"
        fonds.mkdir(parents=True)
        (fonds / "photo.JPG").write_bytes(b"\xff\xd8photo")
        cible = self.depot / "home/Pictures/Wallpapers/photo.JPG"
        exiftool = self.bin / "exiftool"
        for cas, script, publie in (("sans exiftool", None, False),
                                    ("avec GPS", "echo 48.8584; echo 2.2945", False),
                                    ("sans GPS", ":", True)):
            with self.subTest(cas=cas):
                if script is None:
                    exiftool.unlink(missing_ok=True)
                else:
                    exiftool.write_text(f"#!/bin/sh\n{script}\n")
                    exiftool.chmod(0o755)
                r = self.exporter()
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(cible.exists(), publie, r.stderr)
                if not publie:
                    self.assertIn("nouveau, pas publié : ~/Pictures/Wallpapers/photo.JPG (image", r.stderr)
                    self.assertEqual(self.etat(), "")

    def test_e5_clone_partiel_refuse(self):
        """E5 : la garde « ancienne version » (git log --find-object) ne voit rien dans un clone --depth 1."""
        (self.depot / "home/.local/bin/nc-dictee").write_text("#!/bin/sh\necho version-2\n")
        self.commit("version 2")
        clone = self.racine / "clone"
        subprocess.run(["git", "clone", "-q", "--depth", "1", "file://" + str(self.depot), str(clone)], env=self.env,
                       capture_output=True, check=True)
        shutil.copy2(self.depot / "export.sh", clone / "export.sh")
        for a in (("--preview",), ()):
            r = subprocess.run([str(clone / "export.sh"), *a], env=self.env, capture_output=True, text=True, timeout=20)
            self.assertEqual(r.returncode, 1, r.stderr)
            self.assertIn("clone partiel", r.stderr)
            self.assertIn("git fetch --unshallow", r.stderr)
        self.assertIn("version-2", (clone / "home/.local/bin/nc-dictee").read_text())
        self.assertFalse(list(clone.glob(".nc-export.*")))

    def test_e6_dossier_personnel_echappe_et_borne(self):
        """E6 : sed « s|$HOME|@HOME@| » sans échappement ni borne : /home/al changeait /home/alice en @HOME@ice, et un
        « . » du chemin valait n'importe quel caractère."""
        maison = self.racine / "mai.son+1"
        shutil.copytree(self.home, maison, symlinks=True)
        self.env["HOME"] = str(maison)
        voisin = self.racine / "maiXson1"                        # le « . » et le « + » ne sont pas des jokers
        lignes = [f'A="{maison}/bin"', f"B={maison}ice/bin", f"C={voisin}/bin", f"D='{maison}'", f"E={maison}"]
        (maison / ".local/bin/nc-dictee").write_text("\n".join(lignes) + "\n")
        r = self.exporter()
        self.assertEqual(r.returncode, 0, r.stderr)
        publie = (self.depot / "home/.local/bin/nc-dictee").read_text().splitlines()
        self.assertEqual(publie, ['A="@HOME@/bin"', lignes[1], lignes[2], "D='@HOME@'", "E=@HOME@"])

    def test_e7_kdeglobals_sans_historique(self):
        """E7 : les dialogues KDE écrivent les derniers dossiers ouverts dans kdeglobals ([KFileDialog Settings])."""
        kde = self.home / ".config/kdeglobals"
        kde.write_text("[General]\nColorScheme=noctalia\n\n[KFileDialog Settings]\nRecent URLs[$e]=file:///tmp/x/Photos/\n"
                       "Show hidden files=false\n\n[Icons]\nTheme=Papirus-Dark\nRecent Files=/tmp/x/a.txt\n")
        r = self.exporter()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.depot / "home/.config/kdeglobals").read_text(),
                         "[General]\nColorScheme=noctalia\n\n[Icons]\nTheme=Papirus-Dark\n")
        self.assertIn("historique des dialogues de fichiers retiré", r.stderr)


OUTILS = ("bash", "dirname", "mkdir", "mktemp", "find", "rm", "grep", "sed", "cp", "mv", "id", "git", "jq", "python3",
          "realpath", "readlink", "timeout", "cat")


class ExportDepotReel(unittest.TestCase):
    """Le vrai home/ du dépôt (fichiers suivis), exporté depuis un HOME temporaire."""

    def setUp(self):
        r = subprocess.run(["git", "-C", str(REPO), "ls-files", "-z", "--", "home", "export.sh"],
                           capture_output=True, text=True)
        if r.returncode != 0:
            self.skipTest("pas un dépôt git")
        tmp = tempfile.TemporaryDirectory(prefix="nc-export-reel-")
        self.addCleanup(tmp.cleanup)
        racine = Path(tmp.name)
        self.depot, self.home, self.bin = racine / "depot", racine / "utilisateur", racine / "bin"
        for p in (self.depot, self.home, self.bin):
            p.mkdir()
        for rel in filter(None, r.stdout.split("\0")):
            src = REPO / rel
            if not src.exists() and not src.is_symlink():
                continue                                   # supprimé mais pas encore commité
            (self.depot / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, self.depot / rel, follow_symlinks=False)
        for nom in OUTILS:
            outil = shutil.which(nom)
            if not outil:
                self.skipTest(nom + " requis")
            (self.bin / nom).symlink_to(outil)
        self.hyprctl(None)                                 # un faux qui échoue, jamais le vrai
        self.env = dict(HOME=str(self.home), PATH=str(self.bin), NC_LANGUE="fr", LC_ALL="C",
                        GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        for a in (("init", "-q"), ("add", "home"),
                  ("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "base")):
            subprocess.run(["git", "-C", str(self.depot), *a], env=self.env, capture_output=True, check=True)

    def hyprctl(self, moniteurs):
        """Faux hyprctl : les écrans donnés, ou None pour échouer comme hors session Hyprland."""
        h = self.bin / "hyprctl"
        if moniteurs is None:
            h.write_text('#!/bin/sh\necho "HYPRLAND_INSTANCE_SIGNATURE not set! (is hyprland running?)"\nexit 1\n')
        else:
            h.write_text("#!/bin/sh\ncat <<'FIN'\n" + moniteurs + "\nFIN\n")
        h.chmod(0o755)

    def exporter(self, *a):
        return subprocess.run([str(self.depot / "export.sh"), *a], env=self.env, capture_output=True, text=True,
                              timeout=120)

    def etat(self):
        return subprocess.run(["git", "-C", str(self.depot), "status", "--porcelain", "--", "home"], env=self.env,
                              capture_output=True, text=True, check=True).stdout

    def test_home_vide_aucune_difference(self):
        """A3-R1 : les substitutions s'appliquent aussi aux fichiers gardés du dépôt. Elles doivent être sans effet
        sur un fichier qui a déjà ses repères : sinon « @PLUGIN_ILE@@PLUGIN_ILE@] »."""
        e = self.exporter("--preview")
        self.assertEqual(e.returncode, 0, e.stderr[-2000:])
        self.assertNotIn("diff --git", e.stdout, e.stdout[e.stdout.find("diff --git"):][:4000])
        self.assertNotIn("Only in", e.stdout)
        # Puis un vrai export : le dépôt ne change pas (substitutions appliquées deux fois = même résultat)
        e = self.exporter()
        self.assertEqual(e.returncode, 0, e.stderr[-2000:])
        self.assertEqual(self.etat(), "")

    def installer(self, valeurs):
        """Le home/ du dépôt « installé » dans le HOME temporaire, repères remplis comme le fait install.sh."""
        racine = self.depot / "home"
        for src in racine.rglob("*"):
            if src.is_dir() or src.is_symlink():
                continue
            rel = src.relative_to(racine)
            dst = self.home / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            b = src.read_bytes()
            if b"\0" not in b[:8192] and str(rel) not in (".zshrc", ".p10k.zsh"):
                t = b.decode("utf-8")
                for cle, v in valeurs.items():
                    t = t.replace(f"@{cle}@", v)
                b = t.encode("utf-8")
            dst.write_bytes(b)
            shutil.copymode(src, dst)

    def test_home_rempli_rend_exactement_les_reperes(self):
        """P2-3 : un sed qui ne correspond plus à son fichier (clavier.lua réécrit avec nc.reglage) publiait la
        disposition de ce PC à la place de @KB_LAYOUT@. Un HOME aux repères remplis doit redonner le dépôt exact,
        y compris quand ce PC n'est plus comme à l'installation : les repères sont reposés par alignement."""
        h = str(self.home)
        commun = {"HOME": h, "MONITOR": "eDP-1", "LCX": "800.0", "LCY1": "300.0",
                  "LCY2": "405.0", "LCY3": "640.0", "LCY4": "860.0", "LCY5": "930.0", "ICON_THEME": "NC",
                  "DISTRO_LOGO": h + "/.config/noctalia/arch-logo.png"}
        variantes = (
            {"KB_LAYOUT": "fr", "KB_VARIANT": "", "KB_OPTIONS": "", "POLKIT": "true", "QT_STYLE": "Fusion", "ILE_CENTRE": "",
             "NOTIF_NOCTALIA": "false", "NOTIF_WIDGET": "", "PLUGIN_ILE": "", "BROWSER": "firefox"},
            {"KB_LAYOUT": "us,fr", "KB_VARIANT": ",bepo", "KB_OPTIONS": "ctrl:nocaps,grp:win_space_toggle", "POLKIT": "false", "QT_STYLE": "Breeze",
             "ILE_CENTRE": '"nc/ile:pilule"', "NOTIF_NOCTALIA": "true", "NOTIF_WIDGET": ', "notifications"',
             "PLUGIN_ILE": ', "nc/ile"', "BROWSER": "org.chromium.Chromium"},
        )
        # Ce que hyprctl répond au moment de l'export (l'installation, elle, a vu eDP-1 en 1600 × 1000, échelle 1)
        ecrans = {
            "comme à l'installation": '[{"name": "eDP-1", "width": 1600, "height": 1000, "scale": 1}]',
            "hors session": None,
            "couvercle fermé, écran externe seul": '[{"name": "HDMI-A-1", "width": 2560, "height": 1440, "scale": 1}]',
            "autre échelle": '[{"name": "eDP-1", "width": 1600, "height": 1000, "scale": 1.25}]',
        }
        # Navigateur changé depuis l'installation : l'export ne le demande plus, il est ignoré
        x = self.bin / "xdg-settings"
        x.write_text('#!/bin/sh\necho brave-browser.desktop\n')
        x.chmod(0o755)
        for v in variantes:
            for cas, moniteurs in ecrans.items():
                with self.subTest(KB_LAYOUT=v["KB_LAYOUT"], cas=cas):
                    self.hyprctl(moniteurs)
                    shutil.rmtree(self.home)
                    self.home.mkdir()
                    self.installer({**commun, **v})
                    cl = (self.home / ".config/hypr/nc/clavier.lua").read_text()
                    self.assertNotIn("@KB_LAYOUT@", cl, "le HOME a bien ses valeurs")
                    e = self.exporter()
                    self.assertEqual(e.returncode, 0, e.stderr[-3000:])
                    self.assertNotIn("parse error", e.stdout + e.stderr)
                    self.assertNotIn("jq:", e.stdout + e.stderr)
                    diff = subprocess.run(["git", "-C", str(self.depot), "diff", "--", "home"], env=self.env,
                                          capture_output=True, text=True).stdout
                    self.assertEqual(self.etat(), "", diff[:4000])

    def test_repere_perdu_refuse(self):
        """Un repère que plus rien ne remet (ici la ligne du clavier réécrite autrement) : export refusé, avec le
        fichier, la ligne et quoi faire."""
        self.installer({"HOME": str(self.home)})
        cl = self.home / ".config/hypr/nc/clavier.lua"
        cl.write_text(cl.read_text().replace('"@KB_LAYOUT@"', "'fr'"))
        avant = (self.depot / "home/.config/hypr/nc/clavier.lua").read_text()
        for a in (("--preview",), ()):
            e = self.exporter(*a)
            self.assertEqual(e.returncode, 1, e.stdout[-2000:])
            self.assertIn("home/.config/hypr/nc/clavier.lua perdrait @KB_LAYOUT@", e.stderr)
            self.assertIn('ligne 4 : local disposition = nc.reglage("CLAVIER_DISPOSITION", "@KB_LAYOUT@")', e.stderr)
            self.assertIn("Que faire : dans ~/.config/hypr/nc/clavier.lua", e.stderr)
        self.assertEqual((self.depot / "home/.config/hypr/nc/clavier.lua").read_text(), avant)

    def test_modifications_voulues_gardees_avec_leurs_reperes(self):
        """Le joker de l'alignement avalait ce que l'utilisateur avait ajouté exprès (plugin, appli épinglée en tête,
        widget en fin de liste) : la ligne du dépôt revenait sans un mot. Chaque repère ne prend plus que les valeurs
        d'install.sh : la ligne changée est publiée, son repère à sa place, et la réinstaller redonne la même ligne."""
        h = str(self.home)
        commun = {"HOME": h, "MONITOR": "eDP-1", "LCX": "800.0", "LCY1": "300.0", "LCY2": "405.0", "LCY3": "640.0",
                  "LCY4": "860.0", "LCY5": "930.0", "ICON_THEME": "NC", "DISTRO_LOGO": h + "/logo.png",
                  "KB_LAYOUT": "fr", "KB_VARIANT": "bepo", "KB_OPTIONS": "", "POLKIT": "true", "QT_STYLE": "Fusion", "BROWSER": "firefox"}
        variantes = (
            {"ILE_CENTRE": "", "NOTIF_NOCTALIA": "false", "NOTIF_WIDGET": "", "PLUGIN_ILE": ""},
            {"ILE_CENTRE": '"nc/ile:pilule"', "NOTIF_NOCTALIA": "true", "NOTIF_WIDGET": ', "notifications"',
             "PLUGIN_ILE": ', "nc/ile"'},
        )
        for v in variantes:
            with self.subTest(PLUGIN_ILE=v["PLUGIN_ILE"]):
                valeurs = {**commun, **v}
                shutil.rmtree(self.home)
                self.home.mkdir()
                self.installer(valeurs)
                cfg = self.home / ".config/noctalia/config.toml"
                t = cfg.read_text()
                t = t.replace('"nc/batterie"' + v["PLUGIN_ILE"] + "]",
                              '"nc/batterie", "nc/horloge"' + v["PLUGIN_ILE"] + "]")
                t = t.replace('pinned = ["firefox"', 'pinned = ["vlc", "firefox"', 1)
                # Un 2e navigateur épinglé exprès (celui que l'ancien sed figé changeait aussi en @BROWSER@)
                t = t.replace('pinned = ["firefox", "kitty"', 'pinned = ["firefox", "firefox-developer-edition", "kitty"')
                t = t.replace('"group:status"' + v["NOTIF_WIDGET"] + "]",
                              '"group:status"' + v["NOTIF_WIDGET"] + ', "clock"]')
                self.assertEqual(t.count("nc/horloge") + t.count('"vlc"') + t.count('"clock"')
                                 + t.count("firefox-developer-edition"), 4)
                cfg.write_text(t)
                e = self.exporter()
                self.assertEqual(e.returncode, 0, e.stderr[-3000:])
                publie = (self.depot / "home/.config/noctalia/config.toml").read_text()
                self.assertIn('"nc/batterie", "nc/horloge"@PLUGIN_ILE@]', publie)
                self.assertIn('pinned = ["vlc", "@BROWSER@", "kitty", "org.gnome.Nautilus"]', publie)
                self.assertIn('pinned = ["@BROWSER@", "firefox-developer-edition", "kitty", "org.gnome.Nautilus"]',
                              publie)
                self.assertIn('"group:status"@NOTIF_WIDGET@, "clock"]', publie)
                reinstalle = publie
                for cle, val in valeurs.items():
                    reinstalle = reinstalle.replace(f"@{cle}@", val)
                self.assertEqual(reinstalle, t, "réinstaller la version publiée redonne exactement la config de ce PC")
                self.assertEqual(self.etat(), " M home/.config/noctalia/config.toml\n")
                subprocess.run(["git", "-C", str(self.depot), "checkout", "-q", "--", "home"], env=self.env,
                               check=True)

    def test_ile_en_tete_des_plugins_sans_doublon(self):
        """« "nc/ile" » en PREMIER dans la liste des plugins n'était pas retiré : doublon après installation."""
        h = str(self.home)
        self.installer({"HOME": h, "MONITOR": "eDP-1", "LCX": "800.0", "LCY1": "300.0", "LCY2": "405.0",
                        "LCY3": "640.0", "LCY4": "860.0", "LCY5": "930.0", "ICON_THEME": "NC", "DISTRO_LOGO": "",
                        "KB_LAYOUT": "fr", "KB_VARIANT": "bepo", "KB_OPTIONS": "", "POLKIT": "true", "QT_STYLE": "Fusion",
                        "BROWSER": "firefox", "ILE_CENTRE": '"nc/ile:pilule"', "NOTIF_NOCTALIA": "true",
                        "NOTIF_WIDGET": ', "notifications"', "PLUGIN_ILE": ', "nc/ile"'})
        cfg = self.home / ".config/noctalia/config.toml"
        t = cfg.read_text()
        avant = '"nc/batterie", "nc/ile"]'
        self.assertIn(avant, t)
        t = t.replace('enabled = ["nc/launcher"', 'enabled = ["nc/ile", "nc/launcher"').replace(avant, '"nc/batterie", "nc/horloge"]')
        cfg.write_text(t)
        e = self.exporter()
        self.assertEqual(e.returncode, 0, e.stderr[-3000:])
        ligne = next(l for l in (self.depot / "home/.config/noctalia/config.toml").read_text().splitlines()
                     if l.startswith("enabled = ["))
        self.assertEqual(ligne, 'enabled = ["nc/launcher", "nc/carousel", "nc/sessions", "nc/keys", "nc/verrou", '
                                '"nc/fenetres", "nc/batterie", "nc/horloge"@PLUGIN_ILE@]')
