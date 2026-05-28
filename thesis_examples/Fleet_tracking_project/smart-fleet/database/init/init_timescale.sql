-- Ενεργοποιεί το TimescaleDB extension στη βάση.
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Πίνακας ιστορικών θέσεων οχημάτων.
CREATE TABLE IF NOT EXISTS vehicle_positions (
    time TIMESTAMPTZ NOT NULL,
    imei VARCHAR(32) NOT NULL,
    vehicle_id VARCHAR(64),
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    speed_kmh INTEGER,
    altitude_m INTEGER,
    angle_deg INTEGER,
    satellites INTEGER,
    PRIMARY KEY (time, imei)
);

-- Μετατρέπει τον πίνακα σε hypertable για time-series δεδομένα.
SELECT create_hypertable(
    'vehicle_positions',
    'time',
    if_not_exists => TRUE
);

-- Read model του Position Processor.
-- Εδώ αποθηκεύεται η συσχέτιση IMEI → vehicle_id που έρχεται από Kafka events.
CREATE TABLE IF NOT EXISTS imei_vehicle_mappings (
    device_imei VARCHAR(32) PRIMARY KEY,
    vehicle_id VARCHAR(64) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);