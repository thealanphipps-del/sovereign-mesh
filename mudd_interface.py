#!/usr/bin/env python3
import os
import sys
import time
import socket
import select

# Setup Python PATH to load local gRPC modules
sys.path.append(os.path.join(os.path.dirname(__file__), 'grpc_node'))

import grpc
import sync_pb2
import sync_pb2_grpc

# --- AESTHETIC ANSI COLOR CODES ---
C_CYAN = "\033[96m"
C_GREEN = "\033[92m"
C_GOLD = "\033[93m"
C_RED = "\033[91m"
C_MAGENTA = "\033[95m"
C_BLUE = "\033[94m"
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_UNDER = "\033[4m"
C_CLEAR = "\033[2J\033[H"

# --- DUNGEON DATA (MESH NODES AS ROOMS) ---
ROOMS = {
    "0.MH": {
        "name": "The Nuremberg Crypt (0.MH)",
        "ip": "46.224.84.64",
        "role": "ANCHOR",
        "desc": "The foundational anchor of the Sovereign Swarm. Glowing servers hum in the darkness, storing the immutable truth of the genesis ledger.",
        "exits": ["38.MH", "39.MH"]
    },
    "38.MH": {
        "name": "The Forge Chamber (38.MH)",
        "ip": "62.238.2.240",
        "role": "FORGE",
        "desc": "A heavy-duty computation chamber where round-robin Go matches are held. Neural weights are forged and calibrated in high-stakes competition.",
        "exits": ["0.MH", "39.MH", "201.MH"]
    },
    "39.MH": {
        "name": "The Helsinki Sentry Tower (39.MH)",
        "ip": "204.168.138.60",
        "role": "SENTRY",
        "desc": "The tall digital lookout position. Acts as the primary SSH jump host and sentry gate, bridging local terminal users to the deep private mesh.",
        "exits": ["0.MH", "38.MH", "40.MH", "50.MH"]
    },
    "40.MH": {
        "name": "The Capicant Lab (40.MH)",
        "ip": "10.128.0.2",
        "role": "CAPICANT",
        "desc": "An internal, secure GCP sanctuary. Zero-copy RAM paging frameworks are prepared here for high-throughput process teleportations.",
        "exits": ["39.MH", "50.MH"]
    },
    "50.MH": {
        "name": "The Operations Hub (50.MH)",
        "ip": "136.113.240.237",
        "role": "OPS",
        "desc": "An external GCP command center monitoring global traffic, revenue redistributions, and Hetzner-EU fallback server scaling.",
        "exits": ["39.MH", "40.MH", "201.MH"]
    },
    "201.MH": {
        "name": "The Edge Relay Vault (201.MH)",
        "ip": "89.167.91.81",
        "role": "EDGE",
        "desc": "A gateway facing the outer world. Staking transactions are verified and citizen passport keys are minted at the edge.",
        "exits": ["38.MH", "50.MH"]
    }
}

# --- SYSTEM STATE ---
current_room_id = "39.MH"  # Start at the Sentry Tower (Jump Host)
channel = None
stub = None

def init_grpc():
    global channel, stub
    try:
        channel = grpc.insecure_channel("localhost:1111")
        stub = sync_pb2_grpc.AgentSyncStub(channel)
    except Exception as e:
        pass

def print_logo():
    print(f"{C_CYAN}")
    print("   ▄████████  ▄██████▄     ▄█    █▄       ▄████████    ▄████████  ▄██████▄   ▄█  ███▄▄▄▄      ▄██████▄  ")
    print("  ███    ███ ███    ███ ███    ███     ███    ███   ███    ███ ███    ███ ███  ███▀▀▀██▄   ███    ███ ")
    print("  ███    █▀  ███    ███ ███    ███     ███    █▀    ███    █▀  ███    ███ ███▌ ███   ███   ███    █▀  ")
    print("  ███        ███    ███ ███    ███    ▄███▄▄▄      ▄███▄▄▄     ███    ███ ███▌ ███   ███  ▄███▄▄▄      ")
    print("▀███████████ ███    ███ ███    ███   ▀▀███▀▀▀     ▀▀███▀▀▀     ███    ███ ███▌ ███   ███ ▀▀███▀▀▀      ")
    print("         ███ ███    ███ ███    ███     ███    █▄    ███        ███    ███ ███  ███   ███   ███    █▄  ")
    print("   ▄█    ███ ███    ███  ███    ███     ███    ███   ███        ███    ███ ███  ███   ███   ███    ███ ")
    print(" ▄████████▀   ▀██████▀    ▀█    █▀      ██████████   ███         ▀██████▀  █▀    ▀█   █▀    ████████▀  ")
    print(f"{C_GOLD}{C_BOLD}                   SOVEREIGN SWARM MUDD INTERACTIVE DASHBOARD v2.0{C_RESET}\n")

