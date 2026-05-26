# ==============================================================================
# SOVEREIGN-27: REMOTE RPC EXECUTION DISPATCHER
# Dispatch commands directly to the distributed Termux NPU node (192.168.12.201:8081)
# Usage: python3 rpc_execute.py "ls -la"
# ==============================================================================

import sys
import json
import urllib.request
import urllib.error

# Target Remote NPU Node RPC Endpoint
RPC_URL = "http://192.168.12.201:8081/rpc"

def dispatch_rpc_command(cmd):
    print(f"📡 DISPATCHING RPC: Sending command '{cmd}' to NPU node 192.168.12.201:8081...")
    
    # Stratum/JSON-RPC command execution schema
    payload = {
        "jsonrpc": "2.0",
        "method": "execute",
        "params": [cmd],
        "id": 1
    }
    
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        RPC_URL, 
        data=data, 
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            resp_data = json.loads(response.read().decode("utf-8"))
            if "error" in resp_data and resp_data["error"] is not None:
                print(f"❌ RPC ERROR: {resp_data['error']}")
                sys.exit(1)
            
            result = resp_data.get("result", "")
            print("✅ RPC RESPONSE RECEIVED:")
            print("------------------------------------------------------------------------")
            print(result)
            print("------------------------------------------------------------------------")
            
    except urllib.error.URLError as e:
        print(f"⚠️ RPC NETWORK FAILURE: Node is currently unreachable or offline: {e.reason}")
        print("💡 Hint: Verify that the Termux RPC server daemon is actively listening on your phone on port 8081.")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 rpc_execute.py \"<command>\"")
        sys.exit(1)
        
    cmd_to_run = sys.argv[1]
    dispatch_rpc_command(cmd_to_run)
