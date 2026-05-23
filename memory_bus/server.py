import socket
import struct
import mmap
import os
import sys
import time
import binascii
import threading
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


def log(msg, color=CYAN, prefix="RAM-BUS"):
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"{BOLD}[{timestamp}][{prefix}]{RESET} {color}{msg}{RESET}")


# 16 MB pre-allocated page table space in pure RAM (/dev/shm)
PAGE_TABLE_PATH = "/dev/shm/sovereign_page_table"
DEFAULT_PAGE_SIZE = 4096
TOTAL_BUS_SIZE = 16 * 1024 * 1024  # 16MB
HEADER_FORMAT = "!IIIII"  # Magic, PageIndex, Offset, PageSize, Checksum
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
MAGIC = 0xDEADBEEF


def initialize_shared_memory():
    """Pre-allocates the RAM-backed page table and mmaps it."""
    global PAGE_TABLE_PATH
    log(
        f"Initializing 16MB shared memory swap at: {BOLD}{PAGE_TABLE_PATH}{RESET}...",
        color=BLUE,
    )

    # Ensure path directory exists (fallback to /tmp if run outside WSL)
    dir_name = os.path.dirname(PAGE_TABLE_PATH)
    if not os.path.exists(dir_name):
        log(
            f"Directory {dir_name} not found! Falling back to /tmp/sovereign_page_table",
            color=RED,
        )
        PAGE_TABLE_PATH = "/tmp/sovereign_page_table"

    # Pre-allocate file with zeros
    try:
        with open(PAGE_TABLE_PATH, "wb") as f:
            f.write(b"\x00" * TOTAL_BUS_SIZE)

        f_handle = open(PAGE_TABLE_PATH, "r+b")
        mapped_memory = mmap.mmap(f_handle.fileno(), 0, access=mmap.ACCESS_WRITE)
        log(
            f"Shared memory successfully mapped! Base Address: {BOLD}0x{mapped_memory.tell():08X}{RESET}",
            color=GREEN,
        )
        return mapped_memory, f_handle
    except Exception as e:
        log(f"Failed to map shared memory: {e}", color=RED)
        sys.exit(1)


def handle_client_connection(client_socket, client_address, mapped_memory):
    log(
        f"High-Speed Channel opened from {BOLD}{client_address[0]}:{client_address[1]}{RESET}",
        color=GOLD,
    )
    total_bytes_received = 0
    pages_copied = 0
    start_time = time.time()

    try:
        while True:
            # 1. Read Header
            header_bytes = b""
            while len(header_bytes) < HEADER_SIZE:
                chunk = client_socket.recv(HEADER_SIZE - len(header_bytes))
                if not chunk:
                    break
                header_bytes += chunk

            if not header_bytes:
                break  # Client disconnected

            magic, page_index, offset, page_size, checksum = struct.unpack(
                HEADER_FORMAT, header_bytes
            )

            if magic != MAGIC:
                log(
                    f"Invalid magic number {hex(magic)}! Terminating channel.",
                    color=RED,
                )
                break

            # 2. Read Page Data Payload
            payload_bytes = b""
            while len(payload_bytes) < page_size:
                chunk = client_socket.recv(page_size - len(payload_bytes))
                if not chunk:
                    break
                payload_bytes += chunk

            if len(payload_bytes) < page_size:
                log(
                    f"Incomplete page received! Expected {page_size} bytes, got {len(payload_bytes)}",
                    color=RED,
                )
                break

            # 3. Verify Checksum
            calculated_crc = binascii.crc32(payload_bytes) & 0xFFFFFFFF
            if calculated_crc != checksum:
                log(
                    f"Checksum mismatch on Page {page_index}! Dropping page sync.",
                    color=RED,
                )
                continue

            # 4. Direct Zero-Copy Fast Write to RAM Backed mmap
            if offset + page_size > TOTAL_BUS_SIZE:
                log(
                    f"Memory bounds violation! Offset {offset} + Page {page_size} exceeds {TOTAL_BUS_SIZE}",
                    color=RED,
                )
                break

            t_write_0 = time.time_ns()
            mapped_memory[offset : offset + page_size] = payload_bytes
            t_write_1 = time.time_ns()
            write_time_us = (t_write_1 - t_write_0) / 1000.0

            total_bytes_received += page_size
            pages_copied += 1

            if (
                pages_copied % 100 == 0 or page_size > 65536
            ):  # Log occasionally or for large paging
                log(
                    f"Syncing Page {page_index:04d} -> Mapped Offset 0x{offset:06X} | Size: {page_size}B | Latency: {write_time_us:.2f}μs",
                    color=CYAN,
                )

        elapsed = time.time() - start_time
        if elapsed > 0:
            speed = (total_bytes_received / (1024 * 1024)) / elapsed
            log(
                f"Session closed. Synced {BOLD}{pages_copied}{RESET} pages ({total_bytes_received / 1024:.1f} KB) in {elapsed:.4f}s | Throughput: {BOLD}{speed:.2f} MB/s{RESET}",
                color=GREEN,
            )
        else:
            log(f"Session closed immediately.", color=GREEN)

    except Exception as e:
        log(f"Error handling high speed bus channel: {e}", color=RED)
    finally:
        client_socket.close()


def run_server():
    port = 11111

    # Beautiful Banner
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
                {BOLD}SOVEREIGN SYSTEM - INTER-AGENT HIGHSPEED MEMORY BUS{RESET}
                   FAST MMAP RAM-PAGING ENGINE BOUND TO PORT: {BOLD}{port}{RESET}
    """)

    mapped_memory, file_handle = initialize_shared_memory()

    # Create listening TCP Socket with high-performance opts
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # Enable TCP_NODELAY for minimum latency (disable Nagle's algorithm)
    try:
        server_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    except Exception:
        pass

    server_socket.bind(("0.0.0.0", port))
    server_socket.listen(5)
    log(f"High-Speed RAM Bus listening on TCP Port {port}...", color=GREEN)

    try:
        while True:
            client_sock, client_addr = server_socket.accept()
            # Handle in a dedicated high speed thread
            t = threading.Thread(
                target=handle_client_connection,
                args=(client_sock, client_addr, mapped_memory),
                daemon=True,
            )
            t.start()
    except KeyboardInterrupt:
        log("Shutting down memory bus...", color=GOLD)
    finally:
        mapped_memory.close()
        file_handle.close()
        server_socket.close()
        log("Memory bus stopped.", color=GREEN)


if __name__ == "__main__":
    run_server()
