from __future__ import annotations

from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gui.dat_service import export_dat, import_dat
from gui.workspace_store import file_sha256
from mpinyin_dat import Entry, SelfStudyDat, UserPhraseDat


def test_rejects_wrong_expected_dictionary_type() -> None:
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "user_phrase.dat"
        UserPhraseDat.create((Entry("测试", ("ce", "shi"), 1),)).write(source)
        try:
            import_dat(source, expected_kind="self_study")
        except ValueError as exc:
            assert "实际是“自定义短语”" in str(exc)
        else:
            raise AssertionError("expected type mismatch to be rejected")


def test_import_export_preserves_self_study_source() -> None:
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "self_study.dat"
        SelfStudyDat.create((Entry("测试", ("ce", "shi")),)).write(source)
        before = file_sha256(source)
        session, _ = import_dat(source)
        target = export_dat(session, Path(directory) / "new.dat")
        loaded, _ = import_dat(target)
        assert loaded.entries == session.entries
        assert file_sha256(source) == before


def test_import_export_preserves_user_phrase_source() -> None:
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "user_phrase.dat"
        UserPhraseDat.create((Entry("测试", ("ce", "shi"), 3),)).write(source)
        before = file_sha256(source)
        session, _ = import_dat(source)
        target = export_dat(session, Path(directory) / "new.dat")
        loaded, _ = import_dat(target)
        assert loaded.entries == session.entries
        assert file_sha256(source) == before
