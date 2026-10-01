import csv
import io
import random
import sys
import zipfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
GAZETTEER = BASE_DIR / 'data' / 'gazetteer' / '2024_Gaz_place_national.zip'

STATE_PRICE = {
    'CA': 4.75, 'WA': 4.45, 'OR': 4.20, 'NV': 4.05, 'AZ': 3.85, 'PA': 4.05, 'NY': 4.15, 'CT': 4.10,
    'NJ': 3.85, 'IL': 3.80, 'MI': 3.70, 'IN': 3.75, 'OH': 3.70, 'CO': 3.55, 'UT': 3.60, 'ID': 3.70,
    'MT': 3.60, 'WY': 3.45, 'NM': 3.45, 'TX': 3.15, 'OK': 3.15, 'AR': 3.25, 'LA': 3.25, 'MS': 3.20,
    'AL': 3.30, 'GA': 3.35, 'TN': 3.30, 'MO': 3.20, 'KS': 3.25, 'NE': 3.35, 'IA': 3.35, 'SC': 3.30,
    'NC': 3.45, 'VA': 3.55, 'FL': 3.50, 'KY': 3.45, 'WI': 3.45, 'MN': 3.50, 'SD': 3.40, 'ND': 3.50,
}
DEFAULT_PRICE = 3.60
EXCLUDED_STATES = {'AK', 'HI', 'PR'}


def main(out_path, count, seed=42):
    rng = random.Random(seed)
    with zipfile.ZipFile(GAZETTEER) as zf, zf.open(zf.namelist()[0]) as fh:
        reader = csv.reader(io.TextIOWrapper(fh, encoding='utf-8'), delimiter='\t')
        next(reader)
        places = [(row[3].rsplit(' ', 1)[0], row[0]) for row in reader if row[0] not in EXCLUDED_STATES]

    with open(out_path, 'w', newline='') as fh:
        writer = csv.writer(fh)
        writer.writerow(['OPIS Truckstop ID', 'Truckstop Name', 'Address', 'City', 'State', 'Rack ID', 'Retail Price'])
        for i, (city, state) in enumerate(rng.sample(places, count), start=1):
            price = STATE_PRICE.get(state, DEFAULT_PRICE) + rng.gauss(0, 0.18)
            writer.writerow([
                1000 + i,
                f'DUMMY TRUCK STOP #{i}',
                f'I-{rng.choice([5, 10, 15, 20, 25, 35, 40, 44, 55, 64, 65, 70, 75, 80, 81, 85, 90, 94, 95])}, '
                f'EXIT {rng.randint(1, 350)}',
                city,
                state,
                rng.randint(100, 900),
                f'{max(price, 2.5):.3f}',
            ])
    print(f'Wrote {count} dummy stations to {out_path}')


if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else BASE_DIR / 'data' / 'fuel-prices-for-be-assessment.csv'
    main(out, int(sys.argv[2]) if len(sys.argv) > 2 else 8000)
