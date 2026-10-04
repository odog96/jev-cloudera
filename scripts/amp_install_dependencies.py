"""Install this project's dependencies during an AMP deployment.

Run by the first task in `.project-metadata.yaml`. Cloudera AI runs AMP scripts
with the working directory set to the project root, which is where the
repository is cloned, so the relative paths below resolve there. The check at the
top turns a wrong working directory into a clear message rather than a confusing
pip error. (Pattern from github.com/odog96/rfp-intake-agent.)
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path.cwd()
REQUIRED_MARKERS = (Path("jev") / "client.py", Path("data") / "questions.json")


def check_working_directory() -> None:
    missing = [str(m) for m in REQUIRED_MARKERS if not (PROJECT_ROOT / m).is_file()]
    if missing:
        raise SystemExit(
            f"Not in the project root: {PROJECT_ROOT} is missing "
            f"{', '.join(missing)}. Run this script from the directory holding "
            f"jev/ and data/."
        )


def pip(*args: str) -> None:
    command = [sys.executable, "-m", "pip", "install", *args]
    print(f"$ {' '.join(command)}", flush=True)
    subprocess.run(command, check=True)


def main() -> None:
    check_working_directory()
    pip("-r", "requirements.txt")

    # Fail here rather than when the Application starts, where the only symptom
    # would be an import error in the Application's log.
    subprocess.run(
        [sys.executable, "-c", "import jev.client, openai, httpx, streamlit; print('imports OK')"],
        check=True,
    )
    print("Dependencies installed.", flush=True)


if __name__ == "__main__":
    main()
