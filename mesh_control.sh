#!/bin/bash

# --- AESTHETIC CONSTANTS ---
CYAN="\033[96m"
GREEN="\033[92m"
GOLD="\033[93m"
RED="\033[91m"
MAGENTA="\033[95m"
RESET="\033[0m"
BOLD="\033[1m"

SCRIPT_DIR="/home/aellok/sovereign_mesh"

function print_banner() {
    echo -e "${CYAN}"
    echo -e "   ▄████████  ▄██████▄     ▄█    █▄       ▄████████    ▄████████  ▄██████▄   ▄█  ███▄▄▄▄      ▄██████▄  "
    echo -e "  ███    ███ ███    ███ ███    ███     ███    ███   ███    ███ ███    ███ ███  ███▀▀▀██▄   ███    ███ "
    echo -e "  ███    █▀  ███    ███ ███    ███     ███    █▀    ███    █▀  ███    ███ ███▌ ███   ███   ███    █▀  "
    echo -e "  ███        ███    ███ ███    ███    ▄███▄▄▄      ▄███▄▄▄     ███    ███ ███▌ ███   ███  ▄███▄▄▄      "
    echo -e "▀███████████ ███    ███ ███    ███   ▀▀███▀▀▀     ▀▀███▀▀▀     ███    ███ ███▌ ███   ███ ▀▀███▀▀▀      "
    echo -e "         ███ ███    ███ ███    ███     ███    █▄    ███        ███    ███ ███  ███   ███   ███    █▄  "
    echo -e "   ▄█    ███ ███    ███  ███    ███     ███    ███   ███        ███    ███ ███  ███   ███   ███    ███ "
    echo -e " ▄████████▀   ▀██████▀    ▀█    █▀      ██████████   ███         ▀██████▀  █▀    ▀█   █▀    ████████▀  "
    echo -e "                                                                                                    "
    echo -e "                     ${GOLD}${BOLD}SOVEREIGN SYSTEM - MESH CONTROL ORCHESTRATOR (v2.0)${RESET}"
    echo -e ""
}

function usage() {
    print_banner
    echo -e "${BOLD}Usage:${RESET} $0 [command]"
    echo -e ""
    echo -e "${BOLD}Commands:${RESET}"
    echo -e "  ${GREEN}start${RESET}     - Start both gRPC and HighSpeed Memory Bus servers in background"
    echo -e "  ${GREEN}stop${RESET}      - Stop both running servers"
    echo -e "  ${GREEN}status${RESET}    - Check server daemon statuses and active network interfaces"
    echo -e "  ${GREEN}client${RESET}    - Run gRPC connection tests and memory bus speed tests"
    echo -e "  ${GREEN}compile${RESET}   - Re-compile Protobuf contracts"
    echo -e "  ${GREEN}tunnel${RESET}    - View SSH tunneling instructions and configurations"
    echo -e "  ${GREEN}user${RESET}      - Synchronize, add, list, or modify users/groups across the mesh"
    echo -e "  ${GREEN}ps${RESET}        - List running processes on the remote node"
    echo -e "  ${GREEN}ports${RESET}     - List active port bindings on the remote node"
    echo -e "  ${GREEN}exec${RESET}      - Execute a shell command remotely on the target host (with SSH failover)"
    echo -e "  ${GREEN}travel${RESET}    - Virtually migrate/teleport the agent mind via Memory Bus + remote exec"
    echo -e "  ${GREEN}pedigree${RESET}  - Trace active agent ancestry back to Agent 0 via 7-Layer relational DB"
    echo -e "  ${GREEN}propose${RESET}   - Propose a 7-layer memory/knowledge base mutation under 4/5 consensus"
    echo -e "  ${GREEN}ledger${RESET}    - Audit the immutable multi-dimensional blockchain relational ledger"
    echo -e "  ${GREEN}timemachine${RESET} - Override retroactively agent decisions and refactor the entire state tree"
    echo -e "  ${GREEN}forensics${RESET}   - Retroactively audit decision parameters and voting traces at any point"
    echo -e ""
}

