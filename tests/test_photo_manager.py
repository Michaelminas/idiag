"""Tests for photo file management."""

import tempfile
from pathlib import Path

import pytest

from app.services.photo_manager import PhotoManager


@pytest.fixture
def pm():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield PhotoManager(base_dir=Path(tmpdir))


class TestPhotoManager:
    def test_save_and_get(self, pm):
        filename, relpath = pm.save("udid-001", b"\xff\xd8\xff", label="front")
        assert "front" in filename
        assert pm.get_path(relpath) is not None
        assert pm.get_path(relpath).read_bytes() == b"\xff\xd8\xff"

    def test_list_files(self, pm):
        pm.save("udid-001", b"a", label="front")
        pm.save("udid-001", b"b", label="back")
        files = pm.list_files("udid-001")
        assert len(files) == 2

    def test_delete(self, pm):
        _, relpath = pm.save("udid-001", b"x", label="screen")
        assert pm.delete(relpath)
        assert pm.get_path(relpath) is None

    def test_delete_all(self, pm):
        pm.save("udid-001", b"a", label="front")
        pm.save("udid-001", b"b", label="back")
        count = pm.delete_all("udid-001")
        assert count == 2
        assert pm.list_files("udid-001") == []

    def test_list_empty(self, pm):
        assert pm.list_files("nonexistent") == []
