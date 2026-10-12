import { useEffect, useState } from "react";
import keycloak from "../keycloak";

function TokenTimer() {
    const [remainingSeconds, setRemainingSeconds] = useState<number | null>(null);
    const [remainingPercentage, setRemainingPercentage] = useState(0);

    useEffect(() => {
        // Διαβάζουμε το τρέχον token, ώστε να ακολουθούμε και την ανανέωσή του.
        function updateRemainingTime() {
            const tokenData = keycloak.tokenParsed;

            if (tokenData === undefined || typeof tokenData.exp !== "number") {
                setRemainingSeconds(null);
                setRemainingPercentage(0);
                return;
            }

            const expirationTime = tokenData.exp * 1000;
            const remainingTime = Math.max(0, expirationTime - Date.now());

            setRemainingSeconds(Math.ceil(remainingTime / 1000));

            // Το iat είναι η ώρα έκδοσης και το exp η ώρα λήξης του token.
            let percentage = 0;

            if (typeof tokenData.iat === "number") {
                const totalTime = (tokenData.exp - tokenData.iat) * 1000;

                if (totalTime > 0) {
                    percentage = Math.min(100, remainingTime / totalTime * 100);
                }
            }

            setRemainingPercentage(percentage);
        }

        updateRemainingTime();
        const timer = window.setInterval(updateRemainingTime, 1000);

        return () => {
            window.clearInterval(timer);
        };
    }, []);

    let clockText = "--:--";
    let labelText = "TOKEN";

    if (remainingSeconds !== null) {
        const minutes = Math.floor(remainingSeconds / 60);
        const seconds = remainingSeconds % 60;

        clockText = String(minutes).padStart(2, "0") + ":" + String(seconds).padStart(2, "0");

        if (remainingSeconds === 0) {
            labelText = "EXPIRED";
        }
    }

    return (
        <div className="token-timer" role="timer" aria-label={`Access token remaining time: ${clockText}`}>
            {/* Ο πρώτος κύκλος είναι το φόντο και ο δεύτερος ο χρόνος που απομένει. */}
            <svg className="token-timer-ring" viewBox="0 0 120 120" aria-hidden="true">
                <circle className="token-timer-track" cx="60" cy="60" r="51" />
                <circle className="token-timer-progress" cx="60" cy="60" r="51" pathLength="100"
                        strokeDasharray="100" strokeDashoffset={100 - remainingPercentage} />
            </svg>
            {labelText === "EXPIRED"?(
                <div className="token-timer-center">
                    <button className="my-button" onClick={() =>window.location.reload()}>  Reload</button> </div>):(
            <div className="token-timer-center">
                <span className="token-timer-label">{labelText}</span>
                <span className="token-timer-clock">{clockText}</span>
            </div>)
                }
        </div>
    );
}

export default TokenTimer;