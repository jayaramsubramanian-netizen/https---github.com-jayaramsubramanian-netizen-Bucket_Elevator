import math
from constants import STEEL_ALLOWABLE_STRESS


class StructuralStressEngine:

    @staticmethod
    def equivalent_torque(moment, torque, kb=1.5, kt=1.0):
        return math.sqrt((kb * moment)**2 + (kt * torque)**2)

    @staticmethod
    def shaft_diameter(moment, torque, allowable=STEEL_ALLOWABLE_STRESS):

        te = StructuralStressEngine.equivalent_torque(moment, torque)

        return ((16 * te) / (math.pi * allowable))**(1/3)

    @staticmethod
    def bucket_thickness(bucket_load, allowable_stress=140e6):
        return math.sqrt(bucket_load / allowable_stress) * 1000

    @staticmethod
    def pulley_shell_thickness(diameter):
        return 0.02 * diameter + 0.004

    @staticmethod
    def casing_plate_thickness(height, pressure_factor=1.5):
        return max(0.004, height * 0.00015 * pressure_factor)

    @staticmethod
    def bearing_l10(C, P):
        return (C / P)**3