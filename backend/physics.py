import math
from constants import GRAVITY


class DischargePhysics:

    @staticmethod
    def belt_speed(diameter, rpm):
        return math.pi * diameter * rpm / 60

    @staticmethod
    def centrifugal_release_angle(speed, radius):

        ratio = (speed ** 2) / (GRAVITY * radius)

        ratio = max(-1, min(1, ratio))

        return math.acos(ratio)

    @staticmethod
    def release_condition(speed, radius):
        return (speed ** 2) / radius

    @staticmethod
    def trajectory(speed, angle_rad, release_x=0, release_y=0, dt=0.02):

        trajectory_points = []

        vx = speed * math.cos(angle_rad)
        vy = speed * math.sin(angle_rad)

        t = 0

        while t < 5:
            x = release_x + vx * t
            y = release_y + vy * t - 0.5 * GRAVITY * t**2

            if y < 0:
                break

            trajectory_points.append((x, y))

            t += dt

        return trajectory_points

    @staticmethod
    def stream_envelope(speed, angle_rad, particle_spread=0.15):

        center = DischargePhysics.trajectory(speed, angle_rad)

        upper = []
        lower = []

        for x, y in center:
            upper.append((x, y + particle_spread))
            lower.append((x, y - particle_spread))

        return {
            "center": center,
            "upper": upper,
            "lower": lower
        }

    @staticmethod
    def backlegging_check(trajectory, return_leg_x):

        for x, y in trajectory:
            if x >= return_leg_x:
                return True

        return False