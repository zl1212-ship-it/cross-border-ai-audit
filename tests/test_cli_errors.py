"""
Self-test for the CLI error messages in main.py: a missing file, an empty or
malformed CSV, and a CSV that lacks the requested outcome / group columns must
all fail with a plain one-line error naming the columns found, not a pandas
traceback.

Run: python tests/test_cli_errors.py   (or: pytest tests/)
"""

import os
import subprocess
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run_main(*argv):
    return subprocess.run([sys.executable, "main.py", *argv],
                          cwd=_ROOT, capture_output=True, text=True)


def _tmp_csv(content):
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
    f.write(content)
    f.close()
    return f.name


def _assert_clean_failure(proc, *expected_fragments):
    assert proc.returncode != 0, "bad input should exit non-zero"
    assert "Traceback" not in proc.stderr, f"leaked a traceback:\n{proc.stderr}"
    for frag in expected_fragments:
        assert frag in proc.stderr, f"expected {frag!r} in:\n{proc.stderr}"


def test_missing_file():
    proc = _run_main("--bias-csv", "no_such_file.csv")
    _assert_clean_failure(proc, "no_such_file.csv", "no such file")
    print("missing file: OK")


def test_empty_csv():
    path = _tmp_csv("")
    proc = _run_main("--bias-csv", path)
    _assert_clean_failure(proc, "file is empty")
    print("empty CSV: OK")


def test_header_only_csv():
    path = _tmp_csv("outcome,sex,race_ethnicity\n")
    proc = _run_main("--bias-csv", path)
    _assert_clean_failure(proc, "no data rows", "outcome, sex, race_ethnicity")
    print("header-only CSV: OK")


def test_malformed_csv():
    # Unbalanced quote makes the C parser raise ParserError.
    path = _tmp_csv('a,b\n1,"unclosed\n2,3\n"x,y\n')
    proc = _run_main("--bias-csv", path)
    assert proc.returncode != 0
    assert "Traceback" not in proc.stderr, f"leaked a traceback:\n{proc.stderr}"
    print("malformed CSV: OK")


def test_missing_outcome_column():
    path = _tmp_csv("decision,sex,race_ethnicity\n1,F,White\n0,M,Black\n")
    proc = _run_main("--bias-csv", path)
    _assert_clean_failure(proc, "column(s) not found: outcome",
                          "columns found: decision, sex, race_ethnicity",
                          "--outcome-col")
    print("missing outcome column: OK")


def test_missing_group_column():
    path = _tmp_csv("outcome,sex\n1,F\n0,M\n")
    proc = _run_main("--bias-csv", path)
    _assert_clean_failure(proc, "column(s) not found: race_ethnicity",
                          "columns found: outcome, sex")
    print("missing group column: OK")


def test_privacy_csv_missing_quasi_column():
    path = _tmp_csv("age,zip\n34,10001\n35,10002\n")
    proc = _run_main("--privacy-csv", path, "--quasi-cols", "age,zip,sex")
    _assert_clean_failure(proc, "column(s) not found: sex", "--quasi-cols")
    print("privacy CSV missing quasi column: OK")


def test_recommender_csv_missing_columns():
    path = _tmp_csv("item,clicks\na,10\nb,2\n")
    proc = _run_main("--recommender-csv", path)
    _assert_clean_failure(proc, "column(s) not found: item_id, exposures",
                          "--rec-item-col")
    print("recommender CSV missing columns: OK")


if __name__ == "__main__":
    test_missing_file()
    test_empty_csv()
    test_header_only_csv()
    test_malformed_csv()
    test_missing_outcome_column()
    test_missing_group_column()
    test_privacy_csv_missing_quasi_column()
    test_recommender_csv_missing_columns()
    print("\nALL TESTS PASSED")
