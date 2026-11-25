# NetIA 🌐🤖

Assistant IA en ligne de commande pour les étudiants en **réseau informatique** :
trouver une commande, comprendre un protocole, configurer un routeur ou un switch,
dépanner un réseau, apprendre Python et l'automatisation réseau.

NetIA utilise l'API Claude d'Anthropic.

## Installation

```bash
cd netia
pip install .
```

(Pour développer : `pip install -e ".[dev]"` puis `pytest`.)

## Première utilisation : la clé API

Au **premier lancement**, NetIA te demande ta clé API (saisie masquée) et la
sauvegarde dans `~/.config/netia/config.json`, lisible uniquement par toi.

> `pip` ne peut pas poser de question pendant l'installation : la demande se
> fait donc au premier lancement de `netia`.

- Crée une clé sur <https://console.anthropic.com/settings/keys>
- Changer de clé ou de modèle : `netia config`
- Voir la config (clé masquée) : `netia config --show`
- Tout supprimer : `netia config --reset`
- Tu peux aussi utiliser la variable d'environnement `ANTHROPIC_API_KEY`, qui est prioritaire.

## Utilisation

```bash
netia                                   # mode conversation
netia proto OSPF                        # expliquer un protocole
netia cmd "voir les ports ouverts sous Linux"
netia configure "VLAN 10 et 20 + trunk sur un switch 2960" -v cisco
netia depannage "le PC n'obtient pas d'adresse DHCP"
netia python "script netmiko pour sauvegarder la config de 3 routeurs"
netia ask "différence entre TCP et UDP" -o tcp-udp.md   # enregistre la réponse
```

Options communes :

| Option | Rôle |
|---|---|
| `-v`, `--vendor` | constructeur / système : `cisco`, `mikrotik`, `juniper`, `linux`, `windows`… |
| `-e`, `--effort` | profondeur de réflexion : `low`, `medium` (défaut), `high`, `xhigh`, `max` |
| `-o`, `--output` | enregistrer la réponse dans un fichier Markdown |
| `-t`, `--theme` | (avec `chat` / `ask`) : `general`, `cmd`, `proto`, `config`, `python`, `depannage` |

### Mode conversation

```
toi › comment configurer OSPF zone 0 entre deux routeurs ?
netia › ...
toi › et comment vérifier les voisins ?
```

Commandes internes : `/theme proto`, `/vendor cisco`, `/save cours-ospf.md`,
`/reset`, `/aide`, `/quitter`.

## Coût

Chaque question consomme des crédits sur ton compte Anthropic. Le modèle par
défaut est `claude-opus-5-5`. Tu peux en choisir un moins cher dans
`netia config`, par exemple `claude-haiku-5-5`.
