#!/bin/bash
echo -e "\033[93m[PROTO] Compiling sync.proto...\033[0m"

# Ensure target directory is clean and regenerate
rm -f /home/aellok/sovereign_mesh/grpc_node/sync_pb2*.py

python3 -m grpc_tools.protoc \
    -I/home/aellok/sovereign_mesh/proto \
    --python_out=/home/aellok/sovereign_mesh/grpc_node \
    --grpc_python_out=/home/aellok/sovereign_mesh/grpc_node \
    /home/aellok/sovereign_mesh/proto/sync.proto

echo -e "\033[92m[PROTO] Compilation successful!\033[0m"
