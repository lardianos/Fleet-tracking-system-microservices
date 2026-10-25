import { useEffect, useRef, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import keycloak from "../keycloak";


interface DashboardNotification {
    notification_id: string;
    timestamp_ms: number;
    title: string;
    message: string;
    plate_number: string;
    rule_id: string;
    driver_name?: string;
}

function DashboardNotifications() {
    const { token } = useAuth();

    const [notifications, setNotifications] = useState<DashboardNotification[]>([]);
    const [isOpen, setIsOpen] = useState(false);
    const [unreadCount, setUnreadCount] = useState(0);
    const [connectionStatus, setConnectionStatus] = useState("Connecting...");

    const isOpenRef = useRef(false);

    // Η ανανέωση του token δημιουργεί σύνδεση με τα νέα στοιχεία.
    // Δεν ανανεώνουμε το token από το WebSocket ή από κάποιο timer.
    useEffect(() => {
        if (!token) {
            setConnectionStatus("Disconnected");
            return;
        }

        let stopped = false;
        let socket: WebSocket | null = null;
        let reconnectTimer: number | null = null;

        function connectNotifications() {
            if (stopped || keycloak.isTokenExpired()) {
                setConnectionStatus("Session expired");
                return;
            }

            setConnectionStatus("Connecting...");

            const currentSocket = new WebSocket("ws://localhost:8003/ws/notifications");
            socket = currentSocket;

            currentSocket.onopen = () => {
                if (stopped) return;

                currentSocket.send(JSON.stringify({
                    action: "authenticate",
                    token: token,
                }));
            };

            currentSocket.onmessage = (event) => {
                if (stopped) return;

                try {
                    const message = JSON.parse(event.data);

                    if (message.type === "notifications.connected") {
                        setConnectionStatus("Connected");
                        return;
                    }

                    if (message.type !== "notification.created") return;

                    const notification: DashboardNotification = message.data;

                    if (
                        notification === null ||
                        typeof notification !== "object" ||
                        typeof notification.notification_id !== "string" ||
                        typeof notification.title !== "string" ||
                        typeof notification.message !== "string" ||
                        typeof notification.timestamp_ms !== "number"
                    ) {
                        return;
                    }

                    setNotifications((previous) => {
                        const alreadyExists = previous.some(
                            (item) => item.notification_id === notification.notification_id
                        );

                        if (alreadyExists) return previous;

                        return [notification, ...previous].slice(0, 50);
                    });

                    if (!isOpenRef.current) {
                        setUnreadCount((previous) => Math.min(previous + 1, 50));
                    }
                } catch (error) {
                    console.error("Could not read dashboard notification:", error);
                }
            };

            currentSocket.onclose = (event) => {
                if (stopped) return;

                if (event.code === 4401 || event.code === 1008) {
                    setConnectionStatus("Authentication required");
                    return;
                }

                setConnectionStatus("Disconnected — reconnecting...");

                reconnectTimer = window.setTimeout(connectNotifications, 5000);
            };

            currentSocket.onerror = () => {
                currentSocket.close();
            };
        }

        connectNotifications();

        return () => {
            stopped = true;

            if (reconnectTimer !== null) {
                window.clearTimeout(reconnectTimer);
            }

            if (socket !== null) {
                socket.close();
            }
        };
    }, [token]);

    function toggleNotifications() {
        const nextIsOpen = !isOpen;

        isOpenRef.current = nextIsOpen;
        setIsOpen(nextIsOpen);

        if (nextIsOpen) {
            setUnreadCount(0);
        }
    }
    // Καθαρίζουμε μόνο τη λίστα του συγκεκριμένου browser.
    function clearNotifications() {
        setNotifications([]);
        setUnreadCount(0);
    }
    let buttonText = "Notifications";

    if (unreadCount > 0) {
        buttonText = buttonText + " (" + unreadCount + ")";
    }

    return (
        <div className="dashboard-notifications">
            <button type="button" aria-expanded={isOpen} aria-controls="dashboard-notification-panel" onClick={toggleNotifications}> {buttonText} </button>

            {isOpen && (
                <div className="dashboard-notification-panel" id="dashboard-notification-panel">
                <div className="dashboard-notification-heading">
                    <div className="dashboard-notification-heading-row">
                        <h3>Notifications</h3>
                        <button type="button" onClick={clearNotifications} disabled={notifications.length === 0}> Clear </button>
                    </div>
                    <p role="status">{connectionStatus}</p>
                </div>
                    {notifications.length === 0 && (<p className="dashboard-notification-empty">No notifications received.</p>)}

                    <ul className="dashboard-notification-list">
                        {notifications.map((notification) => (
                            <li key={notification.notification_id}>
                                <strong>{notification.title}</strong>
                                {
                                    typeof notification.driver_name === "string" && ( <p>Driver: {notification.driver_name}</p> )
                                }
                                <p>{notification.message}</p>
                                <time dateTime={new Date(notification.timestamp_ms).toISOString()}>
                                    {new Date(notification.timestamp_ms).toLocaleString("el-GR")}
                                </time>
                            </li>
                        ))}
                    </ul>
                </div>
            )}
        </div>
    );
}

export default DashboardNotifications;