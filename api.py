"""
Mission Control API - FastAPI Backend
Integração entre Dashboard e OpenClaw
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from openclaw_client import OpenClawClient, get_openclaw_client
from workflows import (
    WorkflowManager, 
    get_workflow_manager,
    WorkflowStatus,
    StepStatus
)

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuração CORS
ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:3000",
    "http://localhost:8080",
    "https://*.github.io",
    "*"  # Permite todas as origens em desenvolvimento
]

# Modelos Pydantic
class StatusResponse(BaseModel):
    status: str
    openclaw_connected: bool
    timestamp: str
    version: str = "1.0.0"

class Session(BaseModel):
    id: str
    type: str
    status: str
    created_at: Optional[str] = None
    metadata: dict = Field(default_factory=dict)

class SubagentCreate(BaseModel):
    task: str = Field(..., min_length=1, description="Tarefa do subagente")
    label: Optional[str] = Field(None, description="Label identificador")
    model: Optional[str] = Field(None, description="Modelo a ser usado")

class Subagent(BaseModel):
    id: str
    status: str
    task: str
    label: Optional[str] = None
    created_at: str
    model: Optional[str] = None

class WorkflowCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = ""
    team: Optional[str] = ""
    template: Optional[str] = None
    auto_start: bool = False

class WorkflowStepResponse(BaseModel):
    id: str
    name: str
    description: str
    agent_type: str
    status: str
    depends_on: List[str]
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None

class WorkflowResponse(BaseModel):
    id: str
    name: str
    description: str
    team: str
    status: str
    progress: int
    duration: str
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    steps: List[WorkflowStepResponse]
    current_step: int
    logs: List[dict]

class LogEntry(BaseModel):
    time: str
    level: str
    message: str
    source: Optional[str] = None

class SystemStats(BaseModel):
    workflows_total: int
    workflows_running: int
    workflows_completed: int
    workflows_failed: int
    subagents_active: int
    sessions_active: int
    timestamp: str

# Gerenciadores globais
openclaw_client: Optional[OpenClawClient] = None
workflow_manager: Optional[WorkflowManager] = None
system_logs: List[dict] = []

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia ciclo de vida da aplicação"""
    global openclaw_client, workflow_manager
    
    logger.info("🚀 Iniciando Mission Control API...")
    
    # Inicializa gerenciador de workflows
    workflow_manager = get_workflow_manager()
    
    # Tenta conectar ao OpenClaw (não bloqueia se falhar)
    try:
        openclaw_client = OpenClawClient()
        connected = await asyncio.wait_for(openclaw_client.connect(), timeout=5.0)
        if connected:
            logger.info("✅ Conectado ao OpenClaw!")
            system_logs.append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "level": "success",
                "message": "Conectado ao OpenClaw",
                "source": "system"
            })
        else:
            logger.warning("⚠️ Não foi possível conectar ao OpenClaw")
    except Exception as e:
        logger.warning(f"⚠️ OpenClaw não disponível: {e}")
        logger.info("API funcionará em modo simulado")
        system_logs.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "level": "warning",
            "message": f"OpenClaw não disponível: {e}",
            "source": "system"
        })
    
    yield
    
    # Cleanup
    logger.info("🛑 Encerrando Mission Control API...")
    if openclaw_client:
        await openclaw_client.disconnect()

# Cria aplicação FastAPI
app = FastAPI(
    title="Mission Control API",
    description="API de integração entre Dashboard e OpenClaw",
    version="1.0.0",
    lifespan=lifespan
)

# Configura CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============== ENDPOINTS ==============

@app.get("/")
async def root():
    """Endpoint raiz"""
    return {
        "name": "Mission Control API",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "/api/status"
    }

@app.get("/api/status", response_model=StatusResponse)
async def get_status():
    """Retorna status do sistema"""
    connected = openclaw_client.connected if openclaw_client else False
    
    return StatusResponse(
        status="healthy" if connected else "degraded",
        openclaw_connected=connected,
        timestamp=datetime.now().isoformat()
    )

