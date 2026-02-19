from typing import Any, Dict

import numpy as np

from backend.constants import DISTRICT_CENTERS
from backend.state import RuntimeState



def generate_stations_from_csv(state: RuntimeState) -> list[Dict[str, Any]]:
    """Generate transformer stations from CSV data in kVA format."""
    capacity_options = [50, 100, 160, 200, 240, 300, 400]

    stations = []
    station_id = 1

    target_stations = 20
    green_count = 10
    yellow_count = 5
    red_count = 5

    status_distribution = ["green"] * green_count + ["yellow"] * yellow_count + ["red"] * red_count
    np.random.shuffle(status_distribution)

    status_idx = 0

    for district in state.known_districts:
        if status_idx >= len(status_distribution):
            break

        district_data = state.district_df[state.district_df["district"] == district].sort_values("snapshot_date")
        if district_data.empty:
            continue

        latest = district_data.iloc[-1]
        center = DISTRICT_CENTERS.get(district, [41.3111, 69.2797])

        capacity_mw = float(latest.get("current_capacity_mw", 120))

        remaining_stations = target_stations - station_id + 1
        remaining_districts = len(
            [d for d in state.known_districts if state.known_districts.index(d) >= state.known_districts.index(district)]
        )
        num_stations = max(1, remaining_stations // remaining_districts)

        if num_stations <= 0:
            break

        history_data = []
        for _, row in district_data.iterrows():
            history_data.append(
                {
                    "date": str(row["snapshot_date"]),
                    "load": round(float(row["actual_peak_load_mw"]) / capacity_mw * 100, 1),
                }
            )

        for i in range(num_stations):
            if status_idx >= len(status_distribution) or station_id > target_stations:
                break

            target_status = status_distribution[status_idx]
            status_idx += 1

            capacity_kva = int(np.random.choice(capacity_options))

            if target_status == "green":
                load_pct = np.random.uniform(10, 49)
            elif target_status == "yellow":
                load_pct = np.random.uniform(50, 79)
            else:
                load_pct = np.random.uniform(80, 98)

            station_id_str = f"ts-{station_id:03d}"
            station_id += 1

            stations.append(
                {
                    "id": station_id_str,
                    "name": f"Substation-{district.replace(' ', '-')}-{chr(65 + (i % 26))}",
                    "district": district.title(),
                    "coordinates": [
                        round(center[0] + np.random.uniform(-0.01, 0.01), 6),
                        round(center[1] + np.random.uniform(-0.01, 0.01), 6),
                    ],
                    "load_weight": round(load_pct, 1),
                    "capacity_kva": capacity_kva,
                    "status": target_status,
                    "installDate": int(2023 - np.random.randint(0, 5)),
                    "demographic_growth": round(1.0 + np.random.uniform(0.15, 0.35), 2),
                    "history": history_data[-24:],
                }
            )

    return stations
