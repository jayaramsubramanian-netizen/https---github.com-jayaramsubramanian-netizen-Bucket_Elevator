"""
desktop-poc/typography_sweep.py -- apply a documented TYPE SCALE across the app.
═══════════════════════════════════════════════════════════════════════════
Replaces ad-hoc hardcoded font sizes with a single defensible scale.

THE PROBLEM THIS SOLVES
───────────────────────
470 hardcoded `font-size: Npx` declarations across 30 files, using 17 DIFFERENT
sizes (8, 8.5, 9, 9.5, 10, 10.5, 11, 11.5, 12, 12.5, 13, 14, 15, 16, 23, 28px).
93 of them are 8-9.5px -- genuinely unreadable. There is no scale, just accretion.

WHY NOT JUST SET EVERYTHING TO 16px
────────────────────────────────────
Measured with QFontMetrics (Segoe UI), going 9px -> 16px makes text 78% WIDER and
9px taller per row:
    "Bucket Spacing Gap"        90px -> 161px
    "Belt 356mm - max W=306mm"  144px -> 255px
    20-row table                400px -> 580px tall
Every fixed-width label column and table would overflow. That is a layout
redesign, not a typography sweep -- so the scale below is proportional, and the
tool VERIFIES fit rather than assuming it.

USAGE (from desktop-poc/):
    python typography_sweep.py --dry-run          # show every change, write nothing
    python typography_sweep.py --scale moderate   # apply
    python typography_sweep.py --verify           # report current size distribution
"""
from __future__ import annotations
import argparse, os, re, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_RE = re.compile(r"(font-size:\s*)([0-9]+(?:\.[0-9]+)?)(px)")

# ── The scales ───────────────────────────────────────────────────────────────
# Each maps EVERY size currently in use to a target. Keys are the current sizes.
SCALES = {
    # MODERATE: floor of 12px, proportional growth. Layouts survive with minor
    # padding tweaks. Body text ~13px, headings 15-16px. ~25% average growth.
    "moderate": {
        8: 12, 8.5: 12, 9: 12, 9.5: 12,      # unreadable -> readable floor
        10: 13, 10.5: 13,                     # small -> body
        11: 13, 11.5: 14,                     # body -> body
        12: 14, 12.5: 14,                     # -> comfortable
        13: 15, 14: 16, 15: 17, 16: 18,       # headings step up
        23: 24, 28: 30,                       # display sizes barely move
    },
    # LARGE: floor of 14px, body 15-16px. Closer to Jay's 12pt-Arial target.
    # Expect to widen sidebars/label columns and raise row heights.
    "large": {
        8: 14, 8.5: 14, 9: 14, 9.5: 14,
        10: 15, 10.5: 15,
        11: 15, 11.5: 16,
        12: 16, 12.5: 16,
        13: 17, 14: 18, 15: 19, 16: 20,
        23: 26, 28: 32,
    },
    # TARGET_16: Jay's literal request -- nothing below 16px (12pt Arial).
    # WILL require layout work: +45..78% text width, +9px row height.
    "target_16": {
        8: 16, 8.5: 16, 9: 16, 9.5: 16,
        10: 16, 10.5: 16, 11: 16, 11.5: 16, 12: 16, 12.5: 16,
        13: 17, 14: 18, 15: 19, 16: 20,
        23: 28, 28: 34,
    },
}

SKIP_FILES = {"typography_sweep.py"}


EXCLUDE_DIRS = {"__pycache__", ".git", ".venv", "venv", "site-packages",
                "node_modules", "dist", "build", ".mypy_cache", ".pytest_cache"}

def target_files():
    """Only the app's OWN files. Walking blindly picked up 10,000+ files from
    site-packages on the first run -- restrict to this tree and skip vendored
    or virtual-env directories."""
    out = []
    for root, dirs, files in os.walk(HERE):
        # Skip excluded AND ALL hidden dirs. Critical: the project root contains
        # .venv -- without this the sweep would rewrite font sizes inside
        # site-packages (the first run picked up 10,000+ vendored files).
        dirs[:] = [d for d in dirs
                   if d not in EXCLUDE_DIRS and not d.startswith(".")]
        for fn in files:
            if fn.endswith(".py") and fn not in SKIP_FILES:
                out.append(os.path.join(root, fn))
    return sorted(out)


