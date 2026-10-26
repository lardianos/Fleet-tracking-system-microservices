-- Διατηρούμε το μοντέλο στην υπάρχουσα αντιστοίχιση συσκευής.
ALTER TABLE imei_vehicle_mappings
    ADD COLUMN IF NOT EXISTS device_model TEXT NOT NULL DEFAULT 'GPS';

-- Τα νέα πεδία είναι nullable.
-- Οι παλιές ιστορικές εγγραφές παραμένουν χωρίς OBD μετρήσεις.
ALTER TABLE vehicle_positions
    ADD COLUMN IF NOT EXISTS device_model TEXT,
    ADD COLUMN IF NOT EXISTS ignition_on BOOLEAN,
    ADD COLUMN IF NOT EXISTS engine_rpm INTEGER,
    ADD COLUMN IF NOT EXISTS coolant_temperature_c INTEGER,
    ADD COLUMN IF NOT EXISTS fuel_level_percent INTEGER,
    ADD COLUMN IF NOT EXISTS dtc_count INTEGER;