function start_servers() {
    print_banner
    echo -e "${BOLD}[STARTING MESH SERVERS]${RESET}"
    
    # Check if servers are already running
    PORT_1111=$(ss -tln | grep -q :1111 && echo "Active" || echo "Inactive")
    PORT_11111=$(ss -tln | grep -q :11111 && echo "Active" || echo "Inactive")
    
    if [ "$PORT_1111" = "Active" ] || [ "$PORT_11111" = "Active" ]; then
        echo -e "${RED}Warning: Port 1111 or 11111 is already occupied! Stopping existing daemons...${RESET}"
        stop_servers
        sleep 1
    fi
    
    echo -e "Launching gRPC Server (Port 1111) in background..."
    nohup python3 -u $SCRIPT_DIR/grpc_node/grpc_server.py > /tmp/grpc_server.log 2>&1 &
    GRPC_PID=$!
    
    echo -e "Launching Memory Bus Server (Port 11111) in background..."
    nohup python3 -u $SCRIPT_DIR/memory_bus/server.py > /tmp/memory_bus.log 2>&1 &
    BUS_PID=$!

    echo -e "Launching Swarm Dashboard Web Server (Port 8080) in background..."
    nohup python3 -u $SCRIPT_DIR/grpc_node/web_server.py > /tmp/web_server.log 2>&1 &
    WEB_PID=$!
    
    sleep 2
    
    # Verify they running
    PORT_1111=$(ss -tln | grep -q :1111 && echo "Active" || echo "Inactive")
    PORT_11111=$(ss -tln | grep -q :11111 && echo "Active" || echo "Inactive")
    PORT_8080=$(ss -tln | grep -q :8080 && echo "Active" || echo "Inactive")
    
    if [ "$PORT_1111" = "Active" ] && [ "$PORT_11111" = "Active" ] && [ "$PORT_8080" = "Active" ]; then
        echo -e "${GREEN}SUCCESS: Sovereign Mesh & Web Portal are online and listening!${RESET}"
        echo -e " - gRPC Server Engine: PID $GRPC_PID (Logs: /tmp/grpc_server.log)"
        echo -e " - Memory Bus Engine : PID $BUS_PID (Logs: /tmp/memory_bus.log)"
        echo -e " - Swarm Web Portal  : PID $WEB_PID (Port: 8080, Logs: /tmp/web_server.log)"
    else
        echo -e "${RED}ERROR: Failed to initialize servers. Check logs in /tmp${RESET}"
    fi
}

function stop_servers() {
    echo -e "${BOLD}[STOPPING MESH SERVERS]${RESET}"
    
    # Query PIDs holding port 1111, 11111 and 8080
    GRPC_PIDS=$(lsof -t -i:1111 2>/dev/null)
    BUS_PIDS=$(lsof -t -i:11111 2>/dev/null)
    WEB_PIDS=$(lsof -t -i:8080 2>/dev/null)
    
    if [ -n "$GRPC_PIDS" ]; then
        echo -e "Terminating gRPC Server (PIDs: $GRPC_PIDS)..."
        kill -9 $GRPC_PIDS 2>/dev/null
    fi
    
    if [ -n "$BUS_PIDS" ]; then
        echo -e "Terminating Memory Bus Server (PIDs: $BUS_PIDS)..."
        kill -9 $BUS_PIDS 2>/dev/null
    fi

    if [ -n "$WEB_PIDS" ]; then
        echo -e "Terminating Swarm Dashboard Web Server (PIDs: $WEB_PIDS)..."
        kill -9 $WEB_PIDS 2>/dev/null
    fi
    
    # Kill any general matching processes just in case
    pkill -f grpc_server.py 2>/dev/null
    pkill -f memory_bus/server.py 2>/dev/null
    pkill -f web_server.py 2>/dev/null
    
    echo -e "${GREEN}All Sovereign Mesh Server instances stopped successfully.${RESET}"
}

