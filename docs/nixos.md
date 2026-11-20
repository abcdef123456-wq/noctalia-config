# NixOS

NixOS est détecté, mais il n'est pas géré par nous. Les paquets, les services et les assistants se déclarent dans la
configuration Nix. `install.sh` y copie seulement ta session, comme `--no-system`, et n'installe rien dans le système.
Il n'y a ni CI ni essai de notre part sur NixOS.

Un adaptateur communautaire existe : [noctalia-config-nixos](https://github.com/RaphaelBlanc/noctalia-config-nixos).
Il n'est pas officiel et nous ne le tenons pas.

## Sans root (poste partagé)

Sans root et sans le groupe `wheel`, tu ne peux pas changer la configuration Nix. Clone notre dépôt dans le dossier de
ton choix (ici `~/noctalia-config`), puis lance `install.sh` :

```sh
git clone https://github.com/abcdef123456-wq/noctalia-config.git ~/noctalia-config && ~/noctalia-config/install.sh
```

S'il manque des outils (Hyprland, Noctalia, Quickshell, uwsm…), le script s'arrête et te dit lesquels. Tu peux les
fournir par un environnement Nix à toi (`nix shell`, `nix profile`), puis relancer le script depuis cet environnement.

`install.sh` peut aussi proposer de lancer l'adaptateur communautaire par `nix run`, sans root. C'est proposé seulement
quand une révision de l'adaptateur a été relue : le script ne lance que cette révision précise, après une question dont
la réponse par défaut est non (`--oui` ne l'accepte pas). Aujourd'hui, aucune révision n'est relue : rien n'est proposé.
