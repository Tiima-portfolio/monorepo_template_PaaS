"""What the factory core needs from a source control platform.

The core (risk, boundaries, evidence, agent trust, admission, capacity logic)
decides; an adapter talks to the platform. The core never sees `gh`, GraphQL
or any platform's JSON: adapters return the plain dicts described here.

change     a pull request or merge request:
           {id, number, title, author, labels, draft, head, body, createdAt, mergedAt?}
issue      {number, title, labels, state ("open" or "closed"), createdAt, closedAt?}
job        {name, conclusion}   conclusion is "success", "failure", "skipped", ...
candidate  a change that may enter the merge queue:
           {id, number, author, labels, files, ready_at, in_queue, admitted}
"""

from abc import ABC, abstractmethod


class SCM(ABC):
    # --- reading a change -------------------------------------------------
    @abstractmethod
    def get_change(self, number: int) -> dict: ...

    @abstractmethod
    def get_changed_files(self, number: int) -> list[str]: ...

    @abstractmethod
    def get_approvals(self, number: int) -> list[str]:
        """Logins whose latest review approves the change."""

    @abstractmethod
    def get_job_results(self, run_ref: str) -> list[dict]:
        """What the platform says the pipeline's jobs did, not what they wrote down."""

    @abstractmethod
    def get_run(self, run_ref: str) -> dict:
        """{path, head_sha, run_started_at} of the pipeline run: which workflow file
        produced the evidence, for which commit, and when it started."""

    # --- deciding ---------------------------------------------------------
    @abstractmethod
    def publish_decision(self, number: int, body: str, marker: str) -> None:
        """Creates the change's one factory comment, or updates it in place."""

    @abstractmethod
    def enqueue_change(self, change_id: str, jump: bool = False) -> None:
        """Puts an admitted change in the merge queue (merge train); raises
        SCMError when the platform refuses it (a new push, a conflict)."""

    # --- listings the controllers and reports need -------------------------
    @abstractmethod
    def list_open_changes(self) -> list[dict]: ...

    @abstractmethod
    def list_merged_changes(self, since: str) -> list[dict]: ...

    @abstractmethod
    def list_issues(self, labels: list[str], state: str = "open") -> list[dict]: ...

    @abstractmethod
    def list_pipeline_runs(self, since: str) -> list[dict]:
        """[{conclusion}] of the factory pipeline's runs on changes since a date."""

    @abstractmethod
    def list_queue_state(self) -> tuple[list[dict], list[dict]]:
        """(candidates, queued): open changes that may enter the queue, and what is in it."""

    @abstractmethod
    def change_for_commit(self, sha: str) -> dict | None:
        """The merged change a commit on the default branch came from."""

    @abstractmethod
    def download_evidence(self, head_sha: str, dest: str) -> bool:
        """Saves the evidence bundle of a change's last successful pipeline."""

    @abstractmethod
    def open_change(self, branch: str, title: str, body: str, labels: list[str]) -> str:
        """Opens a change from a pushed branch; returns its URL."""


class SCMError(RuntimeError):
    """The platform refused or failed an operation."""
