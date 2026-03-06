import asyncio
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx


@dataclass
class _LLMJob:
    messages: List[Dict[str, str]]
    temperature: float
    future: "asyncio.Future[Optional[str]]"


class LLMService:
    """
    Ollama ile konuşan, istekleri kuyruklayan ve donanımı koruyan servis.
    Tüm LLM çağrıları bu sınıf üzerinden geçer.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        max_concurrent: int = 1,
    ) -> None:
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip(
            "/"
        )
        self.model = model or os.getenv("OLLAMA_MODEL", "llama3.1")
        self.max_concurrent = max_concurrent

        self._queue: "asyncio.Queue[_LLMJob]" = asyncio.Queue()
        self._client: Optional[httpx.AsyncClient] = None
        self._workers: list[asyncio.Task[None]] = []
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        """
        HTTP istemcisini ve kuyruk tüketicilerini başlatır.
        """

        if self._client is not None:
            return

        timeout = httpx.Timeout(30.0, connect=10.0)
        self._client = httpx.AsyncClient(timeout=timeout)
        self._stop_event.clear()

        for _ in range(self.max_concurrent):
            worker = asyncio.create_task(self._worker_loop())
            self._workers.append(worker)

    async def stop(self) -> None:
        """
        Kuyruk tüketicilerini nazikçe durdurur.
        """

        self._stop_event.set()
        for _ in self._workers:
            await self._queue.put(
                _LLMJob(messages=[], temperature=0.0, future=asyncio.get_running_loop().create_future())
            )

        for worker in self._workers:
            worker.cancel()
        self._workers.clear()

        if self._client:
            await self._client.aclose()
            self._client = None

    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.8,
    ) -> Optional[str]:
        """
        Mesaj listesini Ollama'ya gönderir ve yanıt metnini döner.
        Gerçek HTTP çağrısı arka plandaki worker tarafından yapılır.
        """

        if self._client is None:
            await self.start()

        loop = asyncio.get_running_loop()
        fut: "asyncio.Future[Optional[str]]" = loop.create_future()
        job = _LLMJob(messages=messages, temperature=temperature, future=fut)
        await self._queue.put(job)
        return await fut

    async def _worker_loop(self) -> None:
        """
        Kuyruktan iş çekip Ollama'ya istek atan worker.
        """

        assert self._client is not None

        url = f"{self.base_url}/api/chat"

        while not self._stop_event.is_set():
            job = await self._queue.get()

            # Stop sinyali için boş mesajla sahte job gelebilir
            if not job.messages:
                if not job.future.done():
                    job.future.set_result(None)
                self._queue.task_done()
                continue

            payload: Dict[str, Any] = {
                "model": self.model,
                "messages": job.messages,
                "stream": False,
                "options": {"temperature": job.temperature},
            }

            try:
                resp = await self._client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                message = data.get("message") or {}
                content = message.get("content")
                if not content and isinstance(data, dict):
                    content = data.get("response")
                text = content.strip() if isinstance(content, str) else None
                if not job.future.done():
                    job.future.set_result(text)
            except Exception:
                if not job.future.done():
                    job.future.set_result(None)
            finally:
                self._queue.task_done()

