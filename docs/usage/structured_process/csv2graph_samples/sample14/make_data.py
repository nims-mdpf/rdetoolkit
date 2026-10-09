# make_data.py
# Generate dummy CSV files for the legend_policy samples.
# data.csv: 12 increasing series / data_few.csv: 3 increasing series
from pathlib import Path

import numpy as np

BASE = Path(__file__).parent
RNG = np.random.default_rng(42)


def make_series_csv(path: Path, columns: list[str], offsets: list[float], slopes: list[float]) -> None:
    x = np.arange(11)
    header = ",".join(["x", *columns])
    lines = [header]
    for xi in x:
        values = [
            offset + slope * xi + RNG.normal(0, 0.05)
            for offset, slope in zip(offsets, slopes)
        ]
        lines.append(",".join([str(xi), *[f"{v:.1f}" for v in values]]))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    make_series_csv(
        BASE / "data.csv",
        columns=[f"series_{i:02d}" for i in range(1, 13)],
        offsets=[0.5 * i for i in range(12)],
        slopes=[0.6] * 12,
    )
    make_series_csv(
        BASE / "data_few.csv",
        columns=["series_alpha", "series_beta", "series_gamma"],
        offsets=[0.0, 1.0, 2.0],
        slopes=[0.8, 0.8, 0.8],
    )
    print("generated: data.csv, data_few.csv")
