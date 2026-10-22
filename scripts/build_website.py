#!/usr/bin/env python3
"""Generate static website data and a reading-note page from the library."""
from pathlib import Path
import argparse
import html
import json
import re
import shutil
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
REPO = 'https://github.com/usaginchaku/jojo-research-library'


def inline(text):
    value = html.escape(text)
    def replace_link(match):
        label, target = match.groups()
        url = html.unescape(target)
        if url == '../CATALOG.md':
            url = '../index.html'
        elif urlparse(url).scheme not in {'http', 'https'}:
            return label
        return '<a href="' + html.escape(url, quote=True) + '">' + label + '</a>'
    value = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', replace_link, value)
    value = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', value)
    value = re.sub(r'`([^`]+)`', r'<code>\1</code>', value)
    return value


def note_html(markdown):
    """Render the headings, paragraphs, lists and table used in our note."""
    markdown = re.sub(r'^---\n.*?\n---\n', '', markdown, count=1, flags=re.S)
    lines = markdown.splitlines()
    blocks, paragraph = [], []
    current_list = None
    def flush():
        if paragraph:
            blocks.append('<p>' + inline(' '.join(paragraph)) + '</p>')
            paragraph.clear()
    def close_list():
        nonlocal current_list
        if current_list:
            blocks.append('</' + current_list + '>')
            current_list = None
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            flush(); close_list(); i += 1; continue
        if line.startswith('|'):
            flush(); close_list()
            table = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                table.append([x.strip() for x in lines[i].strip().strip('|').split('|')])
                i += 1
            blocks.append('<div class="table-scroll" tabindex="0"><table>')
            for n, cells in enumerate(table):
                if all(re.fullmatch(r'[: -]+', c) for c in cells):
                    continue
                tag = 'th' if n == 0 else 'td'
                blocks.append('<tr>' + ''.join('<' + tag + '>' + inline(c) + '</' + tag + '>' for c in cells) + '</tr>')
            blocks.append('</table></div>')
            continue
        heading = re.match(r'^(#{1,6})\s+(.+)', line)
        bullet = re.match(r'^(- |\d+\. )(.+)', line)
        if heading:
            flush(); close_list()
            level = len(heading[1])
            blocks.append(f'<h{level}>' + inline(heading[2]) + f'</h{level}>')
        elif bullet:
            flush()
            kind = 'ul' if bullet[1] == '- ' else 'ol'
            if current_list != kind:
                close_list(); blocks.append('<' + kind + '>'); current_list = kind
            blocks.append('<li>' + inline(bullet[2]) + '</li>')
        else:
            close_list(); paragraph.append(line)
        i += 1
    flush(); close_list()
    return '\n'.join(blocks)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT / 'website')
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    rows = json.loads((ROOT / 'data/catalog.json').read_text(encoding='utf-8'))
    payload = json.dumps(rows, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    (out / 'data.js').write_text('window.JOJO_CATALOG = ' + payload + ';\n', encoding='utf-8')
    (out / 'exports').mkdir(exist_ok=True)
    shutil.copyfile(ROOT / 'exports/jojo-library.ris', out / 'exports/jojo-library.ris')
    body = note_html((ROOT / 'notes/jojo-001.md').read_text(encoding='utf-8'))
    document = '''<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>運命が決まっていても、希望は生まれるか｜ジョジョ関連研究図書館</title>
<meta name="description" content="第5部『眠れる奴隷』を哲学から読む、山口尚『宿命論と人生の意味』の読書メモ。">
<style>
:root{color-scheme:light;--ink:#332738;--paper:#f7f4ee;--line:#d8d1c8}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.95 system-ui,-apple-system,"Noto Sans JP",sans-serif}a{color:#65417b;text-underline-offset:4px}a:focus-visible,.table-scroll:focus-visible{outline:3px solid #92713d;outline-offset:4px}header{max-width:1100px;margin:auto;padding:20px 24px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center;gap:12px}header a{font-size:14px;min-height:44px;display:inline-flex;align-items:center}main{max-width:820px;margin:40px auto 80px;padding:0 24px}.eyebrow{font-size:12px;letter-spacing:.16em;color:#776347}h1{font-family:"Noto Serif JP","Yu Mincho",serif;font-size:clamp(1.8rem,5vw,2.7rem);line-height:1.6;margin:20px 0 28px}h2{font-size:1.25rem;margin:52px 0 20px;padding-top:12px;border-top:1px solid var(--line)}p,li{overflow-wrap:anywhere}ul,ol{padding-left:1.6em}li{margin:14px 0}.table-scroll{overflow-x:auto;margin:24px 0}table{border-collapse:collapse;min-width:620px;font-size:14px}th,td{border:1px solid var(--line);padding:14px;text-align:left;vertical-align:top}th{background:#eee8df}footer{padding:28px 24px;text-align:center;border-top:1px solid var(--line);font-size:14px}code{background:#ece5dc;padding:2px 4px}strong{font-weight:650}@media(max-width:480px){header{padding:12px 18px}main{margin-top:24px;padding:0 20px}header span{display:none}}
</style></head><body>
<header><a href="../index.html">← 図書館へ戻る</a><span>JOJO RESEARCH LIBRARY</span></header>
<main><div class="eyebrow">READING NOTE / PART 05</div>''' + body + '''</main>
<footer><a href="../index.html">資料を探す</a> · <a href="''' + REPO + '''/blob/main/notes/jojo-001.md">元の読書メモ</a></footer>
</body></html>
'''
    (out / 'notes').mkdir(exist_ok=True)
    (out / 'notes/jojo-001.html').write_text(document, encoding='utf-8')
    print(f'Generated website data for {len(rows)} records and one reading note in {out}')


if __name__ == '__main__':
    main()
