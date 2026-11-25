#!/bin/sh
# Construit le paquet Debian/Ubuntu de NetIA à partir de l'exécutable autonome.
# Usage : packaging/build_deb.sh <binaire netia> <architecture deb> <dossier de sortie>
#   ex. : packaging/build_deb.sh dist/netia amd64 out/
set -eu

BIN="$1"
ARCH="$2"
OUT="$3"
HERE=$(cd "$(dirname "$0")/.." && pwd)
VERSION=$(sed -n 's/^version = "\(.*\)"/\1/p' "$HERE/pyproject.toml")

ROOT=$(mktemp -d)
trap 'rm -rf "$ROOT"' EXIT
install -Dm755 "$BIN" "$ROOT/usr/bin/netia"
install -Dm644 "$HERE/README.md" "$ROOT/usr/share/doc/netia/README.md"
install -Dm644 "$HERE/LICENSE" "$ROOT/usr/share/doc/netia/copyright"
mkdir -p "$ROOT/DEBIAN"
SIZE=$(du -sk "$ROOT/usr" | cut -f1)
cat > "$ROOT/DEBIAN/control" <<CONTROL
Package: netia
Version: $VERSION
Architecture: $ARCH
Maintainer: chaibou1 <chaibou1@users.noreply.github.com>
Installed-Size: $SIZE
Depends: libc6 (>= 2.35)
Section: net
Priority: optional
Homepage: https://github.com/chaibou1/NOUSSA
Description: Agent IA dans le terminal pour les réseaux informatiques
 NetIA répond aux questions sur les commandes, les protocoles réseau et la
 configuration des routeurs et switches, et peut créer des fichiers, écrire
 du code et lancer des commandes (avec validation). Fonctionne avec Claude,
 OpenAI, Gemini, Mistral, DeepSeek, Groq ou Ollama.
CONTROL

mkdir -p "$OUT"
dpkg-deb --build --root-owner-group "$ROOT" "$OUT/netia_linux_${ARCH}.deb"
echo "Paquet créé : $OUT/netia_linux_${ARCH}.deb (version $VERSION)"
