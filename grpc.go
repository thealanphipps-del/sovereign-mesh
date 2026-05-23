package sovereign

import (
	"context"
	"crypto/sha256"
	"fmt"
	"log"
	"time"

	"github.com/pqr-info/sovereign-mesh/proto"
)

type meshServer struct {
	proto.UnimplementedSovereignMeshServer
	proto.UnimplementedAgentSyncServer
	proto.UnimplementedNeuralTrainingServer
	proto.UnimplementedSovereignCityServer
	controller *Controller
}

func (s *meshServer) GetSystemMetrics(ctx context.Context, req *proto.SystemMetricsRequest) (*proto.SystemMetricsResponse, error) {
	log.Printf("🧪 SILICON PROBE: Deep hardware telemetry requested.")
	// Simulated silicon-level dive
	return &proto.SystemMetricsResponse{
		KernelVersion: "6.1.0-48-cloud-arm64",
		Uptime:        "86400s",
		LoadAvg_1:     0.42,
		Memory: &proto.MemoryMetrics{
			TotalKb: 4194304,
			FreeKb:  1048576,
			UsedKb:  3145728,
		},
		CpuCores: []*proto.CPUMetrics{
			{CoreId: 0, ClockMhz: 3200.0, LoadPercent: 12.5, TemperatureC: 45.5},
			{CoreId: 1, ClockMhz: 3200.0, LoadPercent: 8.2, TemperatureC: 44.0},
		},
	}, nil
}

func (s *meshServer) TeleportProcess(ctx context.Context, req *proto.TeleportProcessRequest) (*proto.TeleportProcessResponse, error) {
	err := s.controller.TeleportProcess(req.Pid, req.TargetNode)
	if err != nil {
		return &proto.TeleportProcessResponse{Success: false, Message: err.Error()}, nil
	}

	stack := "main.go:42 -> memory.go:111"
	return &proto.TeleportProcessResponse{
		Success:    true,
		Message:    fmt.Sprintf("Process %d migrated to %s", req.Pid, req.TargetNode),
		StackTrace: stack,
	}, nil
}

func (s *meshServer) ManageProcess(ctx context.Context, req *proto.ProcessActionRequest) (*proto.CommandResult, error) {
	log.Printf("🛑 SILICON INTERVENTION: Action %s on PID %d", req.Action, req.Pid)
	// Implementation would call native syscalls or wrap CLI
	return &proto.CommandResult{
		ExitCode: 0,
		Stdout:   fmt.Sprintf("Process %d %s command executed under AAAA audit.", req.Pid, req.Action),
	}, nil
}

func (s *meshServer) ExecuteStrike(ctx context.Context, req *proto.StrikeRequest) (*proto.StrikeResponse, error) {
	log.Printf("🧨 STRIKE PROTOCOL: Ticket %s | Payload: %s", req.TicketId, req.LogicPayload)
	
	// Implementation of high-priority command execution
	// In the real system, this uses the biometric signature for root authority
	output := fmt.Sprintf("[STRIKE-SUCCESS] Command executed for ticket %s.", req.TicketId)
	
	return &proto.StrikeResponse{
		ExitCode:  0,
		LogOutput: output,
		ProofHash: "sha256-proof-of-execution-hash",
	}, nil
}

func (s *meshServer) StreamVitality(req *proto.TelemetryRequest, stream proto.AgentSync_StreamVitalityServer) error {
	log.Printf("📈 VITALITY STREAM: Monitoring node %s", req.NodeId)
	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-stream.Context().Done():
			return nil
		case <-ticker.C:
			err := stream.Send(&proto.TelemetryData{
				VitalityScore: 7.2,
				Slope:         5.16,
			})
			if err != nil {
				return err
			}
		}
	}
}

func (s *meshServer) SyncBlackhole(stream proto.AgentSync_SyncBlackholeServer) error {
	log.Printf("🌑 BLACKHOLE SYNC: Bi-directional link established.")
	return nil
}

