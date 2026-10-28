#!/usr/bin/env python3
"""
GTA V Xbox 360 Uncensored Russian Subtitles Patcher.
Injects fully uncensored Russian subtitles into xbox360a.rpf in-place with integrity checks.
"""

import sys
import os
import gzip
import argparse

RUSSIAN_RPF_OFFSET = 0x26491200
RUSSIAN_RPF_ALLOCATED_LEN = 7647232

def validate_target_container(f, file_path: str):
    """Validates that the file is a genuine Xbox 360 GTA V xbox360a.rpf archive."""
    file_size = os.path.getsize(file_path)
    min_required_size = RUSSIAN_RPF_OFFSET + RUSSIAN_RPF_ALLOCATED_LEN
    if file_size < min_required_size:
        raise ValueError(
            f"File is too small ({file_size:,} bytes). Expected at least {min_required_size:,} bytes for xbox360a.rpf."
        )

    # Check root container magic
    f.seek(0)
    root_magic = f.read(4)
    if root_magic != b'RPF7':
        raise ValueError(
            f"Invalid file signature at offset 0: {root_magic!r}. Expected b'RPF7'. "
            "Ensure you selected a valid xbox360a.rpf archive."
        )

    # Check partition magic at target offset
    f.seek(RUSSIAN_RPF_OFFSET)
    nested_magic = f.read(4)
    if nested_magic != b'RPF7':
        raise ValueError(
            f"Invalid nested partition signature at offset 0x{RUSSIAN_RPF_OFFSET:X}: {nested_magic!r}. "
            "Expected b'RPF7'. The file may belong to a different game version or disc."
        )


def patch_xbox360a(input_path: str, backup: bool = True):
    if not os.path.exists(input_path):
        print(f"[-] Error: file not found: {input_path}")
        sys.exit(1)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    patch_gz = os.path.join(script_dir, "data", "russian_uncensored.rpf.gz")

    if not os.path.exists(patch_gz):
        print(f"[-] Error: patch data not found at {patch_gz}")
        sys.exit(1)

    print(f"[*] Validating target container: {input_path}...")
    try:
        with open(input_path, "rb") as f_check:
            validate_target_container(f_check, input_path)
    except Exception as e:
        print(f"[-] Validation failed: {e}")
        sys.exit(1)

    print(f"[*] Decompressing uncensored Russian localization archive...")
    with gzip.open(patch_gz, "rb") as f:
        mod_rpf = f.read()

    if len(mod_rpf) > RUSSIAN_RPF_ALLOCATED_LEN:
        print(f"[-] Error: modified RPF exceeds allocated partition size ({len(mod_rpf)} > {RUSSIAN_RPF_ALLOCATED_LEN})")
        sys.exit(1)

    # Verify RPF7 signature of patch payload
    if mod_rpf[:4] != b'RPF7':
        print(f"[-] Error: patch payload header is corrupted ({mod_rpf[:4]!r})")
        sys.exit(1)

    # Pad with zeros to exact allocated sector size
    padded_rpf = mod_rpf + b'\x00' * (RUSSIAN_RPF_ALLOCATED_LEN - len(mod_rpf))

    # Atomic backup creation
    if backup:
        backup_path = input_path + ".orig_russian.rpf"
        if not os.path.exists(backup_path):
            print(f"[*] Creating atomic backup at {backup_path}...")
            temp_bak = backup_path + ".tmp"
            try:
                with open(input_path, "rb") as f_in, open(temp_bak, "wb") as f_bak:
                    f_in.seek(RUSSIAN_RPF_OFFSET)
                    orig_bytes = f_in.read(RUSSIAN_RPF_ALLOCATED_LEN)
                    if len(orig_bytes) != RUSSIAN_RPF_ALLOCATED_LEN:
                        raise IOError("Truncated read while backing up original partition")
                    if orig_bytes[:4] != b'RPF7':
                        raise ValueError(f"Original partition at offset 0x{RUSSIAN_RPF_OFFSET:X} is not RPF7")
                    f_bak.write(orig_bytes)
                os.replace(temp_bak, backup_path)
                print(f"[+] Original localization safely backed up to {backup_path} (7.6 MB)")
            except Exception as e:
                if os.path.exists(temp_bak):
                    os.remove(temp_bak)
                print(f"[-] Backup failed: {e}. Aborting patch to protect original file.")
                sys.exit(1)
        else:
            print(f"[*] Preserving existing backup at {backup_path}")

    print(f"[*] Patching {input_path} at offset 0x{RUSSIAN_RPF_OFFSET:X}...")
    with open(input_path, "r+b") as f:
        f.seek(RUSSIAN_RPF_OFFSET)
        f.write(padded_rpf)

    print("[+] SUCCESS! Fully uncensored Russian subtitles injected into xbox360a.rpf.")
    print("    Copy this file to your Xbox 360 at Hdd1:\\Games\\GTA5\\xbox360a.rpf")


def restore_xbox360a(input_path: str):
    if not os.path.exists(input_path):
        print(f"[-] Error: file not found: {input_path}")
        sys.exit(1)

    bak_path = input_path + ".orig_russian.rpf"
    if not os.path.exists(bak_path):
        print(f"[-] Error: Backup not found: {bak_path}")
        sys.exit(1)

    bak_size = os.path.getsize(bak_path)
    if bak_size != RUSSIAN_RPF_ALLOCATED_LEN:
        print(f"[-] Error: Backup file is corrupted (size is {bak_size:,} bytes, expected {RUSSIAN_RPF_ALLOCATED_LEN:,})")
        sys.exit(1)

    with open(bak_path, "rb") as f_bak:
        head = f_bak.read(4)
        if head != b'RPF7':
            print(f"[-] Error: Backup file signature is invalid ({head!r}, expected b'RPF7')")
            sys.exit(1)
        f_bak.seek(0)
        orig = f_bak.read()

    print(f"[*] Restoring original localization from {bak_path} into {input_path}...")
    with open(input_path, "r+b") as f_in:
        f_in.seek(RUSSIAN_RPF_OFFSET)
        f_in.write(orig)

    print("[+] SUCCESS! Original official 1C localization successfully restored.")


def main():
    parser = argparse.ArgumentParser(description="GTA V Xbox 360 Uncensored Subtitles Patcher")
    parser.add_argument("file", help="Path to xbox360a.rpf")
    parser.add_argument("--restore", action="store_true", help="Restore original 1C localization from backup")
    parser.add_argument("--no-backup", action="store_true", help="Skip creating backup")

    args = parser.parse_args()
    if args.restore:
        restore_xbox360a(args.file)
    else:
        patch_xbox360a(args.file, backup=not args.no_backup)


if __name__ == "__main__":
    main()
