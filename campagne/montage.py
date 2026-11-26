"""Montage publicitaire : produit détouré posé dans un décor, avec ombres, flou et harmonisation.

Usage : python3 montage.py <produit.png détouré> <decor.png|studio:#RRGGBB> <sortie.jpg> [options]
"""
import argparse
import numpy as np
from PIL import Image, ImageFilter, ImageEnhance, ImageOps

W, H = 1080, 1350  # format 4:5 (Instagram / Facebook)


def cover(im, w, h):
    r = max(w / im.width, h / im.height)
    im = im.resize((round(im.width * r), round(im.height * r)), Image.LANCZOS)
    x, y = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((x, y, x + w, y + h))


def studio(color, w, h):
    """Fond studio : dégradé doux + sol légèrement plus clair au centre."""
    c = np.array(Image.new("RGB", (1, 1), color).getpixel((0, 0)), dtype=np.float32)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    # lumière en haut au centre, assombrie sur les bords
    d = np.sqrt(((xx - w * 0.5) / w) ** 2 + ((yy - h * 0.35) / h) ** 2)
    light = 1.18 - 0.55 * d
    # ligne d'horizon douce (mur / sol)
    floor = 1 / (1 + np.exp(-(yy - h * 0.62) / 25))
    light = light * (1 - 0.08 * floor)
    img = np.clip(c[None, None, :] * light[..., None], 0, 255).astype(np.uint8)
    return Image.fromarray(img)


