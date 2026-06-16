#!/usr/bin/env python3
"""导出产品文档列表为 JSON。"""

import json
from pathlib import Path


def export_sp():
    data = {"zh": {}, "en": {}}
    for lang in ["zh", "en"]:
        lang_dir = Path(lang)
        if not lang_dir.exists():
            continue
        for product_dir in lang_dir.iterdir():
            if not product_dir.is_dir():
                continue
            product_name = product_dir.name
            data[lang][product_name] = {}
            for cat_dir in product_dir.iterdir():
                if not cat_dir.is_dir():
                    continue
                cat_name = cat_dir.name
                files = []
                for f in cat_dir.rglob("*"):
                    if not f.is_file() or f.suffix.lower() != ".pdf":
                        continue
                    rel = str(f.relative_to(cat_dir)).replace("\\", "/")
                    if "/images/" in rel or "/img/" in rel or "/imgs/" in rel:
                        continue
                    files.append(f.name)
                if files:
                    data[lang][product_name][cat_name] = files

    output = Path("sp_documents.json")
    with open(output, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    total = len(data["zh"]) + len(data["en"])
    print(f"[SP] 已导出 {total} 个产品到 {output}")
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    export_sp()