function check_status() {
    print_banner
    echo -e "${BOLD}[TELEMETRY ENGINE STATUS]${RESET}"
    
    PORT_1111=$(ss -tln | grep -q :1111 && echo "ACTIVE" || echo "INACTIVE")
    PORT_11111=$(ss -tln | grep -q :11111 && echo "ACTIVE" || echo "INACTIVE")
    PORT_8080=$(ss -tln | grep -q :8080 && echo "ACTIVE" || echo "INACTIVE")
    
    if [ "$PORT_1111" = "ACTIVE" ]; then
        echo -e " - gRPC Control Bus (Port 1111)    : ${GREEN}${BOLD}ONLINE${RESET}"
    else
        echo -e " - gRPC Control Bus (Port 1111)    : ${RED}${BOLD}OFFLINE${RESET}"
    fi
    
    if [ "$PORT_11111" = "ACTIVE" ]; then
        echo -e " - HighSpeed RAM Bus (Port 11111)  : ${GREEN}${BOLD}ONLINE${RESET}"
    else
        echo -e " - HighSpeed RAM Bus (Port 11111)  : ${RED}${BOLD}OFFLINE${RESET}"
    fi

    if [ "$PORT_8080" = "ACTIVE" ]; then
        echo -e " - Swarm Web Portal (Port 8080)    : ${GREEN}${BOLD}ONLINE${RESET}"
    else
        echo -e " - Swarm Web Portal (Port 8080)    : ${RED}${BOLD}OFFLINE${RESET}"
    fi
    
    echo -e ""
    echo -e "${BOLD}[SHARED MEMORY PAGE MAP]${RESET}"
    if [ -f "/dev/shm/sovereign_page_table" ]; then
        SIZE=$(du -h /dev/shm/sovereign_page_table | cut -f1)
        echo -e " - RAM Page Table (/dev/shm/sovereign_page_table): ${GREEN}ALLOCATED (${SIZE})${RESET}"
    else
        echo -e " - RAM Page Table (/dev/shm/sovereign_page_table): ${GOLD}UNALLOCATED (Starts on server boot)${RESET}"
    fi
    echo -e ""
}

function run_client_suite() {
    print_banner
    echo -e "${BOLD}[RUNNING INTER-AGENT CLIENT SUITE]${RESET}"
    echo -e "Targeting loopback interface (localhost) for diagnostic confirmation..."
    echo -e ""
    
    # Run gRPC Suite
    echo -e "${BOLD}${CYAN}--- Executing gRPC Control Plane Diagnostics ---${RESET}"
    python3 $SCRIPT_DIR/grpc_node/grpc_client.py --host 127.0.0.1 --port 1111 --prompt "Synthesize mesh handshake confirmation"
    
    echo -e ""
    # Run Memory Bus Suite
    echo -e "${BOLD}${MAGENTA}--- Executing HighSpeed Paged RAM Bus Speed Test ---${RESET}"
    python3 $SCRIPT_DIR/memory_bus/client.py --host 127.0.0.1 --port 11111 --test-size 8
}

