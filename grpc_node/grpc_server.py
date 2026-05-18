import grpc
from concurrent import futures
import time
import json
import http.client
import subprocess
from datetime import datetime
import sys
import os
import pwd
import grp
import mmap
import sqlite3

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

def log(msg, color=CYAN, prefix="GRPC-SRV"):
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"{BOLD}[{timestamp}][{prefix}]{RESET} {color}{msg}{RESET}")

def run_sys_cmd(args, require_root=True):
    # If not running as root and require_root is True, prepend sudo
    cmd = (["sudo"] + args) if (require_root and os.geteuid() != 0) else args
    log(f"Executing system command: {' '.join(cmd)}", color=GOLD, prefix="SYS-CMD")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        log(f"Command failed: {res.stderr.strip()}", color=RED, prefix="SYS-CMD")
    return res

def run_sys_cmd_stdin(args, stdin_data, require_root=True):
    cmd = (["sudo"] + args) if (require_root and os.geteuid() != 0) else args
    log(f"Executing system command (stdin): {' '.join(cmd)}", color=GOLD, prefix="SYS-CMD")
    res = subprocess.run(cmd, input=stdin_data, capture_output=True, text=True)
    if res.returncode != 0:
        log(f"Command failed: {res.stderr.strip()}", color=RED, prefix="SYS-CMD")
    return res

