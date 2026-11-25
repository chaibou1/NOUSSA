#!/bin/sh
# Installe NetIA sur Debian / Ubuntu (et dérivées) avec apt.
#   curl -fsSL https://github.com/chaibou1/NOUSSA/releases/latest/download/install.sh | sh
set -eu

REPO="chaibou1/NOUSSA"

if ! command -v apt-get >/dev/null 2>&1; then
    echo "Ce script est pour Debian/Ubuntu (apt). Ailleurs : pip install netia" >&2
    exit 1
fi

ARCH=$(dpkg --print-architecture)
case "$ARCH" in
    amd64|arm64) ;;
    *) echo "Architecture $ARCH non prise en charge. Utilise : pip install netia" >&2; exit 1 ;;
esac

URL="${NETIA_DEB_URL:-https://github.com/$REPO/releases/latest/download/netia_linux_${ARCH}.deb}"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
chmod 755 "$TMP"  # lisible par l'utilisateur _apt

echo "Téléchargement de NetIA ($ARCH)…"
if command -v curl >/dev/null 2>&1; then
    curl -fL --progress-bar -o "$TMP/netia.deb" "$URL"
elif command -v wget >/dev/null 2>&1; then
    wget -q --show-progress -O "$TMP/netia.deb" "$URL"
else
    echo "Il faut curl ou wget : sudo apt install curl" >&2
    exit 1
fi
chmod 644 "$TMP/netia.deb"

SUDO=""
[ "$(id -u)" -eq 0 ] || SUDO="sudo"
$SUDO apt-get install -y "$TMP/netia.deb"

echo
echo "✅ NetIA est installé. Lance-le avec : netia"
echo "   Désinstaller : sudo apt remove netia"
