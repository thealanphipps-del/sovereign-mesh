package sovereign

import (
	"bufio"
	"encoding/json"
	"fmt"
	"net"
	"testing"
	"time"
)

func TestStratumServerLifecycle(t *testing.T) {
	// 1. Initialize Stratum Distributed Inference Server on localhost loopback
	server := NewStratumServer("127.0.0.1:3333")
	err := server.Start()
	if err != nil {
		t.Fatalf("Failed to start Stratum server: %v", err)
	}
	defer server.Stop()

	// Give server a moment to bind
	time.Sleep(100 * time.Millisecond)

	// 2. Establish connection as a simulated mobile NPU worker (Citizen Node)
	conn, err := net.Dial("tcp", "127.0.0.1:3333")
	if err != nil {
		t.Fatalf("NPU Worker failed to connect: %v", err)
	}
	defer conn.Close()

	reader := bufio.NewReader(conn)

	// 3. Send subscription request (inference.subscribe)
	subReq := `{"id":1,"method":"inference.subscribe","params":["Galaxy-S25-FE","NPU-v2"]}`
	fmt.Fprintf(conn, subReq+"\n")

	line, err := reader.ReadBytes('\n')
	if err != nil {
		t.Fatalf("Failed to read subscription response: %v", err)
	}

	var resp map[string]interface{}
	if err := json.Unmarshal(line, &resp); err != nil {
		t.Fatalf("Failed to parse response JSON: %v", err)
	}

	res, ok := resp["result"].(map[string]interface{})
	if !ok {
		t.Fatalf("Response has no result payload: %s", string(line))
	}

	workerID, _ := res["worker_id"].(string)
	if workerID == "" {
		t.Errorf("Expected valid worker_id, got empty")
	}

	// 4. Test Job Broadcasting (inference.notify)
	promptTokens := []int64{101, 203, 305, 407}
	jobID := server.BroadcastJob(promptTokens)

	// Read job notification on client connection
	jobLine, err := reader.ReadBytes('\n')
	if err != nil {
		t.Fatalf("Client failed to receive broadcast job: %v", err)
	}

	var jobNotify map[string]interface{}
	if err := json.Unmarshal(jobLine, &jobNotify); err != nil {
		t.Fatalf("Failed to parse job notification: %v", err)
	}

	method, _ := jobNotify["method"].(string)
	if method != "inference.notify" {
		t.Errorf("Expected method 'inference.notify', got %q", method)
	}

	// 5. Submit an evaluated token share (inference.submit)
	submitReq := fmt.Sprintf(`{"id":2,"method":"inference.submit","params":["%s","%s",[0.98,0.01,0.01]]}`, workerID, jobID)
	fmt.Fprintf(conn, submitReq+"\n")

	submitLine, err := reader.ReadBytes('\n')
	if err != nil {
		t.Fatalf("Failed to read submission response: %v", err)
	}

	var submitResp map[string]interface{}
	if err := json.Unmarshal(submitLine, &submitResp); err != nil {
		t.Fatalf("Failed to parse submission response: %v", err)
	}

	subRes, ok := submitResp["result"].(map[string]interface{})
	if !ok {
		t.Fatalf("Submission response has no result payload: %s", string(submitLine))
	}

	status, _ := subRes["status"].(string)
	if status != "ACCEPTED" {
		t.Errorf("Expected share status 'ACCEPTED', got %q", status)
	}

	t.Logf("✅ STRATUM SUCCESS: Verified subscription, job notify, and share submission for worker %s", workerID)
}
