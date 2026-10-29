#!/usr/bin/env python3
"""
GTA V GXT2 localization text tool.
Supports decoding, encoding, inspecting, and Jenkins One-At-A-Time hashing.
Works with PC (little-endian) and Xbox 360 / PS3 (big-endian).
Supports single files and multi-file batch dictionaries.
"""

import sys
import os
import struct
import json
import argparse
from typing import Dict, List, Tuple, Union, Any


def rage_joaat(key: str) -> int:
    """
    RAGE atStringHash / Jenkins One-at-a-time (joaat) 32-bit hash.
    C++ implementation converts ASCII uppercase characters to lowercase by byte.
    """
    key_bytes = key.encode('utf-8')
    h = 0
    for b in key_bytes:
        if 65 <= b <= 90:  # 'A'-'Z'
            b += 32
        h = (h + b) & 0xFFFFFFFF
        h = (h + (h << 10)) & 0xFFFFFFFF
        h = (h ^ (h >> 6)) & 0xFFFFFFFF
    h = (h + (h << 3)) & 0xFFFFFFFF
    h = (h ^ (h >> 11)) & 0xFFFFFFFF
    h = (h + (h << 15)) & 0xFFFFFFFF
    return h


def parse_key_hash(key: Union[str, int]) -> int:
    """
    Converts a key to a 32-bit unsigned hash.
    Only explicit '0x' or '0X' hexadecimal strings are parsed as hex values.
    All other strings (including 'DEADBEEF', '123', 'SUB_01') are hashed via rage_joaat.
    """
    if isinstance(key, int):
        return key & 0xFFFFFFFF
    key_str = str(key).strip()
    if key_str.startswith(('0x', '0X')):
        try:
            return int(key_str, 16) & 0xFFFFFFFF
        except ValueError:
            raise ValueError(f"Invalid hexadecimal key: {key_str}")
    return rage_joaat(key_str)


def detect_endianness(data: bytes) -> str:
    """Detects whether GXT2 is little-endian (PC) or big-endian (Xbox 360)."""
    if len(data) < 8:
        raise ValueError("file too small to be a valid GXT2")
    file_size = len(data)
    count_le = struct.unpack('<I', data[4:8])[0]
    count_be = struct.unpack('>I', data[4:8])[0]

    le_ok = (8 + count_le * 8 <= file_size) and (count_le < 500_000)
    be_ok = (8 + count_be * 8 <= file_size) and (count_be < 500_000)

    if le_ok and not be_ok:
        return '<'
    if be_ok and not le_ok:
        return '>'
    return '<'


def decode_gxt2(data: bytes, endian: str = 'auto') -> Dict[str, str]:
    """
    Decodes GXT2 binary data into a dictionary of {"0xHASH": "text"}.
    Automatically handles PC / Xbox 360 byte order and file-relative / block-relative offsets.
    """
    if len(data) < 8:
        raise ValueError("file size is less than 8 bytes")

    magic = data[:4]
    if magic not in (b'GXT2', b'2TXG'):
        raise ValueError(f"invalid magic signature: {magic!r} (expected b'GXT2')")

    if endian == 'auto':
        endian = detect_endianness(data)
    elif endian in ('little', 'le', '<'):
        endian = '<'
    elif endian in ('big', 'be', '>'):
        endian = '>'

    count = struct.unpack(f'{endian}I', data[4:8])[0]
    entry_table_end = 8 + count * 8
    if entry_table_end > len(data):
        raise ValueError(f"entry table extends past end of file: count={count}, needed={entry_table_end}, file_size={len(data)}")

    # Read entries
    entries: List[Tuple[int, int]] = []
    for i in range(count):
        pos = 8 + i * 8
        h, off = struct.unpack(f'{endian}II', data[pos:pos + 8])
        entries.append((h, off))

    if not entries:
        return {}

    # Check offset base: relative to file start or relative to string block?
    # Exclude 0 offsets to avoid false detection on empty strings
    valid_offsets = [off for _, off in entries if off > 0]
    if valid_offsets and min(valid_offsets) >= entry_table_end:
        base_offset = 0
    else:
        base_offset = entry_table_end

    result: Dict[str, str] = {}
    for h, off in entries:
        if off == 0 and base_offset == 0:
            result[f"0x{h:08X}"] = ""
            continue
        str_start = base_offset + off
        if str_start >= len(data):
            result[f"0x{h:08X}"] = ""
            continue
        str_end = data.find(b'\x00', str_start)
        raw_str = data[str_start:] if str_end == -1 else data[str_start:str_end]

        try:
            text = raw_str.decode('utf-8')
        except UnicodeDecodeError:
            text = raw_str.decode('utf-8', errors='replace')

        result[f"0x{h:08X}"] = text

    return result


