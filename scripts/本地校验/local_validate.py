#!/usr/bin/env python3
"""本地 PLM 文档路径统一校验工具。

支持从四个仓库（manual / qa-docs / sp / template1）的本地 zh/en 文件夹中抽取路径和分类，
调用 /github-verification/product/published-files 接口进行校验。

用法：
    python local_validate.py                        # 交互式选择项目、输入邮箱、校验本地文件
    python local_validate.py --project manual       # 指定项目，然后输入邮箱，校验本地文件
    python local_validate.py --project sp --file zh/xxx/通用/xxx.pdf
"""

import argparse
import sys
from pathlib import Path

import requests

# 正式环境
PROD_CN_URL = "https://poweris.inhand.online/api/plm/github-verification/product/published-files"
PROD_EN_URL = "https://poweris.inhandnetworks.com/api/plm/github-verification/product/published-files"
PROD_CN_TOKEN = "1c71aef7360e40bbad8c68b2b6d5e571"
PROD_EN_TOKEN = "e0f3ad9badd6461f94ced4233914847a"

# 测试环境
TEST_CN_URL = "https://cloud-dev.poweris.inhand.online/api/plm/github-verification/product/published-files"
TEST_EN_URL = "https://cloud-test.poweris.inhand.online/api/plm/github-verification/product/published-files"
TEST_CN_TOKEN = "5bfcc5c90c2c4ff485838773e9cc9c05"
TEST_EN_TOKEN = "bea3228c0e6a4bc8807f1606a4753b3b"

LANG_SET = {"en", "zh"}

MANUAL_CATEGORIES = {"develop", "device-dsa", "platform"}

SP_CATEGORIES_ZH = {"通用", "4G版", "5G版", "1G版", "Road", "Rail"}
SP_CATEGORIES_EN = {"General", "4G Version", "5G Version", "1G Version", "Road", "Rail"}
SP_ALL_CATEGORIES = SP_CATEGORIES_ZH | SP_CATEGORIES_EN


def select_env():
    print("请选择环境：")
    print("1. 正式环境 (production)")
    print("2. 测试环境 (test)")
    choice = input("请输入数字 (1-2): ").strip()
    if choice == "2":
        print("[INFO] 使用测试环境\n")
        return {
            "cn_url": TEST_CN_URL,
            "en_url": TEST_EN_URL,
            "cn_token": TEST_CN_TOKEN,
            "en_token": TEST_EN_TOKEN,
        }
    print("[INFO] 使用正式环境\n")
    return {
        "cn_url": PROD_CN_URL,
        "en_url": PROD_EN_URL,
        "cn_token": PROD_CN_TOKEN,
        "en_token": PROD_EN_TOKEN,
    }


def select_project():
    print("请选择要校验的项目类型：")
    print("1. 手册 (manual)")
    print("2. 问答 (qa-docs)")
    print("3. 规格书 (sp)")
    print("4. 方案 (template1)")
    choice = input("请输入数字 (1-4): ").strip()
    mapping = {
        "1": "manual",
        "2": "qa-docs",
        "3": "sp",
        "4": "template1",
    }
    if choice not in mapping:
        print("[FAIL] 无效选择")
        sys.exit(1)
    return mapping[choice]


def input_email():
    email = input("请输入接收校验通知的邮箱: ").strip()
    if not email:
        print("[FAIL] 邮箱不能为空")
        sys.exit(1)
    return email


def filter_files(file_list):
    """统一过滤：只保留 en/zh 下的文件，排除 .gitkeep、images 目录和图片格式文件。"""
    results = []
    for f in file_list:
        p = Path(f)
        parts = p.parts
        if not parts or parts[0] not in LANG_SET:
            continue
        if p.name == ".gitkeep":
            continue
        if "/images/" in f or "\\images\\" in f:
            continue
        if "/img/" in f or "\\img\\" in f:
            continue
        if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".svg", ".bmp", ".webp", ".ico", ".dat"}:
            continue
        results.append(f)
    return results


def get_all_files():
    """获取当前目录下 en/zh 的所有文件（排除 images、img、.gitkeep 和图片格式）。"""
    img_exts = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".bmp", ".webp", ".ico"}
    files = []
    for lang in LANG_SET:
        d = Path(lang)
        if d.exists():
            for f in d.rglob("*"):
                if f.is_file() and f.name != ".gitkeep" and "/images/" not in str(f) and "/img/" not in str(f) and f.suffix.lower() not in img_exts:
                    files.append(str(f))
    return files


TEMPLATE1_ALLOWED_SUBDIRS = {"configs", "config", "images", "img", "imgs"}


