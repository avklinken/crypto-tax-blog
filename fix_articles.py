#!/usr/bin/env python3
import glob
import os
import re

# Pas dit pad aan als je artikelenmap ergens anders staat.
MAP_PAD = "content"

ONDERSTEUNDE_EXTENSIES = (".md", ".markdown", ".txt", ".html", ".htm")

# 5 stabiele CDN-afbeeldingen (rotatie voor unieke posts)
PICSUM_URLS = [
    "https://picsum.photos/id/180/1600/900",  # Laptop / tech
    "https://picsum.photos/id/0/1600/900",    # Werkplek / tech
    "https://picsum.photos/id/1/1600/900",    # Tech
    "https://picsum.photos/id/48/1600/900",   # Tech
    "https://picsum.photos/id/119/1600/900",  # Tech
]

BROKEN_SRC_RE = re.compile(
    r'(<img\b[^>]*\bsrc\s*=\s*["\'])((?:https?:)?//(?:[^"\']*example\.com[^"\']*|[^"\']*source\.unsplash\.com[^"\']*))(["\'][^>]*>)',
    flags=re.IGNORECASE,
)

FRONT_MATTER_RE = re.compile(r"\A---\s*\n.*?\n---\s*\n?", flags=re.DOTALL)
H1_RE = re.compile(r"<h1\b[^>]*>.*?</h1>", flags=re.IGNORECASE | re.DOTALL)


def slug_naar_titel(bestandsnaam):
    naam_zonder_ext = os.path.splitext(bestandsnaam)[0]
    titel = naam_zonder_ext.replace("-", " ").strip()
    if not titel:
        return "Artikel"
    return titel[0].upper() + titel[1:]


def voeg_h1_toe_als_ontbreekt(inhoud, titel):
    if H1_RE.search(inhoud):
        return inhoud

    h1 = f"<h1>{titel}</h1>\n\n"

    fm_match = FRONT_MATTER_RE.match(inhoud)
    if fm_match:
        fm_einde = fm_match.end()
        return inhoud[:fm_einde] + h1 + inhoud[fm_einde:]

    return h1 + inhoud


def vervang_kapotte_img_src(inhoud, nieuwe_url):
    return BROKEN_SRC_RE.sub(rf"\1{nieuwe_url}\3", inhoud)


def verwerk_bestand(pad, index):
    with open(pad, "r", encoding="utf-8") as f:
        origineel = f.read()

    titel = slug_naar_titel(os.path.basename(pad))
    picsum_url = PICSUM_URLS[index % len(PICSUM_URLS)]

    bijgewerkt = voeg_h1_toe_als_ontbreekt(origineel, titel)
    bijgewerkt = vervang_kapotte_img_src(bijgewerkt, picsum_url)

    if bijgewerkt != origineel:
        with open(pad, "w", encoding="utf-8") as f:
            f.write(bijgewerkt)
        return True
    return False


def verzamel_artikelbestanden(map_pad):
    bestanden = []
    for ext in ONDERSTEUNDE_EXTENSIES:
        patroon = os.path.join(map_pad, "**", f"*{ext}")
        bestanden.extend(glob.glob(patroon, recursive=True))
    bestanden = [b for b in bestanden if os.path.isfile(b)]
    bestanden.sort()
    return bestanden


def main():
    if not os.path.isdir(MAP_PAD):
        raise FileNotFoundError(
            f"Map niet gevonden: {MAP_PAD}. Pas MAP_PAD bovenaan fix_articles.py aan."
        )

    bestanden = verzamel_artikelbestanden(MAP_PAD)
    aangepast = 0

    for i, pad in enumerate(bestanden):
        if verwerk_bestand(pad, i):
            aangepast += 1
            print(f"[UPDATED] {pad}")

    print(f"Klaar. Gescand: {len(bestanden)} | Aangepast: {aangepast}")


if __name__ == "__main__":
    main()
