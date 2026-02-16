import pandas as pd
import numpy as np

# Districts of Tashkent
districts = ["Yunusobod", "Shaykhontohur", "Mirzo Ulugbek", "Chilonzor", "Mirobod", 
             "Yakkasaroy", "Sergeli", "Olmazor", "Uchtepa", "Yashnobod", "Bektemir", "Yangihayot"]

data = []
for district in districts:
    # Assign a District Rating (1-5)
    rating = np.random.randint(1, 6)
    for month in range(36):  # 3 years of monthly data
        pop_growth = 1.02 ** (month/12) # 2% annual growth
        load = (rating * 500) * pop_growth + np.random.normal(0, 50)
        temp_effect = 1.3 if (month % 12) in [5,6,7] else 1.1 # Summer spike
        
        data.append({
            "district": district,
            "rating": rating,
            "month_index": month,
            "population_density": 7000 * pop_growth,
            "avg_temp": 35 if (month % 12) in [5,6,7] else 5,
            "transformer_age_avg": 15 + (month/12),
            "commercial_infra_count": rating * 10,
            "total_load_kw": load * temp_effect,
            "capacity_kw": rating * 600,
            "failures_last_year": np.random.randint(0, 5)
        })

df = pd.DataFrame(data)
df.to_csv("tashkent_grid_historic_data.csv", index=False)
print("CSV Generated: 432 rows of historic grid data.")