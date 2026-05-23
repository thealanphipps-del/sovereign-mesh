import grpc
import sync_pb2
import sync_pb2_grpc
import time


def activate_agents():
    channel = grpc.insecure_channel("localhost:1111")
    stub = sync_pb2_grpc.AgentSyncStub(channel)

    for i in range(1, 8):
        agent_id = f"AGENT-{i:03d}"
        print(f"Activating {agent_id}...")
        stub.HandshakeState(
            sync_pb2.StatePayload(
                agent_id=agent_id,
                active_model="gemma2:2b",
                metadata={"node_class": "VALIDATOR", "layer": str(i)},
            )
        )
        time.sleep(0.5)
    print("Swarm swarm activation sequence complete.")


if __name__ == "__main__":
    activate_agents()
