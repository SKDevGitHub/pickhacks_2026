import streamlit as st
import pandas as pd
import numpy as np
from sklearn.preprocessing import PolynomialFeatures
from sklearn.linear_model import LinearRegression
import matplotlib.pyplot as plt

st.title("AI-Powered Intersection Resource Forecast (2023-2050)")

# --- Dataset ---
data = {
    "Year": [2023,2024,2025,2026,2027,2028,2029,2030],
    "Power": [82,105,168,240,385,510,680,945],       
    "Water": [0.85,1.10,2.10,3.25,5.80,8.10,11.20,15.60], 
    "CO2": [32,41,68,95,142,195,260,350],            
}
df = pd.DataFrame(data)

# --- User Input Slider ---
N_intersections = st.slider("Number of intersections in city:", min_value=1, max_value=1000, value=150, step=1)

# --- Prepare Polynomial Regression ---
X = df['Year'].values.reshape(-1,1)
poly = PolynomialFeatures(degree=2)
X_poly = poly.fit_transform(X)

metrics = ['Power','Water','CO2']
models = {}
for metric in metrics:
    y = df[metric].values
    model = LinearRegression()
    model.fit(X_poly, y)
    models[metric] = model

# --- Forecast until 2050 ---
years_future = np.arange(2023, 2051).reshape(-1,1)
X_future_poly = poly.transform(years_future)

forecast_per_intersection = {}
for metric in metrics:
    forecast_per_intersection[metric] = models[metric].predict(X_future_poly)

# --- Multiply by number of intersections for city totals ---
forecast_city = {metric: forecast_per_intersection[metric]*N_intersections for metric in metrics}

# --- Combined Plot ---
fig, ax = plt.subplots(figsize=(10,6))

# Plot per-intersection lines (optional thin lines)
ax.plot(years_future, forecast_per_intersection['Power'], '-', color='orange', alpha=0.5, label='Power per Intersection')
ax.plot(years_future, forecast_per_intersection['Water'], '-', color='blue', alpha=0.5, label='Water per Intersection')
ax.plot(years_future, forecast_per_intersection['CO2'], '-', color='green', alpha=0.5, label='CO₂ per Intersection')

# Plot city totals (main focus)
ax.plot(years_future, forecast_city['Power'], '--', color='red', linewidth=2, label='City Total Power')
ax.plot(years_future, forecast_city['Water'], '--', color='navy', linewidth=2, label='City Total Water')
ax.plot(years_future, forecast_city['CO2'], '--', color='darkgreen', linewidth=2, label='City Total CO₂')

ax.set_xlabel("Year")
ax.set_ylabel("Resource Consumption / Emissions")
ax.set_title(f"Forecast for City ({N_intersections} intersections)")
ax.legend(loc='upper left', bbox_to_anchor=(1,1))
plt.tight_layout()
st.pyplot(fig)