import io
import json
import zipfile

import pytest

from webapp.components import parse_library_zip


def create_zip_bytes(file_contents):
    """
    file_contents: dict of {filename: content}
    """
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename, content in file_contents.items():
            if isinstance(content, dict):
                content = json.dumps(content)
            zf.writestr(filename, content)

    zip_buffer.seek(0)
    return zip_buffer.getvalue()


def test_parse_zip_flattens_nested_paths():
    # Simulate a zip that contains a 'library/' folder
    test_files = {
        "library/cache.json": {"test": 1},
        "library/spotify_tracks.csv": "col1,col2\nval1,val2",
    }
    zip_bytes = create_zip_bytes(test_files)

    loaded = parse_library_zip(zip_bytes)

    # Should be flattened
    assert "cache.json" in loaded
    assert "spotify_tracks.csv" in loaded
    assert loaded["cache.json"] == {"test": 1}
    assert loaded["spotify_tracks.csv"] == "col1,col2\nval1,val2"


def test_parse_zip_skips_directories_and_hidden_files():
    test_files = {
        "library/": "",  # Directory entry
        "library/.DS_Store": "junk",
        "library/data.json": {"ok": True},
    }
    zip_bytes = create_zip_bytes(test_files)

    loaded = parse_library_zip(zip_bytes)

    assert "data.json" in loaded
    assert ".DS_Store" not in loaded
    assert "library/" not in loaded
    assert len(loaded) == 1


def test_parse_zip_blocks_unsafe_paths():
    # Traversal
    with pytest.raises(ValueError, match="unsafe file path"):
        parse_library_zip(create_zip_bytes({"../evil.json": "{}"}))

    # Absolute (Unix-style)
    with pytest.raises(ValueError, match="unsafe file path"):
        parse_library_zip(create_zip_bytes({"/etc/passwd.json": "{}"}))


def test_parse_zip_blocks_unsupported_types():
    with pytest.raises(ValueError, match="unsupported file type"):
        parse_library_zip(create_zip_bytes({"test.txt": "hello"}))


def test_parse_zip_limits_entries():
    # Create 51 files
    test_files = {f"file{i}.json": {} for i in range(51)}
    zip_bytes = create_zip_bytes(test_files)

    with pytest.raises(ValueError, match="too many files"):
        parse_library_zip(zip_bytes)
