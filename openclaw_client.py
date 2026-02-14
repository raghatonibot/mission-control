"""
OpenClaw WebSocket Client
Conecta ao gateway OpenClaw para comunicação em tempo real
"""

import asyncio
import json
import websockets
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class OpenClawClient:
    """Cliente WebSocket para comunicação com o gateway OpenClaw"""
    
    def __init__(self, gateway_url: str = "ws://127.0.0.1:18789"):
        self.gateway_url = gateway_url
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.connected = False
        self.sessions: Dict[str, Any] = {}
        self.subagents: Dict[str, Any] = {}
        self.message_handlers: List[Callable] = []
        self._reconnect_delay = 5
        self._running = False
        
    async def connect(self) -> bool:
        """Conecta ao gateway OpenClaw"""
        try:
            logger.info(f"Conectando ao OpenClaw em {self.gateway_url}...")
            self.websocket = await websockets.connect(self.gateway_url)
            self.connected = True
            self._running = True
            logger.info("✅ Conectado ao OpenClaw!")
            
            # Inicia loop de recebimento de mensagens
            asyncio.create_task(self._receive_loop())
            
            # Envia mensagem de identificação
            await self._send({
                "type": "identify",
                "client": "mission-control-api",
                "version": "1.0.0"
            })
            
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao conectar: {e}")
            self.connected = False
            return False
    
    async def disconnect(self):
        """Desconecta do gateway"""
        self._running = False
        if self.websocket:
            await self.websocket.close()
        self.connected = False
        logger.info("Desconectado do OpenClaw")
    
    async def _send(self, message: dict):
        """Envia mensagem para o gateway"""
        if self.websocket and self.connected:
            try:
                await self.websocket.send(json.dumps(message))
            except Exception as e:
                logger.error(f"Erro ao enviar mensagem: {e}")
                self.connected = False
    
    async def _receive_loop(self):
        """Loop de recebimento de mensagens"""
        while self._running and self.websocket:
            try:
                message = await self.websocket.recv()
                data = json.loads(message)
                await self._handle_message(data)
            except websockets.exceptions.ConnectionClosed:
                logger.warning("Conexão WebSocket fechada")
                self.connected = False
                break
            except Exception as e:
                logger.error(f"Erro no loop de recebimento: {e}")
                
    async def _handle_message(self, data: dict):
        """Processa mensagens recebidas do gateway"""
        msg_type = data.get("type", "unknown")
        
        # Atualiza sessões e subagentes baseado nas mensagens
        if msg_type == "session_list":
            self.sessions = {s["id"]: s for s in data.get("sessions", [])}
        elif msg_type == "session_update":
            session_id = data.get("session_id")
            if session_id:
                self.sessions[session_id] = data.get("data", {})
        elif msg_type == "subagent_list":
            self.subagents = {s["id"]: s for s in data.get("subagents", [])}
        elif msg_type == "subagent_update":
            subagent_id = data.get("subagent_id")
            if data.get("status") == "stopped":
                self.subagents.pop(subagent_id, None)
            elif subagent_id:
                self.subagents[subagent_id] = data.get("data", {})
        elif msg_type == "subagent_created":
            subagent_id = data.get("subagent_id")
            if subagent_id:
                self.subagents[subagent_id] = data.get("data", {})
        
        # Notifica handlers registrados
        for handler in self.message_handlers:
            try:
                handler(data)
            except Exception as e:
                logger.error(f"Erro no handler: {e}")
    
    def add_message_handler(self, handler: Callable):
        """Registra um handler para mensagens"""
        self.message_handlers.append(handler)
    
    async def get_sessions(self) -> List[dict]:
        """Obtém lista de sessões ativas"""
        await self._send({"type": "get_sessions"})
        # Aguarda resposta (em uma implementação real, usaríamos um Future)
        await asyncio.sleep(0.5)
        return list(self.sessions.values())
    
    async def get_session(self, session_id: str) -> Optional[dict]:
        """Obtém detalhes de uma sessão específica"""
        await self._send({
            "type": "get_session",
            "session_id": session_id
        })
        await asyncio.sleep(0.5)
        return self.sessions.get(session_id)
    
    async def get_subagents(self) -> List[dict]:
        """Obtém lista de subagentes"""
        await self._send({"type": "get_subagents"})
        await asyncio.sleep(0.5)
        return list(self.subagents.values())
    
    async def create_subagent(self, task: str, label: str = None, model: str = None) -> dict:
        """Cria um novo subagente"""
        subagent_id = f"subagent-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{len(self.subagents)}"
        
        await self._send({
            "type": "spawn_subagent",
            "subagent_id": subagent_id,
            "task": task,
            "label": label or f"Subagente-{len(self.subagents) + 1}",
            "model": model or "default"
        })
        
        return {
            "id": subagent_id,
            "status": "spawning",
            "task": task,
            "label": label,
            "created_at": datetime.now().isoformat()
        }
    
    async def stop_subagent(self, subagent_id: str) -> bool:
        """Para um subagente"""
        await self._send({
            "type": "stop_subagent",
            "subagent_id": subagent_id
        })
        self.subagents.pop(subagent_id, None)
        return True
    
    async def get_system_status(self) -> dict:
        """Obtém status do sistema OpenClaw"""
        await self._send({"type": "get_status"})
        await asyncio.sleep(0.5)
        
        return {
            "connected": self.connected,
            "gateway_url": self.gateway_url,
            "active_sessions": len(self.sessions),
            "active_subagents": len(self.subagents),
            "timestamp": datetime.now().isoformat()
        }
    
    async def get_logs(self, limit: int = 100) -> List[dict]:
        """Obtém logs do sistema"""
        await self._send({
            "type": "get_logs",
            "limit": limit
        })
        await asyncio.sleep(0.5)
        return []  # Será preenchido via callback


# Singleton do cliente
_client: Optional[OpenClawClient] = None

async def get_openclaw_client() -> OpenClawClient:
    """Obtém instância singleton do cliente OpenClaw"""
    global _client
    if _client is None:
        _client = OpenClawClient()
        await _client.connect()
    return _client