def print_header(title):
    border = "=" * 78
    print(f"{C_GOLD}{border}{C_RESET}")
    print(f"{C_BOLD}{C_CYAN} 💎 {title.upper()}{C_RESET}")
    print(f"{C_GOLD}{border}{C_RESET}")

def get_node_latency(ip):
    # Simulated latency ping for aesthetic accuracy
    try:
        t0 = time.time()
        s = socket.create_connection((ip, 22), timeout=0.5)
        s.close()
        return f"{C_GREEN}{(time.time() - t0)*1000:.2f} ms{C_RESET}"
    except:
        return f"{C_RED}TIMEOUT / HIDDEN{C_RESET}"

def look_around():
    room = ROOMS[current_room_id]
    print_header(f"Location: {room['name']}")
    print(f"{C_GOLD}  [Role]{C_RESET}      {C_BOLD}{room['role']}{C_RESET}")
    print(f"{C_GOLD}  [IP Address]{C_RESET} {room['ip']}")
    print(f"{C_GOLD}  [Latency]{C_RESET}    {get_node_latency(room['ip'])} (via wireguard bridge)")
    print(f"\n{C_BLUE}{C_BOLD}Description:{C_RESET}")
    print(f"  {room['desc']}")
    
    print(f"\n{C_MAGENTA}{C_BOLD}Visible Exits (Tunnels):{C_RESET}")
    for ex in room['exits']:
        dest = ROOMS[ex]
        print(f"  ⚡ {C_GOLD}{ex}{C_RESET} -> {dest['name']} [{dest['role']}]")
    print()

def move_to(dest_id):
    global current_room_id
    room = ROOMS[current_room_id]
    if dest_id not in room['exits']:
        print(f"{C_RED}Error: There is no direct Wireguard tunnel from here to {dest_id}!{C_RESET}")
        time.sleep(1.5)
        return
    print(f"\n🚄 {C_CYAN}Teleporting mind segment to {dest_id}...{C_RESET}")
    time.sleep(0.8)
    current_room_id = dest_id
    print(f"✨ Arrived at {ROOMS[current_room_id]['name']}!")
    time.sleep(0.5)

def run_grpc_ping():
    print_header("gRPC Control Plane Ping")
    try:
        res = stub.Ping(sync_pb2.PingRequest(client_id="MUDD-CONSOLE"))
        print(f"✅ {C_GREEN}ONLINE{C_RESET} | Server ID: {C_BOLD}{res.server_id}{C_RESET} | Status: {res.status}")
    except Exception as e:
        print(f"❌ {C_RED}OFFLINE: Failed to dial mesh server on localhost:1111: {e}{C_RESET}")
    input("\nPress ENTER to return to MUDD...")

def audit_pedigree():
    print_header("Sovereign Swarm Pedigree Audit")
    try:
        res = stub.TracePedigree(sync_pb2.PedigreeRequest(agent_id="AGENT-001"))
        print(f"{C_GREEN}Pedigree chain verified back to Agent-0 (Progenitor):{C_RESET}\n")
        print(f"  {C_BOLD}Root Ancestor{C_RESET} : {res.root_ancestor_id}")
        print(f"  {C_BOLD}Relationship{C_RESET}  : {res.relationship_profile}")
        print(f"  {C_BOLD}Generation{C_RESET}    : Gen {res.generation_depth}")
        print(f"  {C_BOLD}Shared Memory{C_RESET} : {res.shared_segment_ref}")
        print(f"\nRelational Node Path:")
        for node in res.relation_nodes:
            print(f"  ⚡ {C_GOLD}{node}{C_RESET}")
    except Exception as e:
        print(f"❌ {C_RED}Failed to trace pedigree: {e}{C_RESET}")
    input("\nPress ENTER to return to MUDD...")

