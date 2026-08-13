# Data Files

The CSVs are deterministic portfolio fixtures generated with seed 42. They are committed so a reviewer can inspect the evidence without running the generator.

- `raw/`: source-shaped data with controlled defects used to exercise the quality workflow.
- `processed/`: curated facts, dimensions, issue/quarantine evidence, and exact analysis outputs.
- `reference/`: stable canton and vehicle-catalog mappings.

The repository is roughly 84 MB because the quote fact is included at full scale. A production repository would normally keep large extracts in object storage, a governed database, a release asset, or Git LFS rather than ordinary Git history. The data is synthetic and contains no personal or proprietary information.