def current_distribution(files):
    c = Counter()
    for p in files:
        try:
            src = open(p, encoding="utf-8").read()
        except (UnicodeDecodeError, OSError):
            continue
        for _pre, num, _px in FONT_RE.findall(src):
            c[float(num)] += 1
    return c


def apply_scale(files, scale, dry_run=True):
    changed_files, total = 0, 0
    for p in files:
        try:
            raw = open(p, "rb").read()
        except Exception:
            continue
        crlf = b"\r\n" in raw
        try:
            src = raw.decode("utf-8").replace("\r\n", "\n")
        except UnicodeDecodeError:
            # A non-UTF-8 file crashed the first run mid-sweep, which would have
            # left some files rewritten and others not. Skip and report instead.
            print(f"  SKIPPED (not UTF-8): {os.path.relpath(p, HERE)}")
            continue
        hits = []

        def sub(m):
            cur = float(m.group(2))
            new = scale.get(cur, scale.get(int(cur)))
            if new is None or new == cur:
                return m.group(0)
            hits.append((cur, new))
            return f"{m.group(1)}{new}{m.group(3)}"

        out = FONT_RE.sub(sub, src)
        if hits:
            changed_files += 1
            total += len(hits)
            rel = os.path.relpath(p, HERE)
            summary = Counter(hits)
            detail = ", ".join(f"{a}->{b} x{n}" for (a, b), n in sorted(summary.items()))
            print(f"  {rel:42s} {len(hits):3d}  {detail}")
            if not dry_run:
                data = out.replace("\n", "\r\n") if crlf else out
                open(p, "wb").write(data.encode("utf-8"))
    return changed_files, total


def verify_fit(scale):
    """Measure real rendered widths so overflow is a FACT, not a guess."""
    try:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QFont, QFontMetrics
    except Exception as e:
        print(f"  (PySide6 unavailable, skipping fit check: {e})")
        return
    app = QApplication.instance() or QApplication([])
    samples = [
        ("Bucket Spacing Gap", 9), ("MECHANICAL DESIGN", 10),
        ("Belt 356mm - max W=306mm", 9), ("AA 12x7 Centrifugal", 11),
    ]
    print("\n  rendered-width impact (Segoe UI):")
    for text, cur in samples:
        new = scale.get(cur, cur)
        fa, fb = QFont("Segoe UI"), QFont("Segoe UI")
        fa.setPixelSize(int(cur)); fb.setPixelSize(int(new))
        wa = QFontMetrics(fa).horizontalAdvance(text)
        wb = QFontMetrics(fb).horizontalAdvance(text)
        ha = QFontMetrics(fa).height(); hb = QFontMetrics(fb).height()
        print(f"    {cur:>4}px -> {new:>2}px  \"{text[:30]:30s}\" "
              f"{wa:4d}->{wb:4d}px (+{100*(wb-wa)//max(wa,1):2d}%)  row {ha}->{hb}px")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", default="moderate", choices=list(SCALES))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()

    files = target_files()
    dist = current_distribution(files)
    print(f"scanned {len(files)} files, {sum(dist.values())} font-size declarations")
    print(f"current sizes in use: {len(dist)} distinct\n")
    for size in sorted(dist):
        bar = "#" * min(int(dist[size] / 3), 40)
        flag = "  <-- unreadable" if size < 10 else ("  <-- small" if size < 11 else "")
        print(f"  {size:>5}px  {dist[size]:4d}  {bar}{flag}")

    if args.verify:
        return 0

    scale = SCALES[args.scale]
    print(f"\napplying scale '{args.scale}':")
    verify_fit(scale)
    print()
    n_files, n = apply_scale(files, scale, dry_run=args.dry_run)
    print(f"\n{'WOULD CHANGE' if args.dry_run else 'CHANGED'}: {n} declarations in {n_files} files")
    if args.dry_run:
        print("DRY RUN -- nothing written. Re-run without --dry-run to apply.")
    else:
        print("Applied. Launch the app and check: sidebar labels, table rows,")
        print("nav tabs, and any fixed-width column for clipping.")
    return 0


if __name__ == "__main__":
    sys.exit(main())