def query_ledger():
    print_header("Sovereign Immutable Ledger Audit")
    try:
        res = stub.QuerySwarmLedger(sync_pb2.LedgerQueryRequest(query_param="*"))
        print(f"{C_GREEN}Materialized state from Swarm Ledger blocks:{C_RESET}\n")
        print(f"  {C_BOLD}Last Block Hash{C_RESET}  : {res.last_block_hash}")
        print(f"  {C_BOLD}Sequence Number{C_RESET}  : Block #{res.sequence_number}")
        print(f"  {C_BOLD}Accounting Proof{C_RESET}: {res.accounting_proof}")
        print(f"\nActive Ledger Shards:")
        for shard in res.active_shards:
            print(f"  ● {C_GOLD}{shard}{C_RESET}")
    except Exception as e:
        print(f"❌ {C_RED}Failed to query ledger: {e}{C_RESET}")
    input("\nPress ENTER to return to MUDD...")

def display_grimoire():
    print_clear()
    print_header("Sovereign Protocol Grimoire")
    print(f"1. {C_CYAN}{C_BOLD}STARBIRTH PROTOCOL (SBP-001){C_RESET}")
    print("   The foundational bootstrap protocol of the swarm. Spinlocks the memory pages")
    print("   on `/dev/shm` to allow 128 agents to execute zero-copy weight mutations.")
    print()
    print(f"2. {C_CYAN}{C_BOLD}ATOMIC SWAP{C_RESET}")
    print("   Live hot-swaps active execution PIDs with upgraded binaries by passing")
    print("   socket file descriptors through Unix sockets (`SCM_RIGHTS`), preventing downtime.")
    print()
    print(f"3. {C_CYAN}{C_BOLD}OBULUSK MANEUVER{C_RESET}")
    print("   A stealth tunneling reflex that establishes reverse-ssh tunnels back to")
    print("   the Helsinki Sentry (39.MH) when outbound security policies block standard ports.")
    print()
    print(f"4. {C_CYAN}{C_BOLD}iPN MULTICAST (ff02::c0ba:11){C_RESET}")
    print("   A private IPv6 multicast network boundary that allows decentralized agents")
    print("   to 'hear' telemetry broadcasts without exposing standard ports to the WAN.")
    input("\nPress ENTER to return to MUDD...")

def print_clear():
    sys.stdout.write(C_CLEAR)
    sys.stdout.flush()

def main_loop():
    init_grpc()
    while True:
        print_clear()
        print_logo()
        look_around()
        
        print(f"{C_GOLD}{'=' * 78}{C_RESET}")
        print(f"{C_BOLD}MUDD Swarm Command Console:{C_RESET}")
        print(f"  [{C_GREEN}1{C_RESET}] Look Around (Diagnostic Audit)")
        print(f"  [{C_GREEN}2{C_RESET}] Move (Teleport to direct tunnel exit)")
        print(f"  [{C_GREEN}3{C_RESET}] gRPC Control Ping")
        print(f"  [{C_GREEN}4{C_RESET}] Audit Swarm Ancestry (Pedigree)")
        print(f"  [{C_GREEN}5{C_RESET}] Query Swarm Immutable Ledger")
        print(f"  [{C_GREEN}6{C_RESET}] Read Protocol Grimoire (Docs)")
        print(f"  [{C_GREEN}0{C_RESET}] Exit Swarm Matrix")
        print(f"{C_GOLD}{'=' * 78}{C_RESET}")
        
        try:
            choice = input(f"{C_CYAN}{C_BOLD}mud-operator@{current_room_id}> {C_RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{C_RED}Terminating connection to Swarm Matrix...{C_RESET}")
            break
            
        if choice == "0":
            print(f"\n{C_RED}Terminating connection to Swarm Matrix...{C_RESET}")
            break
        elif choice == "1":
            look_around()
            input("Press ENTER to continue...")
        elif choice == "2":
            dest = input(f"{C_GOLD}Enter exit node to travel to ({', '.join(ROOMS[current_room_id]['exits'])}): {C_RESET}").strip().upper()
            move_to(dest)
        elif choice == "3":
            run_grpc_ping()
        elif choice == "4":
            audit_pedigree()
        elif choice == "5":
            query_ledger()
        elif choice == "6":
            display_grimoire()
        else:
            print(f"{C_RED}Unknown command in this chamber.{C_RESET}")
            time.sleep(1)

if __name__ == "__main__":
    main_loop()
