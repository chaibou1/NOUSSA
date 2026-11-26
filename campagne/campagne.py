"""Génère tous les visuels de la campagne : un décor choisi par produit.

Usage : python3 campagne.py <dossier détourages> <dossier décors> <dossier sortie>
"""
import subprocess
import sys
from pathlib import Path

ICI = Path(__file__).parent

# produit -> (décor, options)   décor = fichier dans le dossier décors, ou "studio:#couleur"
PLAN = {
    "soumbala-viande":                    ("cuisine_1.png",   []),
    "soumbala-viande-2":                  ("marche_1.png",    ["--hauteur", "0.50"]),
    "malo-degue":                         ("cuisine_3.png",   ["--hauteur", "0.58"]),
    "kass-mais-jaune":                    ("vue-dessus_2.png", ["--rotation", "180", "--hauteur", "0.80", "--sol", "0.90", "--a-plat", "--flou", "0.6"]),
    "poudre-crevettes-sechees":           ("epices_0.png",    ["--hauteur", "0.50", "--lumiere", "0.92"]),
    "sel-gemme-piment":                   ("studio:#c49a6c",  ["--hauteur", "0.55", "--sol", "0.84"]),
    "clou-de-girofle":                    ("epices_1.png",    ["--hauteur", "0.52", "--sol", "0.90", "--lumiere", "0.92"]),
    "romarin":                            ("exterieur_3.png", ["--hauteur", "0.48", "--sol", "0.88"]),
    "cannelle":                           ("cuisine_0.png",   ["--hauteur", "0.52", "--sol", "0.90"]),
    "anis-vert":                          ("exterieur_1.png", ["--hauteur", "0.50", "--sol", "0.86"]),
    "melange-celeri-persil":              ("exterieur_0.png", ["--hauteur", "0.72", "--sol", "0.90"]),
    "sel-gemme-epice-kokofin":            ("studio:#d8c3a0",  ["--hauteur", "0.74", "--sol", "0.88"]),
    "datou-soumbala-poisson-fume-1sachet": ("vue-dessus_3.png", ["--hauteur", "0.76", "--sol", "0.88", "--a-plat", "--flou", "0.6"]),
    "datou-soumbala-poisson-fume":        ("cuisine_0.png",   ["--hauteur", "0.56", "--sol", "0.90"]),
    "datou-soumbala-2-poissons-seches":   ("cuisine_1.png",   ["--hauteur", "0.56"]),
}


def main():
    cut, decors, sortie = map(Path, sys.argv[1:4])
    sortie.mkdir(parents=True, exist_ok=True)
    for nom, (decor, opts) in PLAN.items():
        src = cut / f"{nom}.png"
        if not src.exists():
            print("manquant :", src)
            continue
        d = decor if decor.startswith("studio:") else str(decors / decor)
        out = sortie / f"{nom}.jpg"
        subprocess.run([sys.executable, str(ICI / "montage.py"), str(src), d, str(out), *opts], check=True)
        print("ok :", out)


if __name__ == "__main__":
    main()
