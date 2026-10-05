from factory.mise import mise_toml


def test_versions_and_tables():
    toml = mise_toml({"go": "1.25", "rust": {"version": "1.99.0", "components": "rustfmt,clippy"}})
    assert toml == '[tools]\n"go" = "1.25"\n"rust" = { version = "1.99.0", components = "rustfmt,clippy" }\n'
