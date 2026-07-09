"""Download PTB-XL from PhysioNet.

Default mode downloads metadata plus 100 Hz records only.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import wfdb


DATABASE = "ptb-xl"
METADATA_FILES = [
    "ptbxl_database.csv",
    "scp_statements.csv",
    "LICENSE.txt",
    "RECORDS",
    "SHA256SUMS.txt",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("data/ptb-xl"))
    parser.add_argument("--sampling", choices=["100", "500", "all"], default="100")
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)

    print("Downloading PTB-XL metadata...")
    wfdb.dl_files(DATABASE, dl_dir=str(args.output), files=METADATA_FILES)

    if args.sampling == "all":
        print("Downloading full PTB-XL database...")
        wfdb.dl_database(DATABASE, dl_dir=str(args.output))
        return

    suffix = "_lr" if args.sampling == "100" else "_hr"
    records = wfdb.get_record_list(DATABASE)
    selected = [record for record in records if record.endswith(suffix)]
    print(f"Downloading {len(selected)} {args.sampling} Hz records...")
    wfdb.dl_database(DATABASE, dl_dir=str(args.output), records=selected)
    print(f"Done: {args.output}")


if __name__ == "__main__":
    main()

