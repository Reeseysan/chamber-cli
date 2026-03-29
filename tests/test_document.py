import os
import tempfile
import pytest

from chamber.document import load_document, load_from_stdin, DocumentError, MAX_FILE_SIZE, MAX_WORD_COUNT


def test_load_text_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("Hello world, this is a test document.")
        f.flush()
        result = load_document(f.name)
    os.unlink(f.name)
    assert "Hello world" in result
    assert "[DOCUMENT:" in result


def test_load_markdown_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("# Title\n\nSome content here.")
        f.flush()
        result = load_document(f.name)
    os.unlink(f.name)
    assert "Title" in result


def test_load_csv_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("name,age\nAlice,30\nBob,25")
        f.flush()
        result = load_document(f.name)
    os.unlink(f.name)
    assert "Alice" in result


def test_file_too_large():
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".txt", delete=False) as f:
        f.write(b"x" * (MAX_FILE_SIZE + 1))
        f.flush()
        with pytest.raises(DocumentError, match="exceeds"):
            load_document(f.name)
    os.unlink(f.name)


def test_word_count_truncation():
    words = " ".join(["word"] * (MAX_WORD_COUNT + 100))
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(words)
        f.flush()
        result = load_document(f.name)
    os.unlink(f.name)
    assert "truncated" in result.lower() or len(result.split()) <= MAX_WORD_COUNT + 50


def test_unsupported_format_without_deps():
    with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as f:
        f.write(b"data")
        f.flush()
        with pytest.raises(DocumentError, match="Unsupported"):
            load_document(f.name)
    os.unlink(f.name)


def test_file_not_found():
    with pytest.raises(DocumentError, match="not found"):
        load_document("/nonexistent/path/file.txt")


def test_load_from_stdin_with_content():
    import io
    content = "This is piped content for analysis."
    result = load_from_stdin(io.StringIO(content))
    assert "piped content" in result
    assert "[DOCUMENT: stdin]" in result


def test_document_header_contains_filename():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("content")
        f.flush()
        result = load_document(f.name)
    os.unlink(f.name)
    assert os.path.basename(f.name) in result
