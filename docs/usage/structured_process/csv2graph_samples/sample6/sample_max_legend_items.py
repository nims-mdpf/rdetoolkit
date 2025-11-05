from rdetoolkit.graph import csv2graph

if __name__ == "__main__":
    csv2graph(
        "sample6/data.csv",
        x_col=0,
        y_cols=[1, 2, 3, 4, 5],
        no_individual=True,
        max_legend_items=3,
    )
