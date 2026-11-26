# Campagne publicitaire

- `entree/` : déposez ici une photo par produit (nette, bien éclairée, fond quelconque).
  Nommez chaque fichier avec le nom du produit, ex. `bouillon-poisson-seche.jpg`.
- `sortie/` : les visuels publicitaires finis (produit détouré, posé dans un décor studio ou extérieur, sans texte ajouté).

## Régénérer les visuels
1. Détourage (rembg, modèle BiRefNet) de chaque photo de `entree/` → PNG transparents.
2. Décors générés en local avec SD-Turbo (open source), sans texte ni personnage.
3. `python3 campagne.py <détourages> <décors> sortie` : le choix du décor par produit est dans `PLAN` (campagne.py), les réglages (taille, ombre, flou, lumière) dans `montage.py --help`.
