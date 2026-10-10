#!/usr/bin/env python3
"""Every Python file of the factory starts with the same shebang."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHEBANG = "#!/usr/bin/env python3"


def test_every_python_file_has_the_shebang():
    files = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "*.py"],
                           cwd=ROOT, check=True, capture_output=True, text=True).stdout.split()
    assert files
    missing = [f for f in files if (ROOT / f).read_text().split("\n", 1)[0] != SHEBANG]
    assert not missing, f"add {SHEBANG} as the first line of: {', '.join(missing)}"


def test_run_py_is_executable():
    assert (ROOT / "run.py").stat().st_mode & 0o111
