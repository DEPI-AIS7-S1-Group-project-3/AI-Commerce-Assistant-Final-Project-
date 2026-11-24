#!/usr/bin/env python3
"""Create the 11 review issues with your own GitHub login.

Usage (after `gh auth login`):
    python post_issues.py            # dry run, prints titles
    python post_issues.py --post     # creates the issues
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = "DEPI-AIS7-S1-Group-project-3/AI-Commerce-Assistant-Final-Project-"
issues = json.loads((Path(__file__).parent / "issues.json").read_text(encoding="utf-8"))

for i, it in enumerate(issues, 1):
    print(f"{i:>2}. {it['title']}  [{', '.join(it['labels'])}]")
    if "--post" not in sys.argv:
        continue
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(it["body"])
    cmd = ["gh", "issue", "create", "--repo", REPO, "--title", it["title"], "--body-file", f.name]
    for label in it["labels"]:
        cmd += ["--label", label]
    subprocess.run(cmd, check=True)
