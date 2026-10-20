"""Catalog-managed local bundles; paths must stay inside the dataset root."""

import json
import pickle
from pathlib import Path

import pandas as pd
from kedro.io import AbstractDataset


class FileBundleDataset(AbstractDataset):
    def __init__(self, filepath):
        self.root = Path(filepath)

    def _save(self, data):
        self.root.mkdir(parents=True, exist_ok=True)
        inventory = []
        for name, value in data.items():
            target = (self.root / name).resolve()
            if not target.is_relative_to(self.root.resolve()):
                raise ValueError("Artifact path escapes dataset directory")
            target.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(value, pd.DataFrame):
                if target.suffix == ".parquet":
                    value.to_parquet(target, index=False)
                elif target.suffix == ".csv":
                    value.to_csv(target, index=False)
                else:
                    raise ValueError("DataFrames require .parquet or .csv")
            elif isinstance(value, bytes):
                target.write_bytes(value)
            elif isinstance(value, str):
                target.write_text(value, encoding="utf-8", newline="\n")
            elif target.suffix == ".pkl":
                target.write_bytes(pickle.dumps(value))
            else:
                target.write_text(json.dumps(value, indent=2, default=str), encoding="utf-8")
            inventory.append(name)
        (self.root / "inventory.json").write_text(json.dumps(inventory), encoding="utf-8")

    def _load(self):
        names = json.loads((self.root / "inventory.json").read_text(encoding="utf-8"))
        output = {}
        for name in names:
            target = self.root / name
            if target.suffix == ".parquet":
                value = pd.read_parquet(target)
            elif target.suffix == ".csv":
                value = pd.read_csv(target)
            elif target.suffix == ".pkl":
                value = pickle.loads(target.read_bytes())
            elif target.suffix == ".json":
                value = json.loads(target.read_text(encoding="utf-8"))
            else:
                value = target.read_bytes()
            output[name] = value
        return output

    def _describe(self):
        return {"filepath": str(self.root), "storage": "local"}


class OptionalJSONDataset(AbstractDataset):
    """Absent external physical input is explicit None, not fabricated values."""
    def __init__(self, filepath):
        self.path = Path(filepath)

    def _load(self):
        return json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else None

    def _save(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _describe(self):
        return {"filepath": str(self.path), "optional_external_input": True}
