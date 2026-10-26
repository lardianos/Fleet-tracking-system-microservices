export interface ObdData {
    ignition_on: boolean | null;
    engine_rpm: number | null;
    coolant_temperature_c: number | null;
    fuel_level_percent: number | null;
    dtc_count: number | null;
}