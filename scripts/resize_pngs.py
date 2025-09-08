#!/usr/bin/env python3
"""
批量高质量缩放 1024x1024 PNG 到 256→64（步长16）的多份方形 PNG。

用法示例：
    python resize_pngs.py source.png              # 输出到 ./resized
    python resize_pngs.py source.png -o out_dir   # 指定输出目录
    python resize_pngs.py source.png --sizes 256,128,64  # 自定义尺寸列表
"""
from __future__ import annotations
import argparse
from pathlib import Path
from PIL import Image

DEFAULT_SIZE_LARGE = list(range(256, 63, -16))  # 256,240,...,64
DEFAULT_SIZE_SMALL = list(range(60, 15, -4))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="高质量缩放方形 PNG")
    p.add_argument("source", type=Path, help="输入 1024x1024 PNG 图像路径")
    p.add_argument("-o", "--out", type=Path, default=Path("resized"), help="输出目录 (默认: resized)")
    p.add_argument("-s", "--sizes", type=str, help="逗号分隔尺寸列表(覆盖默认 256..64). 例如: 256,128,64")
    p.add_argument("--prefix", type=str, default="", help="输出文件名前缀，可选")
    p.add_argument("--suffix", type=str, default="", help="输出文件名后缀，可选，如 _hq")
    p.add_argument("--overwrite", action="store_true", help="已存在文件时覆盖")
    return p.parse_args()


def parse_sizes(size: str | None) -> list[int]:
    if not size:
        return DEFAULT_SIZE_LARGE + DEFAULT_SIZE_SMALL
    if 'l' in size:
        return DEFAULT_SIZE_LARGE
    elif 's' in size:
        return DEFAULT_SIZE_SMALL


def ensure_square_1024(img: Image.Image):
    w, h = img.size
    if w != h:
        raise SystemExit(f"输入不是正方形: {w}x{h}")
    if w != 1024:
        print(f"[警告] 输入尺寸为 {w}x{h} (非 1024). 仍将继续缩放。")


def main():
    args = parse_args()
    sizes = parse_sizes(args.sizes)
    src_path: Path = args.source
    if not src_path.is_file():
        raise SystemExit(f"找不到文件: {src_path}")
    if src_path.suffix.lower() != '.png':
        raise SystemExit("仅支持 PNG 输入")

    out_dir: Path = args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    with Image.open(src_path) as im:
        im.load()  # 读入
        ensure_square_1024(im)
        # 确保保留 alpha
        if im.mode not in ("RGBA", "LA"):
            im = im.convert("RGBA")

        base_name = src_path.stem

        for sz in sizes:
            if sz <= 0:
                print(f"跳过非法尺寸 {sz}")
                continue
            target_path = out_dir / f"{args.prefix}{base_name}_{sz}{args.suffix}.png"
            if target_path.exists() and not args.overwrite:
                print(f"存在，跳过: {target_path}")
                continue
            # 高质量缩放 (Lanczos)
            resized = im.resize((sz, sz), Image.LANCZOS)
            # 以较高压缩但无损方式保存 optimize=True
            resized.save(target_path, format="PNG", optimize=True)
            print(f"生成: {target_path}")

    print("完成。")


if __name__ == "__main__":
    main()
