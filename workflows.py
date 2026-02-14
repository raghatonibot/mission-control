"""
Sistema de Workflows do Mission Control
Gerencia workflows, etapas e execução via subagentes
"""

import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import asyncio
import logging

logger = logging.getLogger(__name__)


class WorkflowStatus(str, Enum):
    PENDING = "pendente"
    RUNNING = "em_andamento"
    COMPLETED = "concluido"
    FAILED = "falhou"
    CANCELLED = "cancelado"


class StepStatus(str, Enum):
    PENDING = "pendente"
    RUNNING = "em_andamento"
    COMPLETED = "concluido"
    FAILED = "falhou"
    SKIPPED = "pulado"


class WorkflowStep:
    """Representa uma etapa de um workflow"""
    
    def __init__(
        self,
        name: str,
        description: str = "",
        agent_type: str = "assistente",
        task_template: str = "",
        depends_on: List[str] = None,
        timeout_minutes: int = 30
    ):
        self.id = str(uuid.uuid4())[:8]
        self.name = name
        self.description = description
        self.agent_type = agent_type
        self.task_template = task_template
        self.depends_on = depends_on or []
        self.timeout_minutes = timeout_minutes
        self.status = StepStatus.PENDING
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.result: Optional[str] = None
        self.error: Optional[str] = None
        self.subagent_id: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "agent_type": self.agent_type,
            "status": self.status.value,
            "depends_on": self.depends_on,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
            "error": self.error,
            "subagent_id": self.subagent_id
        }


class Workflow:
    """Representa um workflow completo"""
    
    def __init__(
        self,
        name: str,
        description: str = "",
        team: str = "",
        created_by: str = "system"
    ):
        self.id = f"wf-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{str(uuid.uuid4())[:4]}"
        self.name = name
        self.description = description
        self.team = team
        self.created_by = created_by
        self.status = WorkflowStatus.PENDING
        self.steps: List[WorkflowStep] = []
        self.created_at = datetime.now()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.current_step_index = 0
        self.logs: List[dict] = []
    
    @property
    def progress(self) -> int:
        """Calcula progresso em porcentagem"""
        if not self.steps:
            return 0
        completed = sum(1 for s in self.steps if s.status == StepStatus.COMPLETED)
        return int((completed / len(self.steps)) * 100)
    
    @property
    def duration(self) -> str:
        """Retorna duração formatada"""
        if not self.started_at:
            return "0m 0s"
        
        end = self.completed_at or datetime.now()
        delta = end - self.started_at
        minutes = int(delta.total_seconds() // 60)
        seconds = int(delta.total_seconds() % 60)
        return f"{minutes}m {seconds}s"
    
    def add_step(self, step: WorkflowStep):
        """Adiciona uma etapa ao workflow"""
        self.steps.append(step)
    
    def add_log(self, level: str, message: str):
        """Adiciona entrada de log"""
        self.logs.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "level": level,
            "message": message
        })
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "team": self.team,
            "status": self.status.value,
            "progress": self.progress,
            "duration": self.duration,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "steps": [s.to_dict() for s in self.steps],
            "current_step": self.current_step_index,
            "logs": self.logs[-20:]  # Últimos 20 logs
        }


