from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mpinyin_dat import Entry, SelfStudyDat, UserPhraseDat  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_self_study_parse_and_unchanged_roundtrip() -> None:
    entries = (Entry("测试", ("ce", "shi")), Entry("词库", ("ci", "ku")))
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "self_study_source.dat"
        target = Path(directory) / "self_study_unchanged.dat"
        SelfStudyDat.create(entries).write(source)
        source_hash = sha256(source)
        dat = SelfStudyDat.read(source)
        assert dat.entries == entries
        dat.write_unchanged(target)
        assert sha256(target) == source_hash
        assert SelfStudyDat.read(target).entries == entries
        assert sha256(source) == source_hash


def test_user_phrase_parse_and_unchanged_roundtrip() -> None:
    entries = (Entry("测试", ("ce", "shi"), 1), Entry("词库", ("ci", "ku"), 2))
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "user_phrase_source.dat"
        target = Path(directory) / "user_phrase_unchanged.dat"
        UserPhraseDat.create(entries).write(source)
        source_hash = sha256(source)
        dat = UserPhraseDat.read(source)
        assert dat.entries == entries
        dat.write_unchanged(target)
        assert sha256(target) == source_hash
        assert UserPhraseDat.read(target).entries == entries
        assert sha256(source) == source_hash


def test_self_study_standard_generation_semantic_roundtrip() -> None:
    entries = (Entry("测试", ("ce", "shi")),)
    with tempfile.TemporaryDirectory() as directory:
        target = Path(directory) / "self_study_generated.dat"
        SelfStudyDat.create(entries).write(target)
        assert SelfStudyDat.read(target).entries == entries


def test_user_phrase_standard_generation_semantic_roundtrip() -> None:
    entries = (Entry("测试", ("ce", "shi"), 7),)
    with tempfile.TemporaryDirectory() as directory:
        target = Path(directory) / "user_phrase_generated.dat"
        UserPhraseDat.create(entries).write(target)
        assert UserPhraseDat.read(target).entries == entries
