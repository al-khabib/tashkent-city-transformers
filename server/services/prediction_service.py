import math
from datetime import date, datetime
from typing import Any, Dict

import numpy as np
from sklearn.cluster import KMeans

from server.constants import DISTRICT_CENTERS
from server.state import RuntimeState
from server.utils import parse_target_date



def predict_grid_load(state: RuntimeState, district: str, target_date: str) -> Dict[str, Any]:
    district_key = district.strip().lower()
    district_rows = state.district_df[state.district_df["district"] == district_key]
    if district_rows.empty:
        raise ValueError(f"Unknown district: {district}")

    current = district_rows.sort_values("snapshot_date").iloc[-1]
    target = parse_target_date(target_date)
    today = date.today()
    months_ahead = max(1, (target.year - today.year) * 12 + (target.month - today.month))

    features = [
        float(current["district_rating"]),
        float(current["population_density"]),
        float(current["avg_temp"]),
        float(current["asset_age"]),
        float(current["commercial_infra_count"]),
        float(months_ahead),
    ]

    predicted_load_mw = float(state.model.predict([features])[0])
    current_capacity_mw = float(current["current_capacity_mw"])

    num_transformers_per_district = 5
    avg_transformer_capacity_mw = 0.075

    scaling_factor = (num_transformers_per_district * avg_transformer_capacity_mw) / max(current_capacity_mw, 1e-6)
    predicted_load = predicted_load_mw * scaling_factor
    current_capacity = current_capacity_mw * scaling_factor

    load_gap = predicted_load - current_capacity
    utilization = predicted_load / max(current_capacity, 1e-6)
    load_percentage = utilization * 100
    risk_score = max(1, min(10, math.ceil(utilization * 8)))
    if load_gap > 0:
        risk_score = min(10, risk_score + 1)
    risk_level = "Low" if risk_score <= 4 else "Medium" if risk_score <= 7 else "High"

    tp_capacity_mw = float(current.get("avg_tp_capacity_mw", 2.5))
    tps_needed = max(0, math.ceil(load_gap / max(tp_capacity_mw * scaling_factor, 0.1)))

    return {
        "district": district,
        "target_date": target.isoformat(),
        "months_ahead": months_ahead,
        "predicted_load_kva": round(predicted_load * 1000, 2),
        "current_capacity_kva": round(current_capacity * 1000, 2),
        "load_gap_kva": round(load_gap * 1000, 2),
        "predicted_load_mw": round(predicted_load, 2),
        "current_capacity_mw": round(current_capacity, 2),
        "load_gap_mw": round(load_gap, 2),
        "load_percentage": round(load_percentage, 2),
        "risk_level": risk_level,
        "risk_score": int(risk_score),
        "transformers_needed": int(tps_needed),
        "affecting_factors": {
            "district_rating": float(current["district_rating"]),
            "population_density": float(current["population_density"]),
            "avg_temp": float(current["avg_temp"]),
            "asset_age": float(current["asset_age"]),
            "commercial_infra_count": float(current["commercial_infra_count"]),
            "months_ahead": months_ahead,
        },
    }



def district_factor_trends(state: RuntimeState, district: str) -> Dict[str, float]:
    rows = state.district_df[state.district_df["district"] == district].sort_values("snapshot_date").tail(24)
    if len(rows) < 12:
        return {"population_pct": 0.0, "commercial_pct": 0.0}

    recent = rows.tail(12)
    previous = rows.head(len(rows) - 12).tail(12)

    def pct_change(new_val: float, old_val: float) -> float:
        if abs(old_val) < 1e-6:
            return 0.0
        return ((new_val - old_val) / old_val) * 100

    return {
        "population_pct": round(
            pct_change(
                float(recent["population_density"].mean()),
                float(previous["population_density"].mean()),
            ),
            1,
        ),
        "commercial_pct": round(
            pct_change(
                float(recent["commercial_infra_count"].mean()),
                float(previous["commercial_infra_count"].mean()),
            ),
            1,
        ),
    }



def seasonal_pressure_note(target_date_iso: str) -> str:
    month = datetime.strptime(target_date_iso, "%Y-%m-%d").month
    if month in (6, 7, 8):
        return "Summer cooling demand is expected to increase grid stress."
    if month in (12, 1, 2):
        return "Winter heating demand is expected to increase grid stress."
    return "Baseline seasonal demand still contributes to elevated peak load."



def make_suggested_tp_points(district: str, transformers_needed: int, overload_scale: float) -> list[Dict[str, Any]]:
    if transformers_needed <= 0:
        return []

    center = DISTRICT_CENTERS.get(district, [41.3111, 69.2797])
    sample_count = max(10, transformers_needed * 8)
    jitter = 0.007 + min(0.02, overload_scale / 1000)
    points = np.column_stack(
        [
            np.random.normal(center[0], jitter, sample_count),
            np.random.normal(center[1], jitter, sample_count),
        ]
    )

    cluster_count = min(transformers_needed, len(points))
    if cluster_count <= 0:
        return []

    kmeans = KMeans(n_clusters=cluster_count, random_state=42, n_init=10)
    kmeans.fit(points)

    centers = kmeans.cluster_centers_
    label_counts = np.bincount(kmeans.labels_, minlength=cluster_count)
    total_samples = max(1, int(label_counts.sum()))

    return [
        {
            "id": f"{district}-tp-{index}",
            "district": district,
            "coordinates": [round(value[0], 6), round(value[1], 6)],
            "cluster_share_pct": round((label_counts[index - 1] / total_samples) * 100, 1),
        }
        for index, value in enumerate(centers.tolist(), start=1)
    ]