def check_template1_structure():
    """校验 template1 项目目录结构。"""
    issues = []
    for lang in LANG_SET:
        lang_dir = Path(lang)
        if not lang_dir.exists():
            continue
        for product_dir in lang_dir.iterdir():
            if product_dir.name == ".gitkeep":
                continue
            if not product_dir.is_dir():
                issues.append(f"{product_dir} 必须是产品目录")
                continue
            for solution_dir in product_dir.iterdir():
                if not solution_dir.is_dir():
                    issues.append(f"{solution_dir} 必须是方案目录")
                    continue
                for item in solution_dir.iterdir():
                    if item.is_dir():
                        if item.name not in TEMPLATE1_ALLOWED_SUBDIRS:
                            issues.append(f"{item} 不是允许的子目录（只允许 {TEMPLATE1_ALLOWED_SUBDIRS}）")
                    elif item.is_file():
                        if item.name != ".gitkeep" and item.suffix.lower() != ".md":
                            issues.append(f"{item} 不是允许的文件（只允许 .md）")
    if issues:
        print(f"[FAIL] template1 项目目录结构非法，发现 {len(issues)} 个问题：")
        for issue in issues:
            print(f"  - {issue}")
        sys.exit(1)


def check_manual_structure():
    """校验 manual 项目的 en/zh 下的一级目录是否严格为 develop / device-dsa / platform。"""
    invalid = []
    for lang in LANG_SET:
        lang_dir = Path(lang)
        if not lang_dir.exists():
            continue
        for sub in lang_dir.iterdir():
            if sub.is_dir() and sub.name not in MANUAL_CATEGORIES:
                invalid.append(str(sub))
    if invalid:
        print("[FAIL] manual 项目目录结构非法，en/zh 下只允许以下三种文件夹：")
        print("  - develop")
        print("  - device-dsa")
        print("  - platform")
        print("\n检测到非法文件夹：")
        for path in invalid:
            print(f"  - {path}")
        sys.exit(1)


def check_sp_structure():
    """校验 sp 项目的目录结构：
    - zh/en 下只能有产品目录
    - 产品目录下只能有合法的分类子目录（通用/General、4G版/4G Version 等）
    - 分类目录下只能有 .pdf、.md 文件和图片子目录
    """
    issues = []
    for lang in LANG_SET:
        lang_dir = Path(lang)
        if not lang_dir.exists():
            continue
        for product_dir in lang_dir.iterdir():
            if product_dir.name == ".gitkeep":
                continue
            if not product_dir.is_dir():
                issues.append(f"{product_dir} 必须是产品目录")
                continue
            for item in product_dir.iterdir():
                if item.name == ".gitkeep":
                    continue
                if not item.is_dir():
                    issues.append(f"{item} 必须是分类目录（不允许文件直接放在产品目录下）")
                    continue
                if item.name not in SP_ALL_CATEGORIES:
                    issues.append(f"{item} 不是允许的分类目录（只允许 {SP_ALL_CATEGORIES}）")
                    continue
                # 检查分类目录下的内容
                for sub in item.iterdir():
                    if sub.name == ".gitkeep":
                        continue
                    if sub.is_file():
                        if sub.suffix.lower() not in {".pdf", ".md"}:
                            issues.append(f"{sub} 不是允许的文件（只允许 .pdf、.md）")
    if issues:
        print(f"[FAIL] sp 项目目录结构非法，发现 {len(issues)} 个问题：")
        for issue in issues:
            print(f"  - {issue}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# 各项目的路径与分类解析
# ---------------------------------------------------------------------------

def _drop_lang(parts):
    if parts and parts[0] in LANG_SET:
        return parts[1:]
    return parts


def resolve_manual(filepath):
    """manual: 按分类解析路径，develop 目录支持 series.txt 产品展开。"""
    parts = Path(filepath).parts
    rest = parts[1:] if parts else []
    if not rest:
        return []

    category_dir = rest[0]
    lang = parts[0] if parts else ""
    manual_cat = "Manuals" if lang == "en" else "Manual"

    # 非标准分类：直接用剩余路径
    if category_dir not in MANUAL_CATEGORIES:
        return [("/".join(rest), manual_cat)]

    if category_dir == "develop":
        src_dir = Path(filepath).parent
        products = get_series_products(src_dir)
        sub = "/".join(rest[2:]) if len(rest) > 2 else ""
        if products:
            return [((f"{p}/{sub}" if sub else p), "Developer Documentation") for p in products]
        # series.txt 不存在时回退到原行为
        path = "/".join(rest[1:])
        return [(path, "Developer Documentation")]

    # device-dsa / platform
    sub = "/".join(rest[1:]) if len(rest) > 1 else ""
    return [(sub, manual_cat)]


def resolve_qa(filepath):
    """qa-docs: zh/EAP600/xxx.md -> (EAP600/xxx.md, FAQ)"""
    parts = _drop_lang(Path(filepath).parts)
    return [("/".join(parts), "FAQ")]


def resolve_sp(filepath):
    """sp: en/EAP600/General/xxx.pdf -> (EAP600/General/xxx.pdf, Datasheets)"""
    parts = _drop_lang(Path(filepath).parts)
    return [("/".join(parts), "Datasheets")]


def get_series_products(start_dir: Path):
    """向上查找 series.txt，返回产品列表。"""
    current = start_dir.resolve()
    while current != current.parent:
        series_file = current / "series.txt"
        if series_file.exists():
            content = series_file.read_text(encoding="utf-8").strip()
            content = content.replace("，", ",")
            products = [p.strip() for p in content.split(",") if p.strip()]
            return products if products else None
        current = current.parent
    return None


def _flatten_config_dir(path_str: str) -> str:
    """平铺 config(s) 目录层级。"""
    for prefix in ("configs/", "config/"):
        if path_str.startswith(prefix):
            return path_str[len(prefix):]
    path_str = path_str.replace("/configs/", "/", 1)
    path_str = path_str.replace("/config/", "/", 1)
    return path_str


def resolve_template1(filepath):
    """template1: zh/IG502/案例名/configs/xxx.cnf -> (IG502/案例名/xxx.cnf, Use Cases)"""
    parts = _drop_lang(Path(filepath).parts)
    path_str = "/".join(parts)

    # 平铺 config(s) 目录
    path_str = _flatten_config_dir(path_str)
    parts = path_str.split("/")

    product = parts[0] if parts else ""
    rest = parts[1:]

    npath = "/".join([product] + rest) if rest else product
    return [(npath, "Use Cases")]


RESOLVERS = {
    "manual": resolve_manual,
    "qa-docs": resolve_qa,
    "sp": resolve_sp,
    "template1": resolve_template1,
}


# ---------------------------------------------------------------------------
# API 校验
# ---------------------------------------------------------------------------

def _call_api(payload, api_url, api_token, email):
    """调用 PLM API 并返回结果是否成功。"""
    if not payload:
        return True

    print(f"=== 调用 API 校验 {len(payload)} 个路径 ===")
    print(f"API: {api_url}\n")
    for item in payload:
        print(f"  [{item['categoryName']}] {item['path']} ({item['size']} bytes)")
    print()

    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }

    api_url_with_params = f"{api_url}?email={email}"

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
                failed = [item for item in result["data"] if not item.get("valid", True)]
                if failed:
                    print("[FAIL] 以下文件校验未通过:")
                    for item in failed:
                        print(f"  - {item.get('path', 'unknown')}: {item.get('message', '未知错误')}")
                    return False

        print("[OK] API 校验成功")
        return True

    except requests.exceptions.Timeout:
        print("[FAIL] 请求超时")
        return False
    except requests.exceptions.HTTPError as e:
        print(f"[FAIL] HTTP 错误: {e}")
        if hasattr(e, "response") and e.response:
            print(f"状态码: {e.response.status_code}")
            print(f"响应内容: {e.response.text}")
        return False
    except requests.exceptions.RequestException as e:
        print(f"[FAIL] 请求失败: {e}")
        return False


