import os

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestRegressor


def main() -> None:
    base_dir = os.path.dirname(__file__)
    csv_path = os.path.join(base_dir, "tashkent_grid_historic_data.csv")
    model_path = os.path.join(base_dir, "grid_load_rf.joblib")

    if not os.path.exists(csv_path):
        raise FileNotFoundError(
            f"Dataset not found at {csv_path}. Run generate_mock_data.py first."
        )

    df = pd.read_csv(csv_path)
    snapshot_dates = pd.to_datetime(df["snapshot_date"])
    first_date = snapshot_dates.min()
    df["months_since_start"] = (
        (snapshot_dates.dt.year - first_date.year) * 12
        + (snapshot_dates.dt.month - first_date.month)
    )

    feature_cols = [
        "district_rating",
        "population_density",
        "avg_temp",
        "asset_age",
        "commercial_infra_count",
        "months_since_start",
    ]
    target_col = "actual_peak_load_mw"

    X = df[feature_cols]
    y = df[target_col]

    model = RandomForestRegressor(
        n_estimators=300,
        random_state=42,
        min_samples_leaf=2,
        n_jobs=-1,
    )
    model.fit(X, y)
    joblib.dump(model, model_path)

    print(f"Model trained and saved to: {model_path}")
    print(f"Rows: {len(df)}, Features: {feature_cols}")


if __name__ == "__main__":
    main()
