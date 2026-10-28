#!/usr/bin/env python3
"""
Upload patched GTA V xbox360a.rpf to Xbox 360 (Aurora / DashLaunch) over FTP.
"""

import sys
import os
import ftplib
import time
import argparse

def upload_to_xbox(ip, port, user, password, local_file, remote_path):
    if not os.path.exists(local_file):
        print(f"[-] Local file not found: {local_file}")
        sys.exit(1)
        
    print(f"[*] Connecting to Xbox 360 at {ip}:{port}...")
    try:
        ftp = ftplib.FTP()
        ftp.connect(ip, port, timeout=10)
        ftp.login(user, password)
        print(f"[+] Connected to FTP!")
        
        file_size = os.path.getsize(local_file)
        print(f"[*] Uploading {local_file} ({file_size/(1024*1024):.1f} MB) -> {remote_path}...")
        
        start_time = time.time()
        uploaded = 0
        
        with open(local_file, "rb") as f:
            def callback(chunk):
                nonlocal uploaded
                uploaded += len(chunk)
                elapsed = time.time() - start_time
                if elapsed > 0:
                    speed = (uploaded / (1024*1024)) / elapsed
                    percent = (uploaded / file_size) * 100
                    sys.stdout.write(f"\rProgress: {percent:.1f}% ({uploaded/(1024*1024):.1f}/{file_size/(1024*1024):.1f} MB) @ {speed:.2f} MB/s")
                    sys.stdout.flush()
                    
            ftp.storbinary(f"STOR {remote_path}", f, blocksize=65536, callback=callback)
            
        print(f"\n[+] Upload complete in {time.time() - start_time:.1f}s!")
        ftp.quit()
    except Exception as e:
        print(f"\n[-] FTP Error: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Upload patched GTA V to Xbox 360 via FTP")
    parser.add_argument("--ip", default="10.42.0.247", help="Xbox 360 IP address")
    parser.add_argument("--port", type=int, default=21, help="FTP port (default: 21)")
    parser.add_argument("--user", default="xboxftp", help="FTP username (default: xboxftp)")
    parser.add_argument("--pass", dest="password", default="xboxftp", help="FTP password (default: xboxftp)")
    parser.add_argument("--file", default="/home/arch/Downloads/GTA5_EXTRACTED/xbox360a.rpf", help="Path to patched xbox360a.rpf")
    parser.add_argument("--remote", default="/Hdd1/Games/GTA5/xbox360a.rpf", help="Target path on Xbox 360 HDD")
    
    args = parser.parse_args()
    upload_to_xbox(args.ip, args.port, args.user, args.password, args.file, args.remote)

if __name__ == "__main__":
    main()
