# AGENT INSTRUCTIONS — GTA V Xbox 360 Uncensored Toolkit

This repository contains reverse-engineering tools, an in-place RPF7 binary patcher, and subtitle dataset for GTA V on Xbox 360 (RGH / Freeboot / Xenia).

## Architecture & Layout
- `patcher.py`: In-place binary patcher for `xbox360a.rpf`. Targets `data/lang/russian.rpf` at static offset `0x26491200` (length: 7,647,232 bytes / 14,936 sectors). Validates 16-byte header `525046370000025680001d000ffffff7` (magic RPF7 + 598 TOC entries). Creates atomic backup `<file>.orig_russian.rpf`.
- `gxt2_tool.py`: CLI encoder/decoder for RAGE GXT2 binary localization files. Uses Big-Endian byte order for Xbox 360 and custom ASCII-lowercasing Jenkins One-At-A-Time (`rage_joaat`) hash. Supports `--base-dir` for non-destructive delta merging.
- `upload_ftp.py`: Non-interactive FTP uploader for deployment to Xbox 360 consoles running Aurora/DashLaunch.
- `data/uncensored_subtitles.json`: Text-only JSON mapping of 1,889 uncensored dialogue lines across 221 files. Does not contain raw Rockstar game blobs.

## Non-Interactive CLI Workflows

### 1. Patching xbox360a.rpf
```bash
# Apply patch using downloaded payload:
python3 patcher.py /path/to/xbox360a.rpf --payload data/russian_uncensored.rpf.gz

# Restore original 1C localization:
python3 patcher.py /path/to/xbox360a.rpf --restore
```

### 2. GXT2 Encoding & Decoding
```bash
# Decode single GXT2 to JSON:
python3 gxt2_tool.py decode input.gxt2 output.json

# Decode directory of GXT2 files into combined JSON (handles nested DLC paths):
python3 gxt2_tool.py decode folder_gxt2/ combined.json

# Merge delta JSON over original GXT2 files (preserves all mission dialogue):
python3 gxt2_tool.py encode delta.json --base-dir raw_gxt2/ --output-dir out_gxt2/ --platform x360

# Compute RAGE joaat hash for a label:
python3 gxt2_tool.py hash SUB_LABEL_NAME
```

### 3. Deploying to Console
```bash
python3 upload_ftp.py --ip <CONSOLE_IP> --file /path/to/xbox360a.rpf --remote /Hdd1/Games/GTA5/xbox360a.rpf
```

## Constraints for Subtitle Editing
- Never strip or modify RAGE control tags: `~z~` (subtitle color), `~s~`, `~w~`, `~n~` (newline), or gamepad button glyphs (`~PAD_A~`, `~INPUT_...~`).
- Keys can be string labels or `0x...` hex hashes. `gxt2_tool.py` automatically resolves both.
