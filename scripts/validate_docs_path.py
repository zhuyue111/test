#!/usr/bin/env python3
"""校验 docs 文件路径到 PLM 系统（sp）。

用法：
    python scripts/validate_docs_path.py                    # 校验 git 变更的文件
    python scripts/validate_docs_path.py --file path.md     # 校验单个文件
    python scripts/validate_docs_path.py --diff             # 只校验 git 变更的文件
    python scripts/validate_docs_path.py --all              # 校验所有 docs 文件
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

import requests

CN_API_URL = "https://poweris.inhand.online/api/plm/github-verification/product/published-files"
EN_API_URL = "https://poweris.inhandnetworks.com/api/plm/github-verification/product/published-files"
CN_API_TOKEN = "1c71aef7360e40bbad8c68b2b6d5e571"
EN_API_TOKEN = "e0f3ad9badd6461f94ced4233914847a"

VALID_EXTENSIONS = {".md", ".pdf"}
DEFAULT_LANGUAGES = {"zh", "en"}


def load_config():
    config_path = Path("config.json")
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARN] 读取 config.json 失败: {e}")
    return {}


def get_notify_emails():
    config = load_config()
    emails = config.get("notify_emails", [])
    if emails:
        return emails
    try:
        cmd = ["git", "config", "user.email"]
        output = subprocess.check_output(cmd).decode("utf-8").strip()
        if output:
            return [output]
    except Exception:
        pass
    return ["unknown@inhand.com.cn"]


def get_file_size(file_path: Path) -> int:
    return file_path.stat().st_size


def _drop_lang(parts):
    if parts and parts[0] in DEFAULT_LANGUAGES:
        return parts[1:]
    return parts


def resolve_sp(filepath):
    parts = _drop_lang(Path(filepath).parts)
    return [("/".join(parts), "Datasheets")]


def get_changed_files():
    try:
        cmd = ["git", "-c", "core.quotePath=false", "diff", "--name-only", "HEAD~1", "HEAD"]
        output = subprocess.check_output(cmd).decode("utf-8")
        files = output.splitlines()
        return [f for f in files if f.startswith(("zh/", "en/")) and not f.endswith(".gitkeep")]
    except Exception as e:
        print(f"[WARN] Git 获取差异失败 (HEAD~1): {e}")
        try:
            cmd = ["git", "-c", "core.quotePath=false", "diff", "--name-only", "--cached"]
            output = subprocess.check_output(cmd).decode("utf-8")
            files = output.splitlines()
            return [f for f in files if f.startswith(("zh/", "en/")) and not f.endswith(".gitkeep")]
        except Exception as e2:
            print(f"[WARN] Git 获取缓存区差异也失败: {e2}")
            return []


def get_pr_changed_files():
    try:
        import os
        base_ref = os.environ.get("GITHUB_BASE_REF")
        head_ref = os.environ.get("GITHUB_HEAD_REF")
        if base_ref and head_ref:
            cmd = ["git", "-c", "core.quotePath=false", "diff", "--name-only", f"origin/{base_ref}", "HEAD"]
            output = subprocess.check_output(cmd).decode("utf-8")
            files = output.splitlines()
            return [f for f in files if f.startswith(("zh/", "en/")) and not f.endswith(".gitkeep")]
    except Exception as e:
        print(f"[WARN] Git 获取 PR 差异失败: {e}")
    return []


def find_all_docs_files():
    files = []
    for lang in DEFAULT_LANGUAGES:
        lang_dir = Path(lang)
        if lang_dir.exists():
            for ext in VALID_EXTENSIONS:
                files.extend([f for f in lang_dir.rglob(f"*{ext}") if f.name != ".gitkeep"])
    return [str(f) for f in files]


def _call_api(payload, api_url, api_token, emails):
    if not payload:
        return True
    emails_str = ",".join(emails)
    api_url_with_params = f"{api_url}?email={emails_str}"
    print(f"=== 校验 {len(payload)} 个路径 ===")
    print(f"API: {api_url}\n")
    for item in payload:
        print(f"  [{item['categoryName']}] {item['path']} ({item['size']} bytes)")
    print()
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }
    try:
        response = requests.post(api_url_with_params, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        print(f"响应: {result}\n")
        if isinstance(result, dict):
            if result.get("error"):
                print(f"[FAIL] API 返回错误: {result['error']}")
                return False
            if result.get("result") == [] and result.get("error"):
                print("[FAIL] 所有文件校验失败")
                return False
            if result.get("success") is False:
                print("[FAIL] API 返回校验失败")
                return False
            if "data" in result and isinstance(result["data"], list):
                failed_items = [item for item in result["data"] if not item.get("valid", True)]
                if failed_items:
                    print("[FAIL] 以下文件校验未通过:")
                    for item in failed_items:
                        print(f"  - {item.get('path', 'unknown')}: {item.get('message', '未知错误')}")
                    return False
        print("[OK] 校验成功")
        return True
    except requests.exceptions.Timeout:
        print("[FAIL] 请求超时")
        return False
    except requests.exceptions.HTTPError as e:
        print(f"[FAIL] HTTP 错误: {e}")
        return False
    except requests.exceptions.RequestException as e:
        print(f"[FAIL] 请求失败: {e}")
        return False


def validate_files(file_list):
    file_list = [f for f in file_list if Path(f).name != ".gitkeep"]
    if not file_list:
        print("[WARN] 没有需要校验的文件")
        return True

    file_list = [f for f in file_list if "/images/" not in f and "\\images\\" not in f and "/img/" not in f and "\\img\\" not in f]
    if not file_list:
        print("[INFO] 所有文件都在 images/img 目录下，跳过校验")
        return True

    zh_payload = []
    en_payload = []
    for filepath in file_list:
        file_path = Path(filepath)
        if not file_path.exists():
            print(f"[SKIP] 文件不存在: {filepath}")
            continue
        if file_path.suffix.lower() not in VALID_EXTENSIONS:
            print(f"[SKIP] 不支持的文件类型: {filepath}")
            continue
        size = get_file_size(file_path)
        for path, category in resolve_sp(filepath):
            item = {
                "path": path,
                "size": size,
                "categoryName": category,
            }
            filepath_norm = filepath.replace("\\", "/")
            if filepath_norm.startswith("zh/"):
                zh_payload.append(item)
            elif filepath_norm.startswith("en/"):
                en_payload.append(item)

    if not zh_payload and not en_payload:
        print("[WARN] 没有有效文件需要校验")
        return True

    notify_emails = get_notify_emails()
    all_ok = True
    if zh_payload:
        all_ok = _call_api(zh_payload, CN_API_URL, CN_API_TOKEN, notify_emails) and all_ok
    if en_payload:
        all_ok = _call_api(en_payload, EN_API_URL, EN_API_TOKEN, notify_emails) and all_ok
    return all_ok


def main():
    parser = argparse.ArgumentParser(description="校验 specifications 文件路径到 PLM 系统")
    parser.add_argument("--file", type=Path, nargs="+", help="指定要校验的文件路径")
    parser.add_argument("--diff", action="store_true", help="只校验 git 变更的文件")
    parser.add_argument("--all", action="store_true", help="校验所有 specifications 文件")
    args = parser.parse_args()

    if args.file:
        file_list = [str(f) for f in args.file]
    elif args.all:
        file_list = find_all_docs_files()
    elif args.diff:
        file_list = get_pr_changed_files()
        if not file_list:
            file_list = get_changed_files()
    else:
        file_list = get_pr_changed_files()
        if not file_list:
            file_list = get_changed_files()

    if not file_list:
        print("[INFO] 没有找到需要校验的文件")
        sys.exit(0)

    print(f"[INFO] 找到 {len(file_list)} 个待校验文件\n")
    success = validate_files(file_list)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
