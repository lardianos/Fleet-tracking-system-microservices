# src/models.py
from dataclasses import dataclass, asdict, field
from typing import Dict, Any


@dataclass
class AvlRecord:
    imei: str
    codec_id: int
    timestamp_ms: int
    latitude: float
    longitude: float
    speed_kmh: int
    angle_deg: int
    altitude_m: int
    satellites: int
    priority: int
    event_io_id: int
    io_elements: Dict[int, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)