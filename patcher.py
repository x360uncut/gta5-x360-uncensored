#!/usr/bin/env python3
"""
GTA V Xbox 360 Uncensored Russian Subtitles Patcher.
Injects fully uncensored Russian subtitles into xbox360a.rpf in-place.
"""

import sys
import os
import gzip
import argparse

RUSSIAN_RPF_OFFSET = 0x26491200
RUSSIAN_RPF_ALLOCATED_LEN = 7647232

def patch_xbox360a(input_path: str, backup: bool = True):
    if not os.path.exists(input_path):
        print(f"[-] Error: file not found: {input_path}")
        sys.exit(1)
        
    file_size = os.path.getsize(input_path)
    if file_size < RUSSIAN_RPF_OFFSET + RUSSIAN_RPF_ALLOCATED_LEN:
        print(f"[-] Error: {input_path} is too small to be a valid xbox360a.rpf ({file_size:,} bytes)")
        sys.exit(1)
        
    script_dir = os.path.dirname(os.path.abspath(__file__))
    patch_gz = os.path.join(script_dir, "data", "russian_uncensored.rpf.gz")
    
    if not os.path.exists(patch_gz):
        print(f"[-] Error: patch data not found at {patch_gz}")
        sys.exit(1)
        
    print(f"[*] Decompressing uncensored Russian localization archive...")
    with gzip.open(patch_gz, "rb") as f:
        mod_rpf = f.read()
        
    if len(mod_rpf) > RUSSIAN_RPF_ALLOCATED_LEN:
        print(f"[-] Error: modified RPF exceeds allocated partition size ({len(mod_rpf)} > {RUSSIAN_RPF_ALLOCATED_LEN})")
        sys.exit(1)
        
    # Pad to exact allocated sector size
    padded_rpf = mod_rpf + b'\x00' * (RUSSIAN_RPF_ALLOCATED_LEN - len(mod_rpf))
    
    # Backup if requested
    if backup:
        backup_path = input_path + ".bak"
        if not os.path.exists(backup_path):
            print(f"[*] Creating backup at {backup_path}...")
            # We only need to backup the original russian.rpf bytes to save 2GB disk space!
            with open(input_path, "rb") as f_in, open(input_path + ".orig_russian.rpf", "wb") as f_bak:
                f_in.seek(RUSSIAN_RPF_OFFSET)
                orig_bytes = f_in.read(RUSSIAN_RPF_ALLOCATED_LEN)
                f_bak.write(orig_bytes)
            print(f"[+] Original localization backed up to {input_path}.orig_russian.rpf (7.6 MB)")

    print(f"[*] Patching {input_path} at offset 0x{RUSSIAN_RPF_OFFSET:X}...")
    with open(input_path, "r+b") as f:
        f.seek(RUSSIAN_RPF_OFFSET)
        f.write(padded_rpf)
        
    print("[+] SUCCESS! Fully uncensored Russian subtitles injected into xbox360a.rpf.")
    print("    Copy this file to your Xbox 360 at Hdd1:\\Games\\GTA5\\xbox360a.rpf")

def restore_xbox360a(input_path: str):
    bak_path = input_path + ".orig_russian.rpf"
    if not os.path.exists(bak_path):
        print(f"[-] Backup not found: {bak_path}")
        sys.exit(1)
        
    print(f"[*] Restoring original localization from {bak_path}...")
    with open(bak_path, "rb") as f_bak, open(input_path, "r+b") as f_in:
        orig = f_bak.read()
        f_in.seek(RUSSIAN_RPF_OFFSET)
        f_in.write(orig)
    print("[+] SUCCESS! Original localization restored.")

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