function manage_users() {
    # If no parameters, print help
    if [ -z "$2" ]; then
        print_banner
        echo -e "${BOLD}[SOVEREIGN MESH - USER MAINTENANCE SYSTEM]${RESET}"
        echo -e "${BOLD}Usage:${RESET} $0 user [action] [options]"
        echo -e ""
        echo -e "Actions:"
        echo -e "  ${GREEN}list${RESET}             - List all system users on the remote node"
        echo -e "  ${GREEN}sync${RESET}             - Synchronize local users (UID >= 1000) to the remote node"
        echo -e "  ${GREEN}add [name]${RESET}       - Add a new user to the remote node"
        echo -e "  ${GREEN}passwd [name]${RESET}    - Change a user's password on the remote node"
        echo -e "  ${GREEN}group [group]${RESET}    - Manage a group (create, add user, or remove user)"
        echo -e ""
        echo -e "General Options:"
        echo -e "  --host [ip]      - Target host (default: 127.0.0.1)"
        echo -e "  --port [port]    - Target port (default: 1111)"
        echo -e "  --uid [uid]      - Specify explicit UID (for add)"
        echo -e "  --gid [gid]      - Specify explicit GID (for group create)"
        echo -e "  --password [pw]  - Specify password (for add/passwd)"
        echo -e "  --group [group]  - Specify primary group (for add)"
        echo -e "  --action [act]   - Specify group action: create, add, remove"
        echo -e "  --username [usr] - Specify username for group operations"
        echo -e ""
        echo -e "Examples:"
        echo -e "  $0 user sync --host 10.0.0.5"
        echo -e "  $0 user list --host 10.0.0.5"
        echo -e "  $0 user add alice --password mySecret123 --host 10.0.0.5"
        echo -e "  $0 user passwd alice --password newSecret123 --host 10.0.0.5"
        echo -e "  $0 user group admin --action create --gid 2000 --host 10.0.0.5"
        echo -e "  $0 user group admin --action add --username alice --host 10.0.0.5"
        return
    fi

    case "$2" in
        list)
            python3 $SCRIPT_DIR/grpc_node/grpc_client.py --list-users "${@:3}"
            ;;
        sync)
            python3 $SCRIPT_DIR/grpc_node/grpc_client.py --sync-users "${@:3}"
            ;;
        add)
            if [ -z "$3" ]; then
                echo -e "${RED}Error: Username is required for add action.${RESET}"
                return
            fi
            python3 $SCRIPT_DIR/grpc_node/grpc_client.py --adduser "$3" "${@:4}"
            ;;
        passwd)
            if [ -z "$3" ]; then
                echo -e "${RED}Error: Username is required for passwd action.${RESET}"
                return
            fi
            python3 $SCRIPT_DIR/grpc_node/grpc_client.py --chpasswd "$3" "${@:4}"
            ;;
        group)
            if [ -z "$3" ]; then
                echo -e "${RED}Error: Group name is required for group action.${RESET}"
                return
            fi
            python3 $SCRIPT_DIR/grpc_node/grpc_client.py --manage-group "$3" "${@:4}"
            ;;
        *)
            echo -e "${RED}Unknown action: $2${RESET}"
            ;;
    esac
}

case "$1" in
    start)
        start_servers
        ;;
    stop)
        stop_servers
        ;;
    status)
        check_status
        ;;
    client)
        run_client_suite
        ;;
    compile)
        chmod +x $SCRIPT_DIR/proto/compile_proto.sh
        $SCRIPT_DIR/proto/compile_proto.sh
        ;;
    tunnel)
        chmod +x $SCRIPT_DIR/tunnels/setup_tunnels.sh
        $SCRIPT_DIR/tunnels/setup_tunnels.sh
        ;;
    user)
        manage_users "$@"
        ;;
    ps)
        shift
        python3 $SCRIPT_DIR/grpc_node/grpc_client.py --ps "$@"
        ;;
    ports)
        shift
        python3 $SCRIPT_DIR/grpc_node/grpc_client.py --ports "$@"
        ;;
    exec)
        shift
        if [ -z "$1" ]; then
            echo -e "${RED}Error: Command string is required for exec.${RESET}"
            exit 1
        fi
        python3 $SCRIPT_DIR/grpc_node/grpc_client.py --exec "$1" "${@:2}"
        ;;
    travel)
        shift
        if [ -z "$1" ]; then
            echo -e "${RED}Error: Resume command string is required for travel.${RESET}"
            exit 1
        fi
        python3 $SCRIPT_DIR/grpc_node/grpc_client.py --travel "$1" "${@:2}"
        ;;
    pedigree)
        shift
        python3 $SCRIPT_DIR/grpc_node/grpc_client.py --pedigree "$@"
        ;;
    propose)
        shift
        python3 $SCRIPT_DIR/grpc_node/grpc_client.py --propose "$@"
        ;;
    ledger)
        shift
        python3 $SCRIPT_DIR/grpc_node/grpc_client.py --ledger "$@"
        ;;
    timemachine)
        shift
        python3 $SCRIPT_DIR/grpc_node/grpc_client.py --timemachine "$@"
        ;;
    forensics)
        shift
        python3 $SCRIPT_DIR/grpc_node/grpc_client.py --forensics "$@"
        ;;
    *)
        usage
        ;;
esac
