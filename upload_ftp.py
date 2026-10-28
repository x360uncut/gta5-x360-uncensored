#!/usr/bin/env python3
"""
Upload patched GTA V xbox360a.rpf to Xbox 360 (Aurora / DashLaunch) over FTP.
Clean, production-ready script with proper error handling, CRLF protection, and connection cleanup.
"""

import sys
import os
import ftplib
import time
import argparse


def upload_to_xbox(ip: str, port: int, user: str, password: str, local_file: str, remote_path: str):
    if not os.path.exists(local_file):
        print(f"[-] Error: local file not found: {local_file}")
        sys.exit(1)

    file_size = os.path.getsize(local_file)
    if file_size == 0:
        print(f"[-] Error: local file is empty (0 bytes): {local_file}")
        sys.exit(1)

    # Protect against FTP command injection via remote_path
    if any(c in remote_path for c in ('\r', '\n')):
        print("[-] Error: invalid characters in remote_path (CRLF injection prevented)")
        sys.exit(1)

    ftp = None
    try:
        print(f"[*] Connecting to Xbox 360 at {ip}:{port}...")
        ftp = ftplib.FTP()
        ftp.connect(ip, port, timeout=15)
        ftp.login(user, password)
        print("[+] Connected to Xbox 360 FTP server successfully!")

        print(f"[*] Uploading {local_file} ({file_size / (1024 * 1024):.1f} MB) -> {remote_path}...")
        start_time = time.time()
        uploaded = 0

        with open(local_file, "rb") as f:
            def callback(chunk):
                nonlocal uploaded
                uploaded += len(chunk)
                elapsed = time.time() - start_time
                if elapsed > 0:
                    speed = (uploaded / (1024 * 1024)) / elapsed
                    percent = (uploaded / file_size) * 100
                    sys.stdout.write(
                        f"\rProgress: {percent:5.1f}% ({uploaded / (1024 * 1024):.1f}/{file_size / (1024 * 1024):.1f} MB) @ {speed:.2f} MB/s"
                    )
                    sys.stdout.flush()

            ftp.storbinary(f"STOR {remote_path}", f, blocksize=65536, callback=callback)

        total_elapsed = time.time() - start_time
        avg_speed = (file_size / (1024 * 1024)) / total_elapsed if total_elapsed > 0 else 0
        print(f"\n[+] Upload complete in {total_elapsed:.1f}s (Average speed: {avg_speed:.2f} MB/s)!")

    except KeyboardInterrupt:
        print("\n[-] Upload aborted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n[-] FTP Error: {e}")
        sys.exit(1)
    finally:
        if ftp:
            try:
                ftp.quit()
            except Exception:
                ftp.close()


def main():
    parser = argparse.ArgumentParser(description="Upload patched GTA V xbox360a.rpf to Xbox 360 via FTP")
    parser.add_argument("--ip", required=True, help="Xbox 360 IP address on your local network (e.g. 192.168.1.50)")
    parser.add_argument("--file", required=True, help="Path to patched xbox360a.rpf on your PC")
    parser.add_argument("--remote", default="/Hdd1/Games/GTA5/xbox360a.rpf", help="Target path on Xbox 360 HDD (default: /Hdd1/Games/GTA5/xbox360a.rpf)")
    parser.add_argument("--port", type=int, default=21, help="FTP port (default: 21)")
    parser.add_argument("--user", default="xboxftp", help="FTP username (default: xboxftp)")
    parser.add_argument("--pass", dest="password", default="xboxftp", help="FTP password (default: xboxftp)")

    args = parser.parse_args()
    upload_to_xbox(args.ip, args.port, args.user, args.password, args.file, args.remote)


if __name__ == "__main__":
    main()