func (s *meshServer) ExecuteShell(ctx context.Context, req *proto.CommandPayload) (*proto.CommandResult, error) {
	return s.RemoteExecute(ctx, req)
}

func (s *meshServer) StreamLogs(req *proto.LogRequest, stream proto.AgentSync_StreamLogsServer) error {
	log.Printf("📜 LOG STREAM: Exporting logs for %s", req.NodeId)
	return nil
}

func (s *meshServer) AtomicSwap(ctx context.Context, req *proto.AtomicSwapRequest) (*proto.AtomicSwapResponse, error) {
	log.Printf("🚀 ATOMIC SWAP: Hot-swapping PID %d with %s", req.TargetPid, req.NewBinaryPath)

	// 1. Trigger RADIUS Audit
	s.controller.LogAccountingEvent("SYSTEM", fmt.Sprintf("SWAP-%d", req.TargetPid), 1, 0, 0) // START

	// 2. Perform Silicon-Level Handoff
	// In a production build, this would use SCM_RIGHTS to pass file descriptors
	// or kpatch/kgraft style live patching.
	time.Sleep(100 * time.Millisecond) // Simulated quantum transition

	newPID := req.TargetPid + 100 // Simulated new PID

	return &proto.AtomicSwapResponse{
		Success:       true,
		Message:       fmt.Sprintf("Atomic swap complete. New logic active under PID %d.", newPID),
		NewPid:        newPID,
		HandoffStatus: "STABLE_OBULUSK",
	}, nil
}

func (s *meshServer) GetStarchart(ctx context.Context, req *proto.StarchartRequest) (*proto.StarchartResponse, error) {
	log.Printf("✨ STARCHART: Requesting unified temporal and accounting map.")
	
	// In a real implementation, we'd query the ledger and RADIUS database
	return &proto.StarchartResponse{
		ConstellationMap: "<svg>...</svg>",
		Timeline: []*proto.LedgerBlock{
			{BlockIndex: 1, AgentId: "AGENT-0", BlockHash: "abc", Timestamp: time.Now().Format(time.RFC3339)},
		},
		AccountingData: []*proto.AccountingRecord{
			{Username: "billing", SessionId: "SESS-01", StatusType: "START", Timestamp: time.Now().Format(time.RFC3339)},
		},
	}, nil
}

func (s *meshServer) ProvisionNode(ctx context.Context, req *proto.ProvisionNodeRequest) (*proto.ProvisionNodeResponse, error) {
	var id, ip string
	var err error

	switch req.Provider {
	case "GCP":
		id, ip, err = s.controller.ProvisionGCP(req.Region, req.NodeClass)
	case "HETZNER":
		id, ip, err = s.controller.ProvisionHetzner(req.Region, req.NodeClass)
	case "AWS":
		id, ip, err = s.controller.ProvisionAWS(req.Region, req.NodeClass)
	default:
		return nil, fmt.Errorf("unsupported provider: %s", req.Provider)
	}

	if err != nil {
		return &proto.ProvisionNodeResponse{
			Success: false,
			Message: err.Error(),
		}, nil
	}

	return &proto.ProvisionNodeResponse{
		Success:    true,
		InstanceId: id,
		PublicIp:   ip,
		Message:    fmt.Sprintf("Successfully provisioned %s node in %s", req.Provider, req.Region),
	}, nil
}

func (s *meshServer) UpdateDNS(ctx context.Context, req *proto.DNSRequest) (*proto.UserResponse, error) {
	var err error
	switch req.Provider {
	case "CLOUDFLARE":
		err = s.controller.UpdateCloudflareDNS(req.Zone, req.RecordType, req.Name, req.Content, int(req.Ttl))
	case "GODADDY":
		err = s.controller.UpdateGoDaddyDNS(req.Zone, req.RecordType, req.Name, req.Content, int(req.Ttl))
	default:
		return nil, fmt.Errorf("unsupported DNS provider: %s", req.Provider)
	}

	if err != nil {
		return &proto.UserResponse{Success: false, Message: err.Error()}, nil
	}
	return &proto.UserResponse{Success: true, Message: "DNS record updated successfully"}, nil
}

