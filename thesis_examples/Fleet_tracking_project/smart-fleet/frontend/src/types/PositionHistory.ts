// Το ιστορικό περιέχει τα πεδία που αποθηκεύονται στο TimescaleDB.
// Δεν απαιτεί τα επιπλέον πεδία του ζωντανού telemetry.
export interface HistoricalPosition {
    timestamp_ms: number;
    imei: string;
    vehicle_id: string;
    latitude: number;
    longitude: number;
    speed_kmh: number | null;
    altitude_m: number | null;
    angle_deg: number | null;
    satellites: number | null;
}

export interface PositionHistoryCursor {
    after_time: string;
    after_imei: string;
}

export interface VehiclePositionHistoryResponse {
    vehicle_id: string;
    positions: HistoricalPosition[];
    has_more: boolean;
    next_cursor: PositionHistoryCursor | null;
}

export interface DriverAssignmentPeriod {
    vehicle_id: string;
    plate_number: string | null;
    fleet_id: string | null;
    start_time: string;
    end_time: string;
}

export interface DriverAssignmentPeriodsResponse {
    driver_id: string;
    assignment_periods: DriverAssignmentPeriod[];
}

export interface VehicleAssignmentAudit {
    id: string;
    timestamp: string;
    changes: { driver_id: { from_value: string | null; to_value: string | null } };
}

// Κάθε τμήμα αφορά ένα όχημα και ένα γνωστό ή άγνωστο διάστημα ανάθεσης.
export interface PositionHistorySegment {
    vehicleId: string;
    plateNumber: string;
    driverId: string | null;
    assignmentKnown: boolean;
    startTime: string;
    endTime: string;
    positions: HistoricalPosition[];
}
