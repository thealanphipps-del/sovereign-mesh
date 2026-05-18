#!/usr/bin/env python3
import http.server
import socketserver
import json
import sqlite3
import os
import sys
import grpc

# Append path to import sync files
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(SCRIPT_DIR)

import sync_pb2
import sync_pb2_grpc

PORT = 8080
DB_PATH = "/home/aellok/sovereign_mesh/agent_pedigree.db"

class SwarmDashboardHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Override to prevent stdout spam
        pass

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            with open(os.path.join(SCRIPT_DIR, "index.html"), "rb") as f:
                self.wfile.write(f.read())
            return

        elif self.path == "/api/agents":
            self.send_json_response(self.query_db("SELECT agent_id, name, parent_agent_id, layer_level, specialty, subspecialty FROM agents ORDER BY layer_level ASC"))
            return

        elif self.path == "/api/tickets":
            self.send_json_response(self.query_db("SELECT ticket_id, Queue, Subject, Status, Owner, Creator, Priority, TimeEstimated, TimeWorked, TimeLeft, Created, Resolved, LastUpdated, LastUpdatedBy, agent_id, layer_level, specialty, task_description FROM tickets ORDER BY ticket_id DESC"))
            return

        elif self.path == "/api/transactions":
            self.send_json_response(self.query_db("SELECT transaction_id, ObjectType, ObjectId, TimeTaken, Type, Field, OldValue, NewValue, Data, Creator, Created FROM transactions ORDER BY transaction_id DESC"))
            return

        elif self.path == "/api/ledger":
            blocks = self.query_db("SELECT block_index, previous_hash, timestamp, agent_id, mutation_payload, consensus_votes, minority_report, block_hash FROM ledger ORDER BY block_index ASC")
            
            # Chain verification audit logic on retrieval
            chain_valid = "SECURE: Chain validation integrity matches perfectly."
            for idx, r in enumerate(blocks):
                if idx > 0:
                    prev_block = blocks[idx - 1]
                    if r["previous_hash"] != prev_block["block_hash"]:
                        chain_valid = f"CORRUPTED: Hash mismatch at Block #{r['block_index']}!"
            
            response_data = {
                "blocks": blocks,
                "chain_validation_status": chain_valid
            }
            self.send_json_response(response_data)
            return

        else:
            self.send_error(404, "Resource not found")

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        payload = json.loads(post_data.decode('utf-8'))

        if self.path == "/api/tickets/create":
            key = payload.get("key")
            val = payload.get("value")
            reason = payload.get("reason")
            proposer = payload.get("proposer", "WEB-PORTAL")

            channel = grpc.insecure_channel('127.0.0.1:1111')
            stub = sync_pb2_grpc.AgentSyncStub(channel)
            req = sync_pb2.MutationRequest(
                proposer_agent_id=proposer,
                target_key=key,
                proposed_value=val,
                change_reason=reason
            )
            try:
                res = stub.ProposeSwarmMutation(req)
                votes = []
                for v in res.votes:
                    votes.append({
                        "agent_id": v.agent_id,
                        "vote_agree": v.vote_agree,
                        "rationale": v.rationale
                    })
                response_data = {
                    "consensus_reached": res.consensus_reached,
                    "consensus_ratio": res.consensus_ratio,
                    "votes": votes,
                    "minority_report": res.minority_report,
                    "block_index": res.block_index,
                    "block_hash": res.block_hash,
                    "status": res.status
                }
            except Exception as e:
                response_data = {"error": str(e), "consensus_reached": False, "consensus_ratio": "0/5"}

            self.send_json_response(response_data)
            return

        elif self.path == "/api/tickets/timemachine":
            block_idx = int(payload.get("block_index"))
            key = payload.get("key")
            val = payload.get("value")
            reason = payload.get("reason")

            channel = grpc.insecure_channel('127.0.0.1:1111')
            stub = sync_pb2_grpc.AgentSyncStub(channel)
            req = sync_pb2.TimeTravelRequest(
                target_block_index=block_idx,
                new_target_key=key,
                new_proposed_value=val,
                override_reason=reason
            )
            try:
                res = stub.TimeTravelOverride(req)
                response_data = {
                    "success": res.success,
                    "message": res.message,
                    "refactor_logs": list(res.refactor_logs),
                    "new_chain_validation_status": res.new_chain_validation_status
                }
            except Exception as e:
                response_data = {"success": False, "message": str(e), "refactor_logs": []}

            self.send_json_response(response_data)
            return

        else:
            self.send_error(404, "Endpoint not found")

    def send_json_response(self, data):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def query_db(self, query, params=()):
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            print(f"[DB-QUERY-ERROR] {e}")
            return []

if __name__ == "__main__":
    handler = SwarmDashboardHandler
    # Allow port reuse to prevent address already in use errors
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), handler) as httpd:
        print(f"[WEB-SERVER] Sovereign Swarm control workspace listening on port {PORT}...")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[WEB-SERVER] Stopping dashboard server...")
            httpd.server_close()
            sys.exit(0)
