import pytest

from tools.filesystem import cleanup_run, list_run_files, new_run_id, write_text_file


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
