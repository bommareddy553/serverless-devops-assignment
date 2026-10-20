"""Install runtime-only dependencies and prepare build/lambda for Terraform packaging."""
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BUILD_DIR = ROOT / "build" / "lambda"
SRC_DIR = ROOT / "src"

if BUILD_DIR.exists():
    shutil.rmtree(BUILD_DIR)
BUILD_DIR.mkdir(parents=True)

subprocess.check_call([
    sys.executable, "-m", "pip", "install",
    "--disable-pip-version-check",
    "--no-compile",
    "-r", str(ROOT / "requirements-lambda.txt"),
    "-t", str(BUILD_DIR),
])

for filename in ("app.py", "telemetry.py", "__init__.py"):
    source = SRC_DIR / filename
    if source.exists():
        shutil.copy2(source, BUILD_DIR / filename)

print(f"Lambda package prepared at: {BUILD_DIR}")
