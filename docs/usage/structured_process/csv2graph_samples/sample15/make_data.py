# make_data.py
# Generate a dummy CSV with 32 series for dense-legend samples.
# Each series is a straight line: series_i(x) = i + 0.1 * x  (x = 0..10)
from pathlib import Path

BASE = Path(__file__).parent

if __name__ == "__main__":
    columns = [f"series_{i:02d}" for i in range(1, 33)]
    lines = [",".join(["x", *columns])]
    for x in range(11):
        values = [i + 0.1 * x for i in range(1, 33)]
        lines.append(",".join([str(x), *[f"{v:.1f}" for v in values]]))
    (BASE / "data.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("generated: data.csv")
