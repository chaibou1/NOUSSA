# NetIA 🌐🤖

**Un agent IA directement dans ton terminal**, pensé pour la filière réseau
informatique. Tu lui parles comme à un collègue : il répond de façon technique,
et il peut **créer des dossiers et des fichiers, écrire du code et lancer des
commandes** pour toi, toujours avec ta validation.

- Commandes et protocoles : OSPF, VLAN, STP, DHCP, NAT, ACL…
- Configuration de routeurs, switches, pare-feux et serveurs
- Dépannage réseau méthodique
- Python et automatisation réseau (netmiko, scapy, ipaddress…)
- Plusieurs IA au choix : **Claude, OpenAI, Gemini, Mistral, DeepSeek, Groq,
  Ollama (local et gratuit)**

## Installation

```bash
cd netia
pip install .
```

(Pour développer : `pip install -e ".[dev]"` puis `pytest`.)

## Premier lancement

```bash
netia
```

La première fois, NetIA te pose trois questions :
1. **Quel fournisseur d'IA ?** (Claude, OpenAI, Gemini, Mistral, DeepSeek, Groq, Ollama)
2. **Quel modèle ?** (liste de suggestions, ou n'importe quel autre nom)
3. **Ta clé API** (saisie masquée)

La config est enregistrée dans `~/.config/netia/config.json`, un fichier
lisible uniquement par toi.

> `pip` ne peut pas poser de question pendant l'installation : c'est pour ça
> que la demande se fait au premier lancement.

| Fournisseur | `-p` | Clé à créer sur |
|---|---|---|
| Claude (Anthropic) | `anthropic` | console.anthropic.com/settings/keys |
| OpenAI | `openai` | platform.openai.com/api-keys |
| Google Gemini | `gemini` | aistudio.google.com/apikey |
| Mistral AI | `mistral` | console.mistral.ai/api-keys |
| DeepSeek | `deepseek` | platform.deepseek.com/api_keys |
| Groq | `groq` | console.groq.com/keys |
| Ollama (local) | `ollama` | pas de clé : installe [Ollama](https://ollama.com) puis `ollama pull llama3.1` |

Commandes utiles :
- `netia config` : changer de fournisseur, de modèle ou de clé
- `netia models` : voir tous les fournisseurs et modèles, et les clés déjà enregistrées
- `netia config --show` : afficher la config (clés masquées)

Les variables d'environnement (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
`GEMINI_API_KEY`, `MISTRAL_API_KEY`, `DEEPSEEK_API_KEY`, `GROQ_API_KEY`) sont
prioritaires sur le fichier de config.

## Le mode agent (conversation)

Lance `netia` **dans le dossier où tu veux travailler** :

```
$ cd ~/tp-reseau
$ netia
NetIA 0.2.0 — ton agent réseau dans le terminal
Claude (Anthropic) · claude-opus-5-5 · dossier : /home/moi/tp-reseau

❯ crée-moi un projet Python qui scanne mon réseau 192.168.1.0/24 avec un ping sweep

Ok, je te prépare ça : un script avec ipaddress + subprocess, en parallèle…

● Créer  scanner/ping_sweep.py
╭─ scanner/ping_sweep.py ──────────────────────────╮
│   1 import ipaddress                             │
│   …                                              │
╰──────────────────────────────────────────────────╯
Autoriser ? oui / non / toujours pour ce type d'action › o
  ⎿ créé (42 lignes)
```

Ce que l'agent peut faire, **uniquement dans le dossier de travail** :

| Outil | Validation demandée ? |
|---|---|
| lister un dossier, lire un fichier | non |
| créer un dossier | non |
| créer / modifier un fichier (aperçu ou diff affiché) | **oui** |
| lancer une commande (`python script.py`, `ping`, `pip install`…) | **oui** |

À chaque demande de validation, tu réponds `o` (oui), `n` (non, et tu peux dire
quoi faire à la place) ou `t` (toujours pour ce type d'action pendant la
session). `netia -y` valide tout automatiquement : à utiliser avec prudence.

Commandes dans la conversation :

| Commande | Effet |
|---|---|
| `/model claude-sonnet-5-5` | changer de modèle (sans nom : liste) |
| `/provider mistral` | changer d'IA (nouvelle conversation) |
| `/theme proto` | thème : `general`, `cmd`, `proto`, `config`, `python`, `depannage` |
| `/vendor cisco` | constructeur / système de tes équipements |
| `/auto` | activer / désactiver la validation automatique |
| `/save cours.md` | enregistrer la conversation |
| `/reset` · `/aide` · `/quitter` | |

## Questions directes

```bash
netia "différence entre OSPF et EIGRP"           # question directe
netia proto STP                                    # explication complète d'un protocole
netia cmd "voir les ports ouverts sous Linux"
netia configure "VLAN 10/20 + trunk sur un 2960" -v cisco
netia depannage "le PC n'obtient pas d'adresse DHCP"
netia python "script netmiko pour sauvegarder la config de 3 routeurs"
netia -p mistral -m codestral-latest "crée une API Flask hello world"
netia ask "résume le modèle OSI" -o osi.md         # enregistre la réponse
```

Options : `-p` fournisseur, `-m` modèle, `-v` constructeur, `-e` effort de
réflexion (Claude : `low` → `max`), `-y` validation auto, `--no-tools` texte
seulement, `-o` fichier de sortie.

## Coût

Chaque question consomme des crédits chez le fournisseur choisi (sauf Ollama,
qui tourne gratuitement sur ton PC). En mode agent, une tâche peut demander
plusieurs appels à l'IA. Pour dépenser moins : `claude-haiku-5-5`,
`gpt-5-mini`, `gemini-2.5-flash`, ou Ollama.

Les noms de modèles proposés ne sont que des suggestions : si un fournisseur en
renomme un, il suffit de saisir le nouveau nom avec `netia config` ou `-m`.
