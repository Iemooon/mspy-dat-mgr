from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from mpinyin_dat import Entry
from .session import Session

FORMAT_VERSION = 1


def file_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def workspace_path(root: str | Path, kind: str) -> Path:
    """Create an ASCII-only cache name from dictionary mode and timestamp."""
    if kind not in {"self_study", "user_phrase"}:
        raise ValueError("不支持的词库类型")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return Path(root) / f"{kind}_{timestamp}.json"


def save_workspace(path: str | Path, session: Session, *, source_path: str = "", source_sha256: str = "") -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "format_version": FORMAT_VERSION,
        "kind": session.kind,
        "source_path": source_path,
        "source_sha256": source_sha256,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "entries": [{"word": e.word, "codes": list(e.codes), "rank": e.rank} for e in session.entries],
    }
    temp = target.with_suffix(target.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, target)


def load_workspace(path: str | Path) -> tuple[Session, dict[str, str]]:
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取工作副本：{exc}") from exc
    if payload.get("format_version") != FORMAT_VERSION or payload.get("kind") not in {"self_study", "user_phrase"}:
        raise ValueError("工作副本版本或词库类型不受支持")
    try:
        entries = [Entry(str(e["word"]), tuple(e["codes"]), int(e.get("rank", 0))) for e in payload["entries"]]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("工作副本词条数据损坏") from exc
    # saved_at describes the loaded cache; it is not an input to save_workspace.
    metadata = {key: str(payload.get(key, "")) for key in ("source_path", "source_sha256")}
    return Session(entries, kind=payload["kind"]), metadata
