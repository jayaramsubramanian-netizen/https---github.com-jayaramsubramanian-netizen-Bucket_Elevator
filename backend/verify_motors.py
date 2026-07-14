"""
backend/verify_motors.py -- run BEFORE trusting the motor rewiring.
═══════════════════════════════════════════════════════════════════════════
Asserts that catalog.load_motor_sizes() (DISTINCT Pkw from the `motors` table)
reproduces the kW ladder that used to be hardcoded in calculations.py.

The old constant, for reference:

    MOTOR_SIZES = [
        0.37, 0.55, 0.75, 1.1, 1.5, 2.2, 3.0, 4.0, 5.5, 7.5,
        11, 15, 18.5, 22, 30, 37, 45, 55, 75, 90, 110, 132, 160, 200, 250, 315, 400,
    ]

WHY THIS MATTERS
────────────────
calculations.py picks the first rating AT OR ABOVE the required power. So the
failure modes are asymmetric and both bad:

  * A rung MISSING from the DB   -> the solver jumps to the next size up.
                                    An 11 kW duty silently specs a 15 kW motor.
  * A rung ADDED in the DB       -> the solver may pick a rating that was
                                    previously skipped.
  * The ladder EMPTY / unsorted  -> selection is meaningless.

None of these throw. They just quietly change the motor on the BOM, so this has
to be checked by diff, not by looking at the UI.

USAGE (from backend/):
    python verify_motors.py
"""
import sys

# The ladder as it was hardcoded, before the switch.
OLD_MOTOR_SIZES = [
    0.37, 0.55, 0.75, 1.1, 1.5, 2.2, 3.0, 4.0, 5.5, 7.5,
    11, 15, 18.5, 22, 30, 37, 45, 55, 75, 90, 110, 132, 160, 200, 250, 315, 400,
]


def main():
    try:
        from catalog import load_motor_sizes
        db = list(load_motor_sizes())
    except Exception as e:
        sys.exit(f"Could not load motor sizes from the DB via catalog.py: {e}")

    print(f"old hardcoded ladder : {len(OLD_MOTOR_SIZES)} ratings")
    print(f"DB `motors` DISTINCT Pkw : {len(db)} ratings")
    print()

    old_s, db_s = set(OLD_MOTOR_SIZES), set(db)
    missing = sorted(old_s - db_s)   # in the constant, absent from the DB
    extra   = sorted(db_s - old_s)   # in the DB, never in the constant

    if missing:
        print(f"!! {len(missing)} rating(s) in the OLD ladder but MISSING from the DB:")
        print(f"   {missing}")
        print("   -> a duty landing on one of these now jumps to the NEXT SIZE UP.")
        print("      That is an oversized motor on the BOM, with no error.\n")
    if extra:
        print(f"   {len(extra)} rating(s) in the DB that were never in the constant:")
        print(f"   {extra}")
        print("   -> these become newly selectable. Fine IF they are real motors you")
        print("      stock; check they are not seed noise.\n")

    if db != sorted(db):
        print("!! DB ladder is NOT ascending -- the 'first rating >= P' pick is broken.")

    ok = not missing and db == sorted(db)
    if not missing and not extra:
        print("Ladders are IDENTICAL.")
    print()
    if ok:
        print("CLEAN -- motor selection behaves identically (or strictly better).")
        print("The solver now reads the same motor catalogue the Components Library edits.")
    else:
        print("NOT CLEAN -- review the above before trusting motor selection.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())