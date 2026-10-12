import { useEffect, useState } from "react";
import type { Position } from "../types/Position";

export function useVehicleTracking(imei: string | null) {
    // Κρατάμε την τελευταία θέση του οχήματος που παρακολουθούμε.
    const [latestPosition, setLatestPosition] = useState<Position | null>(null);

    useEffect(() => {
        // Αφαιρούμε τη θέση του προηγούμενου οχήματος.
        setLatestPosition(null);

        // Χωρίς επιλεγμένο όχημα δεν ανοίγουμε σύνδεση.
        if (imei === null || imei === "") {
            return;
        }

        const socket = new WebSocket("ws://localhost:8003/ws");

        // Ελέγχουμε αν η συγκεκριμένη σύνδεση χρησιμοποιείται ακόμη.
        let isActive = true;

        socket.onopen = () => {
            if (!isActive) {
                return;
            }

            // Ζητάμε ενημερώσεις για το επιλεγμένο IMEI.
            socket.send(JSON.stringify({
                action: "subscribe",
                imei,
            }));
        };

        socket.onmessage = (event) => {
            if (!isActive) {
                return;
            }

            try {
                const message = JSON.parse(event.data);

                // Η αρχική θέση επιστρέφεται μαζί με την
                // επιβεβαίωση του subscription.
                if (message.type === "subscribed" && message.latest_position) {
                    const position: Position = message.latest_position;

                    if (position.imei === imei) {
                        setLatestPosition(position);
                    }
                }

                // Οι επόμενες θέσεις φτάνουν ως live ενημερώσεις.
                if (message.type === "position.updated" && message.data) {
                    const position: Position = message.data;

                    if (position.imei === imei) {
                        setLatestPosition(position);
                    }
                }
            } catch (error) {
                console.error("Could not read tracking message:", error);
            }
        };

        socket.onerror = (event) => {
            if (isActive) {
                console.error("Vehicle tracking WebSocket error:", event);
            }
        };

        // Κλείνουμε τη σύνδεση όταν αλλάζει το όχημα
        // ή όταν αποσυνδέεται το component.
        return () => {
            isActive = false;
            socket.close();
        };
    }, [imei]);

    // Εμφανίζουμε θέση μόνο για το επιλεγμένο όχημα.
    if (latestPosition !== null && latestPosition.imei === imei) {
        return latestPosition;
    }

    return null;
}