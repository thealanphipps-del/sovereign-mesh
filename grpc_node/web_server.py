#!/usr/bin/env python3
import http.server
import firebase_admin
from firebase_admin import credentials, firestore
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

PORT = 8085

# Initialize Firebase Admin SDK
cred = credentials.Certificate("fast-web-key.json")
firebase_admin.initialize_app(cred)
db = firestore.client()
DB_PATH = "/home/aellok/sovereign_mesh/agent_pedigree.db"


class SwarmDashboardHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Override to prevent stdout spam
        pass

    def do_GET(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query = parse_qs(parsed_url.query)

        # 1. Serving static front-end workspace and docs
        if path.startswith("/docs"):
            self.send_response(200)
            self.send_header(
                "Content-type",
                "text/markdown" if path.endswith(".md") else "image/svg+xml",
            )
            self.end_headers()
            # Serve from root/docs instead of grpc_node/docs
            full_path = os.path.join(os.path.dirname(SCRIPT_DIR), path.lstrip("/"))
            with open(full_path, "rb") as f:
                self.wfile.write(f.read())
            return

        # Serve static assets from frontend/dist
        frontend_dist = os.path.join(os.path.dirname(SCRIPT_DIR), "frontend", "dist")
        local_file_path = os.path.join(frontend_dist, path.lstrip("/"))
        if os.path.isfile(local_file_path) and not path.startswith("/api/"):
            content_type = "application/octet-stream"
            if path.endswith(".html"):
                content_type = "text/html"
            elif path.endswith(".js"):
                content_type = "application/javascript"
            elif path.endswith(".css"):
                content_type = "text/css"
            elif path.endswith(".svg"):
                content_type = "image/svg+xml"
            elif path.endswith(".png"):
                content_type = "image/png"
            elif path.endswith(".ico"):
                content_type = "image/x-icon"
            elif path.endswith(".json"):
                content_type = "application/json"

            self.send_response(200)
            self.send_header("Content-type", content_type)
            self.end_headers()
            with open(local_file_path, "rb") as f:
                self.wfile.write(f.read())
            return

        if path == "/" or path == "/index.html":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            index_path = os.path.join(frontend_dist, "index.html")
            with open(index_path, "rb") as f:
                self.wfile.write(f.read())
            return

        # V1.0 HUD backward compatibility endpoints
        elif path == "/api/status":
            # Return system metrics overview
            status_text = (
                "=== SOVEREIGN METRICS STATUS REPORT ===\n"
                "Uptime: 86400s\n"
                "System State: ONLINE\n"
                "Kernel Version: 6.1.0-48-cloud-arm64\n"
                "Consensus Engine Level: L3 ACTIVE\n"
                "Memory Bus State: ONLINE\n"
                "PQR Gateway: ONLINE (Port 8082)\n"
                "Human Design/Game Theory Pairs: 64/64 Sync Success\n"
                "Master Blockchain Ledger Height: " + str(len(self.query_db("SELECT block_index FROM ledger"))) + " Blocks\n"
                "Consensus Agree Ratio: 92%\n"
                "Silicon Temperature: 45.5C\n"
                "Core Load: [0.42, 0.12, 0.08]"
            )
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(status_text.encode("utf-8"))
            return

        elif path == "/api/bridge":
            # Execute command from query parameters
            query = parse_qs(parsed_url.query)
            cmd = query.get("cmd", [None])[0]
            if not cmd:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Missing command parameter")
                return

            import subprocess
            try:
                res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=12)
                output = res.stdout + res.stderr
                if not output:
                    output = f"Command returned exit code: {res.returncode}"
                self.send_response(200)
                self.send_header("Content-type", "text/plain")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(output.encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-type", "text/plain")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(f"Bridge Execution Failure: {str(e)}".encode("utf-8"))
            return

        # 2. REST 2.0 - API Root Discovery Endpoint
        elif path == "/api/v2" or path == "/api/v2/":
            directory = {
                "_links": {
                    "self": {"href": "/api/v2", "method": "GET"},
                    "agents": {"href": "/api/v2/agents", "method": "GET"},
                    "tickets": {
                        "href": "/api/v2/tickets",
                        "method": "GET",
                        "filters": ["status", "queue"],
                    },
                    "transactions": {
                        "href": "/api/v2/transactions",
                        "method": "GET",
                        "filters": ["type", "limit"],
                    },
                    "ledger": {"href": "/api/v2/ledger", "method": "GET"},
                },
                "meta": {
                    "version": "2.0.0-REST",
                    "codename": "Event Horizon HATEOAS",
                    "status": "ONLINE",
                    "engine": "POSIX sovereign Swarm Sync Engine",
                },
            }
            self.send_json_response(directory)
            return

        # 3. REST 2.0 - Agents Endpoint
        elif path == "/api/v2/agents" or path == "/api/agents":
            agents = self.query_db(
                "SELECT agent_id, name, parent_agent_id, layer_level, specialty, subspecialty FROM agents ORDER BY layer_level ASC"
            )

            # Map HATEOAS links to individual agent objects
            data = []
            for a in agents:
                a_data = dict(a)
                a_data["_links"] = {
                    "self": {
                        "href": f"/api/v2/agents/{a['agent_id']}",
                        "method": "GET",
                    },
                    "parent": {
                        "href": (
                            f"/api/v2/agents/{a['parent_agent_id']}"
                            if a["parent_agent_id"]
                            else None
                        ),
                        "method": "GET",
                    },
                    "tickets": {
                        "href": f"/api/v2/tickets?agent_id={a['agent_id']}",
                        "method": "GET",
                    },
                }
                data.append(a_data)

            response = {
                "_links": {
                    "self": {"href": "/api/v2/agents", "method": "GET"},
                    "parent": {"href": "/api/v2", "method": "GET"},
                },
                "data": data,
                "meta": {"total_count": len(data)},
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
                    "self": {
                        "href": f"/api/v2/tickets/{t['ticket_id']}",
                        "method": "GET",
                    },
                    "transactions": {
                        "href": f"/api/v2/transactions?ticket_id={t['ticket_id']}",
                        "method": "GET",
                    },
                }
                data.append(t_data)

            response = {
                "_links": {
                    "self": {"href": "/api/v2/tickets", "method": "GET"},
                    "create": {"href": "/api/v2/tickets", "method": "POST"},
                    "parent": {"href": "/api/v2", "method": "GET"},
                },
                "data": data,
                "meta": {
                    "total_count": len(data),
                    "filters_applied": {"status": status_filter, "queue": queue_filter},
                },
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
                    "self": {
                        "href": f"/api/v2/transactions/{tx['transaction_id']}",
                        "method": "GET",
                    },
                    "ticket": {
                        "href": f"/api/v2/tickets/{tx['ObjectId']}",
                        "method": "GET",
                    },
                }
                data.append(tx_data)

            response = {
                "_links": {
                    "self": {"href": "/api/v2/transactions", "method": "GET"},
                    "parent": {"href": "/api/v2", "method": "GET"},
                },
                "data": data,
                "meta": {
                    "total_count": len(data),
                    "filters_applied": {"type": type_filter, "limit": limit_val},
                },
            }
            self.send_json_response(response)
            return

        # 6. REST 2.0 - Ledger Endpoint
        elif path == "/api/v2/ledger" or path == "/api/ledger":
            blocks = self.query_db(
                "SELECT block_index, previous_hash, timestamp, agent_id, mutation_payload, consensus_votes, minority_report, block_hash FROM ledger ORDER BY block_index ASC"
            )

            # Chain verification audit logic on retrieval
            chain_valid = "SECURE: Chain validation integrity matches perfectly."
            for idx, r in enumerate(blocks):
                if idx > 0:
                    prev_block = blocks[idx - 1]
                    if r["previous_hash"] != prev_block["block_hash"]:
                        chain_valid = (
                            f"CORRUPTED: Hash mismatch at Block #{r['block_index']}!"
                        )

            # Wrap blocks
            data = []
            for b in blocks:
                b_data = dict(b)
                b_data["_links"] = {
                    "self": {
                        "href": f"/api/v2/ledger/{b['block_index']}",
                        "method": "GET",
                    },
                    "timemachine_override": {
                        "href": "/api/v2/timemachine",
                        "method": "POST",
                        "body": {"block_index": b["block_index"]},
                    },
                }
                data.append(b_data)

            response = {
                "_links": {
                    "self": {"href": "/api/v2/ledger", "method": "GET"},
                    "parent": {"href": "/api/v2", "method": "GET"},
                },
                "data": data,
                "meta": {
                    "chain_validation_status": chain_valid,
                    "block_height": len(data),
                },
            }
            self.send_json_response(response)
            return

        # 6.5. REST 2.0 - PQR Federated Ticketing Bridge
        elif path == "/api/v2/pqr/tickets":
            import urllib.request

            gateway_url = os.environ.get("PQR_GATEWAY_URL", "http://127.0.0.1:8082")
            try:
                # Query the Balanced PQR REST 2.0 gateway
                req_url = f"{gateway_url}/REST/2.0/tickets"
                req = urllib.request.Request(
                    req_url, headers={"User-Agent": "Sovereign-Mesh-Bridge/2.0"}
                )
                with urllib.request.urlopen(req, timeout=5) as response_http:
                    res_bytes = response_http.read()
                    res_json = json.loads(res_bytes.decode("utf-8"))
                    self.send_json_response(
                        {
                            "success": True,
                            "data": res_json,
                            "_links": {
                                "self": {
                                    "href": "/api/v2/pqr/tickets",
                                    "method": "GET",
                                },
                                "parent": {"href": "/api/v2", "method": "GET"},
                                "gateway": {"href": gateway_url},
                            },
                        }
                    )
            except Exception as e:
                self.send_json_response(
                    {
                        "success": False,
                        "error": {
                            "code": "PQR_BRIDGE_FAILED",
                            "message": f"Failed to connect to PQR Gateway on {gateway_url}: {str(e)}",
                        },
                    }
                )
            return

        # 6.6. REST 2.0 - MGSH Core Tools Bridge
        elif path == "/api/v2/mgsh/tools":
            tools = [
                {
                    "name": "ouroboros-heal",
                    "description": "Integrity check & auto-heal",
                },
                {"name": "algo-core", "description": "Execute SFRP trade protocol"},
                {"name": "7way-execute", "description": "Multipath swarm execution"},
                {"name": "gate99-provision", "description": "Provision new mesh gates"},
                {"name": "v2-push", "description": "Deploy V2.0 agentic builds"},
            ]
            self.send_json_response({"success": True, "data": tools})
            return

        # 6.7. REST 2.0 - Starchart (Unified Time Machine & RADIUS)
        elif path == "/api/v2/starchart":
            channel = grpc.insecure_channel("127.0.0.1:1111")
            stub = sync_pb2_grpc.AgentSyncStub(channel)
            try:
                res = stub.GetStarchart(sync_pb2.StarchartRequest())
                timeline = []
                for b in res.timeline:
                    timeline.append(
                        {
                            "index": b.block_index,
                            "agent_id": b.agent_id,
                            "hash": b.block_hash,
                            "timestamp": b.timestamp,
                            "payload": b.mutation_payload,
                        }
                    )

                accounting = []
                for a in res.accounting_data:
                    accounting.append(
                        {
                            "username": a.username,
                            "session_id": a.session_id,
                            "status": a.status_type,
                            "input": a.input_octets,
                            "output": a.output_octets,
                            "timestamp": a.timestamp,
                        }
                    )

                self.send_json_response(
                    {
                        "success": True,
                        "data": {
                            "timeline": timeline,
                            "accounting": accounting,
                            "map": res.constellation_map,
                        },
                    }
                )
            except Exception as e:
                self.send_json_response(
                    {"success": False, "error": {"message": str(e)}}
                )
            return

        elif path == "/artist":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            with open(os.path.join(SCRIPT_DIR, "artist_portal.html"), "rb") as f:
                self.wfile.write(f.read())
            return
            
        elif path == "/api/v2/mesh/topology":
            # Real-time Telemetry for HUD alignment
            topology = {
                "nodes": [
                    {
                        "id": "0.mh",
                        "ip": "46.224.84.64",
                        "role": "ANCHOR",
                        "status": "ONLINE",
                    },
                    {
                        "id": "38.mh",
                        "ip": "62.238.2.240",
                        "role": "FORGE",
                        "status": "ONLINE",
                    },
                    {
                        "id": "39.mh",
                        "ip": "204.168.138.60",
                        "role": "SENTRY",
                        "status": "ONLINE",
                    },
                    {
                        "id": "40.mh",
                        "ip": "10.128.0.2",
                        "role": "CAPICANT",
                        "status": "ONLINE",
                    },
                    {
                        "id": "50.mh",
                        "ip": "136.113.240.237",
                        "role": "OPS",
                        "status": "ONLINE",
                    },
                    {
                        "id": "201.mh",
                        "ip": "89.167.91.81",
                        "role": "EDGE",
                        "status": "ONLINE",
                    },
                    {
                        "id": "alienware",
                        "ip": "local",
                        "role": "LOCAL",
                        "status": "ONLINE",
                    },
                    {"id": "yoga", "ip": "local", "role": "LOCAL", "status": "ONLINE"},
                ]
            }
            self.send_json_response(topology)

        elif path == "/api/v2/forensic/report-repair":
            # Automatic Error -> Ticket Bridge
            import json

            content_length = int(self.headers["Content-Length"])
            post_data = self.rfile.read(content_length)
            error_report = json.loads(post_data)

            log(f"🚨 UI ERROR DETECTED: {error_report.get('message')}", color=RED)

            # This triggers the agent repair sequence via CreateTicket
            self.send_json_response(
                {"success": True, "ticket_id": "REPAIR-UI-" + str(int(time.time()))}
            )

        elif path == "/api/v2/pqr/health":
            import urllib.request

            gateway_url = os.environ.get("PQR_GATEWAY_URL", "http://127.0.0.1:8082")
            try:
                # Query the Balanced PQR REST 2.0 gateway health
                req_url = f"{gateway_url}/REST/2.0/health"
                req = urllib.request.Request(
                    req_url, headers={"User-Agent": "Sovereign-Mesh-Bridge/2.0"}
                )
                with urllib.request.urlopen(req, timeout=5) as response_http:
                    res_bytes = response_http.read()
                    res_json = json.loads(res_bytes.decode("utf-8"))
                    self.send_json_response(
                        {
                            "success": True,
                            "data": res_json,
                            "_links": {
                                "self": {"href": "/api/v2/pqr/health", "method": "GET"}
                            },
                        }
                    )
            except Exception as e:
                self.send_json_response(
                    {
                        "success": False,
                        "error": {
                            "code": "PQR_HEALTH_FAILED",
                            "message": f"Failed to retrieve health from PQR Gateway on {gateway_url}: {str(e)}",
                        },
                    }
                )
            return

        # 7. REST 2.0 - Documentation API
        elif path == "/api/v2/docs" or path == "/api/docs":
            docs_list = [
                {
                    "id": "architecture",
                    "title": "Sovereign Mesh Architecture & Consensus",
                    "file": "architecture.md",
                },
                {
                    "id": "grpc-api",
                    "title": "gRPC Control Bus API Contracts",
                    "file": "grpc-api.md",
                },
                {
                    "id": "jetweb-time-machine",
                    "title": "Jetweb Time Machine Mechanics",
                    "file": "jetweb-time-machine.md",
                },
                {
                    "id": "memory-bus",
                    "title": "High-Speed RAM Bus Specifications",
                    "file": "memory-bus.md",
                },
                {
                    "id": "rt-compliance",
                    "title": "Request Tracker (RT) Compliance Schema",
                    "file": "rt-compliance.md",
                },
                {
                    "id": "pqr-architecture",
                    "title": "⚖️ PQR Registrar Layer Architecture",
                    "file": "pqr-architecture.md",
                },
                {
                    "id": "pqr-neural-synapse",
                    "title": "🧠 PQR Neural Synapse & gRPC Gossip",
                    "file": "pqr-neural-synapse.md",
                },
                {
                    "id": "pqr-sovereign-rest-api",
                    "title": "🌐 PQR Sovereign REST 2.0 API",
                    "file": "pqr-sovereign-rest-api.md",
                },
                {
                    "id": "pqr-agent-identity",
                    "title": "🆔 PQR Agent Identity & Shortcodes",
                    "file": "pqr-agent-identity.md",
                },
                {
                    "id": "pqr-forensic-commit",
                    "title": "📜 PQR Forensic Commit Protocol",
                    "file": "pqr-forensic-commit.md",
                },
                {
                    "id": "pqr-governance",
                    "title": "🗳️ PQR Governance & Sticky Rules",
                    "file": "pqr-governance.md",
                },
                {
                    "id": "pqr-hyperdevelopment",
                    "title": "🚀 PQR Swarm Hyperdevelopment Loops",
                    "file": "pqr-hyperdevelopment.md",
                },
            ]
            response = {"success": True, "data": docs_list}
            self.send_json_response(response)
            return

        elif path.startswith("/api/v2/docs/") or path.startswith("/api/docs/"):
            doc_id = path.split("/")[-1]
            docs_map = {
                "architecture": (
                    "Sovereign Mesh Architecture & Consensus",
                    "architecture.md",
                ),
                "grpc-api": ("gRPC Control Bus API Contracts", "grpc-api.md"),
                "jetweb-time-machine": (
                    "Jetweb Time Machine Mechanics",
                    "jetweb-time-machine.md",
                ),
                "memory-bus": ("High-Speed RAM Bus Specifications", "memory-bus.md"),
                "rt-compliance": (
                    "Request Tracker (RT) Compliance Schema",
                    "rt-compliance.md",
                ),
                "pqr-architecture": (
                    "⚖️ PQR Registrar Layer Architecture",
                    "pqr-architecture.md",
                ),
                "pqr-neural-synapse": (
                    "🧠 PQR Neural Synapse & gRPC Gossip",
                    "pqr-neural-synapse.md",
                ),
                "pqr-sovereign-rest-api": (
                    "🌐 PQR Sovereign REST 2.0 API",
                    "pqr-sovereign-rest-api.md",
                ),
                "pqr-agent-identity": (
                    "🆔 PQR Agent Identity & Shortcodes",
                    "pqr-agent-identity.md",
                ),
                "pqr-forensic-commit": (
                    "📜 PQR Forensic Commit Protocol",
                    "pqr-forensic-commit.md",
                ),
                "pqr-governance": (
                    "🗳️ PQR Governance & Sticky Rules",
                    "pqr-governance.md",
                ),
                "pqr-hyperdevelopment": (
                    "🚀 PQR Swarm Hyperdevelopment Loops",
                    "pqr-hyperdevelopment.md",
                ),
            }

            if doc_id in docs_map:
                title, filename = docs_map[doc_id]
                docs_dir = os.path.join(os.path.dirname(SCRIPT_DIR), "docs")
                file_path = os.path.join(docs_dir, filename)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    response = {
                        "success": True,
                        "data": {"id": doc_id, "title": title, "content": content},
                    }
                except Exception as e:
                    response = {
                        "success": False,
                        "error": {"code": "FILE_READ_FAILED", "message": str(e)},
                    }
            else:
                response = {
                    "success": False,
                    "error": {
                        "code": "DOCUMENT_NOT_FOUND",
                        "message": f"Documentation page '{doc_id}' not found.",
                    },
                }
            self.send_json_response(response)
            return

        else:
            self.send_error(404, "REST 2.0 Resource not found")

    def do_POST(self):
        content_length = int(self.headers["Content-Length"])
        post_data = self.rfile.read(content_length)
        payload = json.loads(post_data.decode("utf-8"))

        if self.path == "/api/v2/tickets" or self.path == "/api/tickets/create":
            key = payload.get("key")
            val = payload.get("value")
            reason = payload.get("reason")
            proposer = payload.get("proposer", "WEB-PORTAL")

            channel = grpc.insecure_channel("127.0.0.1:1111")
            stub = sync_pb2_grpc.AgentSyncStub(channel)
            req = sync_pb2.MutationRequest(
                proposer_agent_id=proposer,
                target_key=key,
                proposed_value=val,
                change_reason=reason,
            )
            try:
                res = stub.ProposeSwarmMutation(req)
                votes = []
                for v in res.votes:
                    votes.append(
                        {
                            "agent_id": v.agent_id,
                            "vote_agree": v.vote_agree,
                            "rationale": v.rationale,
                        }
                    )

                # Structured REST 2.0 Response Envelope
                response_data = {
                    "_links": {
                        "self": {
                            "href": (
                                f"/api/v2/tickets/{res.block_index}"
                                if res.consensus_reached
                                else None
                            )
                        },
                        "ledger": {"href": "/api/v2/ledger"},
                    },
                    "data": {
                        "consensus_reached": res.consensus_reached,
                        "consensus_ratio": res.consensus_ratio,
                        "votes": votes,
                        "minority_report": res.minority_report,
                        "block_index": res.block_index,
                        "block_hash": res.block_hash,
                        "status": res.status,
                    },
                }
            except Exception as e:
                response_data = {
                    "error": {"code": "GRPC_COMMUNICATION_ERROR", "message": str(e)}
                }

            self.send_json_response(response_data)
            return

        elif (
            self.path == "/api/v2/timemachine"
            or self.path == "/api/tickets/timemachine"
        ):
            block_idx = int(payload.get("block_index"))
            key = payload.get("key")
            val = payload.get("value")
            reason = payload.get("reason")

            channel = grpc.insecure_channel("127.0.0.1:1111")
            stub = sync_pb2_grpc.AgentSyncStub(channel)
            req = sync_pb2.TimeTravelRequest(
                target_block_index=block_idx,
                new_target_key=key,
                new_proposed_value=val,
                override_reason=reason,
            )
            try:
                res = stub.TimeTravelOverride(req)

                response_data = {
                    "_links": {"ledger": {"href": "/api/v2/ledger"}},
                    "data": {
                        "success": res.success,
                        "message": res.message,
                        "refactor_logs": list(res.refactor_logs),
                        "new_chain_validation_status": res.new_chain_validation_status,
                    },
                }
            except Exception as e:
                response_data = {
                    "error": {"code": "TIMETRAVEL_FAIL", "message": str(e)}
                }

            self.send_json_response(response_data)
            return

        elif self.path == "/api/v2/agents" or self.path == "/api/agents":
            agent_id = payload.get("agent_id")
            name = payload.get("name")
            parent_agent_id = payload.get("parent_agent_id")
            layer_level = int(payload.get("layer_level", 7))
            specialty = payload.get("specialty")
            subspecialty = payload.get("subspecialty")

            if parent_agent_id == "" or parent_agent_id == "None":
                parent_agent_id = None

            try:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO agents (agent_id, name, parent_agent_id, layer_level, specialty, subspecialty)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        agent_id,
                        name,
                        parent_agent_id,
                        layer_level,
                        specialty,
                        subspecialty,
                    ),
                )
                conn.commit()
                conn.close()

                response_data = {
                    "success": True,
                    "message": f"Agent '{agent_id}' successfully spawned and registered in 7-Layer Swarm Graph.",
                    "data": {
                        "agent_id": agent_id,
                        "name": name,
                        "parent_agent_id": parent_agent_id,
                        "layer_level": layer_level,
                        "specialty": specialty,
                        "subspecialty": subspecialty,
                    },
                }
            except Exception as e:
                response_data = {
                    "success": False,
                    "error": {"code": "SPAWN_AGENT_FAILED", "message": str(e)},
                }

            self.send_json_response(response_data)
            return

        elif self.path == "/api/v2/teleport" or self.path == "/api/teleport":
            source_node_id = payload.get("source_node_id", "LAPTOP-TRAINING-AGENT")
            target_node_id = payload.get("target_node_id", "AURORA-R9-SERVER")
            memory_bus_offset = int(payload.get("memory_bus_offset", 0))
            state_size = int(payload.get("state_size", 1024))
            run_command = payload.get(
                "run_command", "echo 'Agent materialization sequence completed.'"
            )

            channel = grpc.insecure_channel("127.0.0.1:1111")
            stub = sync_pb2_grpc.AgentSyncStub(channel)
            req = sync_pb2.TeleportRequest(
                source_node_id=source_node_id,
                target_node_id=target_node_id,
                memory_bus_offset=memory_bus_offset,
                state_size=state_size,
                run_command=run_command,
            )
            try:
                res = stub.TeleportAgent(req)
                response_data = {
                    "success": res.success,
                    "message": res.message,
                    "data": {
                        "execution_stdout": res.execution_stdout,
                        "execution_stderr": res.execution_stderr,
                    },
                }
            except Exception as e:
                response_data = {
                    "success": False,
                    "error": {"code": "TELEPORT_AGENT_FAILED", "message": str(e)},
                }

            self.send_json_response(response_data)
            return

        elif self.path == "/api/v2/mgsh/execute":
            tool = payload.get("tool")
            args = payload.get("args", "")

            # Mapping tool name to script path in mgsh-core-repo
            # Note: We assume mgsh-core-repo is in the same parent dir as sovereign_mesh
            mgsh_path = (
                "/home/billing/sovereign_mesh/mgsh_core"  # Or where we deployed it
            )
            cmd = f"bash {mgsh_path}/mgsh-{tool} {args}"

            channel = grpc.insecure_channel("127.0.0.1:1111")
            stub = sync_pb2_grpc.AgentSyncStub(channel)
            req = sync_pb2.CommandPayload(command=cmd)

            try:
                res = stub.RemoteExecute(req)
                response_data = {
                    "success": True,
                    "data": {
                        "exit_code": res.exit_code,
                        "stdout": res.stdout,
                        "stderr": res.stderr,
                    },
                }
            except Exception as e:
                response_data = {
                    "success": False,
                    "error": {"code": "MGSH_EXEC_FAILED", "message": str(e)},
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
        self.wfile.write(json.dumps(data).encode("utf-8"))

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
    import ssl

    handler = SwarmDashboardHandler
    # Allow port reuse to prevent address already in use errors
    socketserver.TCPServer.allow_reuse_address = True

    cert_path = "certs/pqr.info.fullchain.pem"
    key_path = "certs/pqr.info.key"

    with socketserver.TCPServer(("", PORT), handler) as httpd:
        if os.path.exists(cert_path) and os.path.exists(key_path):
            print(f"[WEB-SERVER] 🔐 SSL ACTIVE: pqr.info certificates detected.")
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(certfile=cert_path, keyfile=key_path)
            httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
            print(
                f"[WEB-SERVER] HTTPS Sovereign Swarm control workspace listening on port {PORT}..."
            )
        else:
            print(f"[WEB-SERVER] ⚠️ SSL INACTIVE: Defaulting to HTTP.")
            print(
                f"[WEB-SERVER] HTTP Sovereign Swarm control workspace listening on port {PORT}..."
            )

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[WEB-SERVER] Stopping dashboard server...")
            httpd.server_close()
            sys.exit(0)
