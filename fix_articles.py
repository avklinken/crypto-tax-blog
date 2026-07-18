#!/usr/bin/env python3
import glob
import os
import re

MAP_PAD = "content"

EXTENSIES = (".md", ".markdown", ".txt", ".html", ".htm")

PICSUM_URLS = [
    "https://picsum.photos/id/180/1600/900",
    "https://picsum.photos/id/0/1600/900",
    "https://picsum.photos/id/1/1600/900",
    "https://picsum.photos/id/48/1600/900",
    "https://picsum.photos/id/119/1600/900",
]

FRONT_MATTER_RE = re.compile(r"\A---\s*\n.*?\n---\s*\n?", flags=re.DOTALL)
TOP_H1_RE = re.compile(r"^\s*<h1\b[^>]*>.*?</h1>\s*", flags=re.IGNORECASE | re.DOTALL)
BROKEN_IMG_RE = re.compile(
    r'(<img\b[^>]*\bsrc\s*=\s*["\'])'
    r'([^"\']*(?:example\.com|unsplash\.com|source\.unsplash\.com)[^"\']*)'
    r'(["\'][^>]*>)',
    flags=re.IGNORECASE,
)


def slug_naar_titel(bestandsnaam):
    basis = os.path.splitext(bestandsnaam)[0]
    titel = basis.replace("-", " ").strip()
    if not titel:
        return "Artikel"
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


def vervang_kapotte_afbeeldingen(inhoud, picsum_url):
    return BROKEN_IMG_RE.sub(rf"\1{picsum_url}\3", inhoud)


def verzamel_bestanden(map_pad):
    bestanden = []
    for ext in EXTENSIES:
        patroon = os.path.join(map_pad, "**", f"*{ext}")
        bestanden.extend(glob.glob(patroon, recursive=True))
    bestanden = [pad for pad in bestanden if os.path.isfile(pad)]
    bestanden.sort()
    return bestanden


def verwerk_bestand(pad, index):
    with open(pad, "r", encoding="utf-8") as f:
        origineel = f.read()

    titel = slug_naar_titel(os.path.basename(pad))
    picsum_url = PICSUM_URLS[index % len(PICSUM_URLS)]

    bijgewerkt = origineel
    bijgewerkt = vervang_crypto_tax_blog(bijgewerkt, titel)
    bijgewerkt = forceer_h1_bovenaan(bijgewerkt, titel)
    bijgewerkt = vervang_kapotte_afbeeldingen(bijgewerkt, picsum_url)

    if bijgewerkt != origineel:
        with open(pad, "w", encoding="utf-8") as f:
            f.write(bijgewerkt)
        return True
    return False


def main():
    if not os.path.isdir(MAP_PAD):
        raise FileNotFoundError(
            f"Map niet gevonden: {MAP_PAD}. Pas MAP_PAD in fix_articles.py aan."
        )

    bestanden = verzamel_bestanden(MAP_PAD)
    aangepast = 0

    for i, pad in enumerate(bestanden):
        if verwerk_bestand(pad, i):
            aangepast += 1
            print(f"[UPDATED] {pad}")

    print(f"Klaar. Gescand: {len(bestanden)} | Aangepast: {aangepast}")


if __name__ == "__main__":
    main()
