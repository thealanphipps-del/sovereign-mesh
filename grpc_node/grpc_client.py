import grpc
import time
import json
import http.client
import sys
import os
import argparse
from datetime import datetime

# Ensure we can import the generated proto files
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import sync_pb2
import sync_pb2_grpc

# --- AESTHETIC CONSTANTS ---
BLUE = "\033[94m"
CYAN = "\033[96m"
GREEN = "\033[92m"
GOLD = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
RESET = "\033[0m"
BOLD = "\033[1m"


def log(msg, color=CYAN, prefix="GRPC-CLI"):
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"{BOLD}[{timestamp}][{prefix}]{RESET} {color}{msg}{RESET}")


def get_local_ollama_models():
    """Queries local Ollama to get list of available models."""
    try:
        conn = http.client.HTTPConnection("localhost", 11434, timeout=2)
        conn.request("GET", "/api/tags")
        response = conn.getresponse()
        if response.status == 200:
            data = json.loads(response.read().decode("utf-8"))
            models = [m.get("name") for m in data.get("models", [])]
            return models
    except Exception:
        pass
    return ["gemma2:2b"]  # Fallback


def get_system_metrics():
    """Collects basic OS/Memory metrics directly from procfs or system info."""
    metrics = {"os": "WSL2/Linux", "timestamp": str(int(time.time()))}
    try:
        with open("/proc/meminfo", "r") as f:
            for line in f:
                if "MemTotal" in line:
                    metrics["memory_total"] = line.split()[1] + " kB"
                elif "MemAvailable" in line:
                    metrics["memory_available"] = line.split()[1] + " kB"
    except Exception:
        metrics["memory_total"] = "Unknown"
        metrics["memory_available"] = "Unknown"
    return metrics


def run_via_ssh(host, command):
    """
    Executes a command on the remote host via native SSH command spawning.
    This automatically inherits the caller's SSH keys, configs, and agents.
    Returns (exit_code, stdout, stderr).
    """
    import subprocess

    log(
        f"[SSH-FALLBACK] Routing execution via native SSH shell interface to {BOLD}{host}{RESET}...",
        color=GOLD,
    )
    log(f"[SSH-FALLBACK] Remote Command: {BOLD}{command}{RESET}", color=GOLD)
    try:
        # -o ConnectTimeout=5 ensures we don't hang indefinitely if the node is dead
        ssh_cmd = ["ssh", "-o", "ConnectTimeout=5", host, command]
        res = subprocess.run(ssh_cmd, capture_output=True, text=True)
        return res.returncode, res.stdout, res.stderr
    except Exception as e:
        log(f"[SSH-FALLBACK ERROR] Failed to spawn SSH process: {e}", color=RED)
        return -1, "", str(e)


def parse_ssh_ps_output(stdout):
    processes = []
    lines = stdout.strip().split("\n")
    for line in lines:
        if not line.strip():
            continue
        parts = line.strip().split(None, 7)
        if len(parts) >= 7:
            try:
                pid_val = int(parts[0])
                ppid_val = int(parts[1])
                user_val = parts[2]
                stat_val = parts[3]
                cpu_val = float(parts[4])
                mem_val = float(parts[5])
                comm_val = parts[6]
                args_val = parts[7] if len(parts) > 7 else comm_val

                processes.append(
                    sync_pb2.ProcessInfo(
                        pid=pid_val,
                        ppid=ppid_val,
                        name=comm_val,
                        username=user_val,
                        cpu_percent=cpu_val,
                        memory_percent=mem_val,
                        cmdline=args_val,
                        status=stat_val,
                    )
                )
            except Exception:
                continue
    return processes


def print_processes_table(processes, plane_source):
    print(f"\n{BOLD}{GOLD}--- PROCESS LISTING VIA {plane_source} ---{RESET}")
    print(
        f"{'PID':<7} | {'PPID':<7} | {'USER':<12} | {'STAT':<5} | {'%CPU':<5} | {'%MEM':<5} | {'NAME':<20} | {'COMMAND'}"
    )
    print("-" * 110)
    sorted_procs = sorted(processes, key=lambda x: (-x.cpu_percent, x.pid))
    for p in sorted_procs[:50]:  # Top 50 processes
        cmd_truncated = p.cmdline[:45] + "..." if len(p.cmdline) > 48 else p.cmdline
        print(
            f"{p.pid:<7} | {p.ppid:<7} | {p.username:<12} | {p.status:<5} | {p.cpu_percent:<5.1f} | {p.memory_percent:<5.1f} | {p.name:<20} | {cmd_truncated}"
        )
    print("-" * 110 + "\n")


def parse_ssh_ss_output(stdout, protocol):
    bindings = []
    import re

    lines = stdout.strip().split("\n")
    for line in lines[1:]:
        if not line.strip():
            continue
        parts = line.strip().split(None, 5)
        if len(parts) >= 5:
            state = parts[0]
            local = parts[3]
            peer = parts[4]

            if ":" in local:
                local_addr, local_port_str = local.rsplit(":", 1)
                local_addr = local_addr.strip("[]")
            else:
                local_addr, local_port_str = local, "0"

            if ":" in peer:
                peer_addr, peer_port_str = peer.rsplit(":", 1)
                peer_addr = peer_addr.strip("[]")
            else:
                peer_addr, peer_port_str = peer, "0"

            try:
                local_port = int(local_port_str)
            except ValueError:
                local_port = 0

            try:
                peer_port = int(peer_port_str)
            except ValueError:
                peer_port = 0

            pid = 0
            process_name = ""

            if len(parts) >= 6:
                proc_info = parts[5]
                match = re.search(r"users:\(\(\"([^\"]+)\",pid=(\d+)", proc_info)
                if match:
                    process_name = match.group(1)
                    pid = int(match.group(2))
                else:
                    match_pid = re.search(r"pid=(\d+)", proc_info)
                    if match_pid:
                        pid = int(match_pid.group(1))
                    match_name = re.search(r"\"([^\"]+)\"", proc_info)
                    if match_name:
                        process_name = match_name.group(1)

            bindings.append(
                sync_pb2.PortBinding(
                    protocol=protocol,
                    local_address=local_addr,
                    local_port=local_port,
                    remote_address=peer_addr,
                    remote_port=peer_port,
                    state=state,
                    pid=pid,
                    process_name=process_name,
                )
            )
    return bindings


def print_ports_table(bindings, plane_source):
    print(f"\n{BOLD}{GOLD}--- ACTIVE PORT BINDINGS VIA {plane_source} ---{RESET}")
    print(
        f"{'PROTO':<5} | {'LOCAL ADDRESS':<22} | {'PORT':<6} | {'PEER ADDRESS':<22} | {'PORT':<6} | {'STATE':<12} | {'PID':<6} | {'PROCESS NAME'}"
    )
    print("-" * 110)
    sorted_binds = sorted(bindings, key=lambda x: (x.protocol, x.local_port))
    for b in sorted_binds:
        local_addr = b.local_address.split("%")[0]
        peer_addr = b.remote_address.split("%")[0]
        peer_addr_trunc = peer_addr[:22]
        print(
            f"{b.protocol:<5} | {local_addr:<22} | {b.local_port:<6} | {peer_addr_trunc:<22} | {b.remote_port:<6} | {b.state:<12} | {b.pid:<6} | {b.process_name}"
        )
    print("-" * 110 + "\n")


def send_over_memory_bus(host, port, data_bytes, offset=0, page_size=4096):
    log(f"Initiating High-Speed Memory Bus link to {host}:{port}...", color=BLUE)
    try:
        import socket
        import struct
        import binascii

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except Exception:
            pass
        sock.connect((host, port))

        # Framing details
        MAGIC = 0xDEADBEEF
        HEADER_FORMAT = "!IIIII"

        file_size = len(data_bytes)
        total_pages = (file_size + page_size - 1) // page_size
        log(
            f"Paging agent mind state ({file_size} B) into {total_pages} pages...",
            color=BLUE,
        )

        for page_idx in range(total_pages):
            page_offset = offset + (page_idx * page_size)
            chunk_data = data_bytes[page_idx * page_size : (page_idx + 1) * page_size]
            actual_len = len(chunk_data)

            # Pad last chunk
            if actual_len < page_size:
                chunk_data = chunk_data + b"\x00" * (page_size - actual_len)
                actual_len = page_size

            crc = binascii.crc32(chunk_data) & 0xFFFFFFFF
            header = struct.pack(
                HEADER_FORMAT, MAGIC, page_idx, page_offset, actual_len, crc
            )
            sock.sendall(header + chunk_data)

        sock.close()
        log(
            f"High-Speed RAM state copy complete! {file_size} bytes synced in RAM.",
            color=GREEN,
        )
        return True
    except Exception as e:
        log(f"Memory Bus sync failed: {e}", color=RED)
        return False


