# Installation arrêtée sur « Vérifications / Checks »

Le titre couvrait les versions des logiciels, les écrans, le clavier, le navigateur,
polkit et le verrouillage Noctalia. Plusieurs commandes n'avaient aucune limite de durée.
Cela rendait impossible d'identifier la commande bloquée à partir du seul titre.

Un scénario est reproduit avec de faux outils Fedora : si `noctalia msg status` ne termine
pas, l'ancien installateur reste en attente. Le banc de test l'arrête après huit secondes.
Cette reproduction établit le défaut du script ; elle n'identifie pas à elle seule la
commande bloquée sur le PC signalé, dont la dernière ligne/capture n'a pas été reçue.

## Correctif

- Chaque étape de détection affiche son nom avant de démarrer.
- Versions Hyprland/Noctalia, version du paquet Hyprland, écrans Hyprland, clavier,
  navigateur et agent polkit : délai de cinq secondes, puis signal de fin forcée après
  deux secondes supplémentaires si nécessaire. Les métadonnées disponibles servent de repli.
- Recherche DNF de Hyprland : trente secondes, puis deux secondes supplémentaires au plus.
  Une erreur ou un délai dépassé arrête l'installation sans activer un COPR sur la seule
  supposition que la bonne version manque. Ce contrôle réseau n'est pas lancé lorsque
  Hyprland est déjà assez récent.
- Verrouillage Noctalia : cinq secondes. Un délai dépassé arrête l'installation avant
  la copie des réglages ; un écran effectivement verrouillé reste également bloquant.
- L'installation des outils de base montre désormais l'authentification et la sortie
  du gestionnaire de paquets. Ces transactions ne sont pas interrompues par les délais
  courts réservés aux lectures. `--files-only` ne tente plus d'installer un outil manquant :
  il donne son nom et s'arrête.
- Une seule interrogation `localectl` et une seule lecture des moniteurs remplacent
  les appels répétés de ces deux détections.

## Validation

`tests/test_install_checks.py` exécute la section réelle de l'installateur avec de faux
logiciels et un HOME temporaire : parcours normal Arch/Fedora/Debian/openSUSE/autre,
commandes qui ne répondent plus, DNF en erreur, écran verrouillé et outils manquants en
mode fichiers seuls. Les durées sont raccourcies dans le banc de test. Aucun paquet n'est
installé et aucun service n'est modifié. Ces tests ne remplacent pas un essai sur Fedora réel.

```sh
python3 -B -m unittest discover -s tests -p test_install_checks.py -v
bash -n install.sh
```

Après récupération du correctif, relancer `nc-maj`. Si le blocage reste présent, transmettre
la dernière ligne affichée, la distribution et la version de Hyprland/Noctalia ; les nouveaux
messages permettent de savoir quelle sonde est concernée. Ne pas réinitialiser le dépôt pour
contourner des modifications personnelles ou un conflit Git.
