import pytest

from tools.filesystem import cleanup_run, get_run_dir, list_run_files, new_run_id, write_text_file


@pytest.fixture
def run_id():
    rid = new_run_id()
    yield rid
    cleanup_run(rid)


def test_write_and_list_text_file(run_id):
    write_text_file(run_id, "notes/hello.txt", "hello world")
    files = list_run_files(run_id)
    assert len(files) == 1
    assert files[0].name == "hello.txt"
    assert files[0].read_text() == "hello world"


def test_write_text_file_refuses_path_traversal(run_id):
    with pytest.raises(ValueError):
        write_text_file(run_id, "../../etc/passwd", "malicious")


def test_get_run_dir_rejects_path_traversal_run_id():
    with pytest.raises(ValueError, match="Invalid run_id"):
        get_run_dir("../../etc")


def test_cleanup_run_rejects_path_traversal_run_id():
    # This is the actual gap that was fixed: cleanup_run() calls
    # shutil.rmtree() on whatever get_run_dir() resolves to, so it must
    # inherit the same validation rather than trusting the caller.
    with pytest.raises(ValueError, match="Invalid run_id"):
        cleanup_run("../../../etc")


def test_get_run_dir_rejects_empty_run_id():
    with pytest.raises(ValueError, match="Invalid run_id"):
        get_run_dir("")


def test_get_run_dir_accepts_new_run_id_output():
    # new_run_id()'s output must always pass its own validator.
    rid = new_run_id()
    d = get_run_dir(rid)
    assert d.exists()
    cleanup_run(rid)
