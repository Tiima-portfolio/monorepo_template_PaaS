"""GitLab adapter: an interface stub.

The factory core is written against `SCM`, so a GitLab deployment needs only
this class, not a rewrite of risk, boundaries, evidence, agent trust,
admission or capacity logic. Every method fails loudly until implemented.
The mapping:

| SCM                  | GitLab                                                              |
| -------------------- | ------------------------------------------------------------------- |
| get_change           | GET /projects/:id/merge_requests/:iid                               |
| get_changed_files    | GET .../merge_requests/:iid/changes (new_path and old_path)         |
| get_approvals        | GET .../merge_requests/:iid/approvals (approved_by)                 |
| get_run              | GET /projects/:id/pipelines/:pipeline_id (ref/sha, created_at)       |
| get_job_results      | GET /projects/:id/pipelines/:pipeline_id/jobs (status)              |
| publish_decision     | notes on the merge request, found by the marker (or a status check) |
| enqueue_change       | POST .../merge_requests/:iid/merge with merge_when_pipeline_succeeds, or add to a merge train |
| list_open_changes    | GET /projects/:id/merge_requests?state=opened                       |
| list_merged_changes  | GET /projects/:id/merge_requests?state=merged&updated_after=        |
| list_issues          | GET /projects/:id/issues?labels=                                    |
| list_pipeline_runs   | GET /projects/:id/pipelines?updated_after= (status)                 |
| list_queue_state     | merge requests plus GET /projects/:id/merge_trains                  |
| change_for_commit    | GET /projects/:id/repository/commits/:sha/merge_requests            |
| download_evidence    | the pipeline's job artifacts (evidence bundle)                      |
| open_change          | POST /projects/:id/merge_requests                                   |

Executors differ too: GitLab runners replace the GitHub Actions runner pools
(platform/runners), and the workflows in .github/workflows become a
.gitlab-ci.yml that calls the same `run.py` commands.
"""

from .base import SCM


class GitLabAdapter(SCM):
    def __init__(self, project: str | None = None):
        self.project = project

    def _todo(self, what):
        raise NotImplementedError(f"GitLabAdapter.{what} is not implemented yet; see the mapping in this module's docstring")


def _stub(name):
    def method(self, *args, **kwargs):
        self._todo(name)
    method.__name__ = name
    return method


for _name in SCM.__abstractmethods__:
    setattr(GitLabAdapter, _name, _stub(_name))
GitLabAdapter.__abstractmethods__ = frozenset()
