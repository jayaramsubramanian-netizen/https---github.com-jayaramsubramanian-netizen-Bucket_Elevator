import math
from constants import GRAVITY


class DynamicLoadEngine:

    @staticmethod
    def startup_tension(running_tension, startup_factor=2.2):
        return running_tension * startup_factor

    @staticmethod
    def shock_loaded_tension(running_tension, shock_factor=1.35):
        return running_tension * shock_factor

    @staticmethod
    def belt_tension(power_kw, speed_mps):
        return (power_kw * 1000) / speed_mps

    @staticmethod
    def chain_tension(total_mass, height, dynamic_factor=2.0):
        return total_mass * GRAVITY * height * dynamic_factor

    @staticmethod
    def acceleration_torque(inertia, angular_acceleration):
        return inertia * angular_acceleration

    @staticmethod
    def transient_power(power_kw, startup_factor=2.2):
        return power_kw * startup_factor