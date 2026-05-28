from physics import DischargePhysics
            speed,
            angle
        )

        shaft_dia = StructuralStressEngine.shaft_diameter(
            moment=2500,
            torque=running_tension
        )

        bucket_thickness = StructuralStressEngine.bucket_thickness(
            bucket_load=material.bulk_density * self.bucket_volume
        )

        pulley_shell = StructuralStressEngine.pulley_shell_thickness(
            self.pulley_diameter
        )

        casing_thickness = StructuralStressEngine.casing_plate_thickness(
            self.height
        )

        inlet_velocity = ChuteFlowEngine.inlet_velocity(
            self.capacity_tph,
            material.bulk_density,
            self.inlet_area
        )

        chute_angle = ChuteFlowEngine.chute_angle(material)

        blockage = ChuteFlowEngine.blockage_risk(
            material,
            chute_angle
        )

        backlegging = DischargePhysics.backlegging_check(
            trajectory,
            return_leg_x=2.5
        )

        print("\n===== BUCKET ELEVATOR ENGINEERING RESULTS =====")

        print(f"Belt Speed: {speed:.2f} m/s")
        print(f"Capacity: {capacity:.1f} TPH")
        print(f"Fill Efficiency: {fill_efficiency:.2f}")

        print(f"Power: {power_kw:.2f} kW")
        print(f"Running Tension: {running_tension:.1f} N")
        print(f"Startup Tension: {startup_tension:.1f} N")
        print(f"Shock Tension: {shock_tension:.1f} N")

        print(f"Release Angle: {angle:.2f} rad")
        print(f"Trajectory Points: {len(trajectory)}")

        print(f"Shaft Diameter: {shaft_dia * 1000:.1f} mm")
        print(f"Bucket Thickness: {bucket_thickness:.2f} mm")
        print(f"Pulley Shell Thickness: {pulley_shell * 1000:.1f} mm")
        print(f"Casing Thickness: {casing_thickness * 1000:.1f} mm")

        print(f"Inlet Velocity: {inlet_velocity:.2f} m/s")
        print(f"Chute Angle: {chute_angle:.1f} deg")
        print(f"Blockage Risk: {blockage}")

        print(f"Backlegging Risk: {backlegging}")

        return {
            "capacity": capacity,
            "power": power_kw,
            "startup_tension": startup_tension,
            "trajectory": trajectory,
            "stream_envelope": stream
        }


if __name__ == "__main__":

    engine = BucketElevatorEngine()

    results = engine.run()