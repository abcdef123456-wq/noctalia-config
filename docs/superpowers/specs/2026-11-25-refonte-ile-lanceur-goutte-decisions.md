# Refonte île, lanceur et ouverture des fenêtres : décisions déjà validées

Date : 2026-11-25
Statut : relevé des décisions prises le 2026-11-24 en conversation. Widgets du bureau retirés (PR #61) ; la goutte
existe en plugin (`plugins/nc-gestes/`, phase 1, pas encore branché à l'installation) ; le reste n'est pas codé.
Pourquoi ce fichier : ces décisions avaient disparu du design `2026-11-24-ecosysteme-barre-ile-jarvis-design.md`
(PR #54), qui n'a livré que le moteur de mouvement, la réaction de la barre et le tiroir JARVIS.

## Ce que l'utilisateur a validé (heures UTC du 2026-11-24)

1. **Constat** (16:36) : l'île est « trop chargée/grosse » ; le dessin de l'île et du Spotlight doit changer ;
   « on en a marre de ce système de Spotlight ». Demande : « très beau, smooth et design », pas lourd (16:43).
2. **Direction « Émail »** (16:45, maquettes 17:07, « j'aime bien » 17:16) : surfaces mates teintées par le thème,
   arêtes douces, un reflet fin en haut ; pas de verre flou, pas de gros contours.
3. **Île** : au repos, une seule ligne à la hauteur de la barre (pochette, titre, lecture/pause). Le volume ou la
   luminosité remplacent brièvement ce contenu. Les bureaux et l'heure ne bougent pas.
4. **Survol** (17:16, validé 17:20) : l'île s'agrandit un peu au survol (progression du morceau + loupe), se replie
   quand le curseur sort. Le survol seul n'ouvre jamais la recherche.
5. **Lanceur** (17:16, validé 17:20) : il se déploie depuis l'île (clic sur la loupe ou `Super + R`), même point
   d'ancrage. Trois espaces séparés : Applis, Fichiers, Actions ; leurs résultats ne se mélangent pas.
6. **Goutte** (17:20 à 17:46, « je veux cette animation ») : au lancement d'une appli, la **fenêtre entière** (pas
   l'icône) grossit sous l'île en restant suspendue, le col s'amincit, se rompt, et la fenêtre tombe à sa place.
   À retravailler : plus de volume **avant** la rupture. L'animation ne retarde jamais l'ouverture de l'appli.
   Essai en vrai le 2026-11-26 (thème clair, échelle 1,6) : « ça ne ressemble pas à une goutte qui gonfle puis se
   détache », « plus clean ». Refaite en vraie goutte d'émail (bulbe rond, col en sablier, pincement, chute, ouverture
   sur un ressort) ; le contenu de l'appli y entre dès qu'il est dessiné.
7. **Un geste par thème** (17:30) : la goutte est la signature d'Émail (Rose Aube) seulement. Chaque thème a sa
   propre ouverture de fenêtre (paravent pour Sakura, rail pour Cyberjaune, ligne cathodique pour Vaporwave,
   balayage pour Matrice, horizon pour Nord…) : voir les quatre planches. « Très simpliste, j'aime bien » (17:43).
8. **Vraie fenêtre déformée** : plugin Hyprland, **option A** (22:33), plutôt qu'un Hyprland modifié. Repli sur
   l'animation native si le plugin ne se charge pas. Piste de départ : le code « Genie » de `hyprglass`
   (`shlok-shinde/hyprglass`, `src/Genie.cpp`), jamais essayé ici.
9. **Widgets** (16:03) : plus aucun widget sur le bureau ; ils restent sur l'écran de verrouillage.

## Maquettes

Dans `docs/superpowers/maquettes/` :

- `atlas-lumiere.webp`, `atlas-paysages.webp`, `atlas-nuit.webp`, `atlas-signal.webp` : les 23 thèmes.
- `email-goutte.html` : démo animée de la goutte, version 2, reconstruite depuis la conversation. Ses trois images
  (`email-ile.png`, `email-lanceur-ile.png`, `email-firefox.svg`) sont perdues : la démo joue sur fond vide.
- `goutte-planche.webp` : neuf images de cette démo, de 27 ms à 680 ms.
- `planche-goutte-reelle.webp` : la goutte rendue par le plugin `nc-gestes` sur une vraie fenêtre, avant et après la
  reprise du 2026-11-26, thème clair et sombre, ralenti et vitesse réelle (Hyprland 0.57.2 imbriqué, échelle 1,6,
  vraie île `nc-ile` au-dessus), avec la maquette validée en référence.
- `planche-gestes-clair.webp`, `planche-gestes-sombre.webp` : les 13 autres gestes du plugin, finis comme la goutte
  (couleurs de l'île, carte d'émail tant que l'appli n'a rien dessiné), une ligne par geste : ralenti ×0,15 puis
  vitesse réelle (Hyprland 0.57.2 imbriqué, échelle 1,6).
- `planche-gestes-natifs.webp` : les 9 gestes natifs (styles Hyprland de `nc/apparence.lua`), ralentis.

Figma (île, survol, lanceur, atlas) : https://www.figma.com/design/pTRxbS5oOZsgV3x41s7Voz

## Ce que le code offre déjà (vérifié le 2026-11-25 sur `main` 941bcd47)

- Ouverture au survol : `ILE_SURVOL` dans `nc-reglages`, `HoverHandler` `survol` dans `Ile.qml`.
- Spotlight qui part de la pilule : `etirementRecherche` et `spotDepuisPilule` dans `Ile.qml`.
- Panneau qui sort de la pilule, réversible : `LanceurFondu.qml` (utilisé par `Code.qml` et `JarvisChat.qml`).
- Profils et vitesse d'animation : `Mouvement.qml` (`ILE_ANIM`, `ILE_ANIM_VITESSE`).
- En-têtes de développement Hyprland 0.57.2 installés ; aucun plugin chargé aujourd'hui.

## Questions ouvertes

- Que deviennent les pages actuelles de l'île (432 × 580) si l'île reste sur une ligne : panneau à part via
  `Super + C`, comme proposé le 24, ou autre chose ?
- Ordre des lots. Proposition : île Émail + survol, puis lanceur, puis la goutte (plugin), puis les gestes des
  autres thèmes.
- Plugin : les 14 gestes ont la même finition (2026-11-26). Restent le branchement (`install.sh`, réglage) et le
  repli natif sur les distributions sans en-têtes Hyprland (Debian, Fedora, Nobara).
- Gestes natifs trop proches à l'œil (planche des natifs) : `fondu` et `apparition` (popin 100 % et 97 %, presque
  le même fondu), `debouche` et `rail` (même glissement depuis le bord le plus proche, seule la courbe change),
  `bloc` et `feuille` (même glissement depuis la gauche). Proposition : passer `feuille` (papier : une feuille
  tirée d'une pile) et `rail` (cyberjaune : file sur un rail puis s'enclenche) au plugin, où ils peuvent avoir une
  vraie forme, et donner à `apparition` un style à part (par exemple `gnomed`) ou la fusionner avec `fondu`.
