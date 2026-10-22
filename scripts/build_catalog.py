#!/usr/bin/env python3
"""Build the public Markdown, CSV and RIS catalog from data/catalog.json.

Uses only the Python standard library.  Run --check to detect stale generated
files without changing anything.  --root lets validation use a temporary copy.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import urlparse


FIELDS = [
    "id", "title", "authors", "year", "source", "source_type", "peer_review",
    "language", "parts", "fields", "relation", "connection", "landing_url",
    "fulltext_url", "doi", "access_status", "checked_on", "verification_scope",
    "license", "notes",
]
OPTIONAL_VALUES = {"landing_url", "doi", "notes", "license"}
PARTS = {
    "01": "ファントムブラッド", "02": "戦闘潮流",
    "03": "スターダストクルセイダース", "04": "ダイヤモンドは砕けない",
    "05": "黄金の風", "06": "ストーンオーシャン",
    "07": "スティール・ボール・ラン", "08": "ジョジョリオン",
    "09": "The JOJOLands",
}
COMMON_PARTS = {"複数部", "共通", "全部共通"}
INITIAL_IDS = {
    "jojo-001", "jojo-002", "jojo-003",
    "context-001", "context-002", "context-003",
}
RELATIONS = {"direct": "直接研究", "context": "背景資料（編集上の関連）"}
LANGUAGES = {"ja": "日本語", "en": "英語", "pt": "ポルトガル語", "es": "スペイン語", "fr": "フランス語"}


def tokens(value: str) -> list[str]:
    return [item.strip() for item in value.split(";") if item.strip()]


def one_line(value: str) -> str:
    return " ".join(value.split())


def md(value: str) -> str:
    value = one_line(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    for character in ("\\", "|", "[", "]", "*", "_", "`"):
        value = value.replace(character, "\\" + character)
    return value


def link(label: str, url: str) -> str:
    return f"[{md(label)}](<{url}>)"


def explicit_parts(record: dict[str, str]) -> list[str]:
    return [part for part in tokens(record["parts"]) if part in PARTS]


def part_label(record: dict[str, str]) -> str:
    return "・".join(f"第{int(p)}部" if p in PARTS else p for p in tokens(record["parts"]))


def author_label(record: dict[str, str]) -> str:
    authors = tokens(record["authors"])
    if len(authors) > 6:
        return "・".join(authors[:3]) + f" ほか（計{len(authors)}名。全著者はCSV・RISに収録）"
    return "・".join(authors)


def load_records(path: Path) -> list[dict[str, str]]:
    records = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(records, list) or not records:
        raise ValueError("catalog.json must be a nonempty array")
    seen: set[str] = set()
    for index, record in enumerate(records, 1):
        if not isinstance(record, dict):
            raise ValueError(f"record {index}: expected an object")
        missing = set(FIELDS) - record.keys()
        if missing:
            raise ValueError(f"record {index}: missing fields {sorted(missing)}")
        for field, value in record.items():
            if not isinstance(value, str):
                raise ValueError(f"record {index}: {field} must be a string")
            if field in FIELDS and field not in OPTIONAL_VALUES and not value.strip():
                raise ValueError(f"record {index}: empty required field {field}")
            if any(ord(ch) < 32 and ch not in "\n\r\t" for ch in value):
                raise ValueError(f"record {index}: control character in {field}")
        identifier = record["id"]
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", identifier):
            raise ValueError(f"record {index}: invalid ID {identifier!r}")
        if identifier in seen:
            raise ValueError(f"duplicate ID: {identifier}")
        seen.add(identifier)
        if record["relation"] not in RELATIONS:
            raise ValueError(f"{identifier}: relation must be direct or context")
        listed_parts = tokens(record["parts"])
        if not listed_parts or set(listed_parts) - (set(PARTS) | COMMON_PARTS):
            raise ValueError(f"{identifier}: invalid parts {record['parts']!r}")
        if len(listed_parts) != len(set(listed_parts)):
            raise ValueError(f"{identifier}: duplicate part tags")
        if not tokens(record["authors"]) or not tokens(record["fields"]):
            raise ValueError(f"{identifier}: empty authors or subject tags")
        for field in ("landing_url", "fulltext_url"):
            value = record[field]
            if not value:
                continue
            parsed = urlparse(value)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc or any(c.isspace() for c in value):
                raise ValueError(f"{identifier}: invalid {field}")
            if any(c in value for c in "<>\"\n\r"):
                raise ValueError(f"{identifier}: unsafe character in {field}")
        if record["doi"] and not re.fullmatch(r"10\.\d{4,9}/\S+", record["doi"]):
            raise ValueError(f"{identifier}: DOI must be an identifier, not a URL")
        try:
            date.fromisoformat(record["checked_on"])
        except ValueError as exc:
            raise ValueError(f"{identifier}: checked_on must be YYYY-MM-DD") from exc
    return records


def has_note(root: Path, record: dict[str, str]) -> bool:
    return (root / "notes" / f"{record['id']}.md").is_file()


def record_block(root: Path, record: dict[str, str], prefix: str = "") -> str:
    r = record
    urls = []
    if r["landing_url"]:
        urls.append(link("書誌ページ", r["landing_url"]))
    urls.append(link("全文", r["fulltext_url"]))
    if r["doi"]:
        urls.append(link("DOI", "https://doi.org/" + r["doi"]))
    if has_note(root, r):
        urls.append(link("読書メモ", f"{prefix}notes/{r['id']}.md"))
    text = [
        f'<a id="{r["id"]}"></a>',
        f"## {r['id']} — {md(r['title'])}",
        f"**{md(author_label(r))}（{md(r['year'])}）**。{md(r['source'])}。",
        f"- 関連部：{md(part_label(r))}／分野：{md('・'.join(tokens(r['fields'])))}／言語：{md(LANGUAGES.get(r['language'], r['language']))}。",
        f"- 関係：{RELATIONS[r['relation']]}。{md(r['connection'])}",
        f"- 資料種別：{md(r['source_type'])}／査読：{md(r['peer_review'])}。",
        f"- 公開状況：**{md(r['access_status'])}**。確認日：{md(r['checked_on'])}。",
        f"- リンク：{'／'.join(urls)}。",
        f"- 確認範囲：{md(r['verification_scope'])}。",
        f"- ライセンス：{md(r['license'] or '未確認')}。",
    ]
    if r["notes"]:
        text.append(f"- 注：{md(r['notes'])}")
    return "\n\n".join(text[:3]) + "\n\n" + "\n".join(text[3:]) + "\n"


def make_catalog(root: Path, records: list[dict[str, str]]) -> str:
    relations = Counter(r["relation"] for r in records)
    access = Counter(r["access_status"] for r in records)
    counts = Counter(p for r in records for p in explicit_parts(r))
    common = [r for r in records if not explicit_parts(r)]
    lines = [
        "# ジョジョ関連研究図書館 — 資料目録",
        "",
        f"収録 **{len(records)}件**（直接研究 {relations['direct']}件／背景資料 {relations['context']}件）。",
        "",
        "公開状況：" + "／".join(f"{md(status)} {count}件" for status, count in sorted(access.items())) + "。",
        "",
        "全文へのアクセス確認と、全体の精読・学術的な質の評価は別です。確認範囲を各資料に記録しています。背景資料との接続は図書館の編集上の提案であり、作者の参照元と確認したものではありません。",
        "",
        "[CSV](catalog.csv) · [Zotero用RIS](exports/jojo-library.ris) · [読書メモ](notes/)",
        "",
        "## 部別の棚",
        "",
        "一件を複数の部に登録できるため、棚の件数の合計と資料の総数は一致しない場合があります。「複数部」だけが付いた資料は共通棚に置き、各部には自動計上しません。",
        "",
        "| 棚 | 件数 | 初期目標（5件） |",
        "|---|---:|---|",
    ]
    for part, title in PARTS.items():
        status = "達成" if counts[part] >= 5 else f"あと{5 - counts[part]}件"
        lines.append(f"| [第{int(part)}部：{title}](parts/{part}.md) | {counts[part]} | {status} |")
    lines.extend([
        f"| [共通・部未指定](parts/common.md) | {len(common)} | 個別に収集 |",
        "", "## 資料一覧", "", "| ID | 資料 | 関連部 | 関係 |", "|---|---|---|---|",
    ])
    for r in records:
        lines.append(f"| {r['id']} | [{md(r['title'])}](#{r['id']}) | {md(part_label(r))} | {RELATIONS[r['relation']]} |")
    lines.extend(["", *[record_block(root, r) for r in records]])
    return "\n".join(lines).rstrip() + "\n"


def make_part(root: Path, records: list[dict[str, str]], part: str) -> str:
    if part == "common":
        title = "共通・部未指定"
        subset = [r for r in records if not explicit_parts(r)]
        explanation = "特定の部を明示していない複数部の研究を置いています。各部の件数へ自動的には加算しません。"
    else:
        title = f"第{int(part)}部 {PARTS[part]}"
        subset = [r for r in records if part in explicit_parts(r)]
        explanation = "背景資料とのつながりは編集上の提案です。作品の元ネタや作者の参照資料であるとの断定ではありません。"
    lines = [f"# {title}", "", f"収録 {len(subset)}件。[総目録へ](../CATALOG.md)", "", explanation, ""]
    if not subset:
        lines.append("この棚は収集中です。")
    lines.extend(record_block(root, r, "../") for r in subset)
    return "\n".join(lines).rstrip() + "\n"


def make_csv(records: list[dict[str, str]]) -> str:
    extras = sorted({key for r in records for key in r} - set(FIELDS))
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=FIELDS + extras, lineterminator="\n")
    writer.writeheader()
    writer.writerows(records)
    return buffer.getvalue()


def ris_type(record: dict[str, str]) -> str:
    source_type = record["source_type"].lower()
    if any(s in source_type for s in ("学位", "修士", "博士", "卒業", "学士", "優等課程論文", "学部論文", "thesis", "dissertation")):
        return "THES"
    if "百科事典" in source_type:
        return "ENCYC"
    if "学術書" in source_type:
        return "BOOK"
    if any(s in source_type for s in ("学術誌", "紀要", "論文", "journal", "article")):
        return "JOUR"
    return "GEN"


def make_ris(root: Path, records: list[dict[str, str]]) -> str:
    entries = []
    for r in records:
        fields = [("TY", ris_type(r)), ("TI", r["title"])]
        fields.extend(("AU", author) for author in tokens(r["authors"]))
        fields.extend([("PY", r["year"]), ("T2", r["source"]), ("LA", r["language"])])
        if r["doi"]:
            fields.append(("DO", r["doi"]))
        fields.append(("UR", r["landing_url"] or r["fulltext_url"]))
        tags = [f"第{int(p)}部" if p in PARTS else p for p in tokens(r["parts"])]
        tags += tokens(r["fields"])
        tags += ["直接研究" if r["relation"] == "direct" else "背景資料"]
        tags += ["読書メモあり" if has_note(root, r) else "未読"]
        fields.extend(("KW", tag) for tag in dict.fromkeys(tags))
        fields.extend([
            ("N1", f"図書館ID: {r['id']}"),
            ("N1", f"ジョジョとの関連（編集者による説明）: {r['connection']}"),
            ("N1", f"全文URL: {r['fulltext_url']}"),
            ("N1", f"公開状況: {r['access_status']} / 確認日: {r['checked_on']}"),
            ("N1", f"確認範囲: {r['verification_scope']}"),
            ("N1", f"資料種別: {r['source_type']} / 査読: {r['peer_review']}"),
            ("N1", f"ライセンス: {r['license'] or '未確認'}"),
        ])
        if r["notes"]:
            fields.append(("N1", f"注: {r['notes']}"))
        if has_note(root, r):
            fields.append(("N1", f"読書メモ: リポジトリ内 notes/{r['id']}.md"))
        # Keep full-text URLs in notes: a URL ending in /download need not be a
        # PDF, and RIS import must not misclassify HTML as a PDF attachment.
        entries.append("\n".join(f"{tag}  - {one_line(value)}" for tag, value in fields) + "\nER  -\n")
    return "\n".join(entries)


def outputs(root: Path, records: list[dict[str, str]]) -> dict[str, str]:
    generated = {"CATALOG.md": make_catalog(root, records), "catalog.csv": make_csv(records)}
    for part in (*PARTS, "common"):
        generated[f"parts/{part}.md"] = make_part(root, records, part)
    generated["exports/jojo-library.ris"] = make_ris(root, records)
    initial = [r for r in records if r["id"] in INITIAL_IDS]
    generated["exports/zotero-initial-6.ris"] = make_ris(root, initial)
    return generated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--check", action="store_true", help="verify generated files without writing")
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        records = load_records(root / "data/catalog.json")
        generated = outputs(root, records)
    except (OSError, ValueError, TypeError) as exc:
        print(f"Catalog error: {exc}", file=sys.stderr)
        return 1
    stale = []
    for name, content in generated.items():
        path = root / name
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != content:
                stale.append(name)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")
    if stale:
        print("Generated files missing or stale: " + ", ".join(stale), file=sys.stderr)
        return 1
    counts = Counter(p for r in records for p in explicit_parts(r))
    print(f"{'Checked' if args.check else 'Built'} {len(generated)} files from {len(records)} records.")
    print("Parts: " + ", ".join(f"{int(p)}={counts[p]}" for p in PARTS))
    missing_initial = sorted(INITIAL_IDS - {r["id"] for r in records})
    if missing_initial:
        print("Warning: initial-six export lacks: " + ", ".join(missing_initial), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
