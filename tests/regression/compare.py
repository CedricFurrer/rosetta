"""Run workflow.py with the old (v1) and the new API on the same data and compare the results.

    python compare.py --data ../../data --old-package <folder containing the v1 package as 'rosetta_v1'>

To get the v1 package from git:

    git archive 8a88344 src/rosetta | tar -x -C /tmp/v1 && mv /tmp/v1/src/rosetta /tmp/v1/rosetta_v1
"""

import argparse
import json
import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).parent


def run(api: str, data: pathlib.Path, out: pathlib.Path, old_package: pathlib.Path | None, log: pathlib.Path) -> None:
    env = dict(os.environ)
    if api == "old":
        env["PYTHONPATH"] = str(old_package) + os.pathsep + env.get("PYTHONPATH", "")
    with open(log, "w") as logfile:
        proc = subprocess.run([sys.executable, "-W", "ignore", str(HERE / "workflow.py"), "--api", api,
                               "--data", str(data), "--out", str(out)],
                              env=env, stdout=logfile, stderr=subprocess.STDOUT)
    if proc.returncode != 0:
        raise SystemExit("The '{}' run failed, see {}".format(api, log))


def first_difference(a, b, path: str = "") -> str | None:
    if type(a) is not type(b):
        return "{}: type {} != {}".format(path, type(a).__name__, type(b).__name__)
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a:
                return "{}/{}: only in new".format(path, k)
            if k not in b:
                return "{}/{}: only in old".format(path, k)
            diff = first_difference(a[k], b[k], "{}/{}".format(path, k))
            if diff:
                return diff
        return None
    if isinstance(a, list):
        if len(a) != len(b):
            return "{}: length {} != {}".format(path, len(a), len(b))
        for i, (x, y) in enumerate(zip(a, b)):
            diff = first_difference(x, y, "{}[{}]".format(path, i))
            if diff:
                return diff
        return None
    return None if a == b else "{}: {!r} != {!r}".format(path, a, b)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=pathlib.Path, required=True)
    parser.add_argument("--old-package", type=pathlib.Path, required=True)
    parser.add_argument("--workdir", type=pathlib.Path, default=pathlib.Path.cwd())
    args = parser.parse_args()
    args.workdir.mkdir(parents=True, exist_ok=True)

    results = {}
    for api in ("old", "new"):
        out = args.workdir / "{}.json".format(api)
        print("Running {} API ...".format(api), flush=True)
        run(api, args.data.resolve(), out, args.old_package.resolve(), args.workdir / "{}.log".format(api))
        results[api] = json.loads(out.read_text())

    old, new = results["old"], results["new"]
    sections = sorted((set(old) | set(new)) - {"api"})
    failed = False
    for section in sections:
        if section not in old or section not in new:
            print("DIFF  {:45s} only in {}".format(section, "new" if section not in old else "old"))
            failed = True
            continue
        diff = first_difference(old[section], new[section], section)
        size = len(old[section]) if isinstance(old[section], (list, dict)) else 1
        if diff:
            failed = True
            print("DIFF  {:45s} ({} items)\n      first difference: {}".format(section, size, diff[:500]))
        else:
            print("SAME  {:45s} ({} items)".format(section, size))
    print("\nRESULT:", "differences found" if failed else "identical")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
