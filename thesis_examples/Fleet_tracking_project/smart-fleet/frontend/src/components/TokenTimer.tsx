import { useEffect, useState } from "react";
import keycloak from "../keycloak";

function TokenTimer() {
    const [remainingSeconds, setRemainingSeconds] = useState<number | null>(null);

    useEffect(() => {
        // Υπολογίζουμε τον χρόνο από την πραγματική ώρα λήξης.
        // Δεν αφαιρούμε απλώς ένα δευτερόλεπτο από έναν μετρητή.
        function updateRemainingTime() {
            const tokenData = keycloak.tokenParsed;

            if (tokenData === undefined || typeof tokenData.exp !== "number") {
                setRemainingSeconds(null);
                return;
            }

            const expirationTime = tokenData.exp * 1000;
            const seconds = Math.ceil((expirationTime - Date.now()) / 1000);

            setRemainingSeconds(Math.max(0, seconds));
        }

        // Εμφανίζουμε αμέσως τον χρόνο και τον ενημερώνουμε κάθε δευτερόλεπτο.
        updateRemainingTime();
        const timer = window.setInterval(updateRemainingTime, 1000);

        return () => {
            window.clearInterval(timer);
        };
    }, []);

    if (remainingSeconds === null) {
        return <span className="token-timer">Token expiry unavailable</span>;
    }

    if (remainingSeconds === 0) {
        return <span className="token-timer">Token expired</span>;
    }

    // Μορφοποιούμε τον χρόνο ως λεπτά και δευτερόλεπτα.
    const minutes = Math.floor(remainingSeconds / 60);
    const seconds = remainingSeconds % 60;
    const minutesText = String(minutes).padStart(2, "0");
    const secondsText = String(seconds).padStart(2, "0");

    return <span className="token-timer">Token expires in: <p className="timer-css" aria-hidden="true">{minutesText}:{secondsText}</p></span>;
}

export default TokenTimer;