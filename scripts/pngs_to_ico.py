#!/usr/bin/env python3
"""
按文件名后缀（末尾的数字）将同目录下的 PNG 打包为多尺寸的 .ico 文件。

行为说明（按用户要求）：
- 仅识别且使用文件名中带有尺寸后缀的 PNG（如 `name_16.png`、`name-32.png`、`name@48.png` 或 `name16.png`）。
- 不对图片做任何缩放或重新采样：脚本会把每个对应尺寸的 PNG 原始字节直接嵌入到 ICO（使用 PNG 格式的图像块），并按后缀声明的尺寸写入目录。
- 如果单个组中某个文件的实际像素尺寸与后缀不符，会发出警告并跳过该文件。

用法示例:
    python pngs_to_ico.py -d . -o output --overwrite

依赖: Pillow
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from pathlib import Path
import re
from PIL import Image

SIZE_RE = re.compile(r'^(.*?)(?:[_@\-]?)(\d+)$')
COMMON_SIZES = {16, 24, 32, 48, 64, 96, 128, 256, 512}


def parse_args():
    p = argparse.ArgumentParser(description='按后缀打包 PNG 为 ICO')
    p.add_argument('-d', '--dir', type=Path, default=Path('.'), help='扫描目录（默认当前目录）')
    p.add_argument('-o', '--out', type=Path, default=Path('.'), help='输出目录（默认当前目录）')
    p.add_argument('--overwrite', action='store_true', help='覆盖已存在的 .ico 文件')
    return p.parse_args()


def center_crop_to_square(img: Image.Image) -> Image.Image:
    w, h = img.size
    if w == h:
        return img
    m = min(w, h)
    left = (w - m) // 2
    top = (h - m) // 2
    return img.crop((left, top, left + m, top + m))


def group_pngs(dirpath: Path):
    """递归扫描目录，只收集带后缀数字的文件（后缀代表尺寸）。

    按文件的父文件夹名分组（folder.name -> list[(Path, size)])，适合文件夹内文件名不同的情况。
    """
    groups = defaultdict(list)  # folder_name -> list of (Path, size)
    # 递归查找 PNG 文件
    for p in sorted(dirpath.rglob('*.png')):
        if not p.is_file():
            continue
        stem = p.stem
        m = SIZE_RE.match(stem)
        if not m:
            # 只处理带尺寸后缀的文件
            continue
        try:
            size = int(m.group(2))
        except ValueError:
            continue
        folder_name = p.parent.name or '.'
        groups[folder_name].append((p, size))
    return groups


def sizes_from_group(items):
    """返回按升序去重的尺寸列表，只从后缀读取（items 中的 size）。"""
    uniq = sorted({int(s) for _, s in items if s and int(s) > 0})
    return uniq


def create_ico_for_group(base: str, items, out_dir: Path, overwrite: bool):
    """根据后缀尺寸将每个 PNG 原始字节嵌入到 ICO（不做缩放）。

    要求：每个文件的实际像素尺寸必须与后缀一致，否则会跳过该文件并报警告。
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    ico_path = out_dir / f"{base}.ico"
    if ico_path.exists() and not overwrite:
        print(f"已存在，跳过: {ico_path}")
        return

    # 只取带后缀的条目
    entries = []  # list of tuples (size:int, data:bytes)
    for p, s in items:
        if not s:
            continue
        try:
            with Image.open(p) as im:
                w, h = im.size
                if w != h:
                    print(f"警告: {p.name} 不是正方形 ({w}x{h}), 跳过")
                    continue
                if w != s:
                    print(f"警告: {p.name} 实际尺寸 {w} 与后缀 {s} 不符, 跳过")
                    continue
            data = p.read_bytes()
            entries.append((s, data))
        except Exception as e:
            print(f"无法读取 {p}: {e}")

    if not entries:
        print(f"跳过（没有可用的同尺寸 PNG）: {base}")
        return

    # 构建 ICO 文件（使用 PNG 图像块直接嵌入）
    import struct

    entries = sorted(entries, key=lambda x: x[0])
    count = len(entries)
    # ICO header: reserved (2 bytes), type (2 bytes=1), count (2 bytes)
    header = struct.pack('<HHH', 0, 1, count)
    dir_entries = b''
    image_data = b''
    # header + 16*count 是目录起始偏移
    offset = 6 + 16 * count

    for size, data in entries:
        w_byte = 0 if size >= 256 else size
        h_byte = 0 if size >= 256 else size
        color_count = 0
        reserved = 0
        # 当 ICO 中存放 PNG 时，planes 和 bitcount 通常设为 0 或 32; 使用 0/32 比较常见
        planes = 0
        bit_count = 32
        data_len = len(data)
        dir_entries += struct.pack('<BBBBHHII', w_byte, h_byte, color_count, reserved, planes, bit_count, data_len, offset)
        image_data += data
        offset += data_len

    try:
        with ico_path.open('wb') as f:
            f.write(header)
            f.write(dir_entries)
            f.write(image_data)
        sizes_str = ', '.join(str(s) for s, _ in entries)
        print(f"已生成: {ico_path} (sizes: {sizes_str})")
    except Exception as e:
        print(f"写入失败: {ico_path} -> {e}")


def main():
    args = parse_args()
    dirpath: Path = args.dir.resolve()
    outdir: Path = args.out.resolve()
    if not dirpath.is_dir():
        raise SystemExit(f"指定目录不存在: {dirpath}")

    groups = group_pngs(dirpath)
    if not groups:
        print("未找到 PNG 文件。")
        return

    for base, items in groups.items():
        create_ico_for_group(base, items, outdir, args.overwrite)

    print('完成。')

if __name__ == '__main__':
    main()
