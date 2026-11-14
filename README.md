# Pultit – 3D-tulostettavat pultit, mutterit ja aluslevyt (STL)

Luo STL-mallit ISO-metrisistä kuusiokantapulteista (ISO 4014/4017), kuusiomuttereista (ISO 4032),
hattumuttereista (DIN 1587, umpinainen kierrereikä) ja aluslevyistä (ISO 7089).
Koot M3, M4, M5, M6, M8, M10, M12.

Kaksi kierretyyppiä:

- **ISO (tarkka)** – oikea 60° ISO-metrinen kierre, normaali karkea nousu. Oletus.
- **Tulostusystävällinen** – suurempi nousu, typistetty ja pyöristetty puolisuunnikasprofiili,
  45° kyljet (ylitys enintään 45° pystyssä tulostettaessa, ei tukia) ja isompi tulostusvara.
  Tarkoitettu FDM-tulostimille, myös heikkolaatuisemmille.

**Tulostusystävällinen kierre ei sovi tavallisiin ISO-pultteihin tai -muttereihin.**
Pultti ja mutteri (tai hattumutteri) pitää tehdä samalla kierretyypillä.

## Asennus
Tarvitset Python 3.8+ (Windows / Mac / Linux).

    pip install -r requirements.txt

## Graafinen käyttöliittymä
    python pultit.py
Valitse tyyppi, koko, kierretyyppi, pituus ja tulostusvara ja paina **Luo STL…**.
(Linuxilla Tkinter voi vaatia paketin `python3-tk`.)

## Komentorivi
    python pultit.py bolt M8 --length 40              # pultti M8x40, ISO-kierre
    python pultit.py bolt M8 -l 40 --thread print     # sama tulostusystävällisellä kierteellä
    python pultit.py bolt M10 -l 60 -t 26             # kierteen pituus 26 mm
    python pultit.py nut M8 --thread print            # mutteri, tulostuskierre
    python pultit.py capnut M8 --thread print         # hattumutteri (DIN 1587)
    python pultit.py washer M8                        # aluslevy
    python pultit.py bolt M6 -l 20 -c 0.3 -o oma.stl  # tulostusvara 0.3 mm

- `--length / -l` varren pituus mm kannan alta (mikä tahansa arvo)
- `--thread-length / -t` kierteen pituus (oletus: koko varsi)
- `--thread iso|print` kierreprofiili (oletus `iso`)
- `--clearance / -c` tulostusvara mm: pultin kierre pienenee ja mutterin kierre suurenee c/2 säteessä
  (oletus 0.2 ISO-tilassa; tulostustilassa 0.20–0.40 koon mukaan, ks. taulukko)
- `--output / -o` tiedostonimi

Tulostusystävällisistä osista tiedostonimeen tulee pääte `_tulostus`.

## Tulostusystävällinen kierre

| Koko | ISO-nousu | Tulostusnousu | Oletusvara (print) |
|------|-----------|---------------|--------------------|
| M3   | 0.50 mm   | 1.00 mm       | 0.20 mm            |
| M4   | 0.70 mm   | 1.25 mm       | 0.25 mm            |
| M5   | 0.80 mm   | 1.50 mm       | 0.30 mm            |
| M6   | 1.00 mm   | 1.75 mm       | 0.35 mm            |
| M8   | 1.25 mm   | 2.00 mm       | 0.40 mm            |
| M10  | 1.50 mm   | 2.50 mm       | 0.40 mm            |
| M12  | 1.75 mm   | 3.00 mm       | 0.40 mm            |

Profiili on puolisuunnikas, jonka kyljet ovat 45° (kuormitus pystyssä tulostettaessa ei vaadi tukia).
Harjat ja pohjat on typistetty ja pyöristetty, ja kierteen alussa on viiste.

## Tulostusvinkit
- Tulosta pultti kanta alaspäin, mutteri ja aluslevy lappeellaan.
- ISO-kierre, etenkin koot M3–M5, vaatii hienon kerroskorkeuden (0.1 mm) ja 0.4 mm suuttimen; kierre voi silti olla epätarkka.
- Tulostusystävällinen kierre on suunniteltu myös karkeammalle FDM-jäljelle (esim. 0.2 mm kerros).
- Jos osat eivät sovi, kasvata `--clearance`-arvoa hieman. Älä sekoita ISO- ja tulostuskierteitä keskenään.
- Hattumutteri tulostetaan kupu ylöspäin (kuusiöpinta alustaa vasten). DIN 1587 -mitat ovat likimääräisiä.

## Windows-versio
`pultit_windows.zip` sisältää valmiin `Pultit.exe`-ohjelman (graafinen käyttöliittymä, Pythonia ei tarvita).
Voit myös ajaa lähdekoodin `run.bat`-tiedostolla, jos Python on asennettu.
