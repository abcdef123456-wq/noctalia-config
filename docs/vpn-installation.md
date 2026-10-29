# Installer un client VPN depuis la fenêtre VPN (V6c)

Sur la ligne d'un fournisseur dont le client est **absent** (Proton VPN, Mullvad, NordVPN), la fenêtre VPN montre :

- **Installer** : ouvre une fenêtre kitty qui lance le script fixe `~/.local/libexec/nc-vpn-installer FOURNISSEUR` (copié depuis
  `home/.local/libexec/` par `install.sh`). Les étapes sont affichées avant d'être lancées, `sudo` demande lui-même le mot de passe dans
  ce terminal, **aucune règle sudoers n'est ajoutée**. Un « accord » (`o`) est demandé avant la première commande.
- **Voir comment installer** (parcours guidé) : affiche les étapes et un bouton « Ouvrir la page officielle » (`xdg-open`, en argv).
  Rien n'est exécuté.

Le bouton n'existe que si le client est absent (état `absent` de `nc-vpn fournisseurs-json`), n'est jamais lancé automatiquement, et la
commande `nc-vpn installer-client ID` refuse un client déjà installé. À la fermeture du terminal, l'état est relu (`fournisseurs-json`).

## Règles du script

- Fournisseur validé par liste blanche (`nord`, `proton`, `mullvad`) avant tout ; `set -eu` ; chaque commande est affichée (`%q`) avant d'être lancée.
- Jamais `curl | sh`, jamais de script téléchargé exécuté. Une clé de dépôt est téléchargée (HTTPS seulement, taille bornée) dans un dossier
  temporaire `0700`, son **empreinte** est comparée à celle épinglée dans le script **avant** tout import ou toute écriture ; une empreinte
  fausse arrête tout (aucune écriture, aucun `sudo`). La clé installée est le fichier vérifié, pas un second téléchargement.
- Les fichiers de dépôt sont écrits par le script lui-même (jamais téléchargés : un fichier reçu pourrait désactiver la vérification des
  signatures), avec des noms fixes : `/usr/share/keyrings/mullvad-keyring.asc`, `/etc/apt/sources.list.d/mullvad.list`,
  `/etc/pki/rpm-gpg/RPM-GPG-KEY-mullvad`, `/etc/yum.repos.d/mullvad.repo`. Rien d'autre n'est touché ; le pare-feu (firewalld, ufw) jamais.
- Distribution lue dans `/etc/os-release` (`ID`, `ID_LIKE`, `VERSION_ID`, lus ligne à ligne, jamais exécutés, valeurs limitées à `[a-z0-9._ -]`).
  Debian : version 13 seulement ; Fedora : 41 et plus ; Arch : `ID=arch` ou `ID_LIKE=arch` (pas Manjaro, dont les dépôts diffèrent) ;
  tout le reste (openSUSE, Ubuntu et dérivés, inconnu) : parcours guidé.
- Les textes du parcours guidé sont fixes dans le script ; `nc-vpn` ne relaie que des lignes à caractères sûrs et un lien `https://` vers
  `protonvpn.com`, `mullvad.net` ou `support.nordvpn.com` (liste blanche), puis la fenêtre les contrôle encore.

## Matrice finale

| Distribution | Proton VPN | Mullvad | NordVPN |
| --- | --- | --- | --- |
| **Arch** | `sudo pacman -S proton-vpn-cli` | `sudo pacman -S mullvad-vpn`, puis `sudo systemctl enable --now mullvad-daemon.service` | guidé |
| **Debian 13** | `curl` du paquet de dépôt, **SHA-256 épinglé**, `sudo dpkg -i`, `sudo apt-get update`, `sudo apt-get install proton-vpn-gnome-desktop` | `curl` de la clé, **empreinte épinglée**, `sudo install` (clé, source apt), `sudo apt-get update`, `sudo apt-get install mullvad-vpn` | guidé |
| **Fedora (41+)** | guidé | `curl` de la clé, **empreinte épinglée**, `sudo install` (clé), `sudo rpm --import`, `sudo install` (fichier `.repo` écrit par le script), `sudo dnf install mullvad-vpn` | guidé |
| **openSUSE** (Tumbleweed et Leap) | guidé | guidé | guidé |

### Pourquoi une case est « guidée » (rien n'est exécuté)

- **NordVPN, partout** : la seule méthode documentée par NordVPN est `sh <(curl … install.sh)` (interdite ici : script téléchargé puis
  exécuté). Ses pages officielles n'indiquent ni dépôt de paquets signé ni empreinte de clé ; aucune empreinte n'est inventée. Après une
  installation à la main, le parcours rappelle `sudo usermod -aG nordvpn "$USER"`, `sudo systemctl enable --now nordvpnd` et de se reconnecter
  à la session pour que le groupe prenne effet (le script n'ajoute donc pas l'utilisateur au groupe lui-même : il n'installe pas Nord).
- **Proton, Fedora** : la page officielle donne un paquet de dépôt `.rpm` sans somme de contrôle, et l'empreinte de la clé n'est donnée que
  pour Fedora 44 et seulement affichée à l'invite de `dnf`. Le paquet lui-même ne peut pas être vérifié avant son installation (ses scripts
  tournent en root) : parcours guidé.
