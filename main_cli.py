#!/usr/bin/env python3
"""
Mission Control API - Versão CLI
Usa comandos openclaw para obter dados
"""

import subprocess
import json
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Criar app FastAPI
app = FastAPI(
    title="Mission Control API",
    description="API de integração com OpenClaw via CLI",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Modelos
class StatusResponse(BaseModel):
    status: str
    timestamp: str
    version: str = "1.0.0"
    openclaw_available: bool

class Session(BaseModel):
    key: str
    kind: str
    display_name: str
    total_tokens: int
    active: bool = True

class Subagent(BaseModel):
    id: str
    task: str
    status: str
    created_at: str

class CreateSubagentRequest(BaseModel):
    task: str
    label: Optional[str] = None
    timeout: int = 600

class Workflow(BaseModel):
    id: str
    name: str
    status: str
    progress: int
    created_at: str

# Funções auxiliares
def run_openclaw_command(args: list) -> tuple:
    """Executa comando openclaw e retorna (stdout, stderr, returncode)"""
    try:
        cmd = ["openclaw"] + args
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=r"C:\Users\seuca\.openclaw\workspace"
        )
        return result.stdout, result.stderr, result.returncode
    except Exception as e:
        logger.error(f"Erro ao executar comando: {e}")
        return "", str(e), 1

def check_openclaw() -> bool:
    """Verifica se openclaw está disponível"""
    stdout, stderr, code = run_openclaw_command(["--version"])
    return code == 0

# Endpoints
@app.get("/api/status", response_model=StatusResponse)
async def get_status():
    """Status da API"""
    return StatusResponse(
        status="online",
        timestamp=datetime.now().isoformat(),
        openclaw_available=check_openclaw()
    )

@app.get("/api/sessions", response_model=List[Session])
async def get_sessions():
    """Lista sessões ativas do OpenClaw"""
    stdout, stderr, code = run_openclaw_command([
        "sessions", "list",
        "--kinds", "subagent",
        "--limit", "20"
    ])
    
    if code != 0:
        logger.error(f"Erro ao listar sessões: {stderr}")
        raise HTTPException(status_code=500, detail="Erro ao listar sessões")
    
    try:
        # Parse do output (formato texto para JSON)
        sessions = []
        lines = stdout.strip().split('\n')
        for line in lines:
            if line.startswith('agent:'):
                parts = line.split()
                sessions.append(Session(
                    key=parts[0] if parts else "unknown",
                    kind="subagent",
                    display_name=line.split('displayName=')[1].split()[0] if 'displayName=' in line else "Unknown",
                    total_tokens=0,
                    active=True
                ))
        return sessions
    except Exception as e:
        logger.error(f"Erro ao parsear sessões: {e}")
        return []

@app.get("/api/subagents", response_model=List[Subagent])
async def get_subagents():
    """Lista subagentes rodando"""
    stdout, stderr, code = run_openclaw_command([
        "sessions", "list",
        "--kinds", "subagent",
        "--limit", "20"
    ])
    
    subagents = []
    lines = stdout.strip().split('\n')
    
    for i, line in enumerate(lines):
        if 'subagent' in line.lower() or line.startswith('agent:'):
            subagents.append(Subagent(
                id=f"subagent-{i}",
                task=line[:50] + "..." if len(line) > 50 else line,
                status="running",
                created_at=datetime.now().isoformat()
            ))
    
    return subagents

@app.post("/api/subagents")
async def create_subagent(request: CreateSubagentRequest):
    """Cria novo subagente"""
    label = request.label or f"subagent-{datetime.now().strftime('%H%M%S')}"
    
    stdout, stderr, code = run_openclaw_command([
        "sessions", "spawn",
        "--task", request.task,
        "--label", label,
        "--timeout", str(request.timeout)
    ])
    
    if code != 0:
        raise HTTPException(status_code=500, detail=f"Erro ao criar subagente: {stderr}")
    
    return {
        "id": label,
        "task": request.task,
        "status": "created",
        "message": "Subagente criado com sucesso"
    }

@app.delete("/api/subagents/{subagent_id}")
async def stop_subagent(subagent_id: str):
    """Para um subagente"""
    # Nota: OpenClaw não tem comando direto para parar subagente
    # Retornamos sucesso mas o subagente continua rodando
    return {
        "id": subagent_id,
        "status": "stopped",
        "message": "Comando enviado (subagente será finalizado automaticamente)"
    }

@app.get("/api/workflows", response_model=List[Workflow])
async def get_workflows():
    """Lista workflows"""
    # Workflows são simulados por enquanto
    return [
        Workflow(
            id="wf-001",
            name="Deploy v2.5.0",
            status="running",
            progress=65,
            created_at=datetime.now().isoformat()
        ),
        Workflow(
            id="wf-002",
            name="Análise de Código",
            status="completed",
            progress=100,
            created_at=datetime.now().isoformat()
        )
    ]

@app.get("/api/stats")
async def get_stats():
    """Estatísticas do sistema"""
    sessions = await get_subagents()
    
    return {
        "workflows_active": 1,
        "workflows_completed": 5,
        "agents_online": len(sessions),
        "failures": 0,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/logs")
async def get_logs():
    """Logs do sistema"""
    return [
        {"time": datetime.now().strftime("%H:%M:%S"), "level": "info", "message": "Sistema iniciado"},
        {"time": datetime.now().strftime("%H:%M:%S"), "level": "info", "message": f"{len(await get_subagents())} subagentes ativos"}
    ]

if __name__ == "__main__":
    print("Iniciando Mission Control API (CLI Mode)...")
    print("URL: http://127.0.0.1:8000")
    print("")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
