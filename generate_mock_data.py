import csv
import os
import random
from datetime import date


DISTRICTS = [
    ("yunusabad", 5),
    ("chilonzor", 4),
    ("mirzo ulugbek", 4),
    ("sergeli", 5),
    ("shaykhontohur", 3),
    ("olmazor", 3),
    ("yakkasaroy", 3),
    ("bektemir", 2),
]


def month_range(start_year: int, start_month: int, periods: int):
    year = start_year
    month = start_month
    for _ in range(periods):
        yield year, month
        month += 1
        if month > 12:
            month = 1
            year += 1


def main() -> None:
    random.seed(42)
    base_dir = os.path.dirname(__file__)
    output_path = os.path.join(base_dir, "tashkent_grid_historic_data.csv")

    headers = [
        "snapshot_date",
        "district",
        "district_rating",
        "population_density",
        "avg_temp",
        "asset_age",
        "commercial_infra_count",
        "current_capacity_mw",
        "avg_tp_capacity_mw",
        "actual_peak_load_mw",
    ]

    rows = []
    for district, rating in DISTRICTS:
        base_density = random.randint(5200, 10800)
        base_age = random.randint(10, 35)
        base_commercial = random.randint(80, 320)
        capacity = random.randint(120, 240)
        tp_capacity = round(random.uniform(2.0, 3.5), 2)

        for year, month in month_range(2021, 1, 48):
            season_temp = {
                12: 1,
                1: -1,
                2: 2,
                3: 10,
                4: 18,
                5: 24,
                6: 31,
                7: 36,
                8: 34,
                9: 28,
                10: 20,
                11: 11,
            }[month]
            temp = round(season_temp + random.uniform(-2.5, 2.5), 1)

            growth_factor = 1 + ((year - 2021) * 0.02) + ((month - 1) * 0.001)
            density = int(base_density * growth_factor + random.uniform(-180, 180))
            infra = int(base_commercial * growth_factor + random.uniform(-8, 8))
            age = round(base_age + ((year - 2021) + (month - 1) / 12), 1)

            weather_stress = 1.12 if month in {1, 7, 8} else 1.0
            peak_load = (
                55
                + (rating * 9)
                + (density / 1000) * 3.8
                + (infra / 100) * 3.2
                + age * 0.75
                + abs(temp - 18) * 1.2
            ) * weather_stress
            peak_load = round(peak_load + random.uniform(-8, 8), 2)

            rows.append(
                [
                    date(year, month, 1).isoformat(),
                    district,
                    rating,
                    density,
                    temp,
                    age,
                    infra,
                    capacity,
                    tp_capacity,
                    max(25.0, peak_load),
                ]
            )

    with open(output_path, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(headers)
        writer.writerows(rows)

    print(f"Generated {len(rows)} rows -> {output_path}")


if __name__ == "__main__":
    main()
