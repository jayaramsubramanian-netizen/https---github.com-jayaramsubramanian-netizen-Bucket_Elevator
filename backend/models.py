from dataclasses import dataclass

@dataclass
class Material:
    name: str
    bulk_density: float
    cohesion: float
    internal_friction_deg: float
    abrasiveness: float
    degradation_factor: float
    moisture: float
    repose_angle_deg: float


@dataclass
class ElevatorGeometry:
    height: float
    pulley_diameter: float
    bucket_volume: float
    bucket_spacing: float
    belt_speed: float
    casing_width: float
    casing_depth: float


@dataclass
class DriveConfig:
    drive_type: str
    motor_kw: float
    gearbox_ratio: float
    service_factor: float = 1.5