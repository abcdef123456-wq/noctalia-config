# Petit aller-retour du bureau à l'ouverture de la vue

Signalement : sur Nobara, la vue s'ouvre au geste à trois doigts ; le bureau se déplace légèrement vers la gauche
puis retrouve immédiatement sa place. Le placement final est correct. La machine n'avait pas encore les dernières mises à jour.
Le geste et l'environnement de cette machine n'ont pas été enregistrés ni reproduits directement.

## Deux défauts reproduits dans le code

1. `Vue.qml` déclarait le cube prêt dès `Component.onCompleted`, alors que le bureau et l'écran pouvaient encore
   être actualisés pendant l'ouverture. Une première position reçue à ce moment était animée comme une navigation,
   avec un recul supplémentaire. Un test QML hors écran, utilisant les vrais calculs de la vue, reproduit cette
   animation en actualisant le bureau pendant l'introduction.
2. Le défilement horizontal acceptait tout delta X non nul. Dans une simulation, un événement de pavé tactile
   de `x = -2, y = 40` lançait un déplacement horizontal, puis le bureau revenait sur sa position à la fin du geste.
   Le code n'exigeait ni direction principalement horizontale ni mouvement minimal.

Ces deux mécanismes sont confirmés en simulation. Ils correspondent au type de symptôme décrit ; leur responsabilité
sur le PC Nobara reste à confirmer par un essai réel.

## Correction

- Attendre la fin de l'introduction, un premier bureau connu et des dimensions valides avant d'activer les animations
  de navigation. Pendant la préparation, placer le bureau directement, sans glissement latéral ni recul parasite.
- Ignorer les gestes de navigation pendant l'introduction, la fermeture et la sélection d'une zone de capture.
- Exiger un mouvement principalement horizontal. Pour les événements précis du pavé tactile, accumuler au moins
  6 pixels avant de commencer ; réutiliser le délai de fin du geste pour oublier une petite dérive isolée.
- Conserver la molette horizontale et les animations de navigation lorsque la vue est prête.

Aucun délai fixe de démarrage, sous-processus ou timer supplémentaire n'est ajouté. L'introduction existante et les
choix d'animation sont conservés. Ce changement est commun aux distributions ; il ne dépend pas d'un nom de machine.

## Ouverture inverse de la fermeture

À la demande de l'utilisateur, l'ouverture reprend désormais le trajet de fermeture en sens inverse : le bureau
part à sa taille réelle, à sa place sur l'écran, puis recule jusqu'à sa miniature. Un seul paramètre de zoom commande
les deux sens, avec la même durée de 260 ms et la même courbe. Refermer pendant l'ouverture inverse le mouvement
depuis sa position courante, sans le remettre au début.

Le grossissement indépendant des miniatures et le glissement vertical des boutons de bureaux ont été retirés.
Le bureau principal garde son opacité pendant le zoom ; ses voisins et les commandes apparaissent à mesure qu'il recule.
La capture du bureau principal reste active pendant l'ouverture pour disposer de son image avant la fin du zoom.
Sans effets, le passage est immédiat. Les protections contre la dérive du geste restent en place.

Le comportement des animations et des événements de défilement est décrit dans la documentation primaire de Qt :
[Behavior](https://doc.qt.io/qt-6/qml-qtquick-behavior.html) et
[WheelHandler](https://doc.qt.io/qt-6/qml-qtquick-wheelhandler.html).

## Validation

Les tests QML hors écran couvrent l'actualisation du bureau pendant l'introduction, une première liste de bureaux
arrivant après l'introduction, les petites dérives, la navigation horizontale volontaire et la molette.
Ils vérifient aussi que la navigation conserve son animation après l'ouverture.
Les tests de géométrie vérifient les positions et dimensions au début et à la fin des deux sens, depuis le premier,
un bureau intermédiaire et le dernier bureau, ainsi que la fermeture pendant l'ouverture.

À vérifier sur Nobara après mise à jour :

1. Ouvrir plusieurs fois avec `Super + A`, puis avec trois doigts vers le haut, y compris légèrement en diagonale.
2. Essayer depuis le premier bureau, un bureau intermédiaire et le dernier bureau.
3. Vérifier l'absence du petit aller-retour et le bon fonctionnement du défilement à deux doigts une fois la vue ouverte.

Une vidéo ou les résultats de ces essais permettront de distinguer une correction effective sur cette machine d'une
autre cause éventuelle. La correction ne vaut pas validation de tous les problèmes d'échelle sur Nobara.