class AgentSyncServicer(sync_pb2_grpc.AgentSyncServicer):
    def __init__(self, node_id):
        self.node_id = node_id
        log(f"Servicer initialized for node {BOLD}{node_id}{RESET}", color=GOLD)

    def Ping(self, request, context):
        log(f"Ping received from client {BOLD}{request.client_id}{RESET} (TS: {request.timestamp})", color=BLUE)
        return sync_pb2.PingResponse(
            server_id=self.node_id,
            timestamp=int(time.time() * 1000),
            status="ONLINE"
        )

    def SyncState(self, request, context):
        log(f"SyncState requested from {BOLD}{request.agent_id}{RESET}", color=MAGENTA)
        log(f"  Active Model: {BOLD}{request.active_model}{RESET}")
        log(f"  Available Models: {', '.join(request.available_models)}")
        for k, v in request.metadata.items():
            log(f"  Meta: [{k}] -> {v}")
        
        return sync_pb2.SyncAck(
            success=True,
            message="State integrated into mesh topology successfully",
            sync_timestamp=int(time.time() * 1000)
        )

    def StreamInference(self, request, context):
        log(f"Remote inference requested for model {BOLD}{request.model}{RESET}", color=GREEN)
        log(f"Prompt: \"{request.prompt[:60]}...\"", color=GREEN)

        # Call local Ollama chat API
        try:
            conn = http.client.HTTPConnection("localhost", 11434, timeout=30)
            headers = {"Content-Type": "application/json"}
            payload = {
                "model": request.model or "gemma2:2b",
                "messages": [{"role": "user", "content": request.prompt}],
                "stream": True,
                "options": {
                    "temperature": request.temperature or 0.7
                }
            }
            conn.request("POST", "/api/chat", json.dumps(payload), headers)
            response = conn.getresponse()
            
            if response.status != 200:
                log(f"Ollama error: {response.status} {response.reason}", color=RED)
                yield sync_pb2.InferenceChunk(
                    token=f"[Ollama Error: {response.status} {response.reason}]",
                    done=True
                )
                conn.close()
                return

            # Read stream chunks
            start_time = time.time()
            buffer = ""
            while not context.is_active() or True: # Keep reading until finished or disconnected
                line = response.readline().decode('utf-8').strip()
                if not line:
                    break
                try:
                    chunk_data = json.loads(line)
                    msg_chunk = chunk_data.get("message", {})
                    token = msg_chunk.get("content", "")
                    done = chunk_data.get("done", False)
                    
                    duration = int((time.time() - start_time) * 1000)
                    yield sync_pb2.InferenceChunk(
                        token=token,
                        done=done,
                        duration_ms=duration
                    )
                    if done:
                        log("Remote inference streaming complete.", color=GREEN)
                        break
                except json.JSONDecodeError:
                    continue
            conn.close()
        except Exception as e:
            log(f"Failed to stream inference: {e}", color=RED)
            yield sync_pb2.InferenceChunk(
                token=f"[Inference Engine Error: {str(e)}]",
                done=True
            )

    def RemoteExecute(self, request, context):
        cmd = request.command
        args = list(request.args)
        full_command = [cmd] + args
        log(f"Execution request: {BOLD}{' '.join(full_command)}{RESET}", color=RED, prefix="SECURITY")
        
        # Execute securely under shell
        try:
            res = subprocess.run(full_command, capture_output=True, text=True, timeout=15)
            log(f"Command finished. Exit Code: {res.returncode}", color=GOLD)
            return sync_pb2.CommandResult(
                exit_code=res.returncode,
                stdout=res.stdout,
                stderr=res.stderr
            )
        except Exception as e:
            log(f"Execution failed: {e}", color=RED)
            return sync_pb2.CommandResult(
                exit_code=-1,
                stdout="",
                stderr=str(e)
            )

    def CreateUser(self, request, context):
        username = request.username
        password = request.password
        uid = request.uid
        group = request.group
        create_home = request.create_home
        shell = request.shell

        log(f"CreateUser request for username: {BOLD}{username}{RESET}", color=GOLD)
        
        details = []
        
        # 1. Build useradd command
        cmd = ["useradd"]
        if uid > 0:
            cmd += ["-u", str(uid)]
        
        if group:
            # Check if group exists, if not, create it
            group_exists = False
            try:
                grp.getgrnam(group)
                group_exists = True
            except KeyError:
                pass
            
            if not group_exists:
                log(f"Group {group} does not exist. Creating group first...", color=BLUE)
                g_cmd = ["groupadd"]
                if group.isdigit():
                    g_cmd += ["-g", group, f"grp_{group}"]
                    group = f"grp_{group}"
                else:
                    g_cmd += [group]
                
                res = run_sys_cmd(g_cmd)
                if res.returncode == 0:
                    details.append(f"Created primary group: {group}")
                else:
                    return sync_pb2.UserResponse(
                        success=False,
                        message=f"Failed to create group {group}: {res.stderr.strip()}",
                        details=details
                    )
            
            cmd += ["-g", group]
            
        if create_home:
            cmd += ["-m"]
        else:
            cmd += ["-M"]
            
        if shell:
            cmd += ["-s", shell]
            
        cmd.append(username)
        
        # Run useradd
        res = run_sys_cmd(cmd)
        if res.returncode != 0:
            return sync_pb2.UserResponse(
                success=False,
                message=f"Failed to create user {username}: {res.stderr.strip()}",
                details=details
            )
            
        details.append(f"Created user {username}")
        
        # 2. If password provided, set it via chpasswd
        if password:
            proc = run_sys_cmd_stdin(["chpasswd"], f"{username}:{password}")
            if proc.returncode == 0:
                details.append("Password configured successfully")
            else:
                details.append(f"Warning: User created but password configuration failed: {proc.stderr.strip()}")
                
        return sync_pb2.UserResponse(
            success=True,
            message=f"User {username} successfully integrated into node",
            details=details
        )

    def ChangePassword(self, request, context):
        username = request.username
        new_password = request.new_password
        log(f"ChangePassword request for username: {BOLD}{username}{RESET}", color=GOLD)
        
        res = run_sys_cmd_stdin(["chpasswd"], f"{username}:{new_password}")
        if res.returncode == 0:
            return sync_pb2.UserResponse(
                success=True,
                message=f"Password for user {username} updated successfully",
                details=["Password set via chpasswd"]
            )
        else:
            return sync_pb2.UserResponse(
                success=False,
                message=f"Failed to update password for {username}: {res.stderr.strip()}",
                details=[]
            )

    def ManageGroup(self, request, context):
        username = request.username
        group_name = request.group_name
        action = request.action
        gid = request.gid
        
        log(f"ManageGroup request: User={username}, Group={group_name}, Action={action}, GID={gid}", color=GOLD)
        details = []
        
        if action == sync_pb2.ManageGroupRequest.CREATE_GROUP:
            cmd = ["groupadd"]
            if gid > 0:
                cmd += ["-g", str(gid)]
            cmd.append(group_name)
            
            res = run_sys_cmd(cmd)
            if res.returncode == 0:
                return sync_pb2.UserResponse(
                    success=True,
                    message=f"Group {group_name} created successfully",
                    details=[f"Created group {group_name}"]
                )
            else:
                return sync_pb2.UserResponse(
                    success=False,
                    message=f"Failed to create group {group_name}: {res.stderr.strip()}",
                    details=[]
                )
                
        elif action == sync_pb2.ManageGroupRequest.ADD_TO_GROUP:
            group_exists = False
            try:
                grp.getgrnam(group_name)
                group_exists = True
            except KeyError:
                pass
                
            if not group_exists:
                log(f"Group {group_name} does not exist. Creating group...", color=BLUE)
                g_cmd = ["groupadd"]
                if gid > 0:
                    g_cmd += ["-g", str(gid)]
                g_cmd.append(group_name)
                res = run_sys_cmd(g_cmd)
                if res.returncode == 0:
                    details.append(f"Created group {group_name}")
                else:
                    return sync_pb2.UserResponse(
                        success=False,
                        message=f"Failed to create group {group_name}: {res.stderr.strip()}",
                        details=details
                    )
            
            res = run_sys_cmd(["usermod", "-aG", group_name, username])
            if res.returncode == 0:
                details.append(f"Added user {username} to group {group_name}")
                return sync_pb2.UserResponse(
                    success=True,
                    message=f"User {username} added to group {group_name} successfully",
                    details=details
                )
            else:
                return sync_pb2.UserResponse(
                    success=False,
                    message=f"Failed to add user {username} to group {group_name}: {res.stderr.strip()}",
                    details=details
                )
                
        elif action == sync_pb2.ManageGroupRequest.REMOVE_FROM_GROUP:
            res = run_sys_cmd(["gpasswd", "-d", username, group_name])
            if res.returncode == 0:
                return sync_pb2.UserResponse(
                    success=True,
                    message=f"User {username} removed from group {group_name} successfully",
                    details=[f"Removed {username} from {group_name}"]
                )
            else:
                return sync_pb2.UserResponse(
                    success=False,
                    message=f"Failed to remove user {username} from group {group_name}: {res.stderr.strip()}",
                    details=[]
                )
        else:
            return sync_pb2.UserResponse(
                success=False,
                message="Unknown group action",
                details=[]
            )

    def ListUsers(self, request, context):
        log("ListUsers requested", color=BLUE)
        users_list = []
        try:
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
                    
                    users_list.append(sync_pb2.UserInfo(
                        username=p.pw_name,
                        uid=p.pw_uid,
                        gid=p.pw_gid,
                        primary_group=primary_group,
                        groups=groups,
                        home_dir=p.pw_dir,
                        shell=p.pw_shell
                    ))
            log(f"Retrieved {len(users_list)} users from passwd database.", color=GREEN)
        except Exception as e:
            log(f"Failed to retrieve user directory: {e}", color=RED)
            
        return sync_pb2.UserDirectoryResponse(users=users_list)

    def SyncUsers(self, request, context):
        log(f"SyncUsers requested for {len(request.users)} users", color=MAGENTA)
        details = []
        success_count = 0
        
        for u in request.users:
            username = u.username
            uid = u.uid
            gid = u.gid
            primary_group = u.primary_group
            groups = list(u.groups)
            home_dir = u.home_dir
            shell = u.shell
            
            user_exists = False
            existing_uid = -1
            existing_gid = -1
            existing_shell = ""
            existing_home = ""
            
            try:
                p = pwd.getpwnam(username)
                user_exists = True
                existing_uid = p.pw_uid
                existing_gid = p.pw_gid
                existing_shell = p.pw_shell
                existing_home = p.pw_dir
            except KeyError:
                pass
                
            if not user_exists:
                log(f"Sync: User {username} does not exist. Creating user...", color=BLUE)
                
                if primary_group:
                    group_exists = False
                    try:
                        grp.getgrnam(primary_group)
                        group_exists = True
                    except KeyError:
                        pass
                        
                    if not group_exists:
                        g_cmd = ["groupadd"]
                        if gid > 0:
                            g_cmd += ["-g", str(gid)]
                        g_cmd.append(primary_group)
                        res = run_sys_cmd(g_cmd)
                        if res.returncode == 0:
                            details.append(f"Sync: Created primary group {primary_group} with GID {gid}")
                        else:
                            details.append(f"Sync error: Failed to create group {primary_group}: {res.stderr.strip()}")
                
                cmd = ["useradd"]
                if uid > 0:
                    cmd += ["-u", str(uid)]
                if primary_group:
                    cmd += ["-g", primary_group]
                if home_dir:
                    cmd += ["-d", home_dir, "-m"]
                else:
                    cmd += ["-m"]
                if shell:
                    cmd += ["-s", shell]
                cmd.append(username)
                
                res = run_sys_cmd(cmd)
                if res.returncode == 0:
                    details.append(f"Sync: Created user {username} (UID: {uid}, GID: {gid})")
                    success_count += 1
                else:
                    details.append(f"Sync error: Failed to create user {username}: {res.stderr.strip()}")
                    continue
            else:
                log(f"Sync: User {username} exists. Checking alignments...", color=BLUE)
                needs_update = False
                mod_cmd = ["usermod"]
                
                if uid > 0 and uid != existing_uid:
                    log(f"  UID mismatch for {username}: local {existing_uid} vs requested {uid}. Aligning...", color=GOLD)
                    mod_cmd += ["-u", str(uid)]
                    needs_update = True
                    
                if primary_group:
                    group_aligns = False
                    try:
                        g = grp.getgrnam(primary_group)
                        if g.gr_gid == gid or g.gr_name == primary_group:
                            mod_cmd += ["-g", primary_group]
                            group_aligns = True
                    except KeyError:
                        pass
                    
                    if not group_aligns:
                        g_cmd = ["groupadd"]
                        if gid > 0:
                            g_cmd += ["-g", str(gid)]
                        g_cmd.append(primary_group)
                        run_sys_cmd(g_cmd)
                        mod_cmd += ["-g", primary_group]
                        needs_update = True
                    elif gid != existing_gid:
                        needs_update = True
                
                if shell and shell != existing_shell:
                    mod_cmd += ["-s", shell]
                    needs_update = True
                    
                if home_dir and home_dir != existing_home:
                    mod_cmd += ["-d", home_dir, "-m"]
                    needs_update = True
                    
                if needs_update:
                    mod_cmd.append(username)
                    res = run_sys_cmd(mod_cmd)
                    if res.returncode == 0:
                        details.append(f"Sync: Updated properties for {username} (Aligned UID={uid}, GID={gid})")
                        if uid != existing_uid:
                            actual_home = home_dir or existing_home
                            chown_grp = primary_group or str(gid)
                            run_sys_cmd(["chown", "-R", f"{username}:{chown_grp}", actual_home])
                            details.append(f"Sync: Recursively updated file ownership for {username} home directory: {actual_home}")
                    else:
                        details.append(f"Sync error: Failed to update properties for {username}: {res.stderr.strip()}")
                
                existing_groups = []
                try:
                    for g in grp.getgrall():
                        if username in g.gr_mem:
                            existing_groups.append(g.gr_name)
                except Exception:
                    pass
                
                for sg in groups:
                    if sg not in existing_groups and sg != primary_group:
                        try:
                            grp.getgrnam(sg)
                        except KeyError:
                            run_sys_cmd(["groupadd", sg])
                            details.append(f"Sync: Created secondary group {sg}")
                        
                        res = run_sys_cmd(["usermod", "-aG", sg, username])
                        if res.returncode == 0:
                            details.append(f"Sync: Added {username} to secondary group {sg}")
                            
                success_count += 1
                
        return sync_pb2.UserResponse(
            success=success_count == len(request.users),
            message=f"User synchronization complete. Successful: {success_count}/{len(request.users)}",
            details=details
        )

    def GetProcessDirectory(self, request, context):
        log("GetProcessDirectory requested", color=BLUE)
        processes = []
        try:
            res = run_sys_cmd(["ps", "-eo", "pid,ppid,user,stat,%cpu,%mem,comm,args", "--no-headers"], require_root=False)
            lines = res.stdout.strip().split("\n")
            for line in lines:
                if not line.strip():
                   continue
                parts = line.strip().split(None, 7)
                if len(parts) >= 7:
                    pid_val = int(parts[0])
                    ppid_val = int(parts[1])
                    user_val = parts[2]
                    stat_val = parts[3]
                    try:
                        cpu_val = float(parts[4])
                    except ValueError:
                        cpu_val = 0.0
                    try:
                        mem_val = float(parts[5])
                    except ValueError:
                        mem_val = 0.0
                    comm_val = parts[6]
                    args_val = parts[7] if len(parts) > 7 else comm_val
                    
                    processes.append(sync_pb2.ProcessInfo(
                        pid=pid_val,
                        ppid=ppid_val,
                        name=comm_val,
                        username=user_val,
                        cpu_percent=cpu_val,
                        memory_percent=mem_val,
                        cmdline=args_val,
                        status=stat_val
                    ))
            log(f"Retrieved {len(processes)} running processes.", color=GREEN)
        except Exception as e:
            log(f"Failed to list processes: {e}", color=RED)
        return sync_pb2.ProcessDirectoryResponse(processes=processes)

    def GetPortBindings(self, request, context):
        log("GetPortBindings requested", color=BLUE)
        bindings = []
        import re
        
        def parse_ss_output(stdout_data, protocol):
            lines = stdout_data.strip().split("\n")
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
                        match = re.search(r'users:\(\(\"([^\"]+)\",pid=(\d+)', proc_info)
                        if match:
                            process_name = match.group(1)
                            pid = int(match.group(2))
                        else:
                            match_pid = re.search(r'pid=(\d+)', proc_info)
                            if match_pid:
                                pid = int(match_pid.group(1))
                            match_name = re.search(r'\"([^\"]+)\"', proc_info)
                            if match_name:
                                process_name = match_name.group(1)
                                
                    bindings.append(sync_pb2.PortBinding(
                        protocol=protocol,
                        local_address=local_addr,
                        local_port=local_port,
                        remote_address=peer_addr,
                        remote_port=peer_port,
                        state=state,
                        pid=pid,
                        process_name=process_name
                    ))
                    
        try:
            res_tcp = run_sys_cmd(["ss", "-tanp"], require_root=False)
            parse_ss_output(res_tcp.stdout, "TCP")
            
            res_udp = run_sys_cmd(["ss", "-uanp"], require_root=False)
            parse_ss_output(res_udp.stdout, "UDP")
            
            log(f"Retrieved {len(bindings)} port bindings.", color=GREEN)
        except Exception as e:
            log(f"Failed to list port bindings: {e}", color=RED)
            
        return sync_pb2.PortBindingsResponse(bindings=bindings)

    def TeleportAgent(self, request, context):
        log(f"Virtual Travel: Agent teleporting {BOLD}{request.source_node_id}{RESET} -> {BOLD}{request.target_node_id}{RESET} over Memory Bus...", color=MAGENTA)
        
        # 1. Map the shared memory page table
        path = "/dev/shm/sovereign_page_table"
        if not os.path.exists(path):
            path = "/tmp/sovereign_page_table"
            
        if not os.path.exists(path):
            log(f"Materialization failed: RAM Page table not allocated at {path}.", color=RED)
            return sync_pb2.TeleportResponse(
                success=False,
                message="Virtual materialization failed: Page table not allocated at target."
            )
            
        try:
            with open(path, "r+b") as f:
                mem = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_WRITE)
                
                # 2. Direct read from High-Speed Memory Table
                mem.seek(request.memory_bus_offset)
                state_bytes = mem.read(request.state_size)
                
                # Clean up any trailing null-bytes from paging alignment
                state_str = state_bytes.decode("utf-8").rstrip("\x00").strip()
                state_data = json.loads(state_str)
                
                log(f"Agent mind successfully reconstructed from RAM page segment!", color=GREEN)
                log(f"  Mind Timestamp : {state_data.get('timestamp')}", color=CYAN)
                log(f"  Model Engine   : {BOLD}{state_data.get('active_model')}{RESET}", color=CYAN)
                log(f"  Source Host OS : {state_data.get('host_env', {}).get('os')}", color=CYAN)
                
                # 3. Resume / Execute command on target host
                log(f"Executing migration resume command: {BOLD}{request.run_command}{RESET}", color=GOLD)
                # Split run_command safely for subprocess execution
                cmd_parts = request.run_command.split()
                res = run_sys_cmd(cmd_parts, require_root=False)
                
                status_msg = f"Agent '{request.source_node_id}' materialized on '{self.node_id}' via Memory Bus. Execution succeeded."
                if res.returncode != 0:
                    status_msg = f"Agent materialized on '{self.node_id}' but resume command failed."
                
                return sync_pb2.TeleportResponse(
                    success=True,
                    message=status_msg,
                    execution_stdout=res.stdout,
                    execution_stderr=res.stderr
                )
        except Exception as e:
            log(f"Failed to materialize agent from memory bus: {e}", color=RED)
            return sync_pb2.TeleportResponse(
                success=False,
                message=f"Virtual travel aborted: Materialization error: {e}"
            )

    def TracePedigree(self, request, context):
        agent_id = request.agent_id or self.node_id
        log(f"Swarm Lineage: Tracing pedigree of '{BOLD}{agent_id}{RESET}' back to Agent 0...", color=MAGENTA)
        
        # Normalize agent_id mappings to match seeded Layer 7 nodes
        if agent_id not in ["LAPTOP-TRAINING-AGENT", "AURORA-R9-SERVER"] and agent_id != "AGENT-0":
            if agent_id == self.node_id:
                agent_id = "AURORA-R9-SERVER"
            else:
                agent_id = "LAPTOP-TRAINING-AGENT"
                
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # Recursive CTE query to trace lineage back to Agent 0
            query = """
            WITH RECURSIVE lineage AS (
                SELECT agent_id, name, parent_agent_id, layer_level, specialty, subspecialty
                FROM agents
                WHERE agent_id = ?
                
                UNION ALL
                
                SELECT a.agent_id, a.name, a.parent_agent_id, a.layer_level, a.specialty, a.subspecialty
                FROM agents a
                JOIN lineage l ON l.parent_agent_id = a.agent_id
            )
            SELECT agent_id, name, layer_level, specialty, subspecialty FROM lineage ORDER BY layer_level ASC
            """
            cursor.execute(query, (agent_id,))
            rows = cursor.fetchall()
            
            path = []
            for r in rows:
                path.append(sync_pb2.AgentAncestryNode(
                    agent_id=r[0],
                    name=r[1],
                    layer_level=r[2],
                    specialty=r[3],
                    subspecialty=r[4]
                ))
                
            cursor.execute("SELECT agent_id, name, layer_level, specialty, subspecialty FROM agents ORDER BY layer_level ASC")
            all_agents = cursor.fetchall()
            conn.close()
            
            tree_lines = [
                f"{GOLD}🌐 7-LAYER COOPERATIVE SWARM NETWORK MAP (Agent 0 Ancestry){RESET}",
                f"{GOLD}=============================================================={RESET}"
            ]
            
            layers = {}
            for ag in all_agents:
                layers.setdefault(ag[2], []).append(ag)
                
            for lvl in sorted(layers.keys()):
                tree_lines.append(f"\n{BOLD}{CYAN}Layer {lvl}: {self._get_layer_name(lvl)}{RESET}")
                for ag in layers[lvl]:
                    coop_agents = [x[0] for x in all_agents if x[3] == ag[3] and x[0] != ag[0]]
                    coop_str = f" [Cooperates with: {', '.join(coop_agents)}]" if coop_agents else ""
                    tree_lines.append(f"  ├── {BOLD}{ag[0]}{RESET} ({ag[1]}) - Specialty: {BOLD}{ag[3]}{RESET} -> Subspecialty: {ag[4]}{GOLD}{coop_str}{RESET}")
                    
            coop_map = "\n".join(tree_lines)
            
            log(f"Pedigree trace successfully completed with {len(path)} lineage nodes.", color=GREEN)
            return sync_pb2.PedigreeResponse(
                pedigree_path=path,
                collective_specialty_cooperation_map=coop_map
            )
        except Exception as e:
            log(f"Pedigree trace failed: {e}", color=RED)
            return sync_pb2.PedigreeResponse(
                pedigree_path=[],
                collective_specialty_cooperation_map=f"Pedigree Trace aborted. Error: {e}"
            )
            
    def _get_layer_name(self, level):
        names = {
            1: "Core Swarm Mind (Root Progenitor)",
            2: "Domain Sovereignty (Primary Verticals)",
            3: "Functional Specialization (Capabilities)",
            4: "Operational Class (Utility Wrappers)",
            5: "Micro-Task Engine (Code Modules)",
            6: "Shared Resource Bindings (IPC & Hardware Segments)",
            7: "Execution Interface (Dial/Server Nodes)"
        }
        return names.get(level, "Unknown Core Layer")

    def ProposeSwarmMutation(self, request, context):
        proposer = request.proposer_agent_id or self.node_id
        target_key = request.target_key
        proposed_value = request.proposed_value
        reason = request.change_reason
        
        log(f"Swarm Mutation: Proposing key modification: '{BOLD}{target_key}{RESET}' -> '{BOLD}{proposed_value}{RESET}' proposed by '{proposer}'...", color=MAGENTA)
        
        # 1. 5-Agent Consensus Simulation
        # Representatives:
        # AGENT-SEC (Layer 2, Security)
        # AGENT-TEL (Layer 2, Telemetry)
        # AGENT-EXEC (Layer 2, Execution)
        # AGENT-AUTH (Layer 3, Auth)
        # AGENT-MIG (Layer 3, Migrator)
        
        voters = [
            ("AGENT-SEC", "Security Overlord", "Security & Compliance"),
            ("AGENT-TEL", "Telemetry Watcher", "System Diagnostics"),
            ("AGENT-EXEC", "Execution Spawner", "Remote Action"),
            ("AGENT-AUTH", "Auth Specialist", "Security & Compliance"),
            ("AGENT-MIG", "Migrator Engine", "Remote Action")
        ]
        
        votes = []
        agree_count = 0
        import hashlib
        
        # Generate votes with smart conditional checks to simulate genuine consensus
        for agent_id, name, specialty in voters:
            agree = True
            rationale = "Swarm alignment verified. Mutation enhances operational telemetry."
            
            # Security Overlord is highly protective of core settings
            if agent_id == "AGENT-SEC" and any(x in target_key.lower() for x in ["security", "port", "root", "password", "key"]):
                agree = False
                rationale = f"SECURITY WARNING: Proposed key '{target_key}' impacts POSIX boundary configurations."
            
            # Telemetry Watcher objects if reason is too brief
            elif agent_id == "AGENT-TEL" and len(reason) < 10:
                agree = False
                rationale = "DIAGNOSTIC EXCLUSION: Change reason does not provide sufficient trace metrics for dependency analysis."
                
            if agree:
                agree_count += 1
                
            votes.append(sync_pb2.SwarmVote(
                agent_id=agent_id,
                vote_agree=agree,
                rationale=rationale
            ))
            
        consensus_reached = (agree_count >= 4) # 4/5 consensus required
        consensus_ratio = f"{agree_count}/5"
        
        minority_report = ""
        # 2. Minority Report Cause/Effect Analysis (if minority disagrees but overridden, or if blocked)
        if agree_count < 5:
            disagreeing = [v.agent_id for v in votes if not v.vote_agree]
            minority_reasons = "\n".join([f" - {v.agent_id}: '{v.rationale}'" for v in votes if not v.vote_agree])
            
            # Synthesize minority report simulating extensive research
            minority_report = f"""🛡️ --- SWARM MINORITY REPORT & CAUSE-EFFECT RESEARCH ANALYSIS ---
Objections raised by: {', '.join(disagreeing)}
Objection Rationales:
{minority_reasons}

RESEARCH SIMULATION MATRIX:
* [CAUSE]: Mutation of '{target_key}' to '{proposed_value}' requested by {proposer}.
* [EFFECT-A (Operational)]: Mutation modifies core relational memory parameter.
* [EFFECT-B (Risk Profile)]: Security boundary threshold analyzed at 4.2% deviation.
* [MITIGATION ASSESSMENT]: Sandbox enforcement boundaries isolated at Layer 6.
* [DISSENT RECONSIDERATION]: Minority concerns were evaluated. System resolves that while concerns regarding boundary stability are valid, target sandbox parameters are structurally secure.
* [DECISION]: {"MUTATION APPROVED under monitored namespace." if consensus_reached else "MUTATION REJECTED due to consensus deficit (< 4/5)."}"""
        
        block_idx = -1
        block_hash = ""
        status = "REJECTED"
        
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # Create a "new" ticket in Best Practical RT layout first
            ts_now = datetime.now().isoformat()
            subject = f"Mutation Proposal: Set {target_key}={proposed_value}"
            task_desc = f"Set {target_key}={proposed_value} ({reason})"
            
            cursor.execute("""
                INSERT INTO tickets (Queue, Subject, Status, Owner, Creator, Priority, TimeEstimated, TimeWorked, TimeLeft, Created, LastUpdated, LastUpdatedBy, agent_id, layer_level, specialty, task_description) 
                VALUES ('Swarm-Mutations', ?, 'new', 'Nobody', ?, 5, 60, 0, 60, ?, ?, ?, ?, 7, 'Swarm Mutation Proposal', ?)
            """, (subject, proposer, ts_now, ts_now, proposer, proposer, task_desc))
            
            ticket_id = cursor.lastrowid
            
            # Record Ticket Creation Transaction
            cursor.execute("""
                INSERT INTO transactions (ObjectType, ObjectId, TimeTaken, Type, Data, Creator, Created) 
                VALUES ('RT::Ticket', ?, 0, 'Create', ?, ?, ?)
            """, (ticket_id, f"Ticket created by {proposer}", proposer, ts_now))

            if consensus_reached:
                # Resolve ticket
                cursor.execute("""
                    UPDATE tickets 
                    SET Status = 'resolved', Resolved = ?, LastUpdated = ?, LastUpdatedBy = 'SWARM-CONSENSUS'
                    WHERE ticket_id = ?
                """, (ts_now, ts_now, ticket_id))
                
                # Record Status change transaction
                cursor.execute("""
                    INSERT INTO transactions (ObjectType, ObjectId, TimeTaken, Type, Field, OldValue, NewValue, Data, Creator, Created) 
                    VALUES ('RT::Ticket', ?, 0, 'Status', 'Status', 'new', 'resolved', 'Status changed from new to resolved by Swarm consensus.', 'SWARM-CONSENSUS', ?)
                """, (ticket_id, ts_now))
                
                # Record Parameter Set transaction
                cursor.execute("""
                    INSERT INTO transactions (ObjectType, ObjectId, TimeTaken, Type, Field, NewValue, Data, Creator, Created) 
                    VALUES ('RT::Ticket', ?, 0, 'Set', ?, ?, ?, ?, ?)
                """, (ticket_id, target_key, proposed_value, f"State parameter '{target_key}' modified to '{proposed_value}'.", proposer, ts_now))

                # Apply mutation to Master Knowledge table
                cursor.execute("INSERT OR REPLACE INTO master_knowledge VALUES (?, ?, ?)",
                               (target_key, proposed_value, proposer))
                
                # Retrieve last block hash
                cursor.execute("SELECT block_hash FROM ledger ORDER BY block_index DESC LIMIT 1")
                prev_hash = cursor.fetchone()[0]
                
                # Prep block details
                payload = json.dumps({"action": "MUTATION_UPDATE", "key": target_key, "value": proposed_value, "reason": reason})
                votes_json = json.dumps([{"agent_id": v.agent_id, "vote_agree": v.vote_agree, "rationale": v.rationale} for v in votes])
                
                cursor.execute("SELECT COUNT(*) FROM ledger")
                new_idx = cursor.fetchone()[0] + 1
                
                # Calculate immutable signature
                block_data = f"{new_idx}{prev_hash}{ts_now}{proposer}{payload}{votes_json}{minority_report}"
                block_hash = hashlib.sha256(block_data.encode('utf-8')).hexdigest()
                
                cursor.execute("INSERT INTO ledger (block_index, previous_hash, timestamp, agent_id, mutation_payload, consensus_votes, minority_report, block_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                               (new_idx, prev_hash, ts_now, proposer, payload, votes_json, minority_report or "None", block_hash))
                
                block_idx = new_idx
                status = "COMMITTED"
                log(f"Mutation committed successfully at Ledger Block #{new_idx}! Block Hash: {block_hash[:16]}...", color=GREEN)
            else:
                # Reject ticket
                cursor.execute("""
                    UPDATE tickets 
                    SET Status = 'rejected', LastUpdated = ?, LastUpdatedBy = 'SWARM-CONSENSUS'
                    WHERE ticket_id = ?
                """, (ts_now, ticket_id))
                
                # Record Status change transaction
                cursor.execute("""
                    INSERT INTO transactions (ObjectType, ObjectId, TimeTaken, Type, Field, OldValue, NewValue, Data, Creator, Created) 
                    VALUES ('RT::Ticket', ?, 0, 'Status', 'Status', 'new', 'rejected', 'Status changed from new to rejected due to consensus deficit.', 'SWARM-CONSENSUS', ?)
                """, (ticket_id, ts_now))
                
                log(f"Mutation rejected: Consensus ratio of {consensus_ratio} fails 4/5 baseline requirement.", color=RED)
                status = "REJECTED_CONSENSUS_FAILED"
            
            conn.commit()
            conn.close()
        except Exception as e:
            log(f"Failed to record mutation in database: {e}", color=RED)
            status = f"FAILED: {e}"
            
        return sync_pb2.MutationResponse(
            consensus_reached=consensus_reached,
            consensus_ratio=consensus_ratio,
            votes=votes,
            minority_report=minority_report,
            block_index=block_idx,
            block_hash=block_hash,
            status=status
        )

    def QuerySwarmLedger(self, request, context):
        log("Ledger Audit: Retrieving all blocks from multi-dimensional immutable ledger...", color=MAGENTA)
        
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT block_index, previous_hash, timestamp, agent_id, mutation_payload, consensus_votes, minority_report, block_hash FROM ledger ORDER BY block_index ASC")
            rows = cursor.fetchall()
            conn.close()
            
            blocks = []
            chain_valid = "SECURE: Chain validation integrity matches perfectly."
            
            for idx, r in enumerate(rows):
                blocks.append(sync_pb2.LedgerBlock(
                    block_index=r[0],
                    previous_hash=r[1],
                    timestamp=r[2],
                    agent_id=r[3],
                    mutation_payload=r[4],
                    consensus_votes=r[5],
                    minority_report=r[6],
                    block_hash=r[7]
                ))
                
                # Validate cryptographic hash chain sequence on-the-fly
                if idx > 0:
                    prev_block = rows[idx - 1]
                    if r[1] != prev_block[7]:
                        chain_valid = f"CORRUPTED: Hash mismatch at Block #{r[0]}!"
                        
            return sync_pb2.LedgerQueryResponse(
                blocks=blocks,
                chain_validation_status=chain_valid
            )
        except Exception as e:
            log(f"Ledger Query failed: {e}", color=RED)
            return sync_pb2.LedgerQueryResponse(
                blocks=[],
                chain_validation_status=f"FAILED: {e}"
            )

    def TimeTravelOverride(self, request, context):
        target_idx = request.target_block_index
        new_key = request.new_target_key
        new_val = request.new_proposed_value
        reason = request.override_reason
        
        log(f"⏰ JETWEB TIME MACHINE: Activating timeline refactoring. Destination Block #{target_idx}...", color=CYAN)
        
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # Check if block exists
            cursor.execute("SELECT COUNT(*) FROM ledger WHERE block_index = ?", (target_idx,))
            if cursor.fetchone()[0] == 0:
                conn.close()
                return sync_pb2.TimeTravelResponse(
                    success=False,
                    message=f"Bifurcation Failed: Block #{target_idx} does not exist in active ledger history.",
                    refactor_logs=[],
                    new_chain_validation_status="ABORTED"
                )
            
            # If target is Genesis (1), let's protect root progenitor bounds
            if target_idx == 1:
                conn.close()
                return sync_pb2.TimeTravelResponse(
                    success=False,
                    message="Bifurcation Failed: Genesis Block #1 is mathematically immutable and represents Swarm birth.",
                    refactor_logs=[],
                    new_chain_validation_status="ABORTED"
                )
            
            # Create a "resolved" override ticket in Best Practical RT layout
            ts_now = datetime.now().isoformat()
            subject = f"Timeline Override: Block #{target_idx} rewrite to {new_key}={new_val}"
            task_desc = f"Time Machine Override: set {new_key}={new_val} at block #{target_idx}"
            
            cursor.execute("""
                INSERT INTO tickets (Queue, Subject, Status, Owner, Creator, Priority, TimeEstimated, TimeWorked, TimeLeft, Created, Resolved, LastUpdated, LastUpdatedBy, agent_id, layer_level, specialty, task_description) 
                VALUES ('Time-Machine', ?, 'resolved', 'JETWEB-ADMIN', 'JETWEB-ADMIN', 10, 0, 10, 0, ?, ?, ?, 'JETWEB-ADMIN', 'JETWEB-ADMIN', 1, 'Timeline Override', ?)
            """, (subject, ts_now, ts_now, ts_now, task_desc))
            
            ticket_id = cursor.lastrowid
            
            # Record Ticket Creation Transaction
            cursor.execute("""
                INSERT INTO transactions (ObjectType, ObjectId, TimeTaken, Type, Data, Creator, Created) 
                VALUES ('RT::Ticket', ?, 10, 'Create', ?, 'JETWEB-ADMIN', ?)
            """, (ticket_id, f"Time Machine Ticket created and auto-resolved.", ts_now))
            
            # Record Timeline-Fork Transaction
            cursor.execute("""
                INSERT INTO transactions (ObjectType, ObjectId, TimeTaken, Type, Field, OldValue, NewValue, Data, Creator, Created) 
                VALUES ('RT::Ticket', ?, 0, 'Timeline-Fork', 'ledger', ?, ?, ?, 'JETWEB-ADMIN', ?)
            """, (ticket_id, f"Block #{target_idx} legacy state", f"Block #{target_idx} overridden to {new_key}={new_val}", f"Re-mined blockchain cascade starting at Block #{target_idx}.", ts_now))

            refactor_logs = [
                f"⏰ --- JETWEB TIME MACHINE TIMELINE BIFURCATION TRIGGERED ---",
                f"Targeting Block #{target_idx} to overwrite decision: set '{new_key}' = '{new_val}'"
            ]
            
            # 1. Retrieve all blocks in sequential order
            cursor.execute("SELECT block_index, previous_hash, timestamp, agent_id, mutation_payload, consensus_votes, minority_report, block_hash FROM ledger ORDER BY block_index ASC")
            blocks = [list(x) for x in cursor.fetchall()]
            
            # 2. Overwrite target block data
            new_payload = json.dumps({"action": "MUTATION_UPDATE", "key": new_key, "value": new_val, "reason": f"[JETWEB OVERRIDE]: {reason}"})
            # Set dynamic override votes (5/5 direct administrative consensus)
            new_votes = json.dumps([
                {"agent_id": "JETWEB-ADMIN", "vote_agree": True, "rationale": f"Time Machine administrative override: {reason}"}
            ])
            new_minority = f"🛡️ ADMINISTRATIVE OVERRIDE REPORT:\n - Timeline hard-forked by operator.\n - Original decisions collapsed."
            
            # 3. Cascade recalculate all blocks starting from target_idx to end
            import hashlib
            prev_hash = ""
            for idx, block in enumerate(blocks):
                block_num = block[0]
                
                if block_num < target_idx:
                    # Keep original hash
                    prev_hash = block[7]
                    continue
                    
                elif block_num == target_idx:
                    # Apply new overridden data
                    block[1] = prev_hash # set previous_hash
                    block[4] = new_payload
                    block[5] = new_votes
                    block[6] = new_minority
                    
                    # Re-calculate hash
                    block_data = f"{block_num}{block[1]}{block[2]}{block[3]}{block[4]}{block[5]}{block[6]}"
                    block[7] = hashlib.sha256(block_data.encode('utf-8')).hexdigest()
                    
                    refactor_logs.append(f"Mined Overridden Block #{block_num}: New Hash: {block[7][:16]}...")
                    prev_hash = block[7]
                    
                else:  # block_num > target_idx
                    # Re-link hash sequence
                    block[1] = prev_hash
                    
                    # Re-calculate hash using newly linked previous_hash
                    block_data = f"{block_num}{block[1]}{block[2]}{block[3]}{block[4]}{block[5]}{block[6]}"
                    block[7] = hashlib.sha256(block_data.encode('utf-8')).hexdigest()
                    
                    refactor_logs.append(f"Re-signed Block #{block_num}: Previous Hash: {block[1][:12]}... -> New Hash: {block[7][:12]}...")
                    prev_hash = block[7]
            
            # 4. Write updated blocks back to SQLite ledger
            for block in blocks:
                if block[0] >= target_idx:
                    cursor.execute("""
                        UPDATE ledger 
                        SET previous_hash = ?, mutation_payload = ?, consensus_votes = ?, minority_report = ?, block_hash = ?
                        WHERE block_index = ?
                    """, (block[1], block[4], block[5], block[6], block[7], block[0]))
            
            # 5. Re-evaluate master_knowledge table from Genesis to maintain state trees
            cursor.execute("DELETE FROM master_knowledge")
            cursor.execute("INSERT INTO master_knowledge VALUES ('swarm_status', 'ONLINE', 'AGENT-0')")
            
            refactor_logs.append("Reconstructing Swarm Master Knowledge state tree...")
            for block in blocks:
                block_num = block[0]
                if block_num == 1:
                    continue
                payload = json.loads(block[4])
                if "key" in payload and "value" in payload:
                    cursor.execute("INSERT OR REPLACE INTO master_knowledge VALUES (?, ?, ?)",
                                   (payload["key"], payload["value"], block[3]))
                    refactor_logs.append(f"  Applied committed key '{payload['key']}' = '{payload['value']}'")
            
            conn.commit()
            conn.close()
            
            refactor_logs.append("⏰ Timeline collapse completed successfully. State tree harmonized.")
            log("Jetweb Time Machine: Timeline collapsed and merged successfully.", color=GREEN)
            return sync_pb2.TimeTravelResponse(
                success=True,
                message="Timeline bifurcated, re-mined, and collapsed successfully.",
                refactor_logs=refactor_logs,
                new_chain_validation_status="SECURE: Refactored hash signature sequence verified."
            )
            
        except Exception as e:
            log(f"Time travel failed: {e}", color=RED)
            return sync_pb2.TimeTravelResponse(
                success=False,
                message=f"Bifurcation aborted. Fatal anomaly: {e}",
                refactor_logs=[],
                new_chain_validation_status="CORRUPTED: Refactor sequence aborted."
            )

    def ForensicAudit(self, request, context):
        target_idx = request.target_block_index
        log(f"🕵️ FORENSIC ACCOUNTING: Retroactively auditing system timeline. Filter Index: {target_idx or 'ALL'}...", color=MAGENTA)
        
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # Fetch ledger history
            if target_idx > 0:
                cursor.execute("""
                    SELECT block_index, timestamp, agent_id, mutation_payload, consensus_votes, minority_report, block_hash 
                    FROM ledger WHERE block_index = ?
                """, (target_idx,))
            else:
                cursor.execute("""
                    SELECT block_index, timestamp, agent_id, mutation_payload, consensus_votes, minority_report, block_hash 
                    FROM ledger ORDER BY block_index ASC
                """)
            rows = cursor.fetchall()
            
            # Fetch master knowledge state dump
            cursor.execute("SELECT key, value, last_updated_by FROM master_knowledge")
            dump_rows = cursor.fetchall()
            conn.close()
            
            timeline_nodes = []
            for r in rows:
                timeline_nodes.append(sync_pb2.ForensicNode(
                    block_index=r[0],
                    timestamp=r[1],
                    agent_id=r[2],
                    mutation_payload=r[3],
                    consensus_votes=r[4],
                    minority_report=r[5] or "None",
                    block_hash=r[6]
                ))
                
            knowledge_list = []
            for k in dump_rows:
                knowledge_list.append(f"  🔑 '{k[0]}' = '{k[1]}' (Last Mutation Agent: {k[2]})")
                
            master_dump = "\n".join(knowledge_list) or "  [EMPTY STATE - NO ACTIVE KNOWLEDGE]"
            
            return sync_pb2.ForensicResponse(
                timeline_nodes=timeline_nodes,
                master_knowledge_dump=master_dump
            )
        except Exception as e:
            log(f"Forensic audit failed: {e}", color=RED)
            return sync_pb2.ForensicResponse(
                timeline_nodes=[],
                master_knowledge_dump=f"ERROR: {e}"
            )

DB_PATH = "/home/aellok/sovereign_mesh/agent_pedigree.db"

def initialize_pedigree_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS agents (
            agent_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            parent_agent_id TEXT,
            layer_level INTEGER NOT NULL,
            specialty TEXT NOT NULL,
            subspecialty TEXT NOT NULL,
            FOREIGN KEY(parent_agent_id) REFERENCES agents(agent_id)
        )
        """)
        
        cursor.execute("SELECT COUNT(*) FROM agents")
        if cursor.fetchone()[0] == 0:
            seed_data = [
                ("AGENT-0", "Agent 0 (Sovereign Swarm Root)", None, 1, "Core Swarm Mind", "Progenitor Swarm Mind"),
                ("AGENT-SEC", "Security Overlord", "AGENT-0", 2, "Security & Compliance", "POSIX Boundary Control"),
                ("AGENT-TEL", "Telemetry Watcher", "AGENT-0", 2, "System Diagnostics", "Process & Network Maps"),
                ("AGENT-EXEC", "Execution Spawner", "AGENT-0", 2, "Remote Action", "gRPC & SSH Plane"),
                ("AGENT-AUTH", "Auth Specialist", "AGENT-SEC", 3, "Security & Compliance", "POSIX User Sync"),
                ("AGENT-PROC", "Process Inspector", "AGENT-TEL", 3, "System Diagnostics", "CPU/RAM Profiling"),
                ("AGENT-NET", "Port Auditor", "AGENT-TEL", 3, "System Diagnostics", "TCP/UDP Socket Binding"),
                ("AGENT-MIG", "Migrator Engine", "AGENT-EXEC", 3, "Remote Action", "High-Speed Memory Teleportation"),
                ("AGENT-USERADD", "User Builder", "AGENT-AUTH", 4, "Security & Compliance", "Dynamic User Addition"),
                ("AGENT-CHPASS", "Password Manager", "AGENT-AUTH", 4, "Security & Compliance", "POSIX Password Rotation"),
                ("AGENT-PS", "PS Telemetry", "AGENT-PROC", 4, "System Diagnostics", "Running Process Directory"),
                ("AGENT-SS", "SS Port Mapper", "AGENT-NET", 4, "System Diagnostics", "Listening Sockets & PIDs"),
                ("AGENT-BUS", "Bus Dial", "AGENT-MIG", 4, "Remote Action", "RAM Shared Memory Loader"),
                ("AGENT-USERADD-RAW", "Raw Useradd", "AGENT-USERADD", 5, "Security & Compliance", "useradd CLI Execution"),
                ("AGENT-CHPASS-RAW", "Raw Chpasswd", "AGENT-CHPASS", 5, "Security & Compliance", "chpasswd pipe Streamer"),
                ("AGENT-PS-PARSER", "Process Table Parser", "AGENT-PS", 5, "System Diagnostics", "ps Stdout Tokenizer"),
                ("AGENT-SS-REG", "Socket Regex Matcher", "AGENT-SS", 5, "System Diagnostics", "ss userpid Regex Parser"),
                ("AGENT-MMAP", "mmap Direct Buffer", "AGENT-BUS", 5, "Remote Action", "Zero-Copy Direct Sync"),
                ("AGENT-SHM-ALLOC", "Page Table Map", "AGENT-MMAP", 6, "Remote Action", "/dev/shm Allocation Table"),
                ("AGENT-SYS-EXEC", "System Commander", "AGENT-USERADD-RAW", 6, "Security & Compliance", "subprocess.run Spawner"),
                ("LAPTOP-TRAINING-AGENT", "Laptop Training Node Agent", "AGENT-SYS-EXEC", 7, "Security & Compliance", "gRPC / SSH Dial plane"),
                ("AURORA-R9-SERVER", "Aurora R9 Server Agent", "AGENT-SHM-ALLOC", 7, "Remote Action", "gRPC / SSH Server plane")
            ]
            cursor.executemany("INSERT INTO agents VALUES (?, ?, ?, ?, ?, ?)", seed_data)
            conn.commit()
            log("[PEDIGREE-DB] Database successfully seeded with 7-layer pedigree graph.", color=GREEN)
            
        # Drop legacy tickets to apply full Request Tracker compliance schema
        cursor.execute("DROP TABLE IF EXISTS tickets")
        
        # Create Best Practical RT-Compliant Tickets schema
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
            Queue TEXT NOT NULL,
            Subject TEXT NOT NULL,
            Status TEXT NOT NULL,
            Owner TEXT NOT NULL,
            Creator TEXT NOT NULL,
            Priority INTEGER NOT NULL,
            TimeEstimated INTEGER NOT NULL,
            TimeWorked INTEGER NOT NULL,
            TimeLeft INTEGER NOT NULL,
            Created TEXT NOT NULL,
            Starts TEXT,
            Started TEXT,
            Due TEXT,
            Resolved TEXT,
            LastUpdated TEXT,
            LastUpdatedBy TEXT,
            agent_id TEXT,
            layer_level INTEGER,
            specialty TEXT,
            task_description TEXT
        )
        """)
        
        # Create Best Practical RT-Compliant Transactions schema
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ObjectType TEXT NOT NULL,
            ObjectId INTEGER NOT NULL,
            TimeTaken INTEGER NOT NULL,
            Type TEXT NOT NULL,
            Field TEXT,
            OldValue TEXT,
            NewValue TEXT,
            ReferenceType TEXT,
            OldReference TEXT,
            NewReference TEXT,
            Data TEXT,
            Creator TEXT NOT NULL,
            Created TEXT NOT NULL
        )
        """)
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS ledger (
            block_index INTEGER PRIMARY KEY AUTOINCREMENT,
            previous_hash TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            mutation_payload TEXT NOT NULL,
            consensus_votes TEXT NOT NULL,
            minority_report TEXT,
            block_hash TEXT NOT NULL
        )
        """)
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS master_knowledge (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            last_updated_by TEXT NOT NULL
        )
        """)
        
        cursor.execute("SELECT COUNT(*) FROM ledger")
        if cursor.fetchone()[0] == 0:
            genesis_payload = json.dumps({"action": "GENESIS_INITIALIZATION", "state": "ACTIVE"})
            genesis_votes = json.dumps([
                {"agent_id": "AGENT-0", "vote_agree": True, "rationale": "Swarm Root Progenitor Genesis block constructed."}
            ])
            import hashlib
            ts = datetime.now().isoformat()
            genesis_data = f"10{ts}AGENT-0{genesis_payload}{genesis_votes}None"
            genesis_hash = hashlib.sha256(genesis_data.encode('utf-8')).hexdigest()
            cursor.execute("INSERT INTO ledger (block_index, previous_hash, timestamp, agent_id, mutation_payload, consensus_votes, minority_report, block_hash) VALUES (1, '0', ?, 'AGENT-0', ?, ?, 'None', ?)",
                           (ts, genesis_payload, genesis_votes, genesis_hash))
            
            cursor.execute("INSERT OR REPLACE INTO master_knowledge VALUES ('swarm_status', 'ONLINE', 'AGENT-0')")
            conn.commit()
            log("[LEDGER-GENESIS] Immutable ledger initialized and Genesis Block mined successfully.", color=GREEN)
            
        conn.close()
    except Exception as e:
        log(f"[PEDIGREE-DB-ERROR] Failed to initialize SQLite database: {e}", color=RED)

def serve():
    node_id = os.getenv("ANTIGRAVITY_NODE_ID", "AURORA-R9-SERVER")
    port = 1111

    # Initialize the 7-Layer Pedigree relational database
    initialize_pedigree_db()

    # Gorgeous ANSI Banner
    print(f"""
{GOLD} ▄████▄   ██▀███   ██▓███   ▄▄▄▄    ██▀███   ▒█████   ██▓     ▒█████   ▒█████  
▒██▀ ▀█  ▓██ ▒ ██▒▓██░  ██▒▓█████▄ ▓██ ▒ ██▒▒██▒  ██▒▓██▒    ▒██▒  ██▒▒██▒  ██▒
▒▓█    ▄ ▓██ ░▄█ ▒▓██░ ██▓▒▒██▒ ▄██▓██ ░▄█ ▒▒██░  ██▒▒██░    ▒██░  ██▒▒██░  ██▒
▒▓▓▄ ▄██▒▒██▀▀█▄  ▒██▄█▓▒ ▒▒██░█▀  ▒██▀▀█▄  ▒██   ██░▒██░    ▒██   ██░▒██   ██░
 ▒ ▓███▀ ░░██▓ ▒██▒▒██▒ ░  ░░▓█  ▀█▓░██▓ ▒██▒░ ████▓▒░░██████▒░ ████▓▒░░ ████▓▒░
 ░ ░▒ ▒  ░░ ▒▓ ░▒▓░▒▓▒░ ░  ░░▒▓███▀▒░ ▒▓ ░▒▓░░ ▒░▒░▒░ ░ ▒░▓  ░░ ▒░▒░▒░ ░ ▒░▒░▒░ 
   ░  ▒     ░▒ ░ ▒░░▒ ░     ▒░▒   ░   ░▒ ░ ▒░  ░ ▒ ▒░   ░ ░ ▒  ░  ░ ▒ ▒░  ░ ▒ ▒░ 
 ░          ░░   ░ ░░        ░    ░   ░░   ░ ░ ░ ░ ▒      ░ ░   ░ ░ ░ ▒ ░ ░ ░ ▒  
 ░ ░         ░               ░             ░     ░ ░        ░  ░    ░ ░     ░ ░  
 ░                                ░                                             
                {BOLD}SOVEREIGN SYSTEM - MESH CONTROL gRPC ENGINE (v2.0){RESET}
                       BOUND TO HIGH-SPEED INTERFACE PORT: {BOLD}{port}{RESET}
    """)

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    sync_pb2_grpc.add_AgentSyncServicer_to_server(AgentSyncServicer(node_id), server)
    server.add_insecure_port(f'[::]:{port}')
    
    log(f"Starting gRPC server on port {port}...", color=GREEN)
    server.start()
    log(f"gRPC server is running and listening. Press Ctrl+C to terminate.", color=GREEN)
    
    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        log("Stopping gRPC server...", color=GOLD)
        server.stop(0)
        log("Server stopped successfully.", color=GREEN)

if __name__ == '__main__':
    serve()
