#!/usr/bin/env python3
import http.server
import socketserver
import json
import sqlite3
import os
import sys
import grpc
from urllib.parse import urlparse, parse_qs

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
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query = parse_qs(parsed_url.query)

        # 1. Serving static front-end workspace
        if path == "/" or path == "/index.html":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            with open(os.path.join(SCRIPT_DIR, "index.html"), "rb") as f:
                self.wfile.write(f.read())
            return

        # 2. REST 2.0 - API Root Discovery Endpoint
        elif path == "/api/v2" or path == "/api/v2/":
            directory = {
                "_links": {
                    "self": {"href": "/api/v2", "method": "GET"},
                    "agents": {"href": "/api/v2/agents", "method": "GET"},
                    "tickets": {"href": "/api/v2/tickets", "method": "GET", "filters": ["status", "queue"]},
                    "transactions": {"href": "/api/v2/transactions", "method": "GET", "filters": ["type", "limit"]},
                    "ledger": {"href": "/api/v2/ledger", "method": "GET"}
                },
                "meta": {
                    "version": "2.0.0-REST",
                    "codename": "Event Horizon HATEOAS",
                    "status": "ONLINE",
                    "engine": "POSIX sovereign Swarm Sync Engine"
                }
            }
            self.send_json_response(directory)
            return

        # 3. REST 2.0 - Agents Endpoint
        elif path == "/api/v2/agents" or path == "/api/agents":
            agents = self.query_db("SELECT agent_id, name, parent_agent_id, layer_level, specialty, subspecialty FROM agents ORDER BY layer_level ASC")
            
            # Map HATEOAS links to individual agent objects
            data = []
            for a in agents:
                a_data = dict(a)
                a_data["_links"] = {
                    "self": {"href": f"/api/v2/agents/{a['agent_id']}", "method": "GET"},
                    "parent": {"href": f"/api/v2/agents/{a['parent_agent_id']}" if a['parent_agent_id'] else None, "method": "GET"},
                    "tickets": {"href": f"/api/v2/tickets?agent_id={a['agent_id']}", "method": "GET"}
                }
                data.append(a_data)

            response = {
                "_links": {
                    "self": {"href": "/api/v2/agents", "method": "GET"},
                    "parent": {"href": "/api/v2", "method": "GET"}
                },
                "data": data,
                "meta": {
                    "total_count": len(data)
                }
            }
            self.send_json_response(response)
            return

        # 4. REST 2.0 - Tickets Endpoint (Supports filters: status, queue)
        elif path == "/api/v2/tickets" or path == "/api/tickets":
            status_filter = query.get("status", [None])[0]
            queue_filter = query.get("queue", [None])[0]
            
            sql = "SELECT ticket_id, Queue, Subject, Status, Owner, Creator, Priority, TimeEstimated, TimeWorked, TimeLeft, Created, Resolved, LastUpdated, LastUpdatedBy, agent_id, layer_level, specialty, task_description FROM tickets"
            params = []
            conditions = []
            
            if status_filter:
                conditions.append("Status = ?")
                params.append(status_filter)
            if queue_filter:
                conditions.append("Queue = ?")
                params.append(queue_filter)
                
            if conditions:
                sql += " WHERE " + " AND ".join(conditions)
            sql += " ORDER BY ticket_id DESC"
            
            tickets = self.query_db(sql, params)
            
            # Wrap in REST 2.0 HATEOAS response
            data = []
            for t in tickets:
                t_data = dict(t)
                t_data["_links"] = {
                    "self": {"href": f"/api/v2/tickets/{t['ticket_id']}", "method": "GET"},
                    "transactions": {"href": f"/api/v2/transactions?ticket_id={t['ticket_id']}", "method": "GET"}
                }
                data.append(t_data)
                
            response = {
                "_links": {
                    "self": {"href": "/api/v2/tickets", "method": "GET"},
                    "create": {"href": "/api/v2/tickets", "method": "POST"},
                    "parent": {"href": "/api/v2", "method": "GET"}
                },
                "data": data,
                "meta": {
                    "total_count": len(data),
                    "filters_applied": {
                        "status": status_filter,
                        "queue": queue_filter
                    }
                }
            }
            self.send_json_response(response)
            return

        # 5. REST 2.0 - Transactions Endpoint (Supports filters: type, limit)
        elif path == "/api/v2/transactions" or path == "/api/transactions":
            type_filter = query.get("type", [None])[0]
            limit_val = query.get("limit", [None])[0]
            
            sql = "SELECT transaction_id, ObjectType, ObjectId, TimeTaken, Type, Field, OldValue, NewValue, Data, Creator, Created FROM transactions"
            params = []
            conditions = []
            
            if type_filter:
                conditions.append("Type = ?")
                params.append(type_filter)
                
            if conditions:
                sql += " WHERE " + " AND ".join(conditions)
            sql += " ORDER BY transaction_id DESC"
            
            if limit_val:
                try:
                    sql += " LIMIT ?"
                    params.append(int(limit_val))
                except ValueError:
                    pass
                    
            transactions = self.query_db(sql, params)
            
            # Wrap in REST 2.0
            data = []
            for tx in transactions:
                tx_data = dict(tx)
                tx_data["_links"] = {
                    "self": {"href": f"/api/v2/transactions/{tx['transaction_id']}", "method": "GET"},
                    "ticket": {"href": f"/api/v2/tickets/{tx['ObjectId']}", "method": "GET"}
                }
                data.append(tx_data)
                
            response = {
                "_links": {
                    "self": {"href": "/api/v2/transactions", "method": "GET"},
                    "parent": {"href": "/api/v2", "method": "GET"}
                },
                "data": data,
                "meta": {
                    "total_count": len(data),
                    "filters_applied": {
                        "type": type_filter,
                        "limit": limit_val
                    }
                }
            }
            self.send_json_response(response)
            return

        # 6. REST 2.0 - Ledger Endpoint
        elif path == "/api/v2/ledger" or path == "/api/ledger":
            blocks = self.query_db("SELECT block_index, previous_hash, timestamp, agent_id, mutation_payload, consensus_votes, minority_report, block_hash FROM ledger ORDER BY block_index ASC")
            
            # Chain verification audit logic on retrieval
            chain_valid = "SECURE: Chain validation integrity matches perfectly."
            for idx, r in enumerate(blocks):
                if idx > 0:
                    prev_block = blocks[idx - 1]
                    if r["previous_hash"] != prev_block["block_hash"]:
                        chain_valid = f"CORRUPTED: Hash mismatch at Block #{r['block_index']}!"
            
            # Wrap blocks
            data = []
            for b in blocks:
                b_data = dict(b)
                b_data["_links"] = {
                    "self": {"href": f"/api/v2/ledger/{b['block_index']}", "method": "GET"},
                    "timemachine_override": {"href": "/api/v2/timemachine", "method": "POST", "body": {"block_index": b['block_index']}}
                }
                data.append(b_data)

            response = {
                "_links": {
                    "self": {"href": "/api/v2/ledger", "method": "GET"},
                    "parent": {"href": "/api/v2", "method": "GET"}
                },
                "data": data,
                "meta": {
                    "chain_validation_status": chain_valid,
                    "block_height": len(data)
                }
            }
            self.send_json_response(response)
            return

        else:
            self.send_error(404, "REST 2.0 Resource not found")

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        payload = json.loads(post_data.decode('utf-8'))

        if self.path == "/api/v2/tickets" or self.path == "/api/tickets/create":
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
                
                # Structured REST 2.0 Response Envelope
                response_data = {
                    "_links": {
                        "self": {"href": f"/api/v2/tickets/{res.block_index}" if res.consensus_reached else None},
                        "ledger": {"href": "/api/v2/ledger"}
                    },
                    "data": {
                        "consensus_reached": res.consensus_reached,
                        "consensus_ratio": res.consensus_ratio,
                        "votes": votes,
                        "minority_report": res.minority_report,
                        "block_index": res.block_index,
                        "block_hash": res.block_hash,
                        "status": res.status
                    }
                }
            except Exception as e:
                response_data = {
                    "error": {
                        "code": "GRPC_COMMUNICATION_ERROR",
                        "message": str(e)
                    }
                }

            self.send_json_response(response_data)
            return

        elif self.path == "/api/v2/timemachine" or self.path == "/api/tickets/timemachine":
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
                    "_links": {
                        "ledger": {"href": "/api/v2/ledger"}
                    },
                    "data": {
                        "success": res.success,
                        "message": res.message,
                        "refactor_logs": list(res.refactor_logs),
                        "new_chain_validation_status": res.new_chain_validation_status
                    }
                }
            except Exception as e:
                response_data = {
                    "error": {
                        "code": "TIMETRAVEL_FAIL",
                        "message": str(e)
                    }
                }

            self.send_json_response(response_data)
            return

        else:
            self.send_error(404, "REST 2.0 Endpoint not found")

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
        print(f"[WEB-SERVER] REST 2.0 Sovereign Swarm control workspace listening on port {PORT}...")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[WEB-SERVER] Stopping dashboard server...")
            httpd.server_close()
            sys.exit(0)
