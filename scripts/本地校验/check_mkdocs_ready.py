#!/usr/bin/env python3
"""本地自检：模拟 MkDocs 构建检查，提前发现会导致构建失败的格式问题。

用法：
    python scripts/check_mkdocs_ready.py              # 检查 zh/ en/ 下所有 .md
    python scripts/check_mkdocs_ready.py --fix        # 尝试自动修复简单问题
"""

import argparse
import re
import sys
from pathlib import Path

LANGUAGES = ["en", "zh"]
SKIP_DIRS = {"zh-old", "en-old", "attachments", "img", "images", "__pycache__", ".claude"}


def should_skip_dir(p: Path) -> bool:
    return any(part in SKIP_DIRS for part in p.parts)


def scan_files():
    files = []
    for lang in LANGUAGES:
        lang_dir = Path(lang)
        if not lang_dir.exists():
            continue
        for md_file in lang_dir.rglob("*.md"):
            if should_skip_dir(md_file):
                continue
            files.append(md_file)
    return sorted(files)


class Checker:
    def __init__(self, filepath: Path, content: str, lines: list):
        self.filepath = filepath
        self.content = content
        self.lines = lines
        self.issues = []

    def add(self, line_no: int, code: str, message: str):
        self.issues.append({"line": line_no, "code": code, "msg": message})

    def check_angle_bracket_urls(self):
        """检查 <http://xxx。后续> 这种中文标点混入 URL 的问题。"""
        # 匹配 <http(s)://...> 但中间包含中文标点
        pattern = re.compile(
            r'<(https?://[^\s<>\u3000-\u303f\uff00-\uffef]+)([\u3000-\u303f\uff00-\uffef][^>]*)>',
            re.UNICODE,
        )
        for i, line in enumerate(self.lines, 1):
            for m in pattern.finditer(line):
                bad_char = m.group(2)[0]
                self.add(i, "URL-CJK", f"URL 尖括号内包含中文标点 '{bad_char}'")

    def check_markdown_link_urls(self):
        """检查 [text](http://xxx。后续) 这种链接 URL 包含中文标点。"""
        pattern = re.compile(
            r'\[([^\]]*)\]\((https?://[^)]+)\)',
            re.UNICODE,
        )
        for i, line in enumerate(self.lines, 1):
            for m in pattern.finditer(line):
                url = m.group(2)
                if re.search(r'[\u3000-\u303f\uff00-\uffef]', url):
                    self.add(i, "LINK-CJK", f"Markdown 链接 URL 包含中文标点: {url[:50]}")

    def check_image_paths(self):
        """检查图片路径中是否有空格（容易导致找不到文件）。"""
        pattern = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
        for i, line in enumerate(self.lines, 1):
            for m in pattern.finditer(line):
                img_path = m.group(2)
                if ' ' in img_path or '\u3000' in img_path:
                    self.add(i, "IMG-SPACE", f"图片路径包含空格: {img_path}")

    def check_table_columns(self):
        """简单检查表格列数是否一致。"""
        table_lines = []
        table_start = 0
        in_table = False
        for i, line in enumerate(self.lines, 1):
            stripped = line.strip()
            if stripped.startswith('|'):
                if not in_table:
                    in_table = True
                    table_start = i
                    table_lines = []
                # 去掉首尾 | 再按 | 分割
                cols = stripped[1:-1].split('|') if stripped.startswith('|') and stripped.endswith('|') else stripped.split('|')
                cols = [c.strip() for c in cols]
                table_lines.append((i, cols))
            else:
                if in_table and table_lines:
                    # 检查这个表格
                    self._validate_table(table_start, table_lines)
                in_table = False
                table_lines = []
        if in_table and table_lines:
            self._validate_table(table_start, table_lines)

    def _validate_table(self, start_line: int, rows: list):
        if len(rows) < 2:
            return
        col_counts = [len(cols) for _, cols in rows]
        first_count = col_counts[0]
        # 跳过只有分隔符行的情况（如 |---|---|）
        for idx, (line_no, cols) in enumerate(rows):
            if len(cols) != first_count:
                self.add(line_no, "TABLE-COLS", f"表格列数不一致，表头 {first_count} 列，此行 {len(cols)} 列")

    def check_yaml_front_matter(self):
        """检查 YAML front matter 是否闭合。"""
        if self.lines and self.lines[0].strip() == '---':
            # 找第二个 ---
            found_close = False
            for i, line in enumerate(self.lines[1:], 2):
                if line.strip() == '---':
                    found_close = True
                    # 简单检查中间是否有明显错误：缺少引号闭合
                    yaml_content = '\n'.join(self.lines[1:i])
                    for j, yline in enumerate(self.lines[1:i], 2):
                        stripped = yline.strip()
                        if ':' in stripped:
                            key, val = stripped.split(':', 1)
                            val = val.strip()
                            if val.startswith('"') and not val.endswith('"'):
                                self.add(j, "YAML-QUOTE", "YAML 值中双引号未闭合")
                            if val.startswith("'") and not val.endswith("'"):
                                self.add(j, "YAML-QUOTE", "YAML 值中单引号未闭合")
                    break
            if not found_close:
                self.add(1, "YAML-CLOSE", "YAML front matter 缺少闭合的 '---'")

    def run_all(self):
        self.check_angle_bracket_urls()
        self.check_markdown_link_urls()
        self.check_image_paths()
        self.check_table_columns()
        self.check_yaml_front_matter()
        return self.issues


