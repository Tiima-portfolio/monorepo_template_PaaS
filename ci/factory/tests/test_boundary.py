from factory.boundary import boundary_of, check_boundary, project_of
from factory.globs import matches
from factory.policy import load_policy

policy = load_policy("boundaries")


def test_glob_double_and_single_star():
    assert matches("product/services/a/x.go", "product/**")
    assert matches("internal-tools/lint/a/b.py", "internal-tools/*/**")
    assert not matches("internal-tools/README.md", "internal-tools/*/**")
    assert matches("README.md", "README.md")
    assert not matches("docs/README.md", "README.md")


def test_each_path_maps_to_its_boundary():
    assert boundary_of("product/services/orders/main.go", policy) == "product"
    assert boundary_of("internal-tools/toolchains/go/toolchain.yaml", policy) == "internal-tool:internal-tools/toolchains"
    assert boundary_of("internal-services/sim/app.py", policy) == "internal-service:internal-services/sim"
    assert boundary_of(".github/workflows/pr.yml", policy) == "ci"
    assert boundary_of("ci/policy/risk.yaml", policy) == "ci"
    assert boundary_of("nx.json", policy) == "workspace"
    assert boundary_of("docs/plan.md", policy) == "docs"
    assert boundary_of("README.md", policy) == "docs"
    assert boundary_of("platform/runners/values.yaml", policy) == "platform"
    assert boundary_of("test-framework/contracts/x.ts", policy) == "test-framework"


def test_one_boundary_passes_even_across_product_services():
    r = check_boundary(["product/services/a/x.ts", "product/libraries/b/y.ts"], policy)
    assert r["ok"] and r["boundary"] == "product"


def test_two_tools_are_two_boundaries():
    r = check_boundary(["internal-tools/a/x", "internal-tools/b/y"], policy)
    assert not r["ok"]
    assert "Split it" in r["message"]


def test_ci_plus_product_fails_with_split_advice():
    r = check_boundary(["ci/policy/risk.yaml", "product/services/a/x.ts"], policy)
    assert not r["ok"]
    assert r["boundaries"] == ["ci", "product"]


def test_override_allows_a_cross_boundary_pr_and_flags_it():
    r = check_boundary(["ci/x", "product/y"], policy, override=True)
    assert r["ok"] and r["override"]


def test_unowned_paths_fail():
    r = check_boundary(["random.txt"], policy)
    assert not r["ok"]
    assert r["unowned"] == ["random.txt"]


def test_empty_change_passes():
    assert check_boundary([], policy)["ok"]


def test_the_project_in_pr_titles_is_the_boundary_or_its_folder():
    policy = load_policy("boundaries")
    assert project_of(boundary_of("product/services/orders/main.go", policy)) == "product"
    assert project_of(boundary_of("internal-services/buildkit/Dockerfile", policy)) == "buildkit"
    assert project_of(boundary_of("internal-tools/toolchains/go/image/Dockerfile", policy)) == "toolchains"
    assert project_of(boundary_of(".github/workflows/factory.yml", policy)) == "ci"
