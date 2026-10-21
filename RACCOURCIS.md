# Raccourcis clavier

Les touches sont nommées comme sur une disposition **US** ; les raccourcis sont définis par la **position** des touches, ils
marchent donc de la même façon avec un clavier AZERTY (par exemple `` ` `` est la touche `²`, sous Échap). **Super** est la
touche Windows.

La fiche s'affiche aussi à l'écran avec **Super + /**. Elle est lue en direct dans ta config : un raccourci que tu ajoutes
avec une description (`{ description = "Section|Texte" }`, voir `~/.config/hypr/nc/raccourcis.lua`) y apparaît tout seul.
La commande `nc-keys` donne la même liste dans le terminal. Tes propres raccourcis : `nc-raccourci ajoute "Super+B" "firefox" "Navigateur"` (rangés dans `~/.config/hypr/perso.lua`,
section « Mes raccourcis » de la fiche).

## Applis et barre

| Touches | Action |
|---|---|
| `Super` + `Entrée` | Terminal |
| `Super` + `E` | Fichiers |
| `Super` + `R` | Rechercher (applis, fichiers, calculs) ; « + nom » : un logiciel à installer (dépôts, AUR, Flatpak), Entrée l'installe |
| `Super` + `W` | Choisir le fond d'écran |
| `Super` + `C` | Centre de contrôle |
| `Super` + `,` | Réglages de la barre |
| `Super` + `Alt` + `,` | Réglages du bureau (fenêtre, avec recherche) ; déjà ouverte : la ramène, la met devant, ou la masque |
| `Super` + `/` | Afficher cette fiche |
| `Super` + `P` | Capture d'une zone de l'écran |
| `Super` + `` ` `` | Terminal déroulant (sous Échap) ; rangé tout seul dès que tu vas ailleurs (clic sur une autre fenêtre ou sur le bureau à côté, Alt + Tab, autre bureau), il revient tel quel ; ce que tu y lances s'ouvre sur le bureau du dessous |
| `Super` + `Maj` + `V` | Historique du presse-papiers |
| `Super` + `.` | Émojis |
| `Impr. écran` | Capture de l'écran |
| `Super` + `Maj` + `S` | Capture à annoter |
| `Super` + `Maj` + `T` | Copier le texte d'une zone de l'écran (image, vidéo, PDF scanné) |

## Fenêtres

| Touches | Action |
|---|---|
| `Super` + `Maj` + `Q` | Fermer (et le programme si dernière) |
| `Super` + `V` | Fenêtre libre ↔ rangée |
| `Super` + `F` | Plein écran |
| `Super` + `Maj` + `P` | Garder sa taille (pseudo) |
| `Super` + `J` | Changer le sens de la division |
| `Super` + `flèches` | Aller à la fenêtre voisine |
| `Super` + `Maj` + `flèches` | Déplacer la fenêtre |
| `Super` + `Ctrl` + `flèches` | Agrandir / rétrécir la fenêtre |
| `Super` + `Ctrl` + `P` | Épingler sur tous les bureaux |
| `Super` + `Ctrl` + `S` | Taille : 50 %, 70 %, 90 % de l'écran |
| `Super` + `Ctrl` + `C` | Recentrer la fenêtre flottante |
| `Super` + `G` | Grouper les fenêtres en onglets |
| `Super` + `Maj` + `G` | Sortir la fenêtre du groupe |
| `Super` + `Ctrl` + `Tab` | Onglet suivant du groupe |
| `Super` + `Ctrl` + `Maj` + `Tab` | Onglet précédent du groupe |
| `Alt` + `Tab` | Passer d'une fenêtre à l'autre |
| `Super` + `Ctrl` + `1…4` | Marque-pages : attacher, puis rappeler la fenêtre (1…4) |
| `Super` + `Ctrl` + `Maj` + `1…4` | Marque-pages : rattacher la fenêtre active (1…4) |

## Bureaux

| Touches | Action |
|---|---|
| `Super` + `1…0` | Aller au bureau 1 à 10 |
| `Super` + `Maj` + `1…0` | Envoyer la fenêtre au bureau 1 à 10 |
| `Super` + `molette` | Bureau suivant / précédent |
| `Super` + `Tab` | Bureau caché (bloc-notes) |
| `Super` + `Maj` + `Tab` | Fenêtre ↔ bureau caché |
| `Super` + `Maj` + `` ` `` | Fenêtre ↔ terminal caché |

## Souris

| Touches | Action |
|---|---|
| `Super` + `glisser` | Déplacer la fenêtre |
| `Super` + `clic droit` | Redimensionner la fenêtre |
| `Super` + `Alt` + `glisser` | Détacher et placer librement |
| `Super` + `Alt` + `clic droit` | Détacher et redimensionner librement |
| `Super` + `Maj` + `glisser` | Redimensionner (pavé tactile) |
| `Super` + `H` ou `Super` + `M` | Masquer la fenêtre (elle revient par la vue des fenêtres, Spotlight, le dock ou Alt + Tab) |
| Survol du titre de la fenêtre, dans la barre | Les icônes des fenêtres du bureau, puis des masquées, et le nom de celle sous la souris : clic pour y aller ou la ramener, `−` pour masquer la fenêtre active |
| Molette sur le titre de la fenêtre, dans la barre | Fenêtre suivante ou précédente du bureau |
| Clic sur le titre de la fenêtre, dans la barre | Page « Fenêtres » de l'île : masquer, ramener, fermer, tout masquer, tout afficher (clic droit : vue des fenêtres) |
| `Super` + `Ctrl` + `M` | Ramener la dernière fenêtre masquée |
| `Super` + `A` (ou trois doigts vers le haut) | Vue de toutes les fenêtres, les masquées comprises (marquées « Masquée ») : clic pour y aller ou la ramener, glisser sur un bureau pour l'y envoyer, clic molette pour fermer |
| Trois doigts vers le bas · `Échap` | Refermer la vue des fenêtres : on arrive sur le bureau choisi dans la vue |
| Dans la vue : `←` `→`, deux doigts à l'horizontale, clic sur un bureau | Parcourir les bureaux (le cube tourne) ; le vrai bureau change en quittant la vue. Animation au choix dans `nc-reglages` → Animations |
| Coins actifs | Pousser la souris dans un coin (au choix dans `nc-reglages` → Clavier et souris) |

Mode **Souris** ou **Les deux** (`nc-reglages` → Clavier et souris), sans toucher au clavier :

| Souris | Action |
|---|---|
| Bouton latéral arrière maintenu + glisser | Déplacer la fenêtre (un simple clic : Précédent) |
| Bouton latéral avant maintenu + glisser | Redimensionner la fenêtre (un simple clic : Suivant) |
| Fenêtre libre lâchée en haut de l'écran | Agrandie |
| Fenêtre libre lâchée sur le bord gauche ou droit | La moitié de l'écran |
| Attraper le bord d'une fenêtre | La redimensionner |
| `Super` + clic molette | Fenêtre libre ↔ rangée |

En mode **Souris**, les fenêtres s'ouvrent libres et centrées, comme sur Windows, puis là où tu les as laissées.

## Système

| Touches | Action |
|---|---|
| `Super` + `L` | Verrouiller l'écran |
| `Super` + `Ctrl` + `Espace` | Éclairage du clavier (palier suivant, puis éteint) |
| `Super` + `Maj` + `Échap` | Verrouiller et mettre en veille |
| `Super` + `Alt` + `P` | Changer de profil d'énergie |
| `Super` + `Alt` + `G` | Mode jeu (effets coupés, pas de notifications) |
| `Super` + `N` | Lumière de nuit |
| `Super` + `O` | Projeter sur un second écran : miroir, étendre, un seul écran (comme Windows + P) |
| `Super` + `Alt` + `M` | Halo musical (pulse sur les basses) |
| `Super` + `Maj` + `N` | Ne pas déranger |
| `Super` + `Ctrl` + `molette` | Loupe : zoomer / dézoomer |
| `Super` + `= / -` | Loupe : zoomer / dézoomer |
| `Super` + `Maj` + `M` | Quitter la session |
| `Super` + `F4` | Éteindre |
| `Super` + `F5` | Redémarrer |
| `Touches média` | Son, luminosité, musique |
| `Super` + `Espace` | Changer la disposition du clavier |

## IA

L'IA du bureau (nc-reglages → Intelligence artificielle : automatique, choisie ou aucune ; en pause en Économie sur
batterie et sans connexion). Détails : [docs/ia.md](docs/ia.md).

| Touches | Action |
|---|---|
| `Super` + `Alt` + `A` | Chat JARVIS : petite fenêtre de conversation vierge (`Super` + `Ctrl` + `P` l'épingle sur tous les bureaux) ; déjà ouverte : la ramène sur ton bureau, la met devant, ou la masque |
| `Super` + `Alt` + `Maj` + `A` | Cockpit JARVIS (grande fenêtre) ; déjà ouvert : le ramène, le met devant, ou le masque |
| `Super` + `Alt` + `I` | IA sur le texte sélectionné (sinon copié) : résumer, traduire, corriger, reformuler, expliquer, répondre, ou une consigne libre (le Spotlight sur `!`) ; résultat copié |
| `Super` + `Alt` + `Maj` + `I` | Expliquer une zone de l'écran avec l'IA (notification, réponse copiée) |
| `Alt` + `I` (terminal) | La description tapée devient une commande, laissée dans l'invite pour être relue |
| `Super` + `R` puis `?` | Question à l'IA (d'abord les réponses de la config) ; la commande proposée se lance avec Entrée |
| `Super` + `R` puis `!` | L'IA sur le texte sélectionné ou copié : résumer, traduire, corriger… ou une consigne libre |
| `Super` + `R` puis `@` | L'IA agit : un plan (services de la session, Wi-Fi, Bluetooth, énergie, son, réglages, mises à jour), chaque action confirmée par Entrée |
| `Espace` + `i` (Neovim) | `i` demander, `e` expliquer, `t` transformer selon une consigne, `c` corriger la sélection |

## Recherche (Super + R)

- Barre vide : tes applications fréquentes, en une rangée d'icônes.
- Texte : applications, puis fichiers et dossiers (à partir de 3 lettres).
- Calcul : `12*8`, ou `=` suivi de n'importe quelle expression (`=20 % de 80`, `=5 km en miles`). **Entrée** copie le résultat.
- **← →** (ou **Tab**) pour choisir une icône, **Entrée** pour lancer, **Échap** pour fermer.

## Fonds d'écran (Super + W)

**← →** (maintenir pour défiler), **Entrée** pour appliquer, taper pour chercher, **Échap** pour fermer.
