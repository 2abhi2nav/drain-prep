"""End-to-end: (optionally) download -> extract -> fit -> classify -> write processed tables."""

import argparse
import json
import sys

from drainage_rec.cli import main as cli_main
from drainage_rec.pipeline import run_pipeline

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--download", action="store_true", help="fetch any missing IMD years first")
    p.add_argument("--n-boot", type=int, default=500)
    args = p.parse_args()
    if args.download and cli_main(["download"]) != 0:
        sys.exit("Some years failed to download; re-run to retry.")
    print(json.dumps(run_pipeline(n_boot=args.n_boot), indent=2, default=str))
