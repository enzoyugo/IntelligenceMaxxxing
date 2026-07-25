"""CLI for IM-local meta-edge research train/infer."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from intelligence_maxxxing.domain_packs.trading.meta_edge_v1.inference import (
    infer_from_observations,
    train_from_inbox,
)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="im-meta-edge-v1")
    sub = p.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("train")
    t.add_argument("--training-jsonl", required=True)
    t.add_argument("--artifact-dir", required=True)
    t.add_argument("--split-hash", required=True)
    t.add_argument("--feature-registry-hash", required=True)

    i = sub.add_parser("infer")
    i.add_argument("--observations-jsonl", required=True)
    i.add_argument("--artifact-dir", required=True)
    i.add_argument("--out-assessments-jsonl", required=True)

    args = p.parse_args(argv)
    if args.cmd == "train":
        out = train_from_inbox(
            inbox_training_jsonl=Path(args.training_jsonl),
            artifact_dir=Path(args.artifact_dir),
            split_hash=args.split_hash,
            feature_registry_hash=args.feature_registry_hash,
        )
    else:
        out = infer_from_observations(
            observations_jsonl=Path(args.observations_jsonl),
            artifact_dir=Path(args.artifact_dir),
            out_assessments_jsonl=Path(args.out_assessments_jsonl),
        )
    print(json.dumps(out, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
