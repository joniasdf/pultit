# Pultit – 3D-tulostettavat pultit, mutterit ja aluslevyt (STL)

Luo STL-mallit ISO-metrisistä kuusiokantapulteista (ISO 4014/4017), kuusiomuttereista (ISO 4032),
hattumuttereista (DIN 1587, umpinainen kierrereikä) ja aluslevyistä (ISO 7089). Koot M3, M4, M5, M6, M8, M10, M12. Oikeat kierukkakierteet
(60°, normaali karkea nousu).

## Asennus
Tarvitset Python 3.8+ (Windows / Mac / Linux).

    pip install -r requirements.txt

## Graafinen käyttöliittymä
    python pultit.py
Valitse tyyppi, koko, pituus ja tulostusvara ja paina **Luo STL…**.
(Linuxilla Tkinter voi vaatia paketin `python3-tk`.)

## Komentorivi
    python pultit.py bolt M8 --length 40              # pultti M8x40, täysi kierre
    python pultit.py bolt M10 -l 60 -t 26             # kierteen pituus 26 mm
    python pultit.py nut M8                           # mutteri
    python pultit.py capnut M8                        # hattumutteri (DIN 1587)
    python pultit.py washer M8                        # aluslevy
    python pultit.py bolt M6 -l 20 -c 0.3 -o oma.stl  # tulostusvara 0.3 mm

- `--length / -l` varren pituus mm kannan alta (mikä tahansa arvo)
- `--thread-length / -t` kierteen pituus (oletus: koko varsi)
- `--clearance / -c` tulostusvara mm (oletus 0.2): pultin kierre pienenee ja mutterin kierre suurenee c/2 säteessä
- `--output / -o` tiedostonimi

## Tulostusvinkit
- Tulosta pultti kanta alaspäin, mutteri ja aluslevy lappeellaan.
- Pienet koot (M3–M5) vaativat hienon kerroskorkeuden (0.1 mm) ja 0.4 mm suuttimen; kierre voi silti olla epätarkka.
- Jos osat eivät sovi, kasvata `--clearance`-arvoa (esim. 0.3–0.4).
- Hattumutteri tulostetaan kupu ylöspäin (kuusiöpinta alustaa vasten). DIN 1587 -mitat ovat likimääräisiä.

## Windows-versio
`pultit_windows.zip` sisältää valmiin `Pultit.exe`-ohjelman (graafinen käyttöliittymä, Pythonia ei tarvita).
Voit myös ajaa lähdekoodin `run.bat`-tiedostolla, jos Python on asennettu.
