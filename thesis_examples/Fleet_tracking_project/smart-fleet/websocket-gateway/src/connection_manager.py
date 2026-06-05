"""
Connection Manager για το WebSocket Gateway.

Κρατάει ποιοι clients είναι συνδεδεμένοι και σε ποια IMEI έχουν κάνει subscribe.
"""

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        # Κρατάμε όλες τις ενεργές WebSocket συνδέσεις.
        self.active_connections: set[WebSocket] = set()

        # Κρατάμε subscriptions ανά IMEI.
        # Παράδειγμα:
        # {
        #   "123456789012345": {websocket1, websocket2}
        # }
        self.subscriptions: dict[str, set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

        # Όταν κλείνει ένα WebSocket, το αφαιρούμε από όλα τα subscriptions.
        for imei in list(self.subscriptions.keys()):
            self.subscriptions[imei].discard(websocket)

            if not self.subscriptions[imei]:
                del self.subscriptions[imei]

    def subscribe(self, websocket: WebSocket, imei: str):
        if imei not in self.subscriptions:
            self.subscriptions[imei] = set()

        self.subscriptions[imei].add(websocket)

    def unsubscribe(self, websocket: WebSocket, imei: str):
        if imei not in self.subscriptions:
            return

        self.subscriptions[imei].discard(websocket)

        if not self.subscriptions[imei]:
            del self.subscriptions[imei]

    async def send_to_subscribers(self, imei: str, message: dict):
        subscribers = self.subscriptions.get(imei, set())

        disconnected_clients = []

        for websocket in subscribers:
            try:
                await websocket.send_json(message)
            except Exception:
                disconnected_clients.append(websocket)

        # Αν κάποιος client έχει αποσυνδεθεί χωρίς καθαρό close,
        # τον αφαιρούμε για να μην προσπαθούμε να του στέλνουμε ξανά.
        for websocket in disconnected_clients:
            self.disconnect(websocket)