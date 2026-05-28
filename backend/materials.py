import math


class MaterialBehaviorEngine:

    @staticmethod
    def flowability_index(material):
        cohesion_factor = max(0.1, 1 - material.cohesion)
        friction_factor = math.cos(math.radians(material.internal_friction_deg))

        return cohesion_factor * friction_factor

    @staticmethod
    def bucket_fill_efficiency(material, elevator_type):

        base = 0.85 if elevator_type == "continuous" else 0.65

        cohesion_penalty = material.cohesion * 0.1
        moisture_penalty = material.moisture * 0.05

        efficiency = base - cohesion_penalty - moisture_penalty

        return max(0.35, min(0.95, efficiency))

    @staticmethod
    def rollback_factor(material):
        return 1 + material.moisture * 0.15 + material.cohesion * 0.2

    @staticmethod
    def chute_friction(material):
        return math.tan(math.radians(material.internal_friction_deg))