def build_prediction_response(state: RuntimeState, target_date: str, all_stations: list[Dict[str, Any]]) -> Dict[str, Any]:
    district_predictions = []
    suggested_tps = []

    for district in state.known_districts:
        prediction = predict_grid_load(state, district, target_date)
        district_predictions.append(prediction)

        critical_transformers = [s for s in all_stations if s["district"] == district.title() and s["status"] == "red"]

        if critical_transformers:
            for i, critical_tf in enumerate(critical_transformers):
                lat = critical_tf["coordinates"][0] + np.random.uniform(-0.002, 0.002)
                lon = critical_tf["coordinates"][1] + np.random.uniform(-0.002, 0.002)
                suggested_tps.append(
                    {
                        "id": f"{district}-tp-{i + 1}",
                        "district": district,
                        "coordinates": [round(lat, 6), round(lon, 6)],
                        "cluster_share_pct": 20.0,
                    }
                )
        elif prediction["predicted_load_mw"] > prediction["current_capacity_mw"]:
            transformers_needed = prediction["transformers_needed"]
            months_ahead = prediction.get("months_ahead", 1)

            time_scale_factor = 1.0
            if months_ahead > 12:
                time_scale_factor = 2.0
            elif months_ahead > 6:
                time_scale_factor = 1.5

            scaled_transformers_needed = max(1, int(transformers_needed * time_scale_factor))
            suggested_tps.extend(
                make_suggested_tp_points(
                    district,
                    scaled_transformers_needed,
                    max(0.0, prediction["load_gap_mw"]),
                )
            )

    district_prediction_map = {entry["district"]: entry for entry in district_predictions}

    for point in suggested_tps:
        district_prediction = district_prediction_map.get(point["district"], {})
        affecting = district_prediction.get("affecting_factors", {})
        trends = district_factor_trends(state, point["district"])

        predicted_load_kva = float(district_prediction.get("predicted_load_kva", 0))
        current_capacity_kva = float(district_prediction.get("current_capacity_kva", 0))
        load_gap_kva = float(district_prediction.get("load_gap_kva", 0))
        load_percentage = float(district_prediction.get("load_percentage", 0))
        cluster_share_pct = float(point.get("cluster_share_pct", 0.0))

        predicted_load_kva = 0 if predicted_load_kva != predicted_load_kva else predicted_load_kva
        current_capacity_kva = 0 if current_capacity_kva != current_capacity_kva else current_capacity_kva
        load_gap_kva = 0 if load_gap_kva != load_gap_kva else load_gap_kva
        load_percentage = 0 if load_percentage != load_percentage else load_percentage

        point["target_date"] = district_prediction.get("target_date", target_date)
        point["expected_load_kva"] = round(float(predicted_load_kva), 1)
        point["expected_load_mw"] = round(float(predicted_load_kva / 1000), 2)
        point["current_capacity_kva"] = round(float(current_capacity_kva), 1)
        point["current_capacity_mw"] = round(float(current_capacity_kva / 1000), 2)
        point["load_gap_kva"] = round(float(load_gap_kva), 1)
        point["load_gap_mw"] = round(float(load_gap_kva / 1000), 2)
        point["load_percentage"] = round(float(load_percentage), 2)
        point["transformers_needed"] = int(district_prediction.get("transformers_needed", 0))
        point["cluster_load_gap_kva"] = round((cluster_share_pct / 100.0) * max(load_gap_kva, 0.0), 1)

        expected_load_display = int(point["expected_load_kva"]) if point["expected_load_kva"] >= 0 else 0
        current_capacity_display = int(point["current_capacity_kva"]) if point["current_capacity_kva"] >= 0 else 0
        load_pct_display = point["load_percentage"] if point["load_percentage"] >= 0 else 0

        point["why_summary"] = (
            f"By {point['target_date']}, projected demand reaches {expected_load_display} kVA "
            f"against {current_capacity_display} kVA capacity "
            f"({load_pct_display}% utilization)."
        )

        current_tp_count = 5
        overloaded_tp_count = min(
            current_tp_count,
            max(0, int(math.ceil((load_gap_kva / max(current_capacity_kva, 1)) * current_tp_count))),
        )

        point["reasons"] = [
            (
                f"Capacity shortfall is {point['load_gap_kva']:.0f} kVA on {point['target_date']}; "
                f"this point covers ~{point['cluster_load_gap_kva']:.0f} kVA of that deficit."
            ),
            (
                f"In {point['district'].title()}, about {overloaded_tp_count} of {current_tp_count} current transformers "
                "are likely to run above safe limits at peak hours, increasing outage/shutdown risk."
            ),
            (
                "Main stress drivers: "
                f"population trend {trends['population_pct']}%, "
                f"commercial growth {trends['commercial_pct']}%, "
                f"temperature indicator {round(float(affecting.get('avg_temp', 0)), 1)}C. "
                f"{seasonal_pressure_note(point['target_date'])}"
            ),
            f"Estimated expansion need for transformer group: {point['transformers_needed']} new unit(s).",
        ]

        point["recommendation"] = (
            f"Proposed Installation: {point['district']}\n\n"
            f"Date: {point['target_date']}\n\n"
            f"Expected Load: {expected_load_display} kVA\n\n"
            f"{point['why_summary']}\n\n"
            + "\n".join(f"{i + 1}. {reason}" for i, reason in enumerate(point["reasons"]))
        )

    future_state = {
        "target_date": target_date,
        "generated_at": datetime.utcnow().isoformat(),
        "district_predictions": district_predictions,
        "suggested_tps": suggested_tps,
        "total_transformers_needed": int(sum(entry["transformers_needed"] for entry in district_predictions)),
    }

    return {
        "mode": "prediction",
        "target_date": target_date,
        "district_predictions": district_predictions,
        "suggested_tps": suggested_tps,
        "total_transformers_needed": future_state["total_transformers_needed"],
        "future_state": future_state,
    }
