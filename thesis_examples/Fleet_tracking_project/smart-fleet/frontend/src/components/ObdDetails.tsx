import type { ObdData } from "../types/ObdData";

interface ObdDetailsProps {
    obd: ObdData | null | undefined;
}

// Η μηδενική τιμή είναι κανονική μέτρηση, όχι απουσία δεδομένων.
function displayObdValue(value: number | null | undefined, unit: string): string {
    if (value === null || value === undefined) return "—";

    return String(value) + unit;
}

function ObdDetails({ obd }: ObdDetailsProps) {
    // Οι συσκευές χωρίς OBD δεν εμφανίζουν αυτή την ενότητα.
    if (obd === null || obd === undefined) return null;

    let ignitionText = "—";

    if (obd.ignition_on === true) {
        ignitionText = "On";
    } else if (obd.ignition_on === false) {
        ignitionText = "Off";
    }

    return (
        <div className="obd-details">
            <h4>OBD Data</h4>
            <p>Ignition: {ignitionText}</p>
            <p>Engine RPM: {displayObdValue(obd.engine_rpm, " rpm")}</p>
            <p>Coolant Temperature: {displayObdValue(obd.coolant_temperature_c, " °C")}</p>
            <p>Fuel Level: {displayObdValue(obd.fuel_level_percent, "%")}</p>
            <p>Diagnostic Trouble Code Count: {displayObdValue(obd.dtc_count, "")}</p>
        </div>
    );
}

export default ObdDetails;