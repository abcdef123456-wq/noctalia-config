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
| `Super` + `R` | Rechercher (applis, fichiers, calculs) |
| `Super` + `W` | Choisir le fond d'écran |
| `Super` + `C` | Centre de contrôle |
| `Super` + `,` | Réglages de la barre |
| `Super` + `/` | Afficher cette fiche |
| `Super` + `P` | Capture d'une zone de l'écran |
| `Super` + `` ` `` | Terminal déroulant (sous Échap) |
| `Super` + `Maj` + `V` | Historique du presse-papiers |
| `Super` + `.` | Émojis |
| `Impr. écran` | Capture de l'écran |
| `Super` + `Maj` + `S` | Capture à annoter |

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

## Système

| Touches | Action |
|---|---|
| `Super` + `L` | Verrouiller l'écran |
| `Super` + `Maj` + `Échap` | Verrouiller et mettre en veille |
| `Super` + `Alt` + `P` | Changer de profil d'énergie |
| `Super` + `Alt` + `G` | Mode jeu (effets coupés, pas de notifications) |
| `Super` + `N` | Lumière de nuit |
| `Super` + `Maj` + `N` | Ne pas déranger |
| `Super` + `Ctrl` + `molette` | Loupe : zoomer / dézoomer |
| `Super` + `= / -` | Loupe : zoomer / dézoomer |
| `Super` + `Maj` + `M` | Quitter la session |
| `Super` + `F4` | Éteindre |
| `Super` + `F5` | Redémarrer |
| `Touches média` | Son, luminosité, musique |
| `Super` + `Espace` | Changer la disposition du clavier |

## Recherche (Super + R)

- Barre vide : tes applications fréquentes, en une rangée d'icônes.
- Texte : applications, puis fichiers et dossiers (à partir de 3 lettres).
- Calcul : `12*8`, ou `=` suivi de n'importe quelle expression (`=20 % de 80`, `=5 km en miles`). **Entrée** copie le résultat.
- **← →** (ou **Tab**) pour choisir une icône, **Entrée** pour lancer, **Échap** pour fermer.

## Fonds d'écran (Super + W)

**← →** (maintenir pour défiler), **Entrée** pour appliquer, taper pour chercher, **Échap** pour fermer.
