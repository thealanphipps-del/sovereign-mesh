import socket
import struct
import os
import sys
import time
import binascii
import argparse
from datetime import datetime

# --- AESTHETIC CONSTANTS ---
BLUE = "\033[94m"
CYAN = "\033[96m"
GREEN = "\033[92m"
GOLD = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
RESET = "\033[0m"
BOLD = "\033[1m"


def log(msg, color=CYAN, prefix="RAM-CLI"):
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"{BOLD}[{timestamp}][{prefix}]{RESET} {color}{msg}{RESET}")


HEADER_FORMAT = "!IIIII"  # Magic, PageIndex, Offset, PageSize, Checksum
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
MAGIC = 0xDEADBEEF


def transmit_data(host, port, file_path=None, page_size=4096, test_size_mb=4):
    target = (host, port)
    log(
        f"Establishing high-speed TCP bus link to {BOLD}{host}:{port}{RESET}...",
        color=BLUE,
    )

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Enable TCP_NODELAY for direct microsecond writes without buffering delay
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except Exception:
            pass

        sock.connect(target)
        log("Connection established. Handshake active.", color=GREEN)
    except Exception as e:
        log(f"Failed to connect to memory bus server: {e}", color=RED)
        return

    # Determine data source
    if file_path:
        if not os.path.exists(file_path):
            log(f"File not found: {file_path}", color=RED)
            sock.close()
            return
        file_size = os.path.getsize(file_path)
        log(
            f"Broadcasting File: {BOLD}{os.path.basename(file_path)}{RESET} ({file_size / 1024:.1f} KB)",
            color=GOLD,
        )
        with open(file_path, "rb") as f:
            data = f.read()
    else:
        # Generate synthetic high-density page memory for speed test
        file_size = test_size_mb * 1024 * 1024
        log(
            f"Broadcasting Synthetic Paged RAM block of {BOLD}{test_size_mb} MB{RESET}...",
            color=GOLD,
        )
        data = bytearray(
            os.urandom(file_size)
        )  # High-entropy random data to prevent compression optimization

    # Partition and transmit pages
    total_pages = (file_size + page_size - 1) // page_size
    log(
        f"Segmenting data into {BOLD}{total_pages}{RESET} memory-aligned pages (Frame size: {page_size}B)...",
        color=BLUE,
    )

    t_start = time.time()
    bytes_sent = 0

    try:
        for page_idx in range(total_pages):
            offset = page_idx * page_size
            chunk_data = data[offset : offset + page_size]
            actual_chunk_len = len(chunk_data)

            # Pad final page chunk to keep memory alignment if necessary
            if actual_chunk_len < page_size:
                chunk_data = chunk_data + b"\x00" * (page_size - actual_chunk_len)
                actual_chunk_len = page_size

            # Compute Page CRC32 Checksum
            crc = binascii.crc32(chunk_data) & 0xFFFFFFFF

            # Pack Header
            header = struct.pack(
                HEADER_FORMAT, MAGIC, page_idx, offset, actual_chunk_len, crc
            )

            # Stream Header + Page Payload
            sock.sendall(header + chunk_data)
            bytes_sent += actual_chunk_len

            if (page_idx + 1) % 250 == 0 or (page_idx + 1) == total_pages:
                log(
                    f"Transmitted: {page_idx + 1:04d}/{total_pages} pages ({bytes_sent / 1024 / 1024:.2f} MB)",
                    color=CYAN,
                )

        t_end = time.time()
        elapsed = t_end - t_start
        if elapsed > 0:
            speed = (bytes_sent / (1024 * 1024)) / elapsed
            log(f"Fast Paging Transmission complete!", color=GREEN)
            log(
                f"  Total Data Sent : {bytes_sent / (1024*1024):.2f} MB ({bytes_sent} bytes)",
                color=GREEN,
            )
            log(f"  Time Elapsed     : {elapsed:.4f} seconds", color=GREEN)
            log(f"  Line Throughput  : {BOLD}{speed:.2f} MB/s{RESET}", color=GREEN)
        else:
            log("Transmission ended immediately.", color=GREEN)

    except Exception as e:
        log(f"Transmission error during high speed memory page sync: {e}", color=RED)
    finally:
        sock.close()
        log("Bus link closed.", color=BLUE)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Antigravity HighSpeed Memory Bus Client"
    )
    parser.add_argument("--host", default="127.0.0.1", help="Target server host IP")
    parser.add_argument(
        "--port", type=int, default=11111, help="Target memory bus port"
    )
    parser.add_argument("--file", help="Path to local file to transmit")
    parser.add_argument(
        "--page-size",
        type=int,
        default=4096,
        help="Data page block size (default: 4096)",
    )
    parser.add_argument(
        "--test-size",
        type=int,
        default=4,
        help="Size in MB of synthetic block for speed test (default: 4)",
    )
    args = parser.parse_args()

    # Client banner
    print(f"""
{MAGENTA} ▄▄▄▄    ██▀███   ██▓▓█████ ▄▄▄      ▓█████ ▄████▄   ▒█████   ██▓███   ▓██   ██▓
▓█████▄ ▓██ ▒ ██▒▓██▒▓█   ▀▒████▄    ▓█   ▀▒██▀ ▀█  ▒██▒  ██▒▓██░  ██▒  ▒██  ██▒
▒██▒ ▄██▓██ ░▄█ ▒▒██▒▒███  ░██  ▀█▄  ▒███  ▒▓█    ▄ ▒██░  ██▒▓██░ ██▓▒   ▒██ ██░
▒██░█▀  ▒██▀▀█▄  ░██░▒▓█  ▄░██▄▄▄▄██ ▒▓█  ▄▒▓▓▄ ▄██▒▒██   ██░▒██▄█▓▒ ▒   ░ ▐██▓░
░▓█  ▀█▓░██▓ ▒██▒░██░░▒████▒▓█   ▓██▒░▒████▒ ▓███▀ ░░ ████▓▒░▒██▒ ░  ░   ░ ██▒▓░
░▒▓███▀▒░ ▒▓ ░▒▓░░▓  ░░ ▒░ ░▒▒   ▓▒█░░░ ▒░ ░ ░▒ ▒  ░░ ▒░▒░▒░ ░▒▓▒░ ░  ░    ██▒▒▒ 
 ▒░▒   ░   ░▒ ░ ▒░ ▒ ░ ░ ░  ░ ▒   ▒▒ ░ ░ ░  ░   ░  ▒   ░ ▒ ▒░  ░▒ ░        ▓██ ░▒ 
  ░    ░   ░░   ░  ▒ ░   ░    ░   ▒      ░  ░ ░        ░ ░ ▒   ░░          ▒ ▐ ░░ 
  ░         ░      ░     ░  ░     ░  ░   ░  ░ ░ ░        ░ ░                 ░   
       ░                                    ░ ░                              ░  
                {BOLD}SOVEREIGN SYSTEM - HIGH-SPEED MEMORY BUS DIALER (v2.0){RESET}
    """)

    transmit_data(args.host, args.port, args.file, args.page_size, args.test_size)
