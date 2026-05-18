#!/bin/bash

# --- AESTHETIC CONSTANTS ---
CYAN="\033[96m"
GREEN="\033[92m"
GOLD="\033[93m"
RED="\033[91m"
RESET="\033[0m"
BOLD="\033[1m"

echo -e "${GOLD}======================================================================${RESET}"
echo -e "${BOLD}${CYAN}          SOVEREIGN MESH WORKSPACE - TUNNELING ENGINE CONFIG${RESET}"
echo -e "${GOLD}======================================================================${RESET}"
echo -e "This script assists in establishing secure SSH/WSL Tunnels between:"
echo -e " - ${BOLD}AURORA-R9-SERVER${RESET} (Development/Training Server)"
echo -e " - ${BOLD}LAPTOP-TRAINING-AGENT${RESET} (Local Laptop Node)"
echo -e ""
echo -e "We are bridging two key protocol layers:"
echo -e " 1. ${BOLD}gRPC Port (1111)${RESET} - Agent control plane and metadata synchronization"
echo -e " 2. ${BOLD}HighSpeed Bus Port (11111)${RESET} - Zero-copy mmap RAM-Paging file pipeline"
echo -e ""

# Quick diagnostics
echo -e "${BOLD}[DIAGNOSTICS] Checking local listener ports...${RESET}"
PORT_1111=$(ss -tln | grep -q :1111 && echo "Active" || echo "Inactive")
PORT_11111=$(ss -tln | grep -q :11111 && echo "Active" || echo "Inactive")

if [ "$PORT_1111" = "Active" ]; then
    echo -e " - Port 1111 (gRPC):  ${GREEN}ACTIVE${RESET} (Server is running locally)"
else
    echo -e " - Port 1111 (gRPC):  ${GOLD}INACTIVE${RESET} (Ready for local port forwarding)"
fi

if [ "$PORT_11111" = "Active" ]; then
    echo -e " - Port 11111 (Bus):  ${GREEN}ACTIVE${RESET} (Server is running locally)"
else
    echo -e " - Port 11111 (Bus):  ${GOLD}INACTIVE${RESET} (Ready for local port forwarding)"
fi
echo -e ""

echo -e "${BOLD}[CONFIGURATION OPTIONS]${RESET}"
echo -e "${BOLD}Option A: Establish local tunnel mapping to remote Aurora-R9-Server${RESET}"
echo -e "Run this command on your ${BOLD}Laptop${RESET} to forward remote server ports to your local host:"
echo -e "  ${GREEN}ssh -L 1111:localhost:1111 -L 11111:localhost:11111 aellok@<AURORA_R9_IP> -N -v${RESET}"
echo -e ""
echo -e "${BOLD}Option B: Establish reverse tunnel (Reverse port forwarding)${RESET}"
echo -e "If your laptop is behind NAT and the Aurora-R9-Server needs to connect to the laptop:"
echo -e "Run this command on your ${BOLD}Laptop${RESET}:"
echo -e "  ${GREEN}ssh -R 1111:localhost:1111 -R 11111:localhost:11111 aellok@<AURORA_R9_IP> -N -v${RESET}"
echo -e ""
echo -e "${BOLD}Option C: Automate inside .ssh/config${RESET}"
echo -e "To make this connection persistent, add this profile to your ${BOLD}~/.ssh/config${RESET} file:"
echo -e "${CYAN}"
cat << 'EOF'
Host aurora-r9
    HostName <AURORA_R9_IP>
    User aellok
    LocalForward 1111 localhost:1111
    LocalForward 11111 localhost:11111
    ExitOnForwardFailure yes
    ServerAliveInterval 60
EOF
echo -e "${RESET}"

echo -e "${GOLD}======================================================================${RESET}"
echo -e "To test gRPC connectivity after tunneling:"
echo -e "  ${BOLD}python3 ~/sovereign_mesh/grpc_node/grpc_client.py --host 127.0.0.1 --port 1111 --prompt \"Hello\"${RESET}"
echo -e ""
echo -e "To test HighSpeed RAM Bus connectivity after tunneling:"
echo -e "  ${BOLD}python3 ~/sovereign_mesh/memory_bus/client.py --host 127.0.0.1 --port 11111${RESET}"
echo -e "${GOLD}======================================================================${RESET}"
