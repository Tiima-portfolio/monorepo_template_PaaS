"""Checks who added the boundary override label: a factory owner's label lets
the gate accept a boundary crossing. Run by the gate job before the gate.

Env: PR, GITHUB_REPOSITORY, GH_TOKEN. Sets FACTORY_OVERRIDE_OK=true in
GITHUB_ENV when a repository admin added it (an org would use the team in
boundaries.yaml).
"""

from ..policy import load_policy
from ..scm import get_scm
from .common import env, set_env


def main(argv):
    label = load_policy("boundaries")["override"]["label"]
    scm = get_scm()
    actor = scm.label_added_by(int(env["PR"]), label)
    admin = bool(actor) and scm.is_admin(actor)
    print(f"Override label added by {actor} ({'admin' if admin else 'not an admin'})")
    if admin:
        set_env(FACTORY_OVERRIDE_OK="true")
