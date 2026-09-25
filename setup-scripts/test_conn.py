#!/usr/bin/env python3
"""Quick paramiko connection test to one node. Usage: python test_conn.py"""
import paramiko, sys

HOST = "clnode213.clemson.cloudlab.us"
USER = "ApiaO"
KEY  = r"C:\Users\djnin\.ssh\id_rsa"   # <-- change to id_ed25519 if that's the one

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    c.connect(HOST, username=USER, key_filename=KEY, timeout=30)
    _, out, _ = c.exec_command("whoami; hostname; ls -d /mydata 2>/dev/null || echo 'no /mydata'")
    print("CONNECTED OK:")
    print(out.read().decode())
    c.close()
except Exception as e:
    print(f"FAILED: {type(e).__name__}: {e}")
    sys.exit(1)
