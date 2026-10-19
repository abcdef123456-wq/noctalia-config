# Corrections après audit du 19 octobre 2026

Les changements locaux préexistants ont été conservés et complétés. Cette note décrit les corrections,
les vérifications effectuées et les essais restant à réaliser sur les autres machines.

Application sur le PC de référence : 11 fichiers ciblés, dont le plugin OpenCode régénéré. Les anciennes versions
sont sauvegardées dans `~/.local/state/noctalia-config/backup-corrections-20261019-142411/` avec un manifeste.
Les services `nc-ile` et `nc-profile-sync` ont été redémarrés. Aucun installateur général ni gestionnaire de paquets
n'a été lancé pour cette application.

## Fonctionnement corrigé

- `export.sh` prépare les fichiers et les contrôles dans un dossier intermédiaire. Il refuse de remplacer un
  `home/` modifié, y compris ses nouveaux fichiers. `--preview` affiche la comparaison sans appliquer l'export.
  Le vérificateur `nc-qs-capture` fait maintenant partie du manifeste.
- La vue enregistre la géométrie au clic Masquer, puis transmet un lot à un processus persistant dans `Etat`.
  « Tout masquer » prend également un instantané unique avant le premier déplacement. Les accès aux fichiers
  d'état restent verrouillés. Un échec de déplacement ou de confirmation ne doit pas supprimer l'état sauvegardé.
- Une capture ponctuelle en mémoire conserve l'image d'une fenêtre marquée dans la vue. Le `ItemGrabResult`
  survit à la fermeture de la vue ; le cache est limité à 12 images et 8 millions de pixels. Sans image conservée,
  la capture disponible ou l'icône reste le secours. Un redémarrage de Quickshell libère ce cache.
- Le rendu en attente et masqué utilise les mêmes marges, niveaux de superposition et estompage. Déplacer ou
  échanger une fenêtre annule son masquage en attente. Rouvrir pendant un lot ne purge pas ses images.
- Les nouvelles géométries incluent le contexte du moniteur. Les coordonnées sont adaptées si l'origine ou la
  taille logique de l'écran change ; les anciens enregistrements restent lisibles.
- Le choix de l'île Quickshell vérifie les imports et le type de capture, y compris après une compilation
  refusée ou échouée. Debian installe aussi les modules QML de Qt utilisés. Ce contrôle ne remplace pas une
  capture réelle avec Hyprland. Les messages de diagnostic distinguent un helper absent et un contrôle échoué.
- Les demandes Coucou sont filtrées par agent. Désactiver Claude ne cache plus une demande Codex activée.
- Le plugin OpenCode résout le répertoire de la session, ordonne les transmissions, limite le cache de métadonnées
  et évite les doublons entre instances d'un même serveur. Une session d'un autre emplacement ne revendique
  pas le terminal du serveur. Les inscriptions sont libérées à l'arrêt du plugin.
- Le choix des variables GPU passe par une seule politique. Le bloc qui la contredisait dans `apply` est retiré.
- Le presse-papiers supprime les PNG évincés, nettoie les fichiers précédents au démarrage et limite les images
  à 64 Mio de fichiers. Désactiver le suivi des téléchargements arrête sa scrutation.

## Vérifications

```sh
python3 -B -m unittest discover -s tests -v
bash -n install.sh export.sh home/.local/bin/nc-fenetre home/.local/bin/nc-profile-sync home/.local/bin/nc-qs-capture
git diff --check
```

Les régressions simulent le retiling, des appels concurrents, les échecs de masquage/restauration et de lecture,
l'export interrompu et sa prévisualisation, le repli sans capture, les demandes Codex, les sessions OpenCode,
les changements de coordonnées et la rétention des images. Elles utilisent des dossiers temporaires et un faux
Hyprland. Le test d'image est exécuté avec Qt hors écran.

Les 19 tests passent sur le PC de référence ; les contrôles Bash et `git diff --check` passent également.

Les composants QML ont également été chargés avec le backend Wayland du PC sans instancier la vue d'ensemble.
Le contrôle de syntaxe et ce chargement ne constituent pas une validation visuelle.

## Vérifications graphiques restantes

1. Une fenêtre : Masquer, Échap, rouvrir ; comparer place, dimensions, contenu, badge et superposition.
2. Plusieurs fenêtres en mosaïque puis flottantes ; réouverture immédiate pendant un lot.
3. Annuler un masquage, déplacer une fenêtre marquée, échanger deux fenêtres, restaurer et fermer une masquée.
4. Deux écrans avec échelles différentes, écran à gauche, portrait et débranchement après masquage.
5. Debian avec ancien Quickshell sans capture, compilation refusée/échouée et capture réelle après installation.
6. Fedora/Nobara : mêmes cycles visuels et transitions entre les profils d'énergie.
7. OpenCode réel : deux projets simultanés, permission, interruption et fin ; le chargement du plugin seul ne suffit pas.

Les optimisations plus larges de scrutation et de recherche du propriétaire de la caméra restent facultatives.
Aucun gain CPU, RAM ou autonomie n'est annoncé sans mesure comparable avant/après.
