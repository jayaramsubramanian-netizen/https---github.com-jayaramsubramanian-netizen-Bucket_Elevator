import math
from constants import GRAVITY


class ChuteFlowEngine:

    @staticmethod
    def inlet_velocity(capacity_tph, density, inlet_area):

        mass_flow = capacity_tph * 1000 / 3600

        volumetric_flow = mass_flow / density

        return volumetric_flow / inlet_area

    @staticmethod
    def chute_angle(material):
        return material.repose_angle_deg + 10

    @staticmethod
    def chute_residence_time(length, velocity):
        return length / velocity

    @staticmethod
    def impact_force(mass_flow_rate, velocity):
        return mass_flow_rate * velocity

    @staticmethod
    def blockage_risk(material, chute_angle_deg):

        if chute_angle_deg < material.repose_angle_deg:
            return "HIGH"

        if material.cohesion > 0.5:
            return "MEDIUM"

        return "LOW"