@app.get("/api/stats", response_model=SystemStats)
async def get_stats():
    """Retorna estatísticas do sistema"""
    wf_stats = workflow_manager.get_stats() if workflow_manager else {}
    
    sessions_count = 0
    subagents_count = 0
    
    if openclaw_client and openclaw_client.connected:
        sessions_count = len(openclaw_client.sessions)
        subagents_count = len(openclaw_client.subagents)
    
    return SystemStats(
        workflows_total=wf_stats.get("total", 0),
        workflows_running=wf_stats.get("running", 0),
        workflows_completed=wf_stats.get("completed", 0),
        workflows_failed=wf_stats.get("failed", 0),
        subagents_active=subagents_count,
        sessions_active=sessions_count,
        timestamp=datetime.now().isoformat()
    )

# ============== SESSIONS ==============

@app.get("/api/sessions", response_model=List[Session])
async def list_sessions():
    """Lista sessões ativas do OpenClaw"""
    if not openclaw_client or not openclaw_client.connected:
        # Retorna dados simulados para testes
        return [
            Session(
                id="session-001",
                type="main",
                status="active",
                created_at=datetime.now().isoformat(),
                metadata={"channel": "telegram"}
            ),
            Session(
                id="session-002",
                type="subagent",
                status="active",
                created_at=datetime.now().isoformat(),
                metadata={"parent": "session-001"}
            )
        ]
    
    sessions = await openclaw_client.get_sessions()
    return [
        Session(
            id=s.get("id", "unknown"),
            type=s.get("type", "unknown"),
            status=s.get("status", "unknown"),
            created_at=s.get("created_at"),
            metadata=s.get("metadata", {})
        )
        for s in sessions
    ]

@app.get("/api/sessions/{session_id}", response_model=Session)
async def get_session(session_id: str):
    """Obtém detalhes de uma sessão específica"""
    if openclaw_client and openclaw_client.connected:
        session = await openclaw_client.get_session(session_id)
        if session:
            return Session(
                id=session.get("id", session_id),
                type=session.get("type", "unknown"),
                status=session.get("status", "unknown"),
                created_at=session.get("created_at"),
                metadata=session.get("metadata", {})
            )
    
    raise HTTPException(status_code=404, detail="Sessão não encontrada")

# ============== SUBAGENTS ==============

@app.get("/api/subagents", response_model=List[Subagent])
async def list_subagents():
    """Lista subagentes ativos"""
    if not openclaw_client or not openclaw_client.connected:
        # Dados simulados
        return [
            Subagent(
                id="subagent-001",
                status="running",
                task="Análise de código",
                label="Revisor",
                created_at=datetime.now().isoformat(),
                model="default"
            )
        ]
    
    subagents = await openclaw_client.get_subagents()
    return [
        Subagent(
            id=s.get("id", "unknown"),
            status=s.get("status", "unknown"),
            task=s.get("task", ""),
            label=s.get("label"),
            created_at=s.get("created_at", datetime.now().isoformat()),
            model=s.get("model")
        )
        for s in subagents
    ]

@app.post("/api/subagents", response_model=Subagent)
async def create_subagent(data: SubagentCreate):
    """Cria um novo subagente"""
    logger.info(f"Criando subagente: {data.label or 'unnamed'}")
    
    if openclaw_client and openclaw_client.connected:
        try:
            result = await openclaw_client.create_subagent(
                task=data.task,
                label=data.label,
                model=data.model
            )
            
            system_logs.append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "level": "info",
                "message": f"Subagente criado: {result.get('id')}",
                "source": "api"
            })
            
            return Subagent(
                id=result.get("id"),
                status="spawning",
                task=data.task,
                label=data.label,
                created_at=datetime.now().isoformat(),
                model=data.model
            )
        except Exception as e:
            logger.error(f"Erro criando subagente: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    else:
        # Modo simulado
        subagent_id = f"subagent-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        return Subagent(
            id=subagent_id,
            status="simulated",
            task=data.task,
            label=data.label,
            created_at=datetime.now().isoformat(),
            model=data.model
        )

@app.delete("/api/subagents/{subagent_id}")
async def stop_subagent(subagent_id: str):
    """Para um subagente"""
    logger.info(f"Parando subagente: {subagent_id}")
    
    if openclaw_client and openclaw_client.connected:
        try:
            success = await openclaw_client.stop_subagent(subagent_id)
            if success:
                system_logs.append({
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "level": "info",
                    "message": f"Subagente parado: {subagent_id}",
                    "source": "api"
                })
                return {"success": True, "message": "Subagente parado"}
        except Exception as e:
            logger.error(f"Erro parando subagente: {e}")
    
    return {"success": True, "message": "Subagente parado (simulado)"}

