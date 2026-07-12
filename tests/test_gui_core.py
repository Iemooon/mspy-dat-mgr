from __future__ import annotations

from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gui.session import MAX_HISTORY, Session, generate_codes, generate_pinyin, generate_self_study_codes, parse_paste, validate_self_study_entries
from gui.workspace_store import load_workspace, save_workspace
from mpinyin_dat import Entry


def test_paste_precheck() -> None:
    result = parse_paste("张三\tzhang san\n张三\tzhang san\n坏\n李四\tli si\t300", is_self_study=True)
    assert [e.word for e in result.valid] == ["张三"]
    assert result.duplicates == ("张三",)
    assert len(result.errors) == 2


def test_self_study_auto_coding_normalizes_v_to_supported_u() -> None:
    assert generate_self_study_codes("经营策略") == ("jing", "ying", "ce", "lue")
    assert generate_self_study_codes("略高于") == ("lue", "gao", "yu")


def test_self_study_paste_normalizes_manual_lve() -> None:
    result = parse_paste("经营策略\tjing ying ce lve\n略高于\tlve gao yu", is_self_study=True)
    assert [(entry.word, entry.codes) for entry in result.valid] == [
        ("经营策略", ("jing", "ying", "ce", "lue")),
        ("略高于", ("lue", "gao", "yu")),
    ]
    assert not result.errors


def test_self_study_paste_rejects_unsupported_pinyin() -> None:
    result = parse_paste("测试\tce v\n测试\tce shi", is_self_study=True)
    assert [entry.word for entry in result.valid] == ["测试"]
    assert result.errors == ("第 1 行：词条“测试”：微软拼音不支持的拼音音节：v",)


def test_self_study_export_validation_identifies_entry_and_code() -> None:
    try:
        validate_self_study_entries([Entry("测试", ("ce", "shi")), Entry("测试二", ("ce", "shi", "v"))])
    except Exception as exc:
        assert str(exc) == "第 2 条词条“测试二”：微软拼音不支持的拼音音节：v"
    else:
        raise AssertionError("expected unsupported syllable to be rejected")


def test_paste_words_generate_pinyin() -> None:
    result = parse_paste("戴厚良\n周心怀", is_self_study=True)
    assert [(e.word, e.codes) for e in result.valid] == [
        ("戴厚良", ("dai", "hou", "liang")),
        ("周心怀", ("zhou", "xin", "huai")),
    ]


def test_paste_words_generate_pinyin_for_user_phrase() -> None:
    result = parse_paste("樊志刚", is_self_study=False)
    assert [(e.word, e.codes, e.rank) for e in result.valid] == [
        ("樊志刚", ("fan", "zhi", "gang"), 0),
    ]


def test_generate_pinyin() -> None:
    assert generate_pinyin("张三丰") == ("zhang", "san", "feng")


def test_custom_phrase_can_generate_initial_codes() -> None:
    assert generate_codes("戴厚良", style="initials") == ("d", "h", "l")
    result = parse_paste("戴厚良", is_self_study=False, code_style="initials")
    assert [(entry.word, entry.codes, entry.rank) for entry in result.valid] == [
        ("戴厚良", ("d", "h", "l"), 0),
    ]


def test_self_study_still_uses_full_pinyin_when_initials_requested() -> None:
    result = parse_paste("戴厚良", is_self_study=True, code_style="initials")
    assert [(entry.word, entry.codes) for entry in result.valid] == [
        ("戴厚良", ("dai", "hou", "liang")),
    ]


def test_quick_delete_model_is_undoable() -> None:
    session = Session([Entry("张三", ("zhang", "san")), Entry("李四", ("li", "si"))], kind="self_study")
    session.delete_indices([0])
    assert [entry.word for entry in session.entries] == ["李四"]
    assert session.undo()
    assert [entry.word for entry in session.entries] == ["张三", "李四"]


def test_deduplicate_is_undoable() -> None:
    session = Session([Entry("张三", ("zhang", "san")), Entry("张三", ("zhang", "san")), Entry("李四", ("li", "si"))], kind="self_study")
    assert session.deduplicate() == 1
    assert [e.word for e in session.entries] == ["张三", "李四"]
    assert session.undo()
    assert [e.word for e in session.entries] == ["张三", "张三", "李四"]


def test_session_undo_redo_and_limit() -> None:
    session = Session([Entry("张三", ("zhang", "san"))], kind="self_study")
    session.add([Entry("李四", ("li", "si"))])
    session.update(0, Entry("张三丰", ("zhang", "san", "feng")))
    session.delete_indices([1])
    assert [e.word for e in session.entries] == ["张三丰"]
    assert session.undo() and [e.word for e in session.entries] == ["张三丰", "李四"]
    assert session.undo() and [e.word for e in session.entries] == ["张三", "李四"]
    assert session.redo() and [e.word for e in session.entries] == ["张三丰", "李四"]
    for index in range(MAX_HISTORY + 5):
        session.add([Entry(f"测试{index}", ("ce", "shi", "a"))])
    assert len(session._undo) == MAX_HISTORY


def test_workspace_roundtrip() -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "current.json"
        session = Session([Entry("王五", ("wang", "wu"), 1)], kind="user_phrase")
        save_workspace(path, session, source_path="source.dat", source_sha256="abc")
        loaded, metadata = load_workspace(path)
        assert loaded.entries == session.entries
        assert loaded.kind == "user_phrase"
        assert metadata["source_path"] == "source.dat"
        # A loaded cache may be immediately auto-saved without passing saved_at back in.
        save_workspace(path, loaded, **metadata)


def test_replace_entries_is_undoable() -> None:
    session = Session([Entry("王五", ("wang", "wu"))], kind="self_study")
    session.replace_entries([Entry("王五", ("w", "w"))])
    assert session.entries[0].codes == ("w", "w")
    assert session.undo()
    assert session.entries[0].codes == ("wang", "wu")


def test_user_phrase_rank_update_is_undoable() -> None:
    session = Session([Entry("王五", ("wang", "wu"), 0)], kind="user_phrase")
    session.update(0, Entry("王五", ("wang", "wu"), 99))
    assert session.entries[0].rank == 99
    assert session.undo()
    assert session.entries[0].rank == 0
