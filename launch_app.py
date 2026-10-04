"""CML Application launcher — starts Streamlit on the correct port."""

import os
import subprocess
import sys
from pathlib import Path

port = os.environ.get("CDSW_APP_PORT", "8100")

# Copied from the startup script of github.com/odog96/rfp-intake-agent.
#
# Cloudera AI starts an Application through a PBJ/IPython kernel where __file__
# does not exist, so the project root is found by marker files, without __file__
# and without importing anything from the project.
#
# The path must not be hardcoded either: a project deployed from
# .project-metadata.yaml puts the repository in /home/cdsw itself, while a manual
# clone puts it in a subfolder.
_MARKERS = ("jev/client.py", "data/questions.json")


def _find_project_root() -> Path:
    home = Path("/home/cdsw")
    candidates = [Path.cwd(), *Path.cwd().parents, home]
    if home.is_dir():
        candidates += sorted(child for child in home.iterdir() if child.is_dir())
    for candidate in candidates:
        if all((candidate / marker).is_file() for marker in _MARKERS):
            return candidate
    raise SystemExit(
        f"Could not find the project root: no directory containing "
        f"{' and '.join(_MARKERS)} under {Path.cwd()} or {home}."
    )


project_root = _find_project_root()

app_path = project_root / "app" / "app.py"
if not app_path.is_file():
    # Fail here with the path, rather than letting Streamlit start and serve an
    # error page the Application's own log will not explain.
    raise SystemExit(f"{app_path} is not a file.")

# Streamlit inherits this process's working directory; the page reads data/ and
# results/ relative to the project. app.py sets this again for safety when it is
# launched some other way.
os.chdir(project_root)

# The page imports `jev` and `app` at module level. Putting the project root on
# the child's PYTHONPATH makes those imports work on any runtime.
environment = dict(os.environ)
source_dir = str(project_root)
existing_path = environment.get("PYTHONPATH")
environment["PYTHONPATH"] = (
    f"{source_dir}{os.pathsep}{existing_path}" if existing_path else source_dir
)

subprocess.run(
    [
        sys.executable, "-m", "streamlit", "run",
        str(app_path),
        f"--server.port={port}",
        "--server.address=127.0.0.1",
        "--server.headless=true",
        "--browser.serverAddress=0.0.0.0",
        "--browser.gatherUsageStats=false",
    ],
    check=True,
    env=environment,
)
