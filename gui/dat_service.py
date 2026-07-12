from __future__ import annotations

from datetime import datetime
from pathlib import Path

from mpinyin_dat import SelfStudyDat, UserPhraseDat
from .session import Session, validate_self_study_entries
from .workspace_store import file_sha256


def import_dat(path: str | Path, *, expected_kind: str | None = None) -> tuple[Session, dict[str, str]]:
    source = Path(path)
    raw = source.read_bytes()
    if raw.startswith(b"mschxudp"):
        dat = UserPhraseDat.read(source)
        kind = "user_phrase"
    else:
        dat = SelfStudyDat.read(source)
        kind = "self_study"
    if expected_kind and expected_kind != kind:
        expected_label = "自学习词库" if expected_kind == "self_study" else "自定义短语"
        actual_label = "自学习词库" if kind == "self_study" else "自定义短语"
        raise ValueError(f"所选文件实际是“{actual_label}”，请使用“导入{actual_label}”")
    return Session(list(dat.entries), kind=kind), {"source_path": str(source), "source_sha256": file_sha256(source)}


def export_dat(session: Session, output: str | Path) -> Path:
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    if session.kind == "self_study":
        validate_self_study_entries(session.entries)
        generated = SelfStudyDat.create(tuple(session.entries))
        generated.write(target)
        if SelfStudyDat.read(target).entries != tuple(session.entries):
            raise ValueError("导出校验失败：自学习词库回读不一致")
    else:
        generated = UserPhraseDat.create(tuple(session.entries))
        generated.write(target)
        if UserPhraseDat.read(target).entries != tuple(session.entries):
            raise ValueError("导出校验失败：自定义短语回读不一致")
    return target


def default_export_name(kind: str) -> str:
    label = "自学习词库" if kind == "self_study" else "自定义短语"
    return f"{label}_{datetime.now():%Y%m%d_%H%M%S}.dat"
