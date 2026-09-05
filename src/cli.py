"""TopWallet CLI.

  python -m src.cli pipeline                     # full run (all stages)
  python -m src.cli discover                     # single stage
  python -m src.cli track-ca --ca 0x...          # track-by-CA feature
  python -m src.cli stats                        # show pipeline stats
  python -m src.cli monitor                      # real-time top-wallet monitor
  python -m src.cli scheduler                    # cron scheduler (weekly rerun)
  python -m src.cli api                          # FastAPI dashboard backend
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys

from src.utils.logger import setup_logging


async def _cmd_pipeline(args) -> int:
    from src.pipeline import ALL_STAGES, Pipeline

    overrides = {k: v for k, v in {
        "max_tokens": args.max_tokens,
        "enrich_limit": args.enrich_limit,
        "lookback_days": args.lookback_days,
    }.items() if v}
    stages = [s.strip() for s in args.stages.split(",") if s.strip() in ALL_STAGES] or ALL_STAGES
    pipe = Pipeline(overrides)
    counts = await pipe.run(stages)
    print(json.dumps(counts, indent=2, default=str))
    return 0


async def _cmd_track_ca(args) -> int:
    from src.track_by_ca import run_track_by_ca

    result = await run_track_by_ca(args.ca, top_n=args.top)
    if result is None:
        print(f"No DexScreener pair / transfers found for CA {args.ca}")
        return 1
    print(json.dumps(result, indent=2, default=str))
    return 0


async def _cmd_monitor(_args) -> int:
    from src.track.wallet_monitor import run_monitor

    await run_monitor()
    return 0


async def _cmd_scheduler(_args) -> int:
    from src.scheduler import run_scheduler

    await run_scheduler()
    return 0


def _cmd_stats(_args) -> int:
    from pathlib import Path

    from config.settings import settings

    stats_path = settings.results_dir / "stats.json"
    if not stats_path.exists():
        print("No stats yet — run `python -m src.cli pipeline` first.")
        return 1
    print(stats_path.read_text())
    latest = settings.results_dir / "top_wallets_latest.json"
    if latest.exists():
        data = json.loads(latest.read_text())
        wallets = data.get("wallets", [])
        print(f"\nTop {len(wallets)} wallets (generated {data.get('generated_at')}):")
        for w in wallets[:20]:
            m = w["metrics"]
            print(f"  #{w['rank']:>3} {w['wallet_address'][:14]}… score={w['composite_score']:<6} "
                  f"win={m['win_rate']:<6} med={m['median_return_multiple']:<8} "
                  f"tokens={m['distinct_tokens']:<3} {w['trading_style']}")
    return 0


def _cmd_api(_args) -> int:
    import uvicorn

    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=False)
    return 0


def _cmd_push(_args) -> int:
    from src.utils.github_pusher import push_results

    ok = push_results()
    print("pushed" if ok else "push failed or skipped")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="topwallet", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_pipe = sub.add_parser("pipeline", help="run pipeline stages")
    p_pipe.add_argument("--stages", default="discover,enrich,prices,analyze",
                        help="comma list from: discover,enrich,prices,analyze")
    p_pipe.add_argument("--max-tokens", type=int, default=None)
    p_pipe.add_argument("--enrich-limit", type=int, default=None)
    p_pipe.add_argument("--lookback-days", type=int, default=None)

    for stage in ("discover", "enrich", "prices", "analyze"):
        p = sub.add_parser(stage, help=f"run only the {stage} stage")
        p.set_defaults(stages=stage)

    p_tc = sub.add_parser("track-ca", help="rank smart wallets that traded a token CA")
    p_tc.add_argument("--ca", required=True, help="token contract address")
    p_tc.add_argument("--top", type=int, default=50)

    sub.add_parser("stats", help="print results/stats.json + top list")
    sub.add_parser("monitor", help="real-time monitor of top wallets")
    sub.add_parser("scheduler", help="cron scheduler for weekly pipeline runs")
    sub.add_parser("api", help="start FastAPI server on :8000")
    sub.add_parser("push", help="push results/ + PROGRESS.md to GitHub")

    args = parser.parse_args(argv)
    setup_logging()

    handlers = {
        "pipeline": _cmd_pipeline,
        "discover": _cmd_pipeline, "prices": _cmd_pipeline,
        "enrich": _cmd_pipeline, "analyze": _cmd_pipeline,
        "track-ca": _cmd_track_ca,
        "monitor": _cmd_monitor,
        "scheduler": _cmd_scheduler,
        "stats": _cmd_stats,
        "api": _cmd_api,
        "push": _cmd_push,
    }
    return asyncio.run(handlers[args.cmd](args))


if __name__ == "__main__":
    sys.exit(main())
