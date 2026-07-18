#!/usr/bin/env python3
import glob
import os
import re

MAP_PAD = "content"

EXTENSIES = (".md", ".markdown", ".txt", ".html", ".htm")
PIXABAY_IMAGE_URL = "https://pixabay.com"

FRONT_MATTER_RE = re.compile(r"\A---\s*\n.*?\n---\s*\n?", flags=re.DOTALL)
TOP_H1_RE = re.compile(r"^\s*<h1\b[^>]*>.*?</h1>\s*", flags=re.IGNORECASE | re.DOTALL)
IMG_TAG_RE = re.compile(r"<img\b[^>]*>", flags=re.IGNORECASE)
IMG_SRC_RE = re.compile(r'(\bsrc\s*=\s*["\'])([^"\']*)(["\'])', flags=re.IGNORECASE)
IMG_CLASS_RE = re.compile(r'(\bclass\s*=\s*["\'])([^"\']*)(["\'])', flags=re.IGNORECASE)
BROKEN_SRC_RE = re.compile(
    r"(example\.com|unsplash\.com|source\.unsplash\.com|^$)",
    flags=re.IGNORECASE,
)


def slug_naar_titel(bestandsnaam):
    basis = os.path.splitext(bestandsnaam)[0]
    woorden = [woord for woord in basis.replace("-", " ").split() if woord]
    if not woorden:
        return "Artikel"
    titel = " ".join(woorden)
    return titel[:1].upper() + titel[1:]


def vervang_crypto_tax_blog(inhoud, titel):
    return re.sub(r"crypto-tax-blog", titel, inhoud, flags=re.IGNORECASE)


def forceer_h1_bovenaan(inhoud, titel):
    h1 = f"<h1>{titel}</h1>\n\n"
    fm_match = FRONT_MATTER_RE.match(inhoud)

    if fm_match:
        voor = inhoud[: fm_match.end()]
        rest = inhoud[fm_match.end() :]
        rest = TOP_H1_RE.sub("", rest, count=1)
        return voor + h1 + rest.lstrip()

    zonder_h1 = TOP_H1_RE.sub("", inhoud, count=1)
    return h1 + zonder_h1.lstrip()


def strip_verbergende_img_classes(img_tag):
    class_match = IMG_CLASS_RE.search(img_tag)
    if not class_match:
        return img_tag

    classes = class_match.group(2).split()
    filtered = [c for c in classes if c.lower() not in {"hidden", "opacity-0", "invisible"}]
    nieuwe_klasse = " ".join(filtered).strip()

    if nieuwe_klasse:
        return IMG_CLASS_RE.sub(rf'\1{nieuwe_klasse}\3', img_tag, count=1)
    return IMG_CLASS_RE.sub("", img_tag, count=1)


def forceer_werkende_img_src(img_tag):
    src_match = IMG_SRC_RE.search(img_tag)
    if src_match:
        huidige_src = (src_match.group(2) or "").strip()
        if BROKEN_SRC_RE.search(huidige_src):
            return IMG_SRC_RE.sub(
                rf'\1{PIXABAY_IMAGE_URL}\3',
                img_tag,
                count=1,
            )
        return img_tag

    return img_tag[:-1] + f' src="{PIXABAY_IMAGE_URL}">'


def herstel_img_tags(inhoud):
    def _repl(match):
        tag = match.group(0)
        tag = strip_verbergende_img_classes(tag)
        tag = forceer_werkende_img_src(tag)
        return tag

    return IMG_TAG_RE.sub(_repl, inhoud)


def verzamel_bestanden(map_pad):
    bestanden = []
    for ext in EXTENSIES:
        patroon = os.path.join(map_pad, "**", f"*{ext}")
        bestanden.extend(glob.glob(patroon, recursive=True))
    bestanden = [pad for pad in bestanden if os.path.isfile(pad)]
    bestanden.sort()
    return bestanden


def verwerk_bestand(pad):
    with open(pad, "r", encoding="utf-8") as f:
        origineel = f.read()

    titel = slug_naar_titel(os.path.basename(pad))
    bijgewerkt = origineel
    bijgewerkt = vervang_crypto_tax_blog(bijgewerkt, titel)
    bijgewerkt = forceer_h1_bovenaan(bijgewerkt, titel)
    bijgewerkt = herstel_img_tags(bijgewerkt)

    if bijgewerkt != origineel:
        with open(pad, "w", encoding="utf-8") as f:
            f.write(bijgewerkt)
        return True
    return False


def main():
    if not os.path.isdir(MAP_PAD):
        raise FileNotFoundError(f"Map niet gevonden: {MAP_PAD}. Pas MAP_PAD aan.")

    bestanden = verzamel_bestanden(MAP_PAD)
    aangepast = 0

    for pad in bestanden:
        if verwerk_bestand(pad):
            aangepast += 1
            print(f"[UPDATED] {pad}")

    print(f"Klaar. Gescand: {len(bestanden)} | Aangepast: {aangepast}")


if __name__ == "__main__":
    main()