def try_fix(filepath: Path, issues: list) -> int:
    """尝试自动修复简单问题，返回修复数量。"""
    content = filepath.read_text(encoding='utf-8')
    lines = content.split('\n')
    fixed = 0

    # 修复 URL 尖括号中的中文标点
    pattern = re.compile(
        r'<(https?://[^\s<>\u3000-\u303f\uff00-\uffef]+)([\u3000-\u303f\uff00-\uffef][^>]*)>',
        re.UNICODE,
    )
    new_lines = []
    for line in lines:
        new_line = pattern.sub(lambda m: f'<{m.group(1)}>{m.group(2)}', line)
        if new_line != line:
            fixed += 1
        new_lines.append(new_line)

    if fixed:
        filepath.write_text('\n'.join(new_lines), encoding='utf-8')

    return fixed


def main():
    parser = argparse.ArgumentParser(description="本地 MkDocs 格式自检")
    parser.add_argument("--fix", action="store_true", help="尝试自动修复简单问题")
    args = parser.parse_args()

    files = scan_files()
    if not files:
        print("未找到需要检查的 .md 文件")
        sys.exit(0)

    total_issues = 0
    total_files_with_issues = 0
    total_fixed = 0

    for md_file in files:
        content = md_file.read_text(encoding='utf-8')
        lines = content.split('\n')
        checker = Checker(md_file, content, lines)
        issues = checker.run_all()

        if issues:
            # 区分错误（会阻塞）和警告（仅提示）
            errors = [i for i in issues if not i['code'].startswith('TABLE-')]
            warnings = [i for i in issues if i['code'].startswith('TABLE-')]

            if errors:
                total_files_with_issues += 1
                total_issues += len(errors)
                print(f"\n[FAIL] {md_file}")
                for issue in errors:
                    print(f"  Line {issue['line']:4d}  [{issue['code']}]  {issue['msg']}")

                if args.fix:
                    fixed = try_fix(md_file, errors)
                    if fixed:
                        total_fixed += fixed
                        print(f"  [FIXED] 自动修复了 {fixed} 处问题")

            if warnings:
                print(f"\n[WARN] {md_file}  ({len(warnings)} 个表格格式建议)")
                for issue in warnings:
                    print(f"  Line {issue['line']:4d}  [{issue['code']}]  {issue['msg']}")

    print(f"\n{'='*60}")
    print(f"检查完成：共 {len(files)} 个文件")
    if total_issues == 0:
        print("未发现阻塞性格式问题")
        if total_files_with_issues == 0:
            sys.exit(0)
    else:
        print(f"阻塞错误：{total_files_with_issues} 个文件，{total_issues} 处")
        if args.fix and total_fixed:
            print(f"自动修复：{total_fixed} 处")
        print("\n建议修复后再提交，避免 MkDocs 构建失败。")
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())