def encode_gxt2(
    strings_map: Dict[Union[str, int], str],
    endian: str = 'little',
    magic: bytes = b'GXT2',
    file_relative: bool = True,
    deduplicate: bool = True
) -> bytes:
    """
    Encodes a dict of {key: text} into GXT2 binary format.
    Automatically sorts by hash and generates valid offsets.
    Handles hash deduplication cleanly.
    """
    e = '>' if endian in ('big', 'be', '>') else '<'

    # Resolve hashes and deduplicate
    unique_entries: Dict[int, str] = {}
    for k, text in strings_map.items():
        h = parse_key_hash(k)
        unique_entries[h] = text if text is not None else ""

    # RAGE requirement: MUST be sorted ascending by unsigned 32-bit hash!
    parsed_entries: List[Tuple[int, str]] = sorted(unique_entries.items(), key=lambda x: x[0])

    count = len(parsed_entries)
    entry_table_size = 8 + count * 8

    # Build string pool with optional deduplication
    string_pool = bytearray()
    pool_offsets: Dict[bytes, int] = {}
    entry_offsets: List[int] = []

    for _, text in parsed_entries:
        str_bytes = text.encode('utf-8') + b'\x00'
        if deduplicate and str_bytes in pool_offsets:
            offset_in_pool = pool_offsets[str_bytes]
        else:
            offset_in_pool = len(string_pool)
            if deduplicate:
                pool_offsets[str_bytes] = offset_in_pool
            string_pool.extend(str_bytes)

        if file_relative:
            entry_offsets.append(entry_table_size + offset_in_pool)
        else:
            entry_offsets.append(offset_in_pool)

    # Build binary output
    output = bytearray()
    output.extend(magic[:4])
    output.extend(struct.pack(f'{e}I', count))

    for (h, _), off in zip(parsed_entries, entry_offsets):
        output.extend(struct.pack(f'{e}II', h, off))

    output.extend(string_pool)
    return bytes(output)


def is_nested_dataset(data: Any) -> bool:
    """Checks if a parsed JSON is a multi-file dataset: { 'file.gxt2': { '0x...': 'text' } }"""
    if isinstance(data, dict) and data:
        first_val = next(iter(data.values()))
        return isinstance(first_val, dict)
    return False


def cmd_decode(args):
    # Check if input is a directory of GXT2 files
    if os.path.isdir(args.input):
        combined: Dict[str, Dict[str, str]] = {}
        for root, _, files in os.walk(args.input):
            for fn in sorted(files):
                if fn.lower().endswith('.gxt2'):
                    full_p = os.path.join(root, fn)
                    rel_p = os.path.relpath(full_p, args.input).replace('\\', '/')
                    with open(full_p, 'rb') as f:
                        data = f.read()
                    # Use relative path if nested to prevent name collisions
                    key = rel_p if rel_p != fn else fn
                    combined[key] = decode_gxt2(data, endian=args.endian)
        out_path = args.output or "combined_subtitles.json"
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(combined, f, ensure_ascii=False, indent=2)
        print(f"[+] Decoded {len(combined)} GXT2 files from directory -> {out_path}")
        return

    with open(args.input, 'rb') as f:
        data = f.read()

    res = decode_gxt2(data, endian=args.endian)
    out_path = args.output or (os.path.splitext(args.input)[0] + '.json')

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=2)

    print(f"[+] Decoded {len(res)} strings -> {out_path}")