def validate(project, file_list, email, env):
    resolver = RESOLVERS[project]
    zh_payload = []
    en_payload = []
    for f in file_list:
        p = Path(f)
        if not p.exists():
            print(f"[SKIP] 文件不存在: {f}")
            continue
        size = p.stat().st_size
        for path, category in resolver(f):
            item = {
                "path": path,
                "size": size,
                "categoryName": category,
            }
            f_norm = f.replace("\\", "/")
            if f_norm.startswith("zh/"):
                zh_payload.append(item)
            elif f_norm.startswith("en/"):
                en_payload.append(item)

    if not zh_payload and not en_payload:
        print("[WARN] 没有需要校验的文件")
        return True

    all_ok = True
    if zh_payload:
        all_ok = _call_api(zh_payload, env["cn_url"], env["cn_token"], email) and all_ok
    if en_payload:
        all_ok = _call_api(en_payload, env["en_url"], env["en_token"], email) and all_ok

    return all_ok


def main():
    parser = argparse.ArgumentParser(description="本地 PLM 文档路径统一校验工具")
    parser.add_argument(
        "--project",
        choices=["manual", "qa-docs", "sp", "template1"],
        help="项目类型（不传则交互选择）",
    )
    parser.add_argument("--file", nargs="+", help="指定要校验的文件路径")
    parser.add_argument("--email", help="通知邮箱（不传则交互输入）")
    parser.add_argument("--env", choices=["prod", "test"], help="环境选择（不传则交互选择）")
    args = parser.parse_args()

    project = args.project or select_project()
    email = args.email or input_email()

    env = {}
    if args.env:
        env = {
            "cn_url": PROD_CN_URL, "en_url": PROD_EN_URL,
            "cn_token": PROD_CN_TOKEN, "en_token": PROD_EN_TOKEN,
        } if args.env == "prod" else {
            "cn_url": TEST_CN_URL, "en_url": TEST_EN_URL,
            "cn_token": TEST_CN_TOKEN, "en_token": TEST_EN_TOKEN,
        }
    else:
        env = select_env()

    if project == "manual":
        check_manual_structure()
    elif project == "template1":
        check_template1_structure()
    elif project == "sp":
        check_sp_structure()

    if args.file:
        raw_files = args.file
    else:
        raw_files = get_all_files()

    file_list = filter_files(raw_files)

    if not file_list:
        print("[INFO] 没有找到需要校验的文件")
        sys.exit(0)

    print(f"[INFO] 项目: {project}，找到 {len(file_list)} 个待校验文件\n")

    ok = validate(project, file_list, email, env)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
