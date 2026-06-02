import pandas as pd
from sqlalchemy import create_engine
import numpy as np

# Load data
flights = pd.read_csv(
    "FLY EMIRATES FLIGHT ANALYSIS/Final_project_data_archive/flights.csv"
)
airlines = pd.read_csv(
    "FLY EMIRATES FLIGHT ANALYSIS/Final_project_data_archive/airlines.csv"
)
airports = pd.read_csv(
    "FLY EMIRATES FLIGHT ANALYSIS/Final_project_data_archive/airports.csv"
)

print("Original flights shape:", flights.shape)

# Basic cleaning
flights["CANCELLATION_REASON"] = flights["CANCELLATION_REASON"].fillna("None")
flights["CANCELLATION_REASON_DESC"] = flights["CANCELLATION_REASON"].map(
    {
        "A": "Airline/Carrier",
        "B": "Weather",
        "C": "National Air System",
        "D": "Security",
        "None": "Not Cancelled",
    }
)


# Time handling - convert HHMM to minutes past midnight
def hhmm_to_minutes(t):
    if pd.isna(t):
        return np.nan
    t = int(t)
    return (t // 100) * 60 + (t % 100)


time_cols = [
    "SCHEDULED_DEPARTURE",
    "DEPARTURE_TIME",
    "SCHEDULED_ARRIVAL",
    "ARRIVAL_TIME",
]
for col in time_cols:
    flights[col + "_MIN"] = flights[col].apply(hhmm_to_minutes)

# Create FLIGHT_DATE
flights["FLIGHT_DATE"] = pd.to_datetime(
    flights[["YEAR", "MONTH", "DAY"]].astype(str).agg("-".join, axis=1)
)

# Fill delay NaNs with 0 where appropriate
delay_cols = [
    "DEPARTURE_DELAY",
    "ARRIVAL_DELAY",
    "AIR_SYSTEM_DELAY",
    "SECURITY_DELAY",
    "AIRLINE_DELAY",
    "LATE_AIRCRAFT_DELAY",
    "WEATHER_DELAY",
]
for col in delay_cols:
    flights[col] = flights[col].fillna(0)

# Save cleaned CSVs if needed
flights.to_csv("data/flights_cleaned.csv", index=False)

# Load to Postgres
engine = create_engine(
    "postgresql+psycopg2://postgres:YOUR_PASSWORD@localhost:5432/flight_delays"
)

airlines.to_sql("airlines", engine, if_exists="replace", index=False)
airports.to_sql("airports", engine, if_exists="replace", index=False)
flights.to_sql("flights", engine, if_exists="replace", index=False, chunksize=100000)

print("Data loaded to PostgreSQL.")