class WorkflowManager:
    """Gerencia todos os workflows do sistema"""
    
    # Templates predefinidos
    TEMPLATES = {
        "ci-cd": {
            "name": "CI/CD Pipeline",
            "description": "Pipeline completo de integração e deploy",
            "steps": [
                {
                    "name": "Revisão de Código",
                    "description": "Análise automatizada do código",
                    "agent_type": "revisor",
                    "task_template": "Revise o código em busca de bugs, code smells e violações de boas práticas. Forneça sugestões de melhoria."
                },
                {
                    "name": "Testes Unitários",
                    "description": "Execução de testes automatizados",
                    "agent_type": "testador",
                    "task_template": "Execute todos os testes unitários e gere relatório de cobertura."
                },
                {
                    "name": "Testes de Integração",
                    "description": "Testes de integração entre componentes",
                    "agent_type": "testador",
                    "task_template": "Execute testes de integração e verifique comunicação entre serviços."
                },
                {
                    "name": "Deploy",
                    "description": "Deploy da aplicação em produção",
                    "agent_type": "deployer",
                    "task_template": "Realize o deploy da aplicação seguindo o checklist de deploy."
                }
            ]
        },
        "analise-codigo": {
            "name": "Análise de Código",
            "description": "Análise completa de qualidade do código",
            "steps": [
                {
                    "name": "Análise Estática",
                    "description": "Análise estática com linters",
                    "agent_type": "revisor",
                    "task_template": "Execute ferramentas de análise estática e identifique problemas."
                },
                {
                    "name": "Análise de Segurança",
                    "description": "Scan de vulnerabilidades",
                    "agent_type": "especialista",
                    "task_template": "Identifique vulnerabilidades de segurança no código."
                },
                {
                    "name": "Relatório",
                    "description": "Geração de relatório consolidado",
                    "agent_type": "analista",
                    "task_template": "Compile relatório com todas as findings e recomendações."
                }
            ]
        },
        "suporte": {
            "name": "Triagem de Suporte",
            "description": "Triagem automatizada de tickets",
            "steps": [
                {
                    "name": "Classificação",
                    "description": "Classifica prioridade do ticket",
                    "agent_type": "analista",
                    "task_template": "Analise o ticket e classifique por severidade e área."
                },
                {
                    "name": "Investigação",
                    "description": "Investiga preliminar do problema",
                    "agent_type": "especialista",
                    "task_template": "Investigue logs e identifique possíveis causas root."
                },
                {
                    "name": "Escalonamento",
                    "description": "Encaminha para equipe adequada",
                    "agent_type": "gerente",
                    "task_template": "Determine qual equipe deve resolver o ticket."
                }
            ]
        }
    }
    
    def __init__(self):
        self.workflows: Dict[str, Workflow] = {}
        self._running: Dict[str, asyncio.Task] = {}
    
    def create_workflow(
        self,
        name: str,
        description: str = "",
        team: str = "",
        template: Optional[str] = None,
        created_by: str = "system"
    ) -> Workflow:
        """Cria um novo workflow"""
        workflow = Workflow(name, description, team, created_by)
        
        # Adiciona etapas do template se especificado
        if template and template in self.TEMPLATES:
            template_data = self.TEMPLATES[template]
            workflow.description = description or template_data["description"]
            
            for step_data in template_data["steps"]:
                step = WorkflowStep(
                    name=step_data["name"],
                    description=step_data["description"],
                    agent_type=step_data["agent_type"],
                    task_template=step_data["task_template"]
                )
                workflow.add_step(step)
        
        self.workflows[workflow.id] = workflow
        workflow.add_log("info", f"Workflow '{name}' criado")
        logger.info(f"Workflow criado: {workflow.id}")
        
        return workflow
    
    def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        """Obtém um workflow pelo ID"""
        return self.workflows.get(workflow_id)
    
    def list_workflows(
        self,
        status: Optional[WorkflowStatus] = None,
        limit: int = 50
    ) -> List[Workflow]:
        """Lista workflows com filtros opcionais"""
        workflows = list(self.workflows.values())
        
        if status:
            workflows = [w for w in workflows if w.status == status]
        
        # Ordena por data de criação (mais recente primeiro)
        workflows.sort(key=lambda w: w.created_at, reverse=True)
        
        return workflows[:limit]
    
    async def start_workflow(self, workflow_id: str, openclaw_client=None) -> bool:
        """Inicia execução de um workflow"""
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            return False
        
        if workflow.status == WorkflowStatus.RUNNING:
            logger.warning(f"Workflow {workflow_id} já está em execução")
            return False
        
        workflow.status = WorkflowStatus.RUNNING
        workflow.started_at = datetime.now()
        workflow.add_log("info", "Workflow iniciado")
        
        # Inicia execução em background
        task = asyncio.create_task(self._execute_workflow(workflow, openclaw_client))
        self._running[workflow_id] = task
        
        logger.info(f"Workflow iniciado: {workflow_id}")
        return True
    
    async def _execute_workflow(self, workflow: Workflow, openclaw_client=None):
        """Executa as etapas do workflow"""
        try:
            for i, step in enumerate(workflow.steps):
                workflow.current_step_index = i
                
                # Verifica dependências
                pending_deps = [
                    s for s in workflow.steps 
                    if s.id in step.depends_on and s.status != StepStatus.COMPLETED
                ]
                if pending_deps:
                    step.status = StepStatus.PENDING
                    workflow.add_log("warning", f"Etapa '{step.name}' aguardando dependências")
                    continue
                
                # Executa etapa
                step.status = StepStatus.RUNNING
                step.started_at = datetime.now()
                workflow.add_log("info", f"Etapa '{step.name}' iniciada")
                
                try:
                    # Aqui integraria com subagentes reais via openclaw_client
                    if openclaw_client:
                        # Cria subagente para executar a tarefa
                        result = await openclaw_client.create_subagent(
                            task=step.task_template,
                            label=f"{workflow.name} - {step.name}"
                        )
                        step.subagent_id = result.get("id")
                        
                        # Simula execução (em produção, aguardaria conclusão)
                        await asyncio.sleep(5)  # Simula tempo de execução
                    else:
                        # Modo simulado para testes
                        await asyncio.sleep(2)
                    
                    step.status = StepStatus.COMPLETED
                    step.completed_at = datetime.now()
                    step.result = "Concluído com sucesso"
                    workflow.add_log("success", f"Etapa '{step.name}' concluída")
                    
                except Exception as e:
                    step.status = StepStatus.FAILED
                    step.error = str(e)
                    workflow.add_log("error", f"Etapa '{step.name}' falhou: {e}")
                    
                    # Decide se continua ou aborta
                    workflow.status = WorkflowStatus.FAILED
                    break
            
            # Finaliza workflow
            if workflow.status != WorkflowStatus.FAILED:
                workflow.status = WorkflowStatus.COMPLETED
                workflow.add_log("success", "Workflow concluído com sucesso")
            
            workflow.completed_at = datetime.now()
            
        except Exception as e:
            workflow.status = WorkflowStatus.FAILED
            workflow.add_log("error", f"Erro na execução: {e}")
            logger.error(f"Erro executando workflow {workflow.id}: {e}")
        
        finally:
            self._running.pop(workflow.id, None)
    
    async def cancel_workflow(self, workflow_id: str) -> bool:
        """Cancela um workflow em execução"""
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            return False
        
        if workflow_id in self._running:
            task = self._running[workflow_id]
            task.cancel()
            self._running.pop(workflow_id, None)
        
        workflow.status = WorkflowStatus.CANCELLED
        workflow.completed_at = datetime.now()
        workflow.add_log("warning", "Workflow cancelado pelo usuário")
        
        return True
    
    def get_templates(self) -> List[dict]:
        """Retorna lista de templates disponíveis"""
        return [
            {
                "id": key,
                "name": data["name"],
                "description": data["description"],
                "steps_count": len(data["steps"])
            }
            for key, data in self.TEMPLATES.items()
        ]
    
    def get_stats(self) -> dict:
        """Retorna estatísticas dos workflows"""
        all_workflows = list(self.workflows.values())
        
        return {
            "total": len(all_workflows),
            "pending": sum(1 for w in all_workflows if w.status == WorkflowStatus.PENDING),
            "running": sum(1 for w in all_workflows if w.status == WorkflowStatus.RUNNING),
            "completed": sum(1 for w in all_workflows if w.status == WorkflowStatus.COMPLETED),
            "failed": sum(1 for w in all_workflows if w.status == WorkflowStatus.FAILED),
            "cancelled": sum(1 for w in all_workflows if w.status == WorkflowStatus.CANCELLED)
        }


# Singleton do manager
_manager: Optional[WorkflowManager] = None

def get_workflow_manager() -> WorkflowManager:
    """Obtém instância singleton do gerenciador"""
    global _manager
    if _manager is None:
        _manager = WorkflowManager()
    return _manager
