from pathlib import Path
import argparse
import pandas as pd

from netintel_ai.config import Settings
from netintel_ai.models import fit_models, validate_labeled_dataset


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("csv")
    parser.add_argument("--label", default="label")
    args = parser.parse_args()

    data = pd.read_csv(args.csv)

    baseline = data[data[args.label].astype(int) == 1].copy()

    settings = Settings()
    models = fit_models(
        baseline,
        settings.model_contamination,
    )

    result = validate_labeled_dataset(
        models,
        data,
        args.label,
    )

    print(result.to_string(index=False))


if __name__ == "__main__":
    main()
