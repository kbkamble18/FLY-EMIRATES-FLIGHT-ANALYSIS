-- ============================================================
-- FINAL TRANSFORMATION SCRIPT (Run After Python Script)
-- ============================================================

-- 1. Add Required Columns
ALTER TABLE flights ADD COLUMN IF NOT EXISTS flight_date DATE;
ALTER TABLE flights ADD COLUMN IF NOT EXISTS scheduled_departure_dt TIMESTAMP;
ALTER TABLE flights ADD COLUMN IF NOT EXISTS scheduled_arrival_dt TIMESTAMP;
ALTER TABLE flights ADD COLUMN IF NOT EXISTS airline_name TEXT;
ALTER TABLE flights ADD COLUMN IF NOT EXISTS origin_airport_name TEXT;
ALTER TABLE flights ADD COLUMN IF NOT EXISTS origin_city TEXT;
ALTER TABLE flights ADD COLUMN IF NOT EXISTS origin_state TEXT;
ALTER TABLE flights ADD COLUMN IF NOT EXISTS dest_airport_name TEXT;
ALTER TABLE flights ADD COLUMN IF NOT EXISTS cancellation_reason_desc TEXT;

-- 2. Populate flight_date
UPDATE flights
SET flight_date = MAKE_DATE("YEAR"::integer, "MONTH"::integer, "DAY"::integer);

-- 3. Populate scheduled_departure_dt (with 2400 handling)
UPDATE flights
SET scheduled_departure_dt = 
    CASE 
        WHEN "SCHEDULED_DEPARTURE" = 2400 THEN 
            (MAKE_DATE("YEAR"::integer, "MONTH"::integer, "DAY"::integer) + INTERVAL '1 day')::timestamp
        ELSE 
            TO_TIMESTAMP(
                "YEAR"::text || '-' || LPAD("MONTH"::text, 2, '0') || '-' || 
                LPAD("DAY"::text, 2, '0') || ' ' || LPAD("SCHEDULED_DEPARTURE"::text, 4, '0'),
            'YYYY-MM-DD HH24MI')
    END;

-- 4. Populate scheduled_arrival_dt (with 2400 handling)
UPDATE flights
SET scheduled_arrival_dt = 
    CASE 
        WHEN "SCHEDULED_ARRIVAL" = 2400 THEN 
            (MAKE_DATE("YEAR"::integer, "MONTH"::integer, "DAY"::integer) + INTERVAL '1 day')::timestamp
        ELSE 
            TO_TIMESTAMP(
                "YEAR"::text || '-' || LPAD("MONTH"::text, 2, '0') || '-' || 
                LPAD("DAY"::text, 2, '0') || ' ' || LPAD("SCHEDULED_ARRIVAL"::text, 4, '0'),
            'YYYY-MM-DD HH24MI')
    END;

-- 5. Fill Nulls in Delay Columns
UPDATE flights
SET 
    "DEPARTURE_DELAY"     = COALESCE("DEPARTURE_DELAY", 0),
    "ARRIVAL_DELAY"       = COALESCE("ARRIVAL_DELAY", 0),
    "AIRLINE_DELAY"       = COALESCE("AIRLINE_DELAY", 0),
    "WEATHER_DELAY"       = COALESCE("WEATHER_DELAY", 0),
    "AIR_SYSTEM_DELAY"    = COALESCE("AIR_SYSTEM_DELAY", 0),
    "SECURITY_DELAY"      = COALESCE("SECURITY_DELAY", 0),
    "LATE_AIRCRAFT_DELAY" = COALESCE("LATE_AIRCRAFT_DELAY", 0);

-- 6. Create Cancellation Reason Description
UPDATE flights
SET cancellation_reason_desc = 
    CASE 
        WHEN "CANCELLATION_REASON" = 'A' THEN 'Airline/Carrier'
        WHEN "CANCELLATION_REASON" = 'B' THEN 'Weather'
        WHEN "CANCELLATION_REASON" = 'C' THEN 'National Air System'
        WHEN "CANCELLATION_REASON" = 'D' THEN 'Security'
        ELSE 'Not Cancelled'
    END;

-- 7. Populate Airline Name
UPDATE flights f
SET airline_name = a."AIRLINE"
FROM airlines a
WHERE f."AIRLINE" = a."IATA_CODE";

-- 8. Populate Origin Airport Details
UPDATE flights f
SET 
    origin_airport_name = ap."AIRPORT",
    origin_city         = ap."CITY",
    origin_state        = ap."STATE"
FROM airports ap
WHERE f."ORIGIN_AIRPORT" = ap."IATA_CODE";

-- 9. Populate Destination Airport Name
UPDATE flights f
SET dest_airport_name = ap."AIRPORT"
FROM airports ap
WHERE f."DESTINATION_AIRPORT" = ap."IATA_CODE";

-- 10. Create Analytical View
DROP VIEW IF EXISTS flight_analysis;

CREATE OR REPLACE VIEW flight_analysis AS
SELECT 
    f.*,
    ao."LATITUDE"  AS origin_lat,
    ao."LONGITUDE" AS origin_lon,
    ad."LATITUDE"  AS dest_lat,
    ad."LONGITUDE" AS dest_lon
FROM flights f
LEFT JOIN airports ao ON f."ORIGIN_AIRPORT" = ao."IATA_CODE"
LEFT JOIN airports ad ON f."DESTINATION_AIRPORT" = ad."IATA_CODE";

-- 11. Create Performance Indexes
CREATE INDEX IF NOT EXISTS idx_flights_airline_name ON flights(airline_name);
CREATE INDEX IF NOT EXISTS idx_flights_origin_name  ON flights(origin_airport_name);
CREATE INDEX IF NOT EXISTS idx_flights_dest_name    ON flights(dest_airport_name);
CREATE INDEX IF NOT EXISTS idx_flights_month        ON flights("MONTH");
CREATE INDEX IF NOT EXISTS idx_flights_day_of_week  ON flights("DAY_OF_WEEK");

-- 12. Final Verification
SELECT 'Setup Complete' AS status, COUNT(*) AS total_flights FROM flight_analysis;
SELECT * FROM flight_analysis LIMIT 5;