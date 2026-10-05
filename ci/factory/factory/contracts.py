"""Contract coverage: every declared contract file exists, and every consumes
edge has a consumer contract test, kept in the consumer under
contracts/<provider>/ (any depth), for example
product/services/orders/contracts/catalog/catalog_contract_test.go."""

import re


def contract_problems(services) -> list[str]:
    """services: [{name, root, service, files}] where files lists the project's
    paths relative to its root."""
    problems = []
    for s in services:
        for c in s["service"].get("contract") or []:
            if c not in s["files"]:
                problems.append(f"{s['name']} declares contract {c}, which doesn't exist")
        for provider in s["service"].get("consumes") or []:
            pattern = re.compile(f"(^|/)contracts/{provider}/.+")
            if not any(pattern.search(f) for f in s["files"]):
                problems.append(f"{s['name']} consumes {provider} but has no contract test under contracts/{provider}/")
    return problems
