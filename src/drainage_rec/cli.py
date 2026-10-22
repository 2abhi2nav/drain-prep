"""Command-line interface.

    drainage-rec download [--start 1901 --end 2024 --workers 6 --keep-raw]
    drainage-rec pipeline
    drainage-rec recommend --rain-1d 120 --rain-3d 250 [--json]
"""

import argparse
import json
import logging
import sys


def _download(args) -> int:
    from .data.download import download_years
    from .data.extract import combine_years, extract_year, extracted_years
    from .utils.config import load_config

    area = load_config("study_area")
    start = args.start or area["start_year"]
    end = args.end or area["end_year"]
    todo = [y for y in range(start, end + 1) if y not in extracted_years()]
    print(f"{len(todo)} year(s) to fetch ({start}-{end}); {end - start + 1 - len(todo)} already extracted")

    def on_done(year, path):
        extract_year(year, path)
        if not args.keep_raw:
            path.unlink(missing_ok=True)
        print(f"  {year} extracted", flush=True)

    failed = download_years(todo, workers=args.workers, on_done=on_done)
    if extracted_years():
        s = combine_years()
        print(f"City series: {s.index.min().date()} .. {s.index.max().date()} ({len(s)} days)")
    if failed:
        print(f"Failed years (re-run to retry): {failed}", file=sys.stderr)
        return 1
    return 0


def _pipeline(args) -> int:
    from .pipeline import run_pipeline

    summary = run_pipeline()
    print(json.dumps(summary, indent=2, default=str))
    return 0


def _recommend(args) -> int:
    from .recommend import Recommender

    rec = Recommender.load().recommend(args.rain_1d, args.rain_3d)
    if args.json:
        print(json.dumps(rec.to_dict(), indent=2))
        return 0
    print(f"Tier: {rec.tier}")
    for k in ("rain_1d", "rain_3d"):
        a = rec.assessment[k]
        print(f"  {k}: {a['value_mm']:.1f} mm  -> {a['percentile']:.1f} pct (wet days), "
              f"return period {a['return_period']:.1f} y")
    print("Recommended actions (highest priority first):")
    for i, a in enumerate(rec.actions, 1):
        print(f"  {i}. [{a['score']:.3f}] {a['name']}")
    return 0


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser(prog="drainage-rec")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("download", help="fetch IMD data and extract the Chennai series")
    d.add_argument("--start", type=int)
    d.add_argument("--end", type=int)
    d.add_argument("--workers", type=int, default=3)
    d.add_argument("--keep-raw", action="store_true", help="keep the ~25 MB/year .grd files")
    d.set_defaults(func=_download)

    pl = sub.add_parser("pipeline", help="fit models, classify history, write processed tables")
    pl.set_defaults(func=_pipeline)

    r = sub.add_parser("recommend", help="tier + ranked actions for a day's rainfall")
    r.add_argument("--rain-1d", type=float, required=True, help="1-day rainfall, mm")
    r.add_argument("--rain-3d", type=float, required=True, help="3-day accumulated rainfall, mm")
    r.add_argument("--json", action="store_true")
    r.set_defaults(func=_recommend)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
