"""Points container builds at the shared BuildKit service
(internal-services/buildkit) by setting the FACTORY_BUILDKIT_* variables the
container toolchain reads. Run by .github/actions/buildkit-service. Without an
address it does nothing, so builds use local BuildKit.

Env: BUILDKIT_ADDR, BUILDKIT_TLS (a base64 tar.gz of ca.crt, tls.crt and
tls.key), BUILDKIT_CACHE_REF, BUILDKIT_CACHE_WRITE ("true" on main only),
RUNNER_TEMP. Writes to GITHUB_ENV.
"""

import base64
import io
import os
import tarfile
import tempfile
from pathlib import Path

from .common import env, set_env


def unpack_tls(tls: str, dest: Path) -> None:
    """Unpacks the client certificate readable by the runner user only; the
    caller deletes it when the job ends."""
    dest.mkdir(mode=0o700, parents=True, exist_ok=True)
    dest.chmod(0o700)
    with tarfile.open(fileobj=io.BytesIO(base64.b64decode(tls)), mode="r:gz") as tar:
        tar.extractall(dest, filter="data")
    for root, dirs, files in os.walk(dest):
        for d in dirs:
            os.chmod(os.path.join(root, d), 0o700)
        for f in files:
            os.chmod(os.path.join(root, f), 0o600)


def main(argv):
    addr = env.get("BUILDKIT_ADDR")
    if not addr:
        return 0
    values = {"FACTORY_BUILDKIT_ADDR": addr}
    if env.get("BUILDKIT_TLS"):
        dest = Path(env.get("RUNNER_TEMP") or tempfile.gettempdir()) / "buildkit-tls"
        unpack_tls(env["BUILDKIT_TLS"], dest)
        values["FACTORY_BUILDKIT_TLS_DIR"] = str(dest)
    if env.get("BUILDKIT_CACHE_REF"):
        values["FACTORY_BUILDKIT_CACHE_REF"] = env["BUILDKIT_CACHE_REF"]
        values["FACTORY_BUILDKIT_CACHE_WRITE"] = env.get("BUILDKIT_CACHE_WRITE") or "false"
    set_env(**values)
    print(f"Container builds use the BuildKit service at {addr}")