- **Proton, openSUSE** : non prise en charge par Proton (seulement Debian, Ubuntu, Fedora, Arch). **Flathub** : l'application
  `com.protonvpn.www` est faite par un tiers, Proton ne la documente pas (le détecteur de nc-vpn la reconnaît si elle est déjà là, mais on ne
  l'installe pas).
- **Mullvad, openSUSE** : aucun dépôt documenté par Mullvad.
- Ubuntu, dérivés de Debian, Manjaro, Debian autre que 13, Fedora avant 41, architecture inconnue : parcours guidé.

## Sources officielles (consultées le 2026-10-29)

Proton VPN
- Guide d'installation Linux : https://protonvpn.com/support/linux-vpn-setup (distributions prises en charge : Debian, Ubuntu, Fedora, Arch ; Flatpak « maintenu par un tiers »).
- Debian : https://protonvpn.com/support/official-linux-vpn-debian et https://protonvpn.com/support/cli-debian-ubuntu : paquet
  `https://repo.protonvpn.com/debian/dists/stable/main/binary-all/protonvpn-stable-release_1.0.10_all.deb`, somme SHA-256
  `c8a9fffb4ebdd63db08ce7f11c9b0ac394064ae6a210feb9ab63a0f7d8d060a7` (publiée par Proton), puis `dpkg -i`, `apt update`,
  `apt install proton-vpn-gnome-desktop`. La page dit de ne pas vérifier la signature du paquet de dépôt (autre clé que le dépôt) ; la somme est la vérification officielle.
- Fedora : https://protonvpn.com/support/official-linux-vpn-fedora (pas de somme du `.rpm`) et https://protonvpn.com/support/cli-fedora.
- Arch : https://protonvpn.com/support/linux-vpn-arch (`pacman -S proton-vpn-cli` ou `proton-vpn-gtk-app`, paquet maintenu par un contributeur) ;
  le paquet est dans le dépôt officiel `extra` : https://archlinux.org/packages/extra/any/proton-vpn-cli/
- Page de téléchargement : https://protonvpn.com/download-linux (ni openSUSE, ni Flathub, ni AUR).

Mullvad
- https://mullvad.net/en/download/vpn/linux et https://mullvad.net/en/help/install-mullvad-app-linux : dépôts `deb` et `rpm`, clés
  `https://repository.mullvad.net/deb/mullvad-keyring.asc` et `https://repository.mullvad.net/rpm/mullvad-keyring.asc`, ligne apt
  `deb [signed-by=… arch=…] https://repository.mullvad.net/deb/stable stable main`, dépôt rpm `https://repository.mullvad.net/rpm/stable/mullvad.repo`
  (`baseurl=https://repository.mullvad.net/rpm/stable/$basearch`, `gpgcheck=1`) ; Arch : `pacman -S mullvad-vpn` (« pas maintenu par Mullvad »).
- Empreinte : https://mullvad.net/en/help/verifying-signatures, clé « Mullvad (code signing) »
  `A1198702FC3E0A09A9AE5B75D5A1D4F266DE8DDF`. Les pages d'installation ne donnent PAS d'empreinte pour le trousseau du dépôt ; il a donc été
  vérifié (sans rien installer, dans un trousseau gpg jetable) que les deux trousseaux ont **exactement cette clé principale** (sous-clés
  `277AE267A409C9C19D5B2B63C187D22C089EF64E` et `CA83A46153BC58D69518ED49A26581F219C8314C`). Le script exige UNE seule clé principale, égale à
  cette empreinte.
- Arch, paquets officiels : https://archlinux.org/packages/extra/x86_64/mullvad-vpn/ (dépend de `mullvad-vpn-daemon`, qui apporte
  `usr/lib/systemd/system/mullvad-daemon.service`, d'après https://archlinux.org/packages/extra/x86_64/mullvad-vpn-daemon/files/).

NordVPN
- https://support.nordvpn.com/hc/en-us/articles/20196094470929-Installing-NordVPN-on-Linux-distributions : seule la commande
  `sh <(curl -sSf https://downloads.nordcdn.com/apps/linux/install.sh)` est documentée ; pas de dépôt signé ni d'empreinte. Page
  https://nordvpn.com/blog/nordvpn-linux-installation/ non lisible (HTTP 403). Parcours guidé partout.

## Limites connues

- Debian, Proton : `dpkg -i` lit le fichier du dossier temporaire de l'utilisateur après la vérification de la somme. Un autre processus du même
  utilisateur pourrait le remplacer entre-temps (il pourrait aussi lancer `sudo` lui-même une fois le mot de passe saisi). Le dossier est en `0700`.
- Les noms de paquets et de services viennent des pages ci-dessus ; les paquets Arch et Fedora/Debian changent de version sans prévenir (la
  somme SHA-256 de Proton est celle de la version `1.0.10` du paquet de dépôt : si Proton publie une autre version, la somme ne correspond
  plus et le script s'arrête avec un message clair, jusqu'à ce que l'épinglage soit mis à jour).
- Aucun essai réel n'a été fait (ni installation, ni `sudo`, ni capture) : les tests utilisent de faux `sudo`, `curl`, `gpg`, `pacman`, etc.
