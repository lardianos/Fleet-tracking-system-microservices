import bisect
import json
import math
import random
import urllib.parse
import urllib.request


def calculate_distance_m(first: tuple, second: tuple) -> float:
    # Απόσταση πάνω στη γήινη επιφάνεια.
    # Εσωτερικά χρησιμοποιούμε τη σειρά latitude, longitude.
    lat1 = math.radians(first[0])
    lat2 = math.radians(second[0])
    dlat = lat2 - lat1
    dlon = math.radians(second[1] - first[1])

    value = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )

    value = max(0.0, min(1.0, value))

    return 12742000 * math.atan2(
        math.sqrt(value),
        math.sqrt(1 - value),
    )


def calculate_angle_deg(first: tuple, second: tuple) -> int:
    # Η κατεύθυνση ακολουθεί το τμήμα του δρόμου που διανύουμε.
    lat1 = math.radians(first[0])
    lat2 = math.radians(second[0])
    dlon = math.radians(second[1] - first[1])

    horizontal = math.sin(dlon) * math.cos(lat2)

    vertical = (
        math.cos(lat1) * math.sin(lat2)
        - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    )

    return round(math.degrees(math.atan2(horizontal, vertical))) % 360


def load_road_route(routing_url: str, start: tuple, end: tuple) -> list:
    # Το OSRM απαιτεί longitude,latitude στην κλήση του API.
    coordinates = f"{start[1]},{start[0]};{end[1]},{end[0]}"

    params = urllib.parse.urlencode({
        "overview": "full",
        "geometries": "geojson",
        "steps": "false",
    })

    url = (
        f"{routing_url.rstrip('/')}/route/v1/driving/"
        f"{coordinates}?{params}"
    )

    with urllib.request.urlopen(url, timeout=30) as response:
        result = json.load(response)

    if result.get("code") != "Ok" or not result.get("routes"):
        raise ValueError(
            f"Could not calculate road route: {result.get('code')}"
        )

    points = []

    for longitude, latitude in result["routes"][0]["geometry"]["coordinates"]:
        point = (float(latitude), float(longitude))

        # Αφαιρούμε διαδοχικά ίδια σημεία.
        if not points or calculate_distance_m(points[-1], point) > 0.01:
            points.append(point)

    if len(points) < 2:
        raise ValueError(
            "The road route must contain at least two distinct points."
        )

    return points


class RoadRoute:
    def __init__(self, points: list):
        self.points = points
        self.distances = [0.0]

        for first, second in zip(points, points[1:]):
            self.distances.append(
                self.distances[-1] + calculate_distance_m(first, second)
            )

        self.length = self.distances[-1]

    def position_at(self, distance_m: float) -> tuple:
        # Εντοπίζουμε το τμήμα του δρόμου βάσει της διανυθείσας απόστασης.
        distance_m = max(0.0, min(distance_m, self.length))

        index = min(
            bisect.bisect_right(self.distances, distance_m) - 1,
            len(self.points) - 2,
        )

        first = self.points[index]
        second = self.points[index + 1]

        length = self.distances[index + 1] - self.distances[index]
        fraction = (distance_m - self.distances[index]) / length

        latitude = first[0] + (second[0] - first[0]) * fraction
        longitude = first[1] + (second[1] - first[1]) * fraction

        return latitude, longitude, calculate_angle_deg(first, second)


