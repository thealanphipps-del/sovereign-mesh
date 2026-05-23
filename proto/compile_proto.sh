#!/bin/bash
echo -e "\033[93m[PROTO] Compiling sync.proto...\033[0m"

# Go generation
pushd proto > /dev/null
protoc -I. \
    --go_out=. \
    --go_opt=paths=source_relative \
    --go-grpc_out=. \
    --go-grpc_opt=paths=source_relative \
    sync.proto mesh_proto.proto
popd > /dev/null

# Move to the nested directory used by the main go.mod replace directive
# The main repo expects them in proto/github.com/pqr-info/sovereign-mesh/proto
TARGET_DIR="proto/github.com/pqr-info/sovereign-mesh/proto"
mkdir -p $TARGET_DIR
mv -f proto/sync.pb.go proto/sync_grpc.pb.go $TARGET_DIR/
mv -f proto/mesh_proto.pb.go proto/mesh_proto_grpc.pb.go $TARGET_DIR/

# Python generation
python3 -m grpc_tools.protoc \
    -Iproto \
    --python_out=grpc_node \
    --grpc_python_out=grpc_node \
    proto/sync.proto proto/mesh_proto.proto

echo -e "\033[92m[PROTO] Compilation successful!\033[0m"