# ============== WORKFLOWS ==============

@app.get("/api/workflows", response_model=List[WorkflowResponse])
async def list_workflows(
    status: Optional[str] = None,
    limit: int = 50
):
    """Lista workflows"""
    if not workflow_manager:
        return []
    
    status_filter = None
    if status:
        try:
            status_filter = WorkflowStatus(status)
        except ValueError:
            pass
    
    workflows = workflow_manager.list_workflows(status=status_filter, limit=limit)
    return [w.to_dict() for w in workflows]

@app.get("/api/workflows/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(workflow_id: str):
    """Obtém detalhes de um workflow"""
    if not workflow_manager:
        raise HTTPException(status_code=503, detail="Workflow manager não disponível")
    
    workflow = workflow_manager.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow não encontrado")
    
    return workflow.to_dict()

@app.post("/api/workflows", response_model=WorkflowResponse)
async def create_workflow(
    data: WorkflowCreate,
    background_tasks: BackgroundTasks
):
    """Cria um novo workflow"""
    if not workflow_manager:
        raise HTTPException(status_code=503, detail="Workflow manager não disponível")
    
    logger.info(f"Criando workflow: {data.name}")
    
    workflow = workflow_manager.create_workflow(
        name=data.name,
        description=data.description or "",
        team=data.team or "",
        template=data.template,
        created_by="api"
    )
    
    system_logs.append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "level": "info",
        "message": f"Workflow criado: {workflow.name}",
        "source": "api"
    })
    
    # Auto-inicia se solicitado
    if data.auto_start:
        background_tasks.add_task(
            workflow_manager.start_workflow,
            workflow.id,
            openclaw_client
        )
    
    return workflow.to_dict()

@app.post("/api/workflows/{workflow_id}/start")
async def start_workflow(workflow_id: str, background_tasks: BackgroundTasks):
    """Inicia um workflow"""
    if not workflow_manager:
        raise HTTPException(status_code=503, detail="Workflow manager não disponível")
    
    workflow = workflow_manager.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow não encontrado")
    
    background_tasks.add_task(
        workflow_manager.start_workflow,
        workflow_id,
        openclaw_client
    )
    
    return {"success": True, "message": "Workflow iniciado"}

@app.post("/api/workflows/{workflow_id}/cancel")
async def cancel_workflow(workflow_id: str):
    """Cancela um workflow"""
    if not workflow_manager:
        raise HTTPException(status_code=503, detail="Workflow manager não disponível")
    
    success = await workflow_manager.cancel_workflow(workflow_id)
    if not success:
        raise HTTPException(status_code=404, detail="Workflow não encontrado")
    
    return {"success": True, "message": "Workflow cancelado"}

@app.get("/api/workflows/templates/list")
async def list_templates():
    """Lista templates disponíveis"""
    if not workflow_manager:
        return []
    
    return workflow_manager.get_templates()

# ============== LOGS ==============

@app.get("/api/logs", response_model=List[LogEntry])
async def get_logs(limit: int = 100, source: Optional[str] = None):
    """Retorna logs do sistema"""
    logs = system_logs[-limit:] if system_logs else []
    
    if source:
        logs = [l for l in logs if l.get("source") == source]
    
    return [LogEntry(**l) for l in logs]

@app.post("/api/logs")
async def add_log(entry: LogEntry):
    """Adiciona uma entrada de log (para testes)"""
    system_logs.append({
        "time": entry.time or datetime.now().strftime("%H:%M:%S"),
        "level": entry.level,
        "message": entry.message,
        "source": entry.source or "external"
    })
    return {"success": True}

# ============== WEBSOCKET (opcional) ==============

from fastapi import WebSocket, WebSocketDisconnect

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket para notificações em tempo real"""
    await websocket.accept()
    
    try:
        while True:
            # Envia atualizações periódicas
            stats = await get_stats()
            await websocket.send_json({
                "type": "stats_update",
                "data": stats.dict()
            })
            
            await asyncio.sleep(3)  # Atualiza a cada 3 segundos
            
    except WebSocketDisconnect:
        logger.info("Cliente WebSocket desconectado")
    except Exception as e:
        logger.error(f"Erro no WebSocket: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