class VehicleSimulation:
    def __init__(self, args):
        self.args = args

        # Κάθε IMEI έχει ανεξάρτητη και επαναλήψιμη ακολουθία μεταβολών.
        self.random = random.Random(args.imei)

        base = (args.base_latitude, args.base_longitude)
        destination = (
            args.destination_latitude,
            args.destination_longitude,
        )

        outward = load_road_route(
            args.routing_url,
            base,
            destination,
        )

        # Υπολογίζουμε χωριστά την επιστροφή για τις κατευθύνσεις των δρόμων.
        homeward = load_road_route(
            args.routing_url,
            outward[-1],
            outward[0],
        )

        # Δεν επιτρέπουμε σημαντικό άλμα όταν ξεκινά η επιστροφή.
        if (
            calculate_distance_m(homeward[0], outward[-1]) > 2
            or calculate_distance_m(homeward[-1], outward[0]) > 2
        ):
            raise ValueError(
                "Return route endpoints do not match. "
                "Select different road coordinates."
            )

        homeward[0] = outward[-1]
        homeward[-1] = outward[0]

        self.routes = [
            RoadRoute(outward),
            RoadRoute(homeward),
        ]

        self.leg = 0
        self.distance = 0.0

        # Οι εσωτερικοί υπολογισμοί ταχύτητας γίνονται σε μέτρα/δευτερόλεπτο.
        self.speed = 0.0
        self.target_speed = 0.0

        self.state = "OUTBOUND"
        self.wait_remaining = 0.0
        self.pause_remaining = 0.0

        self.driving_seconds = 0.0
        self.speed_change_remaining = 0.0
        self.stop_requested = False

    def snapshot(self) -> tuple:
        latitude, longitude, angle = self.routes[self.leg].position_at(
            self.distance
        )

        # Το Codec8 μεταφέρει ακέραια km/h.
        # Μη μηδενική κίνηση δεν πρέπει να εμφανίζεται ως 0 λόγω στρογγυλοποίησης.
        speed_kmh = 0

        if self.speed > 0:
            speed_kmh = min(
                self.args.max_speed,
                math.ceil(self.speed * 3.6),
            )

        return latitude, longitude, speed_kmh, angle, self.state

    def advance(self, seconds: float):
        # Μικρά βήματα προσομοίωσης, ανεξάρτητα από το διάστημα αποστολής.
        while seconds > 0.0000001:
            step = min(0.1, seconds)

            if self.state == "DESTINATION_WAIT":
                step = min(step, self.wait_remaining)

                self.wait_remaining = max(
                    0.0,
                    self.wait_remaining - step,
                )

                if self.wait_remaining <= 0.0000001:
                    self.leg = 1
                    self.distance = 0.0
                    self.state = "RETURNING"

                    self.driving_seconds = 0.0
                    self.speed_change_remaining = 0.0
                    self.stop_requested = False

            elif self.pause_remaining > 0:
                # Στη στάση δεν αλλάζει η απόσταση ούτε η θέση.
                step = min(step, self.pause_remaining)

                self.pause_remaining = max(
                    0.0,
                    self.pause_remaining - step,
                )

            else:
                self.advance_driving(step)

            seconds -= step

    def advance_driving(self, seconds: float):
        route = self.routes[self.leg]
        remaining = route.length - self.distance

        self.driving_seconds += seconds
        self.speed_change_remaining -= seconds

        if self.driving_seconds >= self.args.stop_every_seconds:
            self.stop_requested = True

        if self.speed_change_remaining <= 0 and not self.stop_requested:
            self.target_speed = (
                self.random.randint(1, self.args.max_speed) / 3.6
            )

            self.speed_change_remaining = self.args.speed_change_seconds

        target = self.target_speed

        if self.stop_requested:
            target = 0.0

        # Επιβραδύνουμε πλησιάζοντας το τέλος της διαδρομής.
        target = min(
            target,
            math.sqrt(
                max(0.0, 2 * self.args.deceleration * remaining)
            ),
        )

        previous_speed = self.speed
        rate = self.args.deceleration

        if target > previous_speed:
            rate = self.args.acceleration

        change_seconds = min(
            seconds,
            abs(target - previous_speed) / rate,
        )

        if target > previous_speed:
            self.speed = min(
                target,
                previous_speed + rate * change_seconds,
            )
        else:
            self.speed = max(
                target,
                previous_speed - rate * change_seconds,
            )

        # Η απόσταση προκύπτει από τη μεταβολή της ταχύτητας μέσα στο διάστημα.
        distance_step = (
            (previous_speed + self.speed) / 2 * change_seconds
        )

        distance_step += self.speed * (seconds - change_seconds)

        self.distance = min(
            route.length,
            self.distance + distance_step,
        )

        if self.distance >= route.length - 0.000001:
            self.distance = route.length
            self.speed = 0.0
            self.target_speed = 0.0
            self.pause_remaining = 0.0

            if self.leg == 0:
                self.state = "DESTINATION_WAIT"
                self.wait_remaining = self.args.destination_wait_seconds
            else:
                # Με την επιστροφή στη βάση αρχίζει αμέσως νέος κύκλος.
                # Επαναχρησιμοποιούμε τις οδικές διαδρομές που έχουν φορτωθεί.
                self.leg = 0
                self.distance = 0.0
                self.state = "OUTBOUND"
                self.wait_remaining = 0.0

                # Μηδενίζουμε τους χρόνους οδήγησης και στάσεων του προηγούμενου
                # σκέλους, ώστε το νέο ταξίδι να ξεκινά με κανονική επιτάχυνση.
                self.driving_seconds = 0.0
                self.speed_change_remaining = 0.0
                self.stop_requested = False

        elif self.stop_requested and self.speed == 0:
            # Η διάρκεια της στάσης αρχίζει αφού ολοκληρωθεί το φρενάρισμα.
            self.pause_remaining = self.args.stop_seconds
            self.driving_seconds = 0.0
            self.stop_requested = False
            self.speed_change_remaining = 0.0