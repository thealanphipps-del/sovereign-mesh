// ==============================================================================
# SOVEREIGN-27: STRATUM-STYLE DISTRIBUTED INFERENCE POOL SERVER
# Coordinates mobile NPU edge nodes as distributed inference workers (miners)
# ==============================================================================

package sovereign

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net"
	"sync"
	"sync/atomic"
	"time"
)

// InferenceJob represents a sub-task distributed to NPU workers.
type InferenceJob struct {
	JobID      string  `json:"job_id"`
	Tokens     []int64 `json:"prompt_tokens"`
	TargetHead int     `json:"target_head"`
	Difficulty float64 `json:"target_conformation"`
}

// InferenceShare represents a calculated token logit slice submitted by an NPU worker.
type InferenceShare struct {
	WorkerID string    `json:"worker_id"`
	JobID    string    `json:"job_id"`
	Logits   []float64 `json:"logits"`
	Proof    string    `json:"proof_hash"` // Verification hash
}

// StratumWorker represents an active mobile/NPU connection.
type StratumWorker struct {
	ID         string
	Conn       net.Conn
	DeviceType string
	Active     bool
	LastActive time.Time
}

// StratumServer manages the distributed LLM inference pool.
type StratumServer struct {
	Addr       string
	Listener   net.Listener
	Workers    map[string]*StratumWorker
	WorkersMu  sync.RWMutex
	JobCounter uint64
	ActiveJobs sync.Map
	Ctx        context.Context
	Cancel     context.CancelFunc
}

// NewStratumServer initializes a new inference pool coordinator.
func NewStratumServer(addr string) *StratumServer {
	ctx, cancel := context.WithCancel(context.Background())
	return &StratumServer{
		Addr:    addr,
		Workers: make(map[string]*StratumWorker),
		Ctx:     ctx,
		Cancel:  cancel,
	}
}

// Start boots the JSON-RPC TCP pool listener.
func (s *StratumServer) Start() error {
	var err error
	s.Listener, err = net.Listen("tcp", s.Addr)
	if err != nil {
		return fmt.Errorf("failed to bind Stratum port: %w", err)
	}

	log.Printf("📡 STRATUM INFERENCE POOL: Listening on %s...", s.Addr)

	go func() {
		for {
			conn, err := s.Listener.Accept()
			if err != nil {
				select {
				case <-s.Ctx.Done():
					return
				default:
					log.Printf("⚠️ Stratum Connection Error: %v", err)
					continue
				}
			}
			go s.handleConnection(conn)
		}
	}()

	return nil
}

// Stop shuts down the pool and terminates active connections.
func (s *StratumServer) Stop() {
	s.Cancel()
	if s.Listener != nil {
		s.Listener.Close()
	}
	s.WorkersMu.Lock()
	defer s.WorkersMu.Unlock()
	for _, w := range s.Workers {
		w.Conn.Close()
	}
	log.Println("🛑 STRATUM INFERENCE POOL: Offline.")
}

// handleConnection handles JSON-RPC flows for a single mobile NPU worker.
func (s *StratumServer) handleConnection(conn net.Conn) {
	defer conn.Close()
	reader := bufio.NewReader(conn)
	worker := &StratumWorker{
		Conn:       conn,
		Active:     false,
		LastActive: time.Now(),
	}

	for {
		line, err := reader.ReadBytes('\n')
		if err != nil {
			log.Printf("🔌 Stratum Worker Disconnected: %s", worker.ID)
			s.removeWorker(worker.ID)
			return
		}

		var req map[string]interface{}
		if err := json.Unmarshal(line, &req); err != nil {
			s.sendError(conn, nil, "JSON_PARSE_ERROR", "Invalid JSON-RPC format")
			continue
		}

		method, _ := req["method"].(string)
		id := req["id"]

		switch method {
		case "inference.subscribe":
			params, _ := req["params"].([]interface{})
			device := "Unknown"
			if len(params) > 0 {
				device, _ = params[0].(string)
			}
			worker.ID = fmt.Sprintf("NPU-%x", time.Now().UnixNano())
			worker.DeviceType = device
			worker.Active = true
			worker.LastActive = time.Now()

			s.addWorker(worker)
			log.Printf("📱 STRATUM WORKER SUBSCRIBED: %s [%s]", worker.ID, worker.DeviceType)

			s.sendResponse(conn, id, map[string]interface{}{
				"worker_id":  worker.ID,
				"session_id": fmt.Sprintf("session-%d", time.Now().Unix()),
			})

		case "inference.authorize":
			// Real protocol would verify PQR-273 signed device token
			s.sendResponse(conn, id, true)

		case "inference.submit":
			params, _ := req["params"].([]interface{})
			if len(params) < 3 {
				s.sendError(conn, id, "INVALID_PARAMS", "Expected worker_id, job_id, logits")
				continue
			}
			jobID, _ := params[1].(string)
			
			// Log submission to the console
			log.Printf("📥 STRATUM SHARE SUBMITTED: Worker %s for Job %s (Consensus Share)", worker.ID, jobID)
			
			// Verify if the job exists
			if _, ok := s.ActiveJobs.Load(jobID); !ok {
				s.sendError(conn, id, "JOB_NOT_FOUND", "Inference job expired or already solved")
				continue
			}

			s.sendResponse(conn, id, map[string]interface{}{
				"status":     "ACCEPTED",
				"validation": "STRIKE_CONFIRMED",
			})

		default:
			s.sendError(conn, id, "METHOD_NOT_FOUND", "Unknown Stratum method")
		}
	}
}

// BroadcastJob pushes a new model generation task sheet to all active NPUs.
func (s *StratumServer) BroadcastJob(prompt []int64) string {
	jobID := fmt.Sprintf("job-27-%d", atomic.AddUint64(&s.JobCounter, 1))
	job := InferenceJob{
		JobID:      jobID,
		Tokens:     prompt,
		TargetHead: 27,
		Difficulty: 0.72,
	}

	s.ActiveJobs.Store(jobID, job)

	s.WorkersMu.RLock()
	defer s.WorkersMu.RUnlock()

	log.Printf("📤 STRATUM BROADCAST: Pushing Inference Job %s to %d NPU workers...", jobID, len(s.Workers))

	payload, _ := json.Marshal(map[string]interface{}{
		"method": "inference.notify",
		"params": []interface{}{job.JobID, job.Tokens, job.TargetHead, job.Difficulty},
	})
	payload = append(payload, '\n')

	for _, w := range s.Workers {
		if w.Active {
			w.Conn.Write(payload)
		}
	}

	return jobID
}

func (s *StratumServer) addWorker(w *StratumWorker) {
	s.WorkersMu.Lock()
	defer s.WorkersMu.Unlock()
	s.Workers[w.ID] = w
}

func (s *StratumServer) removeWorker(id string) {
	s.WorkersMu.Lock()
	defer s.WorkersMu.Unlock()
	delete(s.Workers, id)
}

func (s *StratumServer) sendResponse(conn net.Conn, id interface{}, result interface{}) {
	resp := map[string]interface{}{
		"id":     id,
		"result": result,
		"error":  nil,
	}
	b, _ := json.Marshal(resp)
	conn.Write(append(b, '\n'))
}

func (s *StratumServer) sendError(conn net.Conn, id interface{}, code string, message string) {
	resp := map[string]interface{}{
		"id":     id,
		"result": nil,
		"error": map[string]string{
			"code":    code,
			"message": message,
		},
	}
	b, _ := json.Marshal(resp)
	conn.Write(append(b, '\n'))
}
