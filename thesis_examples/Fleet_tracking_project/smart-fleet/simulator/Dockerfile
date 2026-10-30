FROM python:3.11-slim

WORKDIR /app

# Αντιγράφουμε μόνο τον κώδικα, όχι τα μεγάλα αρχεία χαρτών.
COPY teltonika_simulator.py vehicle_simulation.py obd_simulation.py ./

ENV PYTHONUNBUFFERED=1

CMD ["python", "-u", "teltonika_simulator.py"]