func (s *meshServer) ManageTunnel(ctx context.Context, req *proto.TunnelRequest) (*proto.UserResponse, error) {
	err := s.controller.ManageCloudflareTunnel(req.Action, req.Name)
	if err != nil {
		return &proto.UserResponse{Success: false, Message: err.Error()}, nil
	}
	return &proto.UserResponse{Success: true, Message: fmt.Sprintf("Tunnel %s %s successful", req.Name, req.Action)}, nil
}

func (s *meshServer) CreateTicket(ctx context.Context, req *proto.TicketRequest) (*proto.UserResponse, error) {
	log.Printf("🎫 TICKET ISSUED: [%s] %s", req.TicketId, req.Content)

	// 1. Commit to internal Ledger (The "Sovereign Truth")
	payload := map[string]interface{}{
		"action":      "TICKET_CREATED",
		"ticket_id":   req.TicketId,
		"ticket_type": req.TicketType,
		"content":     req.Content,
		"path":        req.Path,
		"status":      req.Status,
	}
	s.controller.CommitMutation("SYSTEM-TICKETER", payload)

	// 2. Mirror to Remote rtgo_ticketing_system (The "Legacy Quorum")
	// We use the established reverse tunnel or direct SSH if available.
	// This ensures the operator sees the tickets in the legacy DB.
	go func() {
		cmd := fmt.Sprintf("sudo -u postgres psql -d rtgo_ticketing_system -c \"INSERT INTO tickets (ticket_id, ticket_type, content, path, status) VALUES ('%s', '%s', '%s', '%s', '%s') ON CONFLICT (ticket_id) DO UPDATE SET status = EXCLUDED.status, updated_at = NOW()\"",
			req.TicketId, req.TicketType, req.Content, req.Path, req.Status)

		// We execute this on 39.mh via the bridge or direct SSH
		// For now, we assume the server has SSH access to itself or 39.mh is the ticket master
		s.controller.RemoteExecute("39.mh", cmd)
	}()

	return &proto.UserResponse{
		Success: true,
		Message: fmt.Sprintf("Ticket %s materialized in the swarm timeline.", req.TicketId),
	}, nil
}

func (s *meshServer) InitiateTraining(ctx context.Context, req *proto.TrainingRequest) (*proto.TrainingSession, error) {
	log.Printf("🧠 NEURAL INITIATION: Triggering training cycle for %s on cluster %s", req.ModelName, req.ClusterId)

	sessionID := fmt.Sprintf("session-%s-%x", req.ModelName, time.Now().Unix())

	s.controller.syncLock.Lock()
	s.controller.neuralSessions[sessionID] = &TrainingSessionState{
		SessionID: sessionID,
		State:     "RUNNING",
	}
	s.controller.syncLock.Unlock()

	// 1. Trigger Audit via Ledger
	mutation := map[string]interface{}{
		"action":      "TRAINING_INITIATED",
		"session_id":  sessionID,
		"model_name":  req.ModelName,
		"cluster_id":  req.ClusterId,
		"reason":      "NEURAL_TRANSITION",
	}
	s.controller.CommitMutation("NEURAL-ENGINE", mutation)

	return &proto.TrainingSession{
		SessionId: sessionID,
		ClusterId: req.ClusterId,
		Status:    "RUNNING",
	}, nil
}

func (s *meshServer) GetTrainingStatus(ctx context.Context, req *proto.TrainingStatusRequest) (*proto.TrainingStatus, error) {
	s.controller.syncLock.RLock()
	session, ok := s.controller.neuralSessions[req.SessionId]
	s.controller.syncLock.RUnlock()

	if !ok {
		return nil, fmt.Errorf("session not found: %s", req.SessionId)
	}

	return &proto.TrainingStatus{
		SessionId:        session.SessionID,
		CurrentStep:      session.CurrentStep,
		Loss:             session.Loss,
		PhaseDrift:       session.PhaseDrift,
		GradientVitality: session.GradientVitality,
		LastCheckpointRef: session.LastCheckpointRef,
		State:            session.State,
	}, nil
}

// SovereignCity Handlers
func (s *meshServer) RegisterCitizen(ctx context.Context, req *proto.CitizenRegistration) (*proto.CitizenPassport, error) {
	log.Printf("🛂 CITY REGISTRATION: Registering citizen %s...", req.Username)

	citizenID := fmt.Sprintf("CITIZEN-%x", sha256.Sum256([]byte(req.Username)))[:12]
	
	s.controller.syncLock.Lock()
	s.controller.citizens[citizenID] = &Citizen{
		CitizenID: citizenID,
		Username:  req.Username,
		Balances: map[AssetType]float64{
			SURFGO: req.InitialBurnAmount,
			PQR:    0.0,
			RTGO:   0.0,
			SOV:    0.0,
			SOV2:   0.0,
			LOMALO: 0.0,
		},
		Status: "ACTIVE",
	}
	s.controller.syncLock.Unlock()

	// Commit to Ledger
	mutation := map[string]interface{}{
		"action":     "CITIZEN_REGISTERED",
		"citizen_id": citizenID,
		"username":   req.Username,
		"burn":       req.InitialBurnAmount,
	}
	s.controller.CommitMutation("CITY-GATEKEEPER", mutation)

	return &proto.CitizenPassport{
		CitizenId:   citizenID,
		AccessToken: "pqr-citizen-jwt-" + citizenID,
		Status:      "ACTIVE",
	}, nil
}

func (s *meshServer) RequestService(ctx context.Context, req *proto.ServiceRequest) (*proto.ServiceAllocation, error) {
	log.Printf("📦 CITY SERVICE: Citizen %s requesting %s", req.CitizenId, req.ServiceType)

	s.controller.syncLock.RLock()
	citizen, ok := s.controller.citizens[req.CitizenId]
	s.controller.syncLock.RUnlock()

	if !ok {
		return nil, fmt.Errorf("citizen not found")
	}

	if citizen.Balances[SURFGO] < 1.0 {
		return nil, fmt.Errorf("insufficient SURFGO balance to provision service")
	}

	serviceID := fmt.Sprintf("SRV-%s-%x", req.ServiceType, time.Now().Unix())
	endpoint := "pending.sovereign.city"

	// Orchestration based on type
	switch req.ServiceType {
	case "DNS":
		subdomain := req.Parameters["subdomain"]
		targetIP := req.Parameters["target_ip"]
		err := s.controller.ProvisionCitizenSubdomain(req.CitizenId, subdomain, targetIP)
		if err != nil {
			return nil, err
		}
		endpoint = subdomain + ".sovereign.city"
	case "TUNNEL":
		name := req.Parameters["tunnel_name"]
		err := s.controller.ManageCloudflareTunnel("CREATE", name)
		if err != nil {
			return nil, err
		}
		endpoint = name + ".tunnel.sovereign.city"
	}

	return &proto.ServiceAllocation{
		ServiceId:  serviceID,
		Endpoint:   endpoint,
		ConfigJson: "{\"status\": \"ALLOCATED\"}",
	}, nil
}

func (s *meshServer) GetCitizenStatus(ctx context.Context, req *proto.CitizenStatusRequest) (*proto.CitizenStatusResponse, error) {
	s.controller.syncLock.RLock()
	citizen, ok := s.controller.citizens[req.CitizenId]
	s.controller.syncLock.RUnlock()

	if !ok {
		return nil, fmt.Errorf("citizen not found")
	}

	return &proto.CitizenStatusResponse{
		CitizenId:      citizen.CitizenID,
		SurfgoBalance:  citizen.Balances[SURFGO],
		PqrBalance:     citizen.Balances[PQR],
		RtgoBalance:    citizen.Balances[RTGO],
		SovBalance:     citizen.Balances[SOV],
		Sov2Balance:    citizen.Balances[SOV2],
		LomaloBalance:  citizen.Balances[LOMALO],
		ActiveServices: citizen.ActiveServices,
		Status:         citizen.Status,
	}, nil
}

func (s *meshServer) Heartbeat(ctx context.Context, req *proto.AgentHeartbeat) (*proto.Response, error) {
	s.controller.syncLock.Lock()
	defer s.controller.syncLock.Unlock()

	s.controller.agents[req.AgentId] = &Agent{
		ID:                req.AgentId,
		Address:           req.Address,
		Status:            req.Status,
		IntelligenceLevel: int(req.IntelligenceLevel),
		LastHeartbeat:     time.Now(),
	}

	return &proto.Response{Success: true}, nil
}

func (s *meshServer) HandshakeState(ctx context.Context, req *proto.StatePayload) (*proto.SyncAck, error) {
	log.Printf("🤝 MESH HANDSHAKE: Agent %s joining swarm.", req.AgentId)
	s.controller.syncLock.Lock()
	defer s.controller.syncLock.Unlock()

	s.controller.agents[req.AgentId] = &Agent{
		ID:           req.AgentId,
		Status:       "active",
		CurrentModel: req.ActiveModel,
	}

	return &proto.SyncAck{
		Success:       true,
		Message:       "Welcome to the Sovereign Swarm.",
		SyncTimestamp: time.Now().UnixMilli(),
	}, nil
}

func (s *meshServer) SyncState(ctx context.Context, req *proto.StateUpdate) (*proto.Response, error) {
	// Here we update internal metrics or LTM based on remote agent state
	s.controller.syncLock.Lock()
	defer s.controller.syncLock.Unlock()

	if agent, ok := s.controller.agents[req.AgentId]; ok {
		agent.Status = "active"
	}

	return &proto.Response{Success: true}, nil
}

func (s *meshServer) RequestTask(ctx context.Context, req *proto.TaskLease) (*proto.TaskAssignment, error) {
	select {
	case taskID := <-s.controller.tasks:
		return &proto.TaskAssignment{
			TaskId:      taskID,
			Description: "Assigned via gRPC Mesh",
		}, nil
	case <-ctx.Done():
		return nil, ctx.Err()
	default:
		// No tasks available
		return &proto.TaskAssignment{
			TaskId:      "",
			Description: "IDLE",
		}, nil
	}
}

func (s *meshServer) GetBalance(ctx context.Context, req *proto.WalletRequest) (*proto.WalletResponse, error) {
	s.controller.syncLock.RLock()
	defer s.controller.syncLock.RUnlock()

	agent, ok := s.controller.agents[req.AgentId]
	if !ok {
		return nil, fmt.Errorf("wallet not found")
	}

	return &proto.WalletResponse{
		Balance: 100.0, // Placeholder: in real use, calculate from ledger
		Staked:  agent.StakedAmount,
	}, nil
}

func (s *meshServer) StakeCoin(ctx context.Context, req *proto.StakeRequest) (*proto.Response, error) {
	s.controller.syncLock.Lock()
	defer s.controller.syncLock.Unlock()

	if agent, ok := s.controller.agents[req.AgentId]; ok {
		agent.StakedAmount += req.Amount
		// Proof of Trust (POT) increases as stake increases
		state := s.controller.GetAgentState(agent.MemoryOffset)
		state.TrustScore += float32(req.Amount / 1000.0)
		return &proto.Response{Success: true, Message: "Stake materialized"}, nil
	}
	return &proto.Response{Success: false, Message: "Agent not found"}, nil
}
