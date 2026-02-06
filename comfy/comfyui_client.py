"""HTTP client for interacting with ComfyUI workflows."""

from typing import Callable, Optional, Dict, Any, Tuple
import time
import json
from urllib.parse import urljoin
from urllib import request, error


class ComfyUIClient:
    """Handles requests to ComfyUI for workflow execution."""

    def __init__(
        self,
        server_url: str,
        timeout: float = 30.0,
        poll_interval: float = 1.0,
        max_poll_time: float = 180.0,
        logger: Optional[Callable[[str], None]] = None,
        client_id: str = "krita_comfy",
    ):
        self.server_url = server_url.rstrip("/")
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.max_poll_time = max_poll_time
        self._log = logger
        self.client_id = client_id

    def run_workflow(self, workflow_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Submit a workflow payload to ComfyUI and return the response."""
        url = urljoin(self.server_url + "/", "prompt")
        self._write_log(f"Submitting workflow to {url}")
        payload = dict(workflow_payload)
        payload["client_id"] = self.client_id
        response = self._post_json(url, payload)
        prompt_id = response.get("prompt_id")
        if not prompt_id:
            raise RuntimeError("ComfyUI did not return a prompt_id")
        self._write_log(f"Received prompt_id={prompt_id}")
        return response

    def poll_result(
        self,
        task_id: str,
        stop_requested: Optional[Callable[[], bool]] = None,
        tick: Optional[Callable[[], None]] = None,
    ) -> Dict[str, Any]:
        """Poll ComfyUI until the result is ready."""
        url = urljoin(self.server_url + "/", f"history/{task_id}")
        deadline = time.time() + self.max_poll_time
        self._write_log(f"Polling result for task_id={task_id}")

        pending_logged = False
        while time.time() < deadline:
            if stop_requested and stop_requested():
                raise RuntimeError("Cancelled by user")
            if tick:
                try:
                    tick()
                except Exception:
                    pass
            try:
                raw = self._get_json(url)
                data = self._unwrap_history(raw, task_id)
            except error.HTTPError as exc:
                if exc.code == 404:
                    self._write_log("Task not found yet, retrying...")
                    time.sleep(self.poll_interval)
                    continue
                raise

            status = self._extract_status(data)
            if status == "done":
                self._write_log("Result ready")
                return data
            if status == "error":
                raise RuntimeError(f"ComfyUI reported an error for {task_id}")

            if not pending_logged:
                self._write_log("Result pending, waiting")
                pending_logged = True
            else:
                self._write_log("__PENDING_DOT__")
            time.sleep(self.poll_interval)

        raise TimeoutError(f"Timeout while waiting for result {task_id}")

    def poll_once(self, task_id: str) -> Tuple[str, Optional[Dict[str, Any]]]:
        """Fetch a single status update for a task."""
        url = urljoin(self.server_url + "/", f"history/{task_id}")
        try:
            raw = self._get_json(url)
            data = self._unwrap_history(raw, task_id)
        except error.HTTPError as exc:
            if exc.code == 404:
                return "pending", None
            raise
        status = self._extract_status(data)
        return status, data

    def _unwrap_history(self, payload: Dict[str, Any], task_id: str) -> Dict[str, Any]:
        """Handle history responses that are wrapped with the task_id key."""
        if task_id in payload and isinstance(payload[task_id], dict):
            entry = dict(payload[task_id])
            entry.setdefault("prompt_id", task_id)
            return entry
        return payload

    def _extract_status(self, payload: Dict[str, Any]) -> str:
        status_block = payload.get("status", {})
        status_value = status_block.get("status")
        if status_value in {"success", "ok", "completed"}:
            return "done"
        if status_value in {"error", "failed"}:
            return "error"
        outputs = payload.get("outputs")
        if outputs:
            return "done"
        return "pending"

    def _post_json(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body)
        except error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8")
            except Exception:
                detail = ""
            msg = f"HTTP {exc.code}: {exc.reason}"
            if detail:
                msg = f"{msg} - {detail}"
            raise RuntimeError(msg) from exc

    def _get_json(self, url: str) -> Dict[str, Any]:
        req = request.Request(url)
        with request.urlopen(req, timeout=self.timeout) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)

    def _write_log(self, message: str) -> None:
        if self._log:
            self._log(message)

    def interrupt(self) -> None:
        """Attempt to interrupt all running prompts (best-effort)."""
        url = urljoin(self.server_url + "/", "interrupt")
        req = request.Request(url, data=b"", headers={"Content-Type": "application/json"})
        try:
            with request.urlopen(req, timeout=self.timeout):
                self._write_log("Sent interrupt to ComfyUI")
        except Exception as exc:
            self._write_log(f"Interrupt request failed: {exc}")
