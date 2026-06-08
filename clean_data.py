import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
import os
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

print("=== Starting Data Cleaning ===")

try:
    flights = pd.read_csv("data/flights.csv")
    airlines = pd.read_csv("data/airlines.csv")
    airports = pd.read_csv("data/airports.csv")
    logging.info(f"Flights loaded: {flights.shape[0]} rows")

    # Cancellation reason mapping (preserved from original)
    reason_map = {
        "A": "Airline/Carrier",
        "B": "Weather",
        "C": "National Air System",
        "D": "Security",
        np.nan: "Not Cancelled",
    }
    flights["CANCELLATION_REASON_DESC"] = flights["CANCELLATION_REASON"].map(reason_map)

    # Time conversion to minutes
    def hhmm_to_minutes(val):
        if pd.isna(val):
            return np.nan
        try:
            val = int(float(val))
            return (val // 100) * 60 + (val % 100)
        except:
            return np.nan

    time_cols = [
        "SCHEDULED_DEPARTURE",
        "DEPARTURE_TIME",
        "SCHEDULED_ARRIVAL",
        "ARRIVAL_TIME",
    ]
    for col in time_cols:
        flights[col + "_MINUTES"] = flights[col].apply(hhmm_to_minutes)

    # Flight date
    flights["FLIGHT_DATE"] = pd.to_datetime(
        flights["YEAR"].astype(str)
        + "-"
        + flights["MONTH"].astype(str).str.zfill(2)
        + "-"
        + flights["DAY"].astype(str).str.zfill(2)
    )

    # Fill delay columns - NaN treated as 0 (no delay recorded). Existing negative values (early arrivals) are preserved.
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

    # Validation: confirm negatives preserved
    neg_arrival = (flights["ARRIVAL_DELAY"] < 0).sum()
    logging.info(
        f"Negative ARRIVAL_DELAY values preserved (early arrivals): {neg_arrival}"
    )

    # IS_ON_TIME flag (arrival within 15 min) for consistent OTP across dashboard
    flights["IS_ON_TIME"] = (flights["ARRIVAL_DELAY"] <= 15).astype(int)

    # Distance group (for Page 3/4 visuals) - only if column exists in source
    if "DISTANCE" in flights.columns:
        flights["DISTANCE_GROUP"] = pd.cut(
            flights["DISTANCE"],
            bins=[0, 500, 1000, 1500, 2500, float("inf")],
            labels=[
                "0-500 miles",
                "501-1000 miles",
                "1001-1500 miles",
                "1501-2500 miles",
                "2500+ miles",
            ],
            include_lowest=True,
        ).astype(str)
        flights["DISTANCE_GROUP"] = flights["DISTANCE_GROUP"].fillna("Unknown")
        logging.info("DISTANCE_GROUP created")
    else:
        logging.warning(
            "DISTANCE column not found - DISTANCE_GROUP skipped. Add column or skip distance visuals."
        )

    flights.to_csv("data/flights_cleaned.csv", index=False)
    logging.info("Cleaned CSV saved.")

    # PostgreSQL load
    password = "password@123"
    if not password:
        raise ValueError(
            "Set environment variable PG_PASSWORD before running (e.g. export PG_PASSWORD='yourpass')"
        )

    url_object = URL.create(
        drivername="postgresql+psycopg2",
        username="postgres",
        password=password,
        host="localhost",
        port=5432,
        database="flight_delays",
    )
    engine = create_engine(url_object)

    airlines.to_sql("airlines", engine, if_exists="replace", index=False)
    airports.to_sql("airports", engine, if_exists="replace", index=False)
    flights.to_sql("flights", engine, if_exists="replace", index=False, chunksize=50000)
    logging.info("Data loaded to PostgreSQL")

    # Create performance indexes for 5-page dashboard queries
    with engine.connect() as conn:
        conn.execute(
            text("""
            DROP TABLE IF EXISTS airports CASCADE;
            DROP TABLE IF EXISTS airlines CASCADE;
            CREATE INDEX IF NOT EXISTS idx_flights_date ON flights(FLIGHT_DATE);
            CREATE INDEX IF NOT EXISTS idx_flights_airline ON flights(airline_name);
            CREATE INDEX IF NOT EXISTS idx_flights_origin ON flights(origin_airport_name);
            CREATE INDEX IF NOT EXISTS idx_flights_month ON flights("MONTH");
            CREATE INDEX IF NOT EXISTS idx_flights_dow ON flights("DAY_OF_WEEK");
            CREATE INDEX IF NOT EXISTS idx_flights_dep_minutes ON flights("SCHEDULED_DEPARTURE_MINUTES");
            CREATE INDEX IF NOT EXISTS idx_flights_cancelled ON flights("CANCELLED");
            CREATE INDEX IF NOT EXISTS idx_flights_is_ontime ON flights("IS_ON_TIME");
        """)
        )
        airlines.to_sql("airlines", engine, if_exists="append", index=False)
        airports.to_sql("airports", engine, if_exists="append", index=False)
        logging.info("Indexes created on flights table")

    logging.info(
        "=== SUCCESS: Pipeline complete. Ready for 5-page Power BI replica ==="
    )

except Exception as e:
    logging.error(f"Pipeline failed: {str(e)}")
    raise
