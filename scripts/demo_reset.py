"""Put the demo database back to its starting state (works on Windows, no make needed).

    uv run python -m scripts.demo_reset

Drops the schema, recreates it and loads the demo data again, so order 10002 is `confirmed`
and the conversations tables are empty. Run it before every demo or rehearsal: the cancel
flow changes order 10002 for good. Stop the API first if it holds open connections.
"""

import subprocess
import sys

STEPS = [
    ["alembic", "downgrade", "base"],
    ["alembic", "upgrade", "head"],
    [sys.executable, "-m", "scripts.seed_database"],
]


def main() -> int:
    for step in STEPS:
        cmd = step if step[0] == sys.executable else [sys.executable, "-m", *step]
        print("->", " ".join(step if step[0] != sys.executable else step[1:]))
        if subprocess.run(cmd).returncode != 0:
            print("Reset failed: check that PostgreSQL is running and DATABASE_URL is right.")
            return 1
    print("\nDemo data is back to its starting state.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