def cmd_encode(args):
    with open(args.input, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Resolve endianness
    if args.endian:
        endian = args.endian
    else:
        endian = 'big' if args.platform == 'x360' else 'little'

    file_rel = not args.block_relative
    magic = b'2TXG' if args.magic_2txg else b'GXT2'

    # Check for multi-file dataset
    if is_nested_dataset(data):
        out_dir = args.output_dir or args.output or "output_gxt2"
        os.makedirs(out_dir, exist_ok=True)
        print(f"[*] Batch encoding multi-file dataset ({len(data)} files) -> {out_dir}/...")
        for fn, strings_map in data.items():
            final_map = strings_map
            # If base directory is provided, merge delta into the original GXT2
            if getattr(args, 'base_dir', None):
                out_fn_candidate = fn if fn.lower().endswith('.gxt2') else (fn + '.gxt2')
                base_candidate = os.path.join(args.base_dir, out_fn_candidate)
                if os.path.exists(base_candidate):
                    with open(base_candidate, 'rb') as f_base:
                        base_bytes = f_base.read()
                    base_raw = decode_gxt2(base_bytes, endian=args.endian or 'auto')
                    # Normalize by 0xHEX key so string labels in strings_map cleanly overwrite decoded hex keys
                    base_dict = {f"0x{parse_key_hash(k):08X}": v for k, v in base_raw.items()}
                    for k, v in strings_map.items():
                        base_dict[f"0x{parse_key_hash(k):08X}"] = v
                    final_map = base_dict

            out_bytes = encode_gxt2(
                final_map,
                endian=endian,
                magic=magic,
                file_relative=file_rel,
                deduplicate=not args.no_dedup
            )
            out_fn = fn if fn.lower().endswith('.gxt2') else (fn + '.gxt2')
            dest_path = os.path.join(out_dir, out_fn)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            with open(dest_path, 'wb') as f_out:
                f_out.write(out_bytes)
        print(f"[+] Successfully encoded {len(data)} GXT2 files (endian={endian})!")
        return

    out_bytes = encode_gxt2(
        data,
        endian=endian,
        magic=magic,
        file_relative=file_rel,
        deduplicate=not args.no_dedup
    )

    out_path = args.output or (os.path.splitext(args.input)[0] + '.gxt2')
    with open(out_path, 'wb') as f:
        f.write(out_bytes)

    print(f"[+] Encoded {len(data)} strings -> {out_path} ({len(out_bytes):,} bytes, endian={endian})")


def cmd_info(args):
    with open(args.input, 'rb') as f:
        data = f.read()

    if len(data) < 8:
        print("error: file too small")
        return

    magic = data[:4]
    endian = detect_endianness(data)
    endian_name = "Xbox 360 / PS3 (Big-Endian)" if endian == '>' else "PC / Modern Console (Little-Endian)"
    count = struct.unpack(f'{endian}I', data[4:8])[0]
    entry_table_end = 8 + count * 8

    print(f"File:        {args.input}")
    print(f"Size:        {len(data):,} bytes")
    print(f"Magic:       {magic!r}")
    print(f"Endianness:  {endian_name}")
    print(f"Entry Count: {count:,}")
    print(f"Table End:   0x{entry_table_end:X} ({entry_table_end:,} bytes)")

    if count > 0 and entry_table_end <= len(data):
        first_h, first_off = struct.unpack(f'{endian}II', data[8:16])
        offset_mode = "Absolute (from file start)" if first_off >= entry_table_end else "Relative (from string pool)"
        print(f"Offset Mode: {offset_mode}")
        print(f"First Entry: hash=0x{first_h:08X}, offset=0x{first_off:X}")


def cmd_hash(args):
    h = rage_joaat(args.label)
    print(f"Label: '{args.label}'")
    print(f"Hash:  0x{h:08X} ({h})")


def main():
    parser = argparse.ArgumentParser(description="GTA V GXT2 Binary Tool (PC & Xbox 360)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # decode
    p_dec = subparsers.add_parser("decode", help="decode .gxt2 to .json (or a directory of .gxt2 into a combined json)")
    p_dec.add_argument("input", help="input .gxt2 file or directory")
    p_dec.add_argument("output", nargs="?", help="output .json file")
    p_dec.add_argument("--endian", choices=["auto", "little", "big"], default="auto", help="byte order (default: auto)")

    # encode
    p_enc = subparsers.add_parser("encode", help="encode .json to .gxt2 (supports single files and multi-file datasets)")
    p_enc.add_argument("input", help="input .json file")
    p_enc.add_argument("output", nargs="?", help="output .gxt2 file")
    p_enc.add_argument("--output-dir", help="output directory for multi-file datasets")
    p_enc.add_argument("--base-dir", help="base directory with original .gxt2 files to merge delta with (prevents losing non-modified dialogue)")
    p_enc.add_argument("--platform", choices=["pc", "x360"], default="x360", help="target platform (default: x360)")
    p_enc.add_argument("--endian", choices=["little", "big"], help="explicit byte order override")
    p_enc.add_argument("--block-relative", action="store_true", help="write offsets relative to string block instead of file start")
    p_enc.add_argument("--magic-2txg", action="store_true", help="use b'2TXG' magic instead of canonical b'GXT2'")
    p_enc.add_argument("--no-dedup", action="store_true", help="disable string deduplication")

    # info
    p_info = subparsers.add_parser("info", help="display GXT2 header and metadata")
    p_info.add_argument("input", help="input .gxt2 file")

    # hash
    p_hash = subparsers.add_parser("hash", help="compute RAGE Jenkins hash for a label")
    p_hash.add_argument("label", help="string label name (e.g. SUB_FIN1_01)")

    args = parser.parse_args()
    if args.command == "decode":
        cmd_decode(args)
    elif args.command == "encode":
        cmd_encode(args)
    elif args.command == "info":
        cmd_info(args)
    elif args.command == "hash":
        cmd_hash(args)


if __name__ == '__main__':
    main()
