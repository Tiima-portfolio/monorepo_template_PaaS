from pathlib import Path

from factory.test_quality import lint_test_file

REPO = Path(__file__).resolve().parents[3]


def test_typescript():
    assert lint_test_file("a.test.ts", "test('ok', () => { assert.equal(1, 1); });\n") == []
    assert "no assertion" in lint_test_file("a.test.ts", "test('empty', () => { run(); });\n")[0]
    assert "skipped" in lint_test_file("a.test.ts", "test.skip('later', () => { assert.ok(1); });\n")[0]


def test_go():
    assert lint_test_file("a_test.go", 'func TestA(t *testing.T) {\n\tif x { t.Fatalf("x") }\n}\n') == []
    assert "no assertion" in lint_test_file("a_test.go", "func TestB(t *testing.T) {\n\tdo()\n}\n")[0]
    assert "skipped" in lint_test_file("a_test.go", 'func TestC(t *testing.T) {\n\tt.Skip("x")\n}\n')[0]


def test_python():
    assert lint_test_file("tests/test_a.py", "def test_a():\n    assert f() == 1\n") == []
    assert "no assertion" in lint_test_file("tests/test_a.py", "def test_b():\n    f()\n")[0]
    assert "skip" in ",".join(lint_test_file("tests/test_a.py", "@pytest.mark.skip\ndef test_c():\n    assert 1\n"))


def test_rust():
    assert lint_test_file("src/main.rs", "#[test]\nfn a() { assert_eq!(1, 1); }\n") == []
    assert "no assertion" in lint_test_file("src/main.rs", "#[test]\nfn b() { run(); }\n")[0]


def test_other_files_are_ignored():
    assert lint_test_file("src/a.ts", "test('x', () => {})") == []


def test_the_example_services_pass():
    for f in ["product/services/catalog/src/products.test.ts", "product/services/orders/main_test.go",
              "product/services/pricing/tests/test_greeting.py", "product/services/inventory/src/main.rs"]:
        assert lint_test_file(f, (REPO / f).read_text()) == [], f