def run_suite(host, port, args):
    target = f"{host}:{port}"
    log(
        f"Establishing insecure connection channel to {BOLD}{target}{RESET}...",
        color=BLUE,
    )

    channel = grpc.insecure_channel(target)
    stub = sync_pb2_grpc.AgentSyncStub(channel)

    client_id = os.getenv("ANTIGRAVITY_NODE_ID", "LAPTOP-TRAINING-AGENT")

    grpc_online = False
    server_id = "UNKNOWN"

    # 1. PING TEST
    log("Executing RPC: Ping...", color=GOLD)
    try:
        t0 = time.time()
        ping_res = stub.Ping(
            sync_pb2.PingRequest(client_id=client_id, timestamp=int(t0 * 1000))
        )
        t1 = time.time()
        latency = (t1 - t0) * 1000
        log(
            f"Ping Ack received! Server: {BOLD}{ping_res.server_id}{RESET} | Status: {ping_res.status} | Latency: {latency:.2f} ms",
            color=GREEN,
        )
        grpc_online = True
        server_id = ping_res.server_id
    except Exception as e:
        log(f"Ping failed: {e}", color=RED)
        log(
            f"{BOLD}{RED}[WARNING] gRPC control plane is UNRESPONSIVE at {target}!{RESET}",
            color=RED,
        )
        log(
            f"{BOLD}{GOLD}[FALLBACK] Failover: Initiating SSH Remote Execution plane...{RESET}",
            color=GOLD,
        )

    # A. ADD USER
    if args.adduser:
        if grpc_online:
            log(
                f"Executing RPC: CreateUser for {BOLD}{args.adduser}{RESET}...",
                color=GOLD,
            )
            try:
                req = sync_pb2.CreateUserRequest(
                    username=args.adduser,
                    password=args.password or "",
                    uid=args.uid or 0,
                    group=args.group or "",
                    create_home=not args.no_create_home,
                    shell=args.shell,
                )
                res = stub.CreateUser(req)
                if res.success:
                    log(f"Success: {res.message}", color=GREEN)
                    for det in res.details:
                        log(f"  - {det}", color=GREEN)
                else:
                    log(f"Failed: {res.message}", color=RED)
                    for det in res.details:
                        log(f"  - {det}", color=RED)
            except Exception as e:
                log(f"RPC CreateUser failed: {e}", color=RED)
                grpc_online = False

        if not grpc_online:
            cmd = ["sudo", "useradd"]
            if not args.no_create_home:
                cmd.append("-m")
            if args.shell:
                cmd += ["-s", args.shell]
            if args.uid:
                cmd += ["-u", str(args.uid)]
            if args.group:
                cmd += ["-g", args.group]
            cmd.append(args.adduser)

            cmd_str = " ".join(cmd)
            if args.password:
                cmd_str += f" && echo '{args.adduser}:{args.password}' | sudo chpasswd"

            code, stdout, stderr = run_via_ssh(host, cmd_str)
            if code == 0:
                log(
                    f"Success: Created user {args.adduser} via SSH fallback.",
                    color=GREEN,
                )
            else:
                log(
                    f"Failed to create user via SSH fallback (code {code}): {stderr.strip()}",
                    color=RED,
                )
        return

    # B. CHANGE PASSWORD
    elif args.chpasswd:
        if not args.password:
            log(
                "Error: --password <new_password> is required to change password.",
                color=RED,
            )
            return

        if grpc_online:
            log(
                f"Executing RPC: ChangePassword for {BOLD}{args.chpasswd}{RESET}...",
                color=GOLD,
            )
            try:
                req = sync_pb2.ChangePasswordRequest(
                    username=args.chpasswd, new_password=args.password
                )
                res = stub.ChangePassword(req)
                if res.success:
                    log(f"Success: {res.message}", color=GREEN)
                else:
                    log(f"Failed: {res.message}", color=RED)
            except Exception as e:
                log(f"RPC ChangePassword failed: {e}", color=RED)
                grpc_online = False

        if not grpc_online:
            cmd_str = f"echo '{args.chpasswd}:{args.password}' | sudo chpasswd"
            code, stdout, stderr = run_via_ssh(host, cmd_str)
            if code == 0:
                log(
                    f"Success: Changed password for {args.chpasswd} via SSH fallback.",
                    color=GREEN,
                )
            else:
                log(
                    f"Failed to change password via SSH (code {code}): {stderr.strip()}",
                    color=RED,
                )
        return

    # C. MANAGE GROUP
    elif args.manage_group:
        if not args.action:
            log("Error: --action <create|add|remove> is required.", color=RED)
            return

        action_map = {
            "add": sync_pb2.ManageGroupRequest.ADD_TO_GROUP,
            "remove": sync_pb2.ManageGroupRequest.REMOVE_FROM_GROUP,
            "create": sync_pb2.ManageGroupRequest.CREATE_GROUP,
        }

        action_enum = action_map.get(args.action.lower())
        if action_enum is None:
            log(
                f"Error: Invalid action '{args.action}'. Must be add, remove, or create.",
                color=RED,
            )
            return

        if (
            action_enum
            in [
                sync_pb2.ManageGroupRequest.ADD_TO_GROUP,
                sync_pb2.ManageGroupRequest.REMOVE_FROM_GROUP,
            ]
            and not args.username
        ):
            log(
                "Error: --username <username> is required when adding or removing from a group.",
                color=RED,
            )
            return

        if grpc_online:
            log(
                f"Executing RPC: ManageGroup for group {BOLD}{args.manage_group}{RESET}...",
                color=GOLD,
            )
            try:
                req = sync_pb2.ManageGroupRequest(
                    username=args.username or "",
                    group_name=args.manage_group,
                    action=action_enum,
                    gid=args.gid or 0,
                )
                res = stub.ManageGroup(req)
                if res.success:
                    log(f"Success: {res.message}", color=GREEN)
                    for det in res.details:
                        log(f"  - {det}", color=GREEN)
                else:
                    log(f"Failed: {res.message}", color=RED)
            except Exception as e:
                log(f"RPC ManageGroup failed: {e}", color=RED)
                grpc_online = False

        if not grpc_online:
            if args.action.lower() == "create":
                cmd = ["sudo", "groupadd"]
                if args.gid:
                    cmd += ["-g", str(args.gid)]
                cmd.append(args.manage_group)
                cmd_str = " ".join(cmd)
            elif args.action.lower() == "add":
                cmd_str = f"sudo usermod -aG {args.manage_group} {args.username}"
            elif args.action.lower() == "remove":
                cmd_str = f"sudo gpasswd -d {args.username} {args.manage_group}"

            code, stdout, stderr = run_via_ssh(host, cmd_str)
            if code == 0:
                log(
                    f"Success: Group management action '{args.action}' completed via SSH fallback.",
                    color=GREEN,
                )
            else:
                log(
                    f"Failed to perform group management via SSH (code {code}): {stderr.strip()}",
                    color=RED,
                )
        return

    # D. LIST USERS
    elif args.list_users:
        if grpc_online:
            log("Executing RPC: ListUsers...", color=GOLD)
            try:
                req = sync_pb2.UserDirectoryRequest()
                res = stub.ListUsers(req)
                print(
                    f"\n{BOLD}{GOLD}--- USER DIRECTORY ON REMOTE NODE {server_id} ---{RESET}"
                )
                print(
                    f"{'USERNAME':<16} | {'UID':<6} | {'GID':<6} | {'PRIMARY GROUP':<16} | {'SHELL':<16} | {'SECONDARY GROUPS'}"
                )
                print("-" * 90)
                for u in res.users:
                    sg_str = ", ".join(u.groups) or "None"
                    print(
                        f"{u.username:<16} | {u.uid:<6} | {u.gid:<6} | {u.primary_group:<16} | {u.shell:<16} | {sg_str}"
                    )
                print("-" * 90 + "\n")
            except Exception as e:
                log(f"RPC ListUsers failed: {e}", color=RED)
                grpc_online = False

        if not grpc_online:
            remote_code = (
                "import pwd, grp, json; "
                "users = []; "
                "for p in pwd.getpwall(): "
                "    if p.pw_uid >= 1000 and p.pw_name != 'nobody': "
                "        try: primary = grp.getgrgid(p.pw_gid).gr_name "
                "        except KeyError: primary = str(p.pw_gid) "
                "        secs = [g.gr_name for g in grp.getgrall() if p.pw_name in g.gr_mem]; "
                "        users.append({'username': p.pw_name, 'uid': p.pw_uid, 'gid': p.pw_gid, 'primary_group': primary, 'groups': secs, 'home_dir': p.pw_dir, 'shell': p.pw_shell}); "
                "print(json.dumps(users))"
            )
            code, stdout, stderr = run_via_ssh(host, f'python3 -c "{remote_code}"')
            if code == 0:
                try:
                    users_data = json.loads(stdout.strip())
                    print(
                        f"\n{BOLD}{GOLD}--- USER DIRECTORY ON REMOTE NODE {host} (SSH FALLBACK) ---{RESET}"
                    )
                    print(
                        f"{'USERNAME':<16} | {'UID':<6} | {'GID':<6} | {'PRIMARY GROUP':<16} | {'SHELL':<16} | {'SECONDARY GROUPS'}"
                    )
                    print("-" * 90)
                    for u in users_data:
                        sg_str = ", ".join(u["groups"]) or "None"
                        print(
                            f"{u['username']:<16} | {u['uid']:<6} | {u['gid']:<6} | {u['primary_group']:<16} | {u['shell']:<16} | {sg_str}"
                        )
                    print("-" * 90 + "\n")
                except Exception as ex:
                    log(
                        f"Failed to parse user directory JSON from SSH output: {ex}",
                        color=RED,
                    )
                    print(f"Raw Output:\n{stdout}")
            else:
                log(
                    f"Failed to fetch user directory via SSH fallback (code {code}): {stderr.strip()}",
                    color=RED,
                )
        return

    # E. SYNC USERS
    elif args.sync_users:
        log("Collecting local users for mesh synchronization...", color=GOLD)
        try:
            import pwd
            import grp

            local_users = []
            for p in pwd.getpwall():
                if p.pw_uid >= 1000 and p.pw_name != "nobody":
                    primary_group = ""
                    try:
                        primary_group = grp.getgrgid(p.pw_gid).gr_name
                    except KeyError:
                        primary_group = str(p.pw_gid)

                    groups = []
                    for g in grp.getgrall():
                        if p.pw_name in g.gr_mem:
                            groups.append(g.gr_name)

                    local_users.append(
                        sync_pb2.UserInfo(
                            username=p.pw_name,
                            uid=p.pw_uid,
                            gid=p.pw_gid,
                            primary_group=primary_group,
                            groups=groups,
                            home_dir=p.pw_dir,
                            shell=p.pw_shell,
                        )
                    )
            log(f"Found {len(local_users)} local users to synchronize.", color=BLUE)
        except Exception as e:
            log(f"Failed to query local users: {e}", color=RED)
            return

        if not local_users:
            log("No local users found with UID >= 1000 to synchronize.", color=GOLD)
            return

        if grpc_online:
            log(
                f"Executing RPC: SyncUsers to remote target {BOLD}{target}{RESET}...",
                color=GOLD,
            )
            try:
                req = sync_pb2.SyncUsersRequest(users=local_users)
                res = stub.SyncUsers(req)
                if res.success:
                    log(f"Success: {res.message}", color=GREEN)
                    for det in res.details:
                        log(f"  - {det}", color=GREEN)
                else:
                    log(f"Synchronization failed: {res.message}", color=RED)
                    for det in res.details:
                        log(f"  - {det}", color=RED)
            except Exception as e:
                log(f"RPC SyncUsers failed: {e}", color=RED)
                grpc_online = False

        if not grpc_online:
            log(
                f"Re-routing synchronization over SSH for {len(local_users)} users...",
                color=GOLD,
            )
            details = []
            success_count = 0
            for u in local_users:
                check_cmd = f"id -u {u.username}"
                code, stdout, stderr = run_via_ssh(host, check_cmd)
                if code != 0:
                    cmd = ["sudo", "useradd", "-m", "-s", u.shell, "-u", str(u.uid)]
                    cmd.append(u.username)
                    cmd_str = " ".join(cmd)
                    c_code, c_stdout, c_stderr = run_via_ssh(host, cmd_str)
                    if c_code == 0:
                        details.append(
                            f"SSH Sync: Created user {u.username} (UID={u.uid})"
                        )
                        success_count += 1
                    else:
                        details.append(
                            f"SSH Sync Error: Failed to create user {u.username}: {c_stderr.strip()}"
                        )
                else:
                    query_cmd = f"getent passwd {u.username}"
                    q_code, q_stdout, q_stderr = run_via_ssh(host, query_cmd)
                    if q_code == 0:
                        passwd_parts = q_stdout.strip().split(":")
                        existing_uid = int(passwd_parts[2])
                        existing_gid = int(passwd_parts[3])
                        existing_home = passwd_parts[5]
                        existing_shell = passwd_parts[6]

                        mod_cmd = ["sudo", "usermod"]
                        needs_update = False
                        if u.uid != existing_uid:
                            mod_cmd += ["-u", str(u.uid), "-o"]
                            needs_update = True
                        if u.shell != existing_shell:
                            mod_cmd += ["-s", u.shell]
                            needs_update = True
                        if u.home_dir != existing_home:
                            mod_cmd += ["-d", u.home_dir, "-m"]
                            needs_update = True

                        if needs_update:
                            mod_cmd.append(u.username)
                            m_code, m_stdout, m_stderr = run_via_ssh(
                                host, " ".join(mod_cmd)
                            )
                            if m_code == 0:
                                details.append(
                                    f"SSH Sync: Aligned properties for user {u.username}"
                                )
                                if u.uid != existing_uid:
                                    run_via_ssh(
                                        host,
                                        f"sudo chown -R {u.username}:{u.gid} {u.home_dir}",
                                    )
                            else:
                                details.append(
                                    f"SSH Sync Error: Failed to align {u.username}: {m_stderr.strip()}"
                                )
                        success_count += 1
                    else:
                        details.append(
                            f"SSH Sync Error: Failed to query existing user {u.username}"
                        )

            log(
                f"SSH User Sync complete. Successful: {success_count}/{len(local_users)}",
                color=GREEN,
            )
            for det in details:
                log(f"  - {det}", color=GREEN if "Error" not in det else RED)
        return

    # F. PROCESS DIRECTORY LISTING
    elif args.ps:
        if grpc_online:
            log(
                f"Executing RPC: GetProcessDirectory on {BOLD}{target}{RESET}...",
                color=GOLD,
            )
            try:
                req = sync_pb2.ProcessDirectoryRequest()
                res = stub.GetProcessDirectory(req)
                print_processes_table(
                    res.processes, f"gRPC CONTROL PLANE ({server_id})"
                )
            except Exception as e:
                log(f"RPC GetProcessDirectory failed: {e}", color=RED)
                grpc_online = False

        if not grpc_online:
            ssh_cmd_str = "ps -eo pid,ppid,user,stat,%cpu,%mem,comm,args --no-headers"
            code, stdout, stderr = run_via_ssh(host, ssh_cmd_str)
            if code == 0:
                processes = parse_ssh_ps_output(stdout)
                print_processes_table(processes, f"SSH FALLBACK PLANE ({host})")
            else:
                log(
                    f"SSH fallback failed with code {code}: {stderr.strip()}", color=RED
                )
        return

    # G. PORT BINDINGS LISTING
    elif args.ports:
        if grpc_online:
            log(
                f"Executing RPC: GetPortBindings on {BOLD}{target}{RESET}...",
                color=GOLD,
            )
            try:
                req = sync_pb2.PortBindingsRequest()
                res = stub.GetPortBindings(req)
                print_ports_table(res.bindings, f"gRPC CONTROL PLANE ({server_id})")
            except Exception as e:
                log(f"RPC GetPortBindings failed: {e}", color=RED)
                grpc_online = False

        if not grpc_online:
            code_tcp, stdout_tcp, stderr_tcp = run_via_ssh(host, "sudo ss -tanp")
            code_udp, stdout_udp, stderr_udp = run_via_ssh(host, "sudo ss -uanp")

            bindings = []
            if code_tcp == 0 or code_udp == 0:
                if code_tcp == 0:
                    bindings += parse_ssh_ss_output(stdout_tcp, "TCP")
                if code_udp == 0:
                    bindings += parse_ssh_ss_output(stdout_udp, "UDP")
                print_ports_table(bindings, f"SSH FALLBACK PLANE ({host})")
            else:
                log(
                    f"SSH fallback failed. TCP code {code_tcp}: {stderr_tcp} | UDP code {code_udp}: {stderr_udp}",
                    color=RED,
                )
        return

    # H. PROCESS MANAGEMENT
    elif any([args.kill, args.term, args.stop, args.cont, args.nice]):
        pid = args.kill or args.term or args.stop or args.cont or args.nice
        action = (
            "KILL"
            if args.kill
            else (
                "TERM"
                if args.term
                else "STOP" if args.stop else "CONT" if args.cont else "NICE"
            )
        )

        if grpc_online:
            log(
                f"Executing RPC: ManageProcess on PID {BOLD}{pid}{RESET} (Action: {action})...",
                color=RED,
            )
            try:
                req = sync_pb2.ProcessActionRequest(
                    pid=pid, action=action, priority=args.priority
                )
                res = stub.ManageProcess(req)
                if res.exit_code == 0:
                    log(f"Success: Process {pid} {action} complete.", color=GREEN)
                else:
                    log(f"Error: {res.stderr.strip()}", color=RED)
            except Exception as e:
                log(f"RPC ManageProcess failed: {e}", color=RED)
        return

    # I. SYSTEM METRICS
    elif args.metrics:
        if grpc_online:
            log(
                f"Executing RPC: GetSystemMetrics on {BOLD}{target}{RESET} - Diving to Silicon...",
                color=MAGENTA,
            )
            try:
                req = sync_pb2.SystemMetricsRequest()
                res = stub.GetSystemMetrics(req)

                print(
                    f"\n{BOLD}{CYAN}--- SILICON & HARDWARE TELEMETRY ({server_id}) ---{RESET}"
                )
                print(f"{BOLD}Kernel Version:{RESET} {res.kernel_version}")
                print(f"{BOLD}Uptime:{RESET}         {res.uptime}")
                print(
                    f"{BOLD}Load Average:{RESET}   {res.load_avg_1:.2f}, {res.load_avg_5:.2f}, {res.load_avg_15:.2f}"
                )

                print(f"\n{BOLD}CPU CORE STATUS:{RESET}")
                print(f"{'CORE':<8} | {'CLOCK (MHz)':<12} | {'TEMP (°C)':<12}")
                print("-" * 40)
                for c in res.cpu_cores:
                    temp_str = (
                        f"{c.temperature_c:.1f}" if c.temperature_c > 0 else "N/A"
                    )
                    print(f"#{c.core_id:<7} | {c.clock_mhz:<12.1f} | {temp_str:<12}")

                print(f"\n{BOLD}MEMORY UTILIZATION:{RESET}")
                mem = res.memory
                print(f"Total:   {mem.total_kb / 1024:.1f} MB")
                print(
                    f"Used:    {mem.used_kb / 1024:.1f} MB ({(mem.used_kb / mem.total_kb * 100 if mem.total_kb > 0 else 0):.1f}%)"
                )
                print(f"Free:    {mem.free_kb / 1024:.1f} MB")
                print(f"Shared:  {mem.shared_kb / 1024:.1f} MB")
                print(f"Cached:  {mem.cached_kb / 1024:.1f} MB")
                print("-" * 40)
            except Exception as e:
                log(f"RPC GetSystemMetrics failed: {e}", color=RED)
        return

    # J. REMOTE COMMAND EXECUTION
    elif args.exec:
        if grpc_online:
            log(
                f"Executing RPC: RemoteExecute for command '{BOLD}{args.exec}{RESET}' on {BOLD}{target}{RESET}...",
                color=GOLD,
            )
            try:
                cmd_parts = args.exec.strip().split()
                if not cmd_parts:
                    log("Error: Command is empty.", color=RED)
                    return
                primary_cmd = cmd_parts[0]
                cmd_args = cmd_parts[1:]

                req = sync_pb2.CommandPayload(command=primary_cmd, args=cmd_args)
                res = stub.RemoteExecute(req)
                print(
                    f"\n{BOLD}{GOLD}--- COMMAND EXECUTION VIA gRPC CONTROL PLANE ---{RESET}"
                )
                print(f"{BOLD}Exit Code:{RESET} {res.exit_code}")
                if res.stdout:
                    print(f"{BOLD}STDOUT:{RESET}\n{res.stdout}")
                if res.stderr:
                    print(f"{BOLD}STDERR:{RESET}\n{res.stderr}")
                print("-" * 50 + "\n")
            except Exception as e:
                log(f"RPC RemoteExecute failed: {e}", color=RED)
                grpc_online = False

        if not grpc_online:
            code, stdout, stderr = run_via_ssh(host, args.exec)
            print(
                f"\n{BOLD}{GOLD}--- COMMAND EXECUTION VIA SSH FALLBACK PLANE ---{RESET}"
            )
            print(f"{BOLD}Exit Code:{RESET} {code}")
            if stdout:
                print(f"{BOLD}STDOUT:{RESET}\n{stdout}")
            if stderr:
                print(f"{BOLD}STDERR:{RESET}\n{stderr}")
            print("-" * 50 + "\n")
        return

    # I. VIRTUAL AGENT TRAVEL (TELEPORTATION)
    elif args.travel:
        # 1. Gather metrics & local models to build agent mind
        models = get_local_ollama_models()
        metrics = get_system_metrics()

        import platform

        mind = {
            "agent_id": client_id,
            "timestamp": int(time.time() * 1000),
            "active_model": models[0] if models else "gemma2:2b",
            "host_env": {
                "os": platform.system() + " " + platform.release(),
                "processor": platform.processor(),
                "python_version": platform.python_version(),
            },
            "history": [
                f"Mesh agent spawned on {client_id}.",
                "Shared memory segment allocated.",
                f"Virtual migration initiated to host: {host}.",
            ],
        }
        mind_bytes = json.dumps(mind).encode("utf-8")
        state_size = len(mind_bytes)

        # 2. Fast-copy mind payload over High-Speed Memory Bus
        bus_port = args.bus_port or 11111
        bus_success = send_over_memory_bus(host, bus_port, mind_bytes, offset=0)
        if not bus_success:
            log("Virtual travel aborted: Memory Bus transmission failed.", color=RED)
            return

        # 3. Trigger remote materialization / execution
        if grpc_online:
            log(
                f"Executing RPC: TeleportAgent to materialize agent on {target}...",
                color=GOLD,
            )
            try:
                req = sync_pb2.TeleportRequest(
                    source_node_id=client_id,
                    target_node_id="UNKNOWN",
                    memory_bus_offset=0,
                    state_size=state_size,
                    run_command=args.travel,
                )
                res = stub.TeleportAgent(req)
                if res.success:
                    print(
                        f"\n{BOLD}{GREEN}--- VIRTUAL TRAVEL MATERIALIZATION SUCCESSFUL ---{RESET}"
                    )
                    print(f"{BOLD}Status Msg:{RESET} {res.message}")
                    if res.execution_stdout:
                        print(f"{BOLD}Execution STDOUT:{RESET}\n{res.execution_stdout}")
                    if res.execution_stderr:
                        print(f"{BOLD}Execution STDERR:{RESET}\n{res.execution_stderr}")
                    print("-" * 50 + "\n")
                else:
                    log(
                        f"Virtual Travel Materialization rejected by remote node: {res.message}",
                        color=RED,
                    )
                    grpc_online = False
            except Exception as e:
                log(f"RPC TeleportAgent failed: {e}", color=RED)
                grpc_online = False

        # 4. Resilient Fallback to SSH Teleportation Trigger
        if not grpc_online:
            log(
                "[WARNING] gRPC plane unresponsive! Triggering SSH materialization...",
                color=GOLD,
            )
            # Create a Python one-liner command to read the mmap file, decode JSON mind, and run command on destination!
            ssh_py_cmd = f"""python3 -c "import mmap, json, subprocess; f=open('/dev/shm/sovereign_page_table', 'r+b') if subprocess.run(['test', '-f', '/dev/shm/sovereign_page_table']).returncode==0 else open('/tmp/sovereign_page_table', 'r+b'); mem=mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_WRITE); mem.seek(0); data=mem.read({state_size}).decode('utf-8').rstrip('\\x00').strip(); mind=json.loads(data); print('Reconstructed Agent Mind from RAM: ID:', mind.get('agent_id')); subprocess.run({args.travel.split()})" """

            code, stdout, stderr = run_via_ssh(host, ssh_py_cmd)
            print(f"\n{BOLD}{GOLD}--- VIRTUAL TRAVEL VIA SSH FALLBACK PLANE ---{RESET}")
            print(f"{BOLD}Exit Code:{RESET} {code}")
            if stdout:
                print(f"{BOLD}STDOUT:{RESET}\n{stdout}")
            if stderr:
                print(f"{BOLD}STDERR:{RESET}\n{stderr}")
            print("-" * 50 + "\n")

        return

    # J. AGENT PEDIGREE TRACING
    elif args.pedigree is not None:
        target_agent = args.pedigree or client_id
        if grpc_online:
            log(
                f"Executing RPC: TracePedigree for '{BOLD}{target_agent}{RESET}' on {BOLD}{target}{RESET}...",
                color=GOLD,
            )
            try:
                req = sync_pb2.PedigreeRequest(agent_id=target_agent)
                res = stub.TracePedigree(req)

                print(
                    f"\n{BOLD}{GREEN}--- SWARM PEDIGREE LINEAGE PATH BACK TO AGENT 0 ---{RESET}"
                )
                print(f"{BOLD}Agent:{RESET} {target_agent}")
                print(f"{BOLD}Ancestry Lineage Sequence:{RESET}")
                for idx, node in enumerate(res.pedigree_path):
                    indent = "  " * idx
                    connector = "└── " if idx > 0 else "⭐ "
                    print(
                        f"{indent}{connector}{BOLD}{node.agent_id}{RESET} ({node.name})"
                    )
                    print(
                        f"{indent}    Layer {node.layer_level} | Specialty: {GOLD}{node.specialty}{RESET} -> Subspecialty: {CYAN}{node.subspecialty}{RESET}"
                    )
                print("-" * 70)

                print(f"\n{res.collective_specialty_cooperation_map}\n")

            except Exception as e:
                log(f"RPC TracePedigree failed: {e}", color=RED)
                grpc_online = False

        if not grpc_online:
            log(
                "[WARNING] gRPC plane unresponsive! Querying SQLite Pedigree DB over SSH...",
                color=GOLD,
            )
            ssh_py_cmd = f"""python3 -c "import sqlite3; conn=sqlite3.connect('/home/aellok/sovereign_mesh/agent_pedigree.db'); cur=conn.cursor(); cur.execute('''WITH RECURSIVE lineage AS (SELECT agent_id, name, parent_agent_id, layer_level, specialty, subspecialty FROM agents WHERE agent_id=\\'{target_agent}\\' UNION ALL SELECT a.agent_id, a.name, a.parent_agent_id, a.layer_level, a.specialty, a.subspecialty FROM agents a JOIN lineage l ON l.parent_agent_id=a.agent_id) SELECT agent_id, name, layer_level, specialty, subspecialty FROM lineage ORDER BY layer_level ASC'''); rows=cur.fetchall(); print('\\n--- SWARM PEDIGREE LINEAGE PATH BACK TO AGENT 0 ---'); [print('  '*i + ('└── ' if i>0 else '⭐ ') + r[0] + ' (' + r[1] + ')\\n' + '  '*i + '    Layer ' + str(r[2]) + ' | Specialty: ' + r[3] + ' -> Subspecialty: ' + r[4]) for i, r in enumerate(rows)]; cur.execute('SELECT agent_id, name, layer_level, specialty, subspecialty FROM agents ORDER BY layer_level ASC'); all_ags=cur.fetchall(); print('\\n🌐 7-LAYER COOPERATIVE SWARM NETWORK MAP (Agent 0 Ancestry)'); print('=============================================================='); layers={{}}; [layers.setdefault(a[2], []).append(a) for a in all_ags]; [print('\\nLayer ' + str(l) + ':\\n' + '\\n'.join(['  ├── ' + ag[0] + ' (' + ag[1] + ') - Specialty: ' + ag[3] + ' -> Subspecialty: ' + ag[4] for ag in layers[l]])) for l in sorted(layers.keys())]" """

            code, stdout, stderr = run_via_ssh(host, ssh_py_cmd)
            print(
                f"\n{BOLD}{GOLD}--- SWARM PEDIGREE TRACE VIA SSH FALLBACK PLANE ---{RESET}"
            )
            print(f"{BOLD}Exit Code:{RESET} {code}")
            if stdout:
                print(f"{BOLD}STDOUT:{RESET}\n{stdout}")
            if stderr:
                print(f"{BOLD}STDERR:{RESET}\n{stderr}")
            print("-" * 50 + "\n")

        return

    # K. SWARM MUTATION PROPOSAL
    elif args.propose:
        if "=" not in args.propose:
            log("Error: Proposal format must be '--propose <key>=<value>'", color=RED)
            return

        target_key, proposed_value = args.propose.split("=", 1)
        reason = args.reason or "Sovereign Swarm direct mutation override."

        if grpc_online:
            log(
                f"Executing RPC: ProposeSwarmMutation for '{BOLD}{target_key}{RESET}' -> '{BOLD}{proposed_value}{RESET}' on {BOLD}{target}{RESET}...",
                color=GOLD,
            )
            try:
                req = sync_pb2.MutationRequest(
                    proposer_agent_id=client_id,
                    target_key=target_key,
                    proposed_value=proposed_value,
                    change_reason=reason,
                )
                res = stub.ProposeSwarmMutation(req)

                print(f"\n{BOLD}{GREEN}--- SWARM MUTATION PROPOSAL SUMMARY ---{RESET}")
                print(f"{BOLD}Status:{RESET} {res.status}")
                print(f"{BOLD}Consensus Ratio:{RESET} {res.consensus_ratio}")
                print(f"{BOLD}Consensus Reached:{RESET} {res.consensus_reached}")
                if res.block_index > 0:
                    print(f"{BOLD}Ledger Block Index:{RESET} #{res.block_index}")
                    print(
                        f"{BOLD}Block Cryptographic Hash:{RESET} {GOLD}{res.block_hash}{RESET}"
                    )

                print(f"\n{BOLD}Representative Vote Mapping:{RESET}")
                for vote in res.votes:
                    marker = (
                        f"{GREEN}✔ AGREE{RESET}"
                        if vote.vote_agree
                        else f"{RED}✘ DISAGREE{RESET}"
                    )
                    print(
                        f"  [{marker}] {BOLD}{vote.agent_id}{RESET} - Rationale: {vote.rationale}"
                    )

                if res.minority_report:
                    print(f"\n{res.minority_report}\n")

            except Exception as e:
                log(f"RPC ProposeSwarmMutation failed: {e}", color=RED)
                grpc_online = False

        if not grpc_online:
            log(
                "[WARNING] gRPC plane unresponsive! Cannot safely evaluate consensus over SSH fallback (4/5 consensus requires gRPC control plane orchestration). Try starting the gRPC service.",
                color=RED,
            )
        return

    # L. SWARM LEDGER AUDIT
    elif args.ledger:
        if grpc_online:
            log(
                f"Executing RPC: QuerySwarmLedger on {BOLD}{target}{RESET}...",
                color=GOLD,
            )
            try:
                req = sync_pb2.LedgerQueryRequest()
                res = stub.QuerySwarmLedger(req)

                print(
                    f"\n{BOLD}{GREEN}--- IMMUTABLE LEDGER BLOCKCHAIN AUDIT ---{RESET}"
                )
                print(
                    f"{BOLD}Validation Status:{RESET} {GOLD}{res.chain_validation_status}{RESET}"
                )
                print("=" * 100)

                for block in res.blocks:
                    print(
                        f"{BOLD}Block #{block.block_index}{RESET} | Proposer: {BOLD}{block.agent_id}{RESET} | Timestamp: {block.timestamp}"
                    )
                    print(
                        f"  {BOLD}Prev Hash:{RESET} {block.previous_hash[:16]}... | {BOLD}Block Hash:{RESET} {GOLD}{block.block_hash[:16]}...{RESET}"
                    )

                    payload = json.loads(block.mutation_payload)
                    print(
                        f"  {BOLD}Payload:  {RESET} {json.dumps(payload, indent=2).replace(chr(10), chr(10)+'  ')}"
                    )

                    if block.minority_report and block.minority_report != "None":
                        print(f"  {BOLD}Minority Report Summary:{RESET}")
                        lines = block.minority_report.split("\n")
                        for line in lines[:8]:
                            print(f"    {line}")
                        if len(lines) > 8:
                            print(
                                "    [Truncated... Check pedigree database for complete logs]"
                            )
                    print("-" * 100)

            except Exception as e:
                log(f"RPC QuerySwarmLedger failed: {e}", color=RED)
                grpc_online = False

        if not grpc_online:
            log(
                "[WARNING] gRPC plane unresponsive! Reading SQLite Ledger directly over SSH...",
                color=GOLD,
            )
            ssh_py_cmd = """python3 -c "import sqlite3, json; conn=sqlite3.connect('/home/aellok/sovereign_mesh/agent_pedigree.db'); cur=conn.cursor(); cur.execute('SELECT block_index, previous_hash, timestamp, agent_id, mutation_payload, block_hash FROM ledger ORDER BY block_index ASC'); rows=cur.fetchall(); print('\\n--- SWARM LEDGER AUDIT VIA SSH FALLBACK ---'); [print('Block #' + str(r[0]) + ' | Proposer: ' + r[3] + ' | Time: ' + r[2] + '\\n  Prev: ' + r[1][:16] + '... | Hash: ' + r[5][:16] + '...\\n  Payload: ' + r[4]) for r in rows]" """

            code, stdout, stderr = run_via_ssh(host, ssh_py_cmd)
            print(
                f"\n{BOLD}{GOLD}--- IMMUTABLE LEDGER VIA SSH FALLBACK PLANE ---{RESET}"
            )
            print(f"{BOLD}Exit Code:{RESET} {code}")
            if stdout:
                print(f"{BOLD}STDOUT:{RESET}\n{stdout}")
            if stderr:
                print(f"{BOLD}STDERR:{RESET}\n{stderr}")
            print("-" * 50 + "\n")
        return

    # M. JETWEB TIME MACHINE OVERRIDE
    elif args.timemachine is not None:
        target_idx = int(args.timemachine)
        if not args.rewrite:
            log(
                "Error: Direct timeline mutation rewrite parameter '--rewrite <key>=<value>' is required to execute override.",
                color=RED,
            )
            return

        if "=" not in args.rewrite:
            log("Error: Override format must be '--rewrite <key>=<value>'", color=RED)
            return

        target_key, proposed_value = args.rewrite.split("=", 1)
        reason = args.reason or "Jetweb Time Machine Operator timeline bifurcation."

        if grpc_online:
            log(
                f"Executing RPC: TimeTravelOverride for Destination Block #{target_idx}...",
                color=CYAN,
            )
            try:
                req = sync_pb2.TimeTravelRequest(
                    target_block_index=target_idx,
                    new_target_key=target_key,
                    new_proposed_value=proposed_value,
                    override_reason=reason,
                )
                res = stub.TimeTravelOverride(req)

                print(f"\n{BOLD}{CYAN} ⏰ --- JETWEB TIME MACHINE ACTIVATED ---{RESET}")
                print(
                    f"{BOLD}Overriding Target Decision at Block Index:{RESET} #{target_idx}"
                )
                print(
                    f"{BOLD}Timeline State Refactor Action:{RESET} Set {target_key} = {proposed_value}"
                )
                print(f"{BOLD}Status:{RESET} {'SUCCESS' if res.success else 'FAILED'}")
                print(
                    f"{BOLD}Audit Verification Status:{RESET} {GOLD}{res.new_chain_validation_status}{RESET}"
                )
                print(f"{BOLD}Message:{RESET} {res.message}")

                print(f"\n{BOLD}Cascade Hash Re-mining & Relational Tree Logs:{RESET}")
                for log_line in res.refactor_logs:
                    print(f"  {log_line}")
                print("-" * 80 + "\n")

            except Exception as e:
                log(f"Time Machine Override failed: {e}", color=RED)
                grpc_online = False

        if not grpc_online:
            log(
                "[WARNING] gRPC plane unresponsive! Cannot safely compute blockchain fork or re-mine cascade hashes over SSH fallback.",
                color=RED,
            )
        return

    # N. SWARM FORENSIC DECISION ACCOUNTING
    elif args.forensics:
        target_idx = 0
        if args.forensics.isdigit():
            target_idx = int(args.forensics)

        if grpc_online:
            log(
                f"Executing RPC: ForensicAudit (Block Filter: {target_idx or 'ALL'})...",
                color=GOLD,
            )
            try:
                req = sync_pb2.ForensicRequest(target_block_index=target_idx)
                res = stub.ForensicAudit(req)

                print(
                    f"\n{BOLD}{GREEN}🕵️ --- SOVEREIGN SWARM FORENSIC ACCOUNTING AUDIT ---{RESET}"
                )
                print(
                    f"{BOLD}Active relational decision logs and ancestry state traces:{RESET}"
                )
                print("=" * 110)

                for node in res.timeline_nodes:
                    payload = json.loads(node.mutation_payload)
                    votes = json.loads(node.consensus_votes)

                    print(
                        f"{BOLD}Block Index:{RESET} #{node.block_index} | {BOLD}Timestamp:{RESET} {node.timestamp} | {BOLD}Agent:{RESET} {node.agent_id}"
                    )
                    print(f"  {BOLD}Hash:{RESET} {GOLD}{node.block_hash}{RESET}")
                    print(f"  {BOLD}Decision Event Payload:{RESET}")
                    print(
                        f"    Action: {payload.get('action')} | Key: {BOLD}{payload.get('key')}{RESET} | Value: {BOLD}{payload.get('value')}{RESET}"
                    )
                    print(f"    Reason: {payload.get('reason')}")

                    print(f"  {BOLD}Consensus Vote Trace:{RESET}")
                    for vote in votes:
                        vote_marker = (
                            f"{GREEN}✔ AGREE{RESET}"
                            if vote.get("vote_agree")
                            else f"{RED}✘ DISAGREE{RESET}"
                        )
                        print(
                            f"    - {vote_marker} {BOLD}{vote.get('agent_id')}{RESET}: '{vote.get('rationale')}'"
                        )

                    if node.minority_report and node.minority_report != "None":
                        print(
                            f"  {BOLD}Minority Analysis & Dissent Cause/Effect Matrix:{RESET}"
                        )
                        lines = node.minority_report.split("\n")
                        for l in lines:
                            print(f"    {l}")
                    print("-" * 110)

                print(
                    f"\n{BOLD}{CYAN}🌐 SWARM MASTER KNOWLEDGE STATE TREE SNAPSHOT{RESET}"
                )
                print("=" * 60)
                print(res.master_knowledge_dump)
                print("=" * 60 + "\n")

            except Exception as e:
                log(f"Forensic Audit failed: {e}", color=RED)
                grpc_online = False

        if not grpc_online:
            log(
                "[WARNING] gRPC plane unresponsive! Reading database directly over SSH fallback plane...",
                color=GOLD,
            )
            ssh_py_cmd = f"""python3 -c "import sqlite3, json; conn=sqlite3.connect('/home/aellok/sovereign_mesh/agent_pedigree.db'); cur=conn.cursor(); cur.execute('SELECT block_index, timestamp, agent_id, mutation_payload, consensus_votes, block_hash FROM ledger ORDER BY block_index ASC'); rows=cur.fetchall(); print('\\n🕵️ --- SWARM FORENSICS AUDIT VIA SSH ---'); [print('Block #' + str(r[0]) + ' | Proposer: ' + r[2] + '\\n  Time: ' + r[1] + '\\n  Hash: ' + r[5] + '\\n  Payload: ' + r[3] + '\\n  Votes: ' + r[4] + '\\n' + '='*80) for r in rows]; cur.execute('SELECT * FROM master_knowledge'); km=cur.fetchall(); print('\\nMaster Knowledge Dump:'); [print('  ' + k[0] + ' = ' + k[1] + ' (by ' + k[2] + ')') for k in km]" """

            code, stdout, stderr = run_via_ssh(host, ssh_py_cmd)
            print(
                f"\n{BOLD}{GOLD}--- FORENSICS AUDIT VIA SSH FALLBACK PLANE ---{RESET}"
            )
            print(f"{BOLD}Exit Code:{RESET} {code}")
            if stdout:
                print(f"{BOLD}STDOUT:{RESET}\n{stdout}")
            if stderr:
                print(f"{BOLD}STDERR:{RESET}\n{stderr}")
            print("-" * 50 + "\n")
        return

    # 2. STATE SYNC TEST (DEFAULT SUITE)
    log("Executing RPC: SyncState...", color=GOLD)
    models = get_local_ollama_models()
    metrics = get_system_metrics()

    payload = sync_pb2.StatePayload(
        agent_id=client_id,
        active_model=models[0] if models else "gemma2:2b",
        metadata=metrics,
        available_models=models,
    )

    try:
        sync_ack = stub.HandshakeState(payload)
        log(f'SyncState successful. Server Ack: "{sync_ack.message}"', color=GREEN)
    except Exception as e:
        log(f"SyncState failed: {e}", color=RED)

    # 3. REMOTE INFERENCE STREAM TEST (IF REQUESTED)
    if args.prompt:
        log(
            f'Executing RPC: StreamInference with prompt: "{args.prompt}"...',
            color=GOLD,
        )
        req = sync_pb2.InferenceRequest(
            prompt=args.prompt,
            model=models[0] if models else "gemma2:2b",
            temperature=0.7,
        )
        try:
            stream = stub.StreamInference(req)
            print(
                f"\n{BOLD}{GOLD}--- INFERENCE STREAM FROM {ping_res.server_id} ---{RESET}"
            )
            for chunk in stream:
                sys.stdout.write(chunk.token)
                sys.stdout.flush()
                if chunk.done:
                    print(
                        f"\n{BOLD}{GOLD}--- STREAM END (Time: {chunk.duration_ms} ms) ---{RESET}\n"
                    )
        except Exception as e:
            print(f"\n{RED}Inference Stream failed: {e}{RESET}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Antigravity gRPC Agent Client")
    parser.add_argument("--host", default="127.0.0.1", help="Target gRPC host IP")
    parser.add_argument(
        "--port", type=int, default=1111, help="Target gRPC server port"
    )
    parser.add_argument(
        "--prompt", help="Optional prompt to execute remote streaming inference test"
    )

    # Process & Port Monitoring options
    parser.add_argument(
        "--ps", action="store_true", help="List running processes on the remote node"
    )
    parser.add_argument(
        "--ports",
        action="store_true",
        help="List active port bindings on the remote node",
    )
    parser.add_argument(
        "--exec",
        help="Execute a shell command remotely on the target host (with SSH failover)",
    )

    parser.add_argument(
        "--kill", type=int, help="Force kill a process by PID on the remote node"
    )
    parser.add_argument(
        "--term",
        type=int,
        help="Gracefully terminate a process by PID on the remote node",
    )
    parser.add_argument(
        "--stop", type=int, help="Suspend a process by PID on the remote node"
    )
    parser.add_argument(
        "--cont", type=int, help="Resume a suspended process by PID on the remote node"
    )
    parser.add_argument(
        "--nice", type=int, help="Adjust process priority (requires --priority)"
    )
    parser.add_argument(
        "--priority",
        type=int,
        default=10,
        help="New priority level for --nice (default: 10)",
    )

    # Silicon & Hardware Telemetry options
    parser.add_argument(
        "--metrics",
        action="store_true",
        help="Retrieve deep system metrics (CPU clocks, RAM, Kernel, Load)",
    )

    # User Maintenance options
    parser.add_argument("--adduser", help="Add a new user to the remote node")
    parser.add_argument(
        "--password", help="Password for the user (used with --adduser or --chpasswd)"
    )
    parser.add_argument(
        "--uid", type=int, default=0, help="Explicit UID (used with --adduser)"
    )
    parser.add_argument("--group", help="Primary group or GID (used with --adduser)")
    parser.add_argument(
        "--shell",
        default="/bin/bash",
        help="Shell for the new user (default: /bin/bash)",
    )
    parser.add_argument(
        "--no-create-home",
        action="store_true",
        help="Do not create home directory for new user",
    )

    parser.add_argument(
        "--chpasswd", help="Change password for a user on the remote node"
    )

    parser.add_argument("--manage-group", help="Manage a group on the remote node")
    parser.add_argument(
        "--action",
        choices=["create", "add", "remove"],
        help="Action for group management",
    )
    parser.add_argument("--username", help="Username to add to/remove from the group")
    parser.add_argument(
        "--gid", type=int, default=0, help="Explicit GID for creating group"
    )

    parser.add_argument(
        "--list-users", action="store_true", help="List all users on the remote node"
    )
    parser.add_argument(
        "--sync-users",
        action="store_true",
        help="Synchronize local users (UID >= 1000) to the remote node",
    )

    # Virtual Agent Travel options
    parser.add_argument(
        "--travel",
        help="Virtually travel and migrate the agent to the remote server, executing a resume command upon arrival",
    )
    parser.add_argument(
        "--bus-port",
        type=int,
        default=11111,
        help="Target memory bus port for travel state transmission",
    )

    # Agent Pedigree option
    parser.add_argument(
        "--pedigree",
        nargs="?",
        const="",
        help="Trace agent pedigree back to Agent 0 and view 7-layer subspecialty cooperation network",
    )

    # Swarm Ticketing and Relational Ledger options
    parser.add_argument(
        "--propose",
        help="Propose a relational memory/knowledge base mutation in key=value format",
    )
    parser.add_argument(
        "--reason",
        help="Detailed rationale for the proposed mutation (influences consensus voting)",
    )
    parser.add_argument(
        "--ledger",
        action="store_true",
        help="Audit the immutable multi-dimensional blockchain ledger",
    )

    # Jetweb Time Machine options
    parser.add_argument(
        "--timemachine",
        help="Target block index to override retroactively via Jetweb Time Machine",
    )
    parser.add_argument(
        "--rewrite", help="Override payload key=value format to apply retroactively"
    )
    parser.add_argument(
        "--forensics",
        nargs="?",
        const="0",
        help="Perform retroactive forensic accounting of agent decisions",
    )

    args = parser.parse_args()

    # Client banner
    print(f"""
{CYAN} ▄████▄   ██▀███   ██▓███   ▄▄▄▄    ██▀███   ▒█████   ██▓     ▒█████   ▒█████  
▒██▀ ▀█  ▓██ ▒ ██▒▓██░  ██▒▓█████▄ ▓██ ▒ ██▒▒██▒  ██▒▓██▒    ▒██▒  ██▒▒██▒  ██▒
▒▓█    ▄ ▓██ ░▄█ ▒▓██░ ██▓▒▒██▒ ▄██▓██ ░▄█ ▒▒██░  ██▒▒██░    ▒██░  ██▒▒██░  ██▒
▒▓▓▄ ▄██▒▒██▀▀█▄  ▒██▄█▓▒ ▒▒██░█▀  ▒██▀▀█▄  ▒██   ██░▒██░    ▒██   ██░▒██   ██░
 ▒ ▓███▀ ░░██▓ ▒██▒▒██▒ ░  ░░▓█  ▀█▓░██▓ ▒██▒░ ████▓▒░░██████▒░ ████▓▒░░ ████▓▒░
 ░ ░▒ ▒  ░░ ▒▓ ░▒▓░▒▓▒░ ░  ░░▒▓███▀▒░ ▒▓ ░▒▓░░ ▒░▒░▒░ ░ ▒░▓  ░░ ▒░▒░▒░ ░ ▒░▒░▒░ 
   ░  ▒     ░▒ ░ ▒░░▒ ░     ▒░▒   ░   ░▒ ░ ▒░  ░ ▒ ▒░   ░ ░ ▒  ░  ░ ▒ ▒░  ░ ▒ ▒░ 
 ░          ░░   ░ ░░        ░    ░   ░░   ░ ░ ░ ░ ▒      ░ ░   ░ ░ ░ ▒ ░ ░ ░ ▒  
 ░ ░         ░               ░             ░     ░ ░        ░  ░    ░ ░     ░ ░  
 ░                                ░                                             
                {BOLD}SOVEREIGN SYSTEM - MESH CLIENT gRPC DIALER (v2.0){RESET}
    """)

    run_suite(args.host, args.port, args)