def vignette(img, strength=0.35):
    w, h = img.size
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    m = np.clip(1 - strength * np.clip(d - 0.55, 0, None) ** 1.5, 0, 1)
    a = np.asarray(img).astype(np.float32) * m[..., None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def harmonise(prod, bg, amount):
    """Rapproche légèrement la teinte du produit de celle du décor."""
    rgb, a = prod.convert("RGB"), prod.getchannel("A")
    p = np.asarray(rgb).astype(np.float32)
    mask = np.asarray(a) > 128
    pm = p[mask].mean(0)
    bm = np.asarray(bg).reshape(-1, 3).astype(np.float32).mean(0)
    # on ne transfère que la teinte (ratio des canaux), pas la luminosité
    tint = (bm / bm.mean()) / (pm / pm.mean())
    p = p * (1 + amount * (tint - 1))[None, None, :]
    out = Image.fromarray(np.clip(p, 0, 255).astype(np.uint8))
    out.putalpha(a)
    return out


def relief(prod, lumiere):
    """Lumière directionnelle douce : haut-gauche éclairé, bas assombri (occlusion)."""
    a = prod.getchannel("A")
    p = np.asarray(prod.convert("RGB")).astype(np.float32)
    h, w = p.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    g = lumiere * (1.06 - 0.10 * (xx / w) - 0.08 * (yy / h))
    g *= 1 - 0.22 * np.clip((yy / h - 0.88) / 0.12, 0, 1) ** 1.5  # base plus sombre
    p = p * g[..., None]
    out = Image.fromarray(np.clip(p, 0, 255).astype(np.uint8))
    out.putalpha(a)
    return out


def light_wrap(canvas_rgb, bg, alpha_full, amount=0.35):
    """Le décor « déborde » légèrement sur les bords du produit pour l'intégrer."""
    m = np.asarray(alpha_full).astype(np.float32) / 255
    inner = np.asarray(alpha_full.filter(ImageFilter.GaussianBlur(6))).astype(np.float32) / 255
    edge = np.clip(m - inner, 0, 1)[..., None] * 2 * amount
    blur = np.asarray(bg.filter(ImageFilter.GaussianBlur(12))).astype(np.float32)
    c = np.asarray(canvas_rgb).astype(np.float32)
    return Image.fromarray(np.clip(c * (1 - edge) + blur * edge, 0, 255).astype(np.uint8))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("produit")
    ap.add_argument("decor")
    ap.add_argument("sortie")
    ap.add_argument("--hauteur", type=float, default=0.56, help="hauteur du produit / hauteur image")
    ap.add_argument("--largeur-max", type=float, default=0.82)
    ap.add_argument("--sol", type=float, default=0.86, help="position verticale de la base du produit")
    ap.add_argument("--flou", type=float, default=5.0, help="flou du décor (px)")
    ap.add_argument("--teinte", type=float, default=0.12)
    ap.add_argument("--rotation", type=int, default=0)
    ap.add_argument("--lumiere", type=float, default=0.97, help="luminosité du produit")
    ap.add_argument("--ombre", type=float, default=1.0, help="intensité des ombres")
    ap.add_argument("--ombre-x", type=float, default=0.10, help="décalage de l'ombre portée (fraction largeur produit)")
    a = ap.parse_args()

    # --- décor ---
    if a.decor.startswith("studio:"):
        bg = studio(a.decor.split(":", 1)[1], W, H)
    else:
        bg = cover(Image.open(a.decor).convert("RGB"), W, H)
        # profondeur de champ : net au niveau de la base du produit, flou devant et derrière
        near = np.asarray(bg.filter(ImageFilter.GaussianBlur(2.5))).astype(np.float32)
        far = np.asarray(bg.filter(ImageFilter.GaussianBlur(a.flou * 2))).astype(np.float32)
        yy = np.arange(H, dtype=np.float32)[:, None, None]
        wgt = np.clip(np.abs(yy - a.sol * H) / (0.22 * H), 0, 1) ** 1.2
        bg = Image.fromarray(np.clip(near * (1 - wgt) + far * wgt, 0, 255).astype(np.uint8))
        bg = ImageEnhance.Color(bg).enhance(0.92)
        # grain léger pour masquer l'agrandissement
        n = np.random.default_rng(0).normal(0, 3.5, (H, W, 1)).astype(np.float32)
        bg = Image.fromarray(np.clip(np.asarray(bg).astype(np.float32) + n, 0, 255).astype(np.uint8))

    # --- produit ---
    prod = Image.open(a.produit).convert("RGBA")
    if a.rotation:
        prod = prod.rotate(a.rotation, expand=True)
    alpha = prod.getchannel("A").point(lambda v: 0 if v < 12 else v)
    prod.putalpha(alpha)
    prod = prod.crop(alpha.getbbox())
    s = min(a.hauteur * H / prod.height, a.largeur_max * W / prod.width)
    prod = prod.resize((round(prod.width * s), round(prod.height * s)), Image.LANCZOS)
    prod = harmonise(prod, bg, a.teinte)
    prod = relief(prod, a.lumiere)
    pw, ph = prod.size
    x = (W - pw) // 2
    y = round(a.sol * H) - ph

    canvas = bg.convert("RGBA")
    pa = prod.getchannel("A")

    # ombre portée : silhouette écrasée et inclinée vers l'arrière
    sh_h = max(1, round(ph * 0.22))
    sil = pa.resize((pw, sh_h)).point(lambda v: min(255, v * 0.6 * a.ombre))
    sil = ImageOps.flip(sil)
    layer = Image.new("L", (W, H), 0)
    layer.paste(sil, (x + round(pw * a.ombre_x), y + ph - sh_h + round(sh_h * 0.08)), sil)
    layer = layer.filter(ImageFilter.GaussianBlur(max(6, pw * 0.025)))
    canvas.alpha_composite(Image.merge("RGBA", (*[Image.new("L", (W, H), 20)] * 3, layer)))

    # ombre de contact : bande sombre et nette juste sous la base
    base = np.asarray(pa)[-max(6, ph // 16):, :].max(0)
    contact = Image.new("L", (W, H), 0)
    cols = np.where(base > 40)[0]
    if len(cols):
        from PIL import ImageDraw
        d = ImageDraw.Draw(contact)
        fill = min(255, round(215 * a.ombre))
        # ombre large et douce
        d.ellipse((x + cols[0] - pw * 0.06, y + ph - ph * 0.05, x + cols[-1] + pw * 0.06, y + ph + ph * 0.05), fill=fill // 2)
        contact = contact.filter(ImageFilter.GaussianBlur(max(10, pw * 0.04)))
        # ombre serrée juste sous la base
        tight = Image.new("L", (W, H), 0)
        ImageDraw.Draw(tight).ellipse((x + cols[0], y + ph - ph * 0.015, x + cols[-1], y + ph + ph * 0.012), fill=fill)
        tight = tight.filter(ImageFilter.GaussianBlur(max(3, pw * 0.008)))
        contact = Image.fromarray(np.maximum(np.asarray(contact), np.asarray(tight)))
        canvas.alpha_composite(Image.merge("RGBA", (*[Image.new("L", (W, H), 8)] * 3, contact)))

    canvas.alpha_composite(prod, (x, y))
    full_a = Image.new("L", (W, H), 0)
    full_a.paste(pa, (x, y))
    out = light_wrap(canvas.convert("RGB"), bg, full_a)
    out = vignette(out, 0.30)
    out = ImageEnhance.Contrast(out).enhance(1.04)
    out.save(a.sortie, quality=92)


if __name__ == "__main__":
    main()
