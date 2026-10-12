// Περιγράφουμε τα στοιχεία του Fleet που επιστρέφει το API.
export interface Fleet {
    fleet_id: string;
    name: string;
    description: string | null;
    base_location: {
        name: string;
        address: string | null;
        city: string | null;
        postal_code: string | null;
        latitude: number;
        longitude: number;
    };
}