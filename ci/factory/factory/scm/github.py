"""GitHub adapter: `gh` and the REST and GraphQL APIs."""

import json
import subprocess

from .base import SCM, SCMError

QUEUE_QUERY = """query($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    pullRequests(states: OPEN, first: 100) { nodes {
      id number createdAt isInMergeQueue author { login }
      labels(first: 20) { nodes { name } }
      files(first: 100) { nodes { path } }
      commits(last: 1) { nodes { commit { checkSuites(first: 20) { nodes {
        checkRuns(first: 20, filterBy: { checkName: "factory/admission" }) { nodes { conclusion } } } } } } }
    } }
    mergeQueue(branch: "main") { entries(first: 100) { nodes { pullRequest {
      number author { login } files(first: 100) { nodes { path } } } } } }
  } }"""
ENQUEUE = "mutation($id: ID!, $jump: Boolean!) { enqueuePullRequest(input: { pullRequestId: $id, jump: $jump }) { mergeQueueEntry { position } } }"


def _out(*cmd, input=None) -> str:
    try:
        return subprocess.run(cmd, input=input, check=True, capture_output=True, text=True).stdout
    except subprocess.CalledProcessError as e:
        raise SCMError((e.stderr or e.stdout or str(e)).strip()) from e


def _gh(*args) -> str:
    return _out("gh", *args)


def _json(*args):
    return json.loads(_gh(*args) or "null")


def _stream(*args) -> list:
    """Paged `gh api --paginate --jq` output is one JSON value per page; flatten the lists."""
    decoder, text, i, out = json.JSONDecoder(), _gh(*args), 0, []
    while i < len(text):
        if text[i].isspace():
            i += 1
            continue
        value, i = decoder.raw_decode(text, i)
        out += value if isinstance(value, list) else [value]
    return out


def _labels(items):
    return [l["name"] for l in items or []]


class GitHubAdapter(SCM):
    def __init__(self, repo: str, workflow: str = "factory.yml"):
        self.repo = repo
        self.workflow = workflow

    # reading a change
    def get_change(self, number):
        p = _json("api", f"repos/{self.repo}/pulls/{number}")
        return {"id": p["node_id"], "number": p["number"], "title": p["title"], "author": (p.get("user") or {}).get("login"),
                "labels": _labels(p.get("labels")), "draft": p.get("draft", False), "head": p["head"]["sha"], "body": p.get("body") or "",
                "createdAt": p["created_at"], "mergedAt": p.get("merged_at")}

    def get_changed_files(self, number):
        return _stream("api", f"repos/{self.repo}/pulls/{number}/files", "--paginate", "--jq", "[.[].filename]")

    def get_approvals(self, number):
        return list(dict.fromkeys(_stream("api", f"repos/{self.repo}/pulls/{number}/reviews", "--paginate",
                                          "--jq", '[group_by(.user.login)[] | last | select(.state == "APPROVED") | .user.login]')))

    def get_job_results(self, run_ref):
        run_id, _, attempt = run_ref.partition("/")
        path = f"repos/{self.repo}/actions/runs/{run_id}/attempts/{attempt or 1}/jobs"
        return _json("api", path, "--jq", "[.jobs[] | {name, conclusion}]") or []

    def get_run(self, run_ref):
        return _json("api", f"repos/{self.repo}/actions/runs/{run_ref.partition('/')[0]}", "--jq", "{path, head_sha, run_started_at}")

    # deciding
    def publish_decision(self, number, body, marker):
        text = f"{marker}\n{body}"
        found = _gh("api", f"repos/{self.repo}/issues/{number}/comments", "--paginate",
                    "--jq", f'.[] | select(.body | startswith("{marker}")) | .id').split()
        if found:
            _gh("api", "-X", "PATCH", f"repos/{self.repo}/issues/comments/{found[0]}", "-f", f"body={text}")
        else:
            _gh("api", f"repos/{self.repo}/issues/{number}/comments", "-f", f"body={text}")

    def enqueue_change(self, change_id, jump=False):
        self._graphql(ENQUEUE, id=change_id, jump=jump)

    # listings
    def list_open_changes(self):
        return [self._change(p) for p in _json("pr", "list", "--repo", self.repo, "--state", "open", "--limit", "500",
                                               "--json", "id,number,title,author,labels,isDraft,headRefOid,createdAt,reviewDecision") or []]

    def list_merged_changes(self, since):
        return [self._change(p) for p in _json("pr", "list", "--repo", self.repo, "--state", "merged", "--limit", "1000",
                                               "--search", f"merged:>={since[:10]}",
                                               "--json", "id,number,title,author,labels,body,createdAt,mergedAt") or []]

    def list_issues(self, labels, state="open"):
        args = ["issue", "list", "--repo", self.repo, "--state", state, "--limit", "1000",
                "--json", "number,title,labels,createdAt,closedAt,state"]
        for label in labels:
            args += ["--label", label]
        return [{**i, "state": i["state"].lower(), "labels": _labels(i["labels"])} for i in _json(*args) or []]

    def list_pipeline_runs(self, since):
        return _json("run", "list", "--repo", self.repo, "--workflow", self.workflow, "--event", "pull_request",
                     "--created", f">={since[:10]}", "--limit", "1000", "--json", "conclusion") or []

    def list_queue_state(self):
        owner, _, name = self.repo.partition("/")
        data = self._graphql(QUEUE_QUERY, owner=owner, name=name)["data"]["repository"]
        candidates = [{
            "id": pr["id"], "number": pr["number"], "author": (pr.get("author") or {}).get("login"),
            "labels": _labels(pr["labels"]["nodes"]), "files": [f["path"] for f in pr["files"]["nodes"]],
            "readyAt": pr["createdAt"], "inQueue": pr["isInMergeQueue"], "admitted": self._admitted(pr),
        } for pr in data["pullRequests"]["nodes"]]
        queued = [{"number": e["pullRequest"]["number"], "author": (e["pullRequest"].get("author") or {}).get("login"),
                   "files": [f["path"] for f in e["pullRequest"]["files"]["nodes"]]}
                  for e in ((data.get("mergeQueue") or {}).get("entries") or {}).get("nodes") or []]
        return candidates, queued

    def change_for_commit(self, sha):
        try:
            return _json("api", f"repos/{self.repo}/commits/{sha}/pulls", "--jq",
                         "[.[] | select(.merged_at != null)] | first | {number, head: .head.sha}")
        except (SCMError, ValueError):
            return None

    def download_evidence(self, head_sha, dest):
        try:
            run_id = _gh("api", f"repos/{self.repo}/actions/workflows/{self.workflow}/runs?head_sha={head_sha}&event=pull_request&per_page=30",
                         "--jq", '[.workflow_runs[] | select(.conclusion == "success")] | first | .id').strip()
            if not run_id or run_id == "null":
                return False
            _gh("run", "download", run_id, "--repo", self.repo, "-n", "factory-evidence", "-D", dest)
            return True
        except SCMError:
            return False

    def open_change(self, branch, title, body, labels):
        args = ["pr", "create", "--repo", self.repo, "--base", "main", "--head", branch, "--title", title, "--body", body]
        for label in labels:
            args += ["--label", label]
        return _gh(*args).strip()

    def open_issue(self, title, body, labels, assignees=()):
        args = ["issue", "create", "--repo", self.repo, "--title", title, "--body", body]
        for label in labels:
            args += ["--label", label]
        for login in assignees:
            args += ["--assignee", login]
        return _gh(*args).strip()

    def label_added_by(self, number, label):
        events = _stream("api", f"repos/{self.repo}/issues/{number}/events", "--paginate",
                         "--jq", f'[.[] | select(.event == "labeled" and .label.name == "{label}") | .actor.login]')
        return events[-1] if events else None

    def is_admin(self, login):
        return _gh("api", f"repos/{self.repo}/collaborators/{login}/permission", "--jq", ".permission").strip() == "admin"

    # GitHub specifics
    @staticmethod
    def _admitted(pr) -> bool:
        commit = (pr["commits"]["nodes"] or [{}])[0].get("commit")
        return bool(commit) and any(r["conclusion"] == "SUCCESS" for s in commit["checkSuites"]["nodes"] for r in s["checkRuns"]["nodes"])

    @staticmethod
    def _change(p):
        return {**p, "author": (p.get("author") or {}).get("login"), "labels": _labels(p.get("labels")),
                "draft": p.get("isDraft", False), "head": p.get("headRefOid")}

    @staticmethod
    def _graphql(query, **variables):
        args = []
        for k, v in variables.items():
            args += ["-f" if isinstance(v, str) else "-F", f"{k}={json.dumps(v) if isinstance(v, bool) else v}"]
        return json.loads(_gh("api", "graphql", "-f", f"query={query}", *args))
