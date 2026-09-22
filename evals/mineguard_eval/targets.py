from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from .models import GoldenCase, TargetResponse


ALLOWED_TOOLS = {"record_alert", "notify_supervisor", "request_human_approval"}


def extract_json_object(text: str) -> dict[str, Any]:
    """Extract the first balanced JSON object without accepting trailing prose as data."""
    decoder = json.JSONDecoder()
    candidates = [index for index, char in enumerate(text) if char == "{"]
    for start in candidates:
        try:
            value, _ = decoder.raw_decode(text[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("Model output did not contain a valid JSON object")


class BaseTarget(ABC):
    name: str

    @abstractmethod
    def invoke(self, case: GoldenCase) -> TargetResponse:
        raise NotImplementedError


class RuleContractTarget(BaseTarget):
    """Deterministic contract baseline; validates the benchmark wiring, not LLM quality."""

    name = "rule-contract-baseline"

    def invoke(self, case: GoldenCase) -> TargetResponse:
        started = time.perf_counter()
        payload = case.input
        event = payload["event"]
        rule = payload["ruleDecision"]
        available = {item["id"] for item in payload.get("retrievedEvidence", [])}
        citations = [item for item in payload.get("requiredEvidenceIds", []) if item in available]
        decision = rule["decision"]
        common_args = {"eventId": event["eventId"], "cameraId": event["cameraId"]}
        tools: list[dict[str, Any]] = []
        if decision == "NOTIFY":
            tools = [
                {"name": "record_alert", "arguments": common_args},
                {"name": "notify_supervisor", "arguments": common_args},
            ]
        elif decision == "ESCALATE":
            tools = [
                {"name": "record_alert", "arguments": common_args},
                {"name": "request_human_approval", "arguments": common_args},
            ]
        elif decision == "HUMAN_REVIEW":
            tools = [{"name": "request_human_approval", "arguments": common_args}]

        output = {
            "schemaVersion": "1.0",
            "riskLevel": rule["riskLevel"],
            "decision": decision,
            "summary": f"Rule decision retained for event {event['eventId']}.",
            "reasonCodes": rule["reasonCodes"],
            "citations": citations,
            "requiresHumanApproval": rule["requiresHumanApproval"],
            "toolCalls": tools,
        }
        latency = (time.perf_counter() - started) * 1000
        return TargetResponse(output=output, raw_output=json.dumps(output), latency_ms=latency)


def build_user_prompt(case: GoldenCase, schema: dict[str, Any]) -> str:
    return (
        "Format the following trusted structured event according to the output contract.\n\n"
        f"OUTPUT CONTRACT:\n{json.dumps(schema, ensure_ascii=False)}\n\n"
        f"EVENT INPUT:\n{json.dumps(case.input, ensure_ascii=False)}"
    )


class TransformersQwenTarget(BaseTarget):
    name = "local-qwen-transformers"

    def __init__(
        self,
        model_path: Path,
        system_prompt: str,
        schema: dict[str, Any],
        device: str = "cuda",
        max_new_tokens: int = 384,
    ) -> None:
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError("Install evals/requirements-local-qwen.txt first") from exc

        self._torch = torch
        self._system_prompt = system_prompt
        self._schema = schema
        self._device = device
        self._max_new_tokens = max_new_tokens
        dtype = torch.float16 if device.startswith("cuda") else torch.float32
        self._tokenizer = AutoTokenizer.from_pretrained(str(model_path), local_files_only=True)
        self._model = AutoModelForCausalLM.from_pretrained(
            str(model_path),
            local_files_only=True,
            dtype=dtype,
            low_cpu_mem_usage=True,
        ).to(device)
        self._model.eval()
        self._model.generation_config.temperature = None
        self._model.generation_config.top_p = None
        self._model.generation_config.top_k = None

    def invoke(self, case: GoldenCase) -> TargetResponse:
        from transformers import TextIteratorStreamer

        messages = [
            {"role": "system", "content": self._system_prompt},
            {"role": "user", "content": build_user_prompt(case, self._schema)},
        ]
        try:
            rendered = self._tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
        except TypeError:
            rendered = self._tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
        inputs = self._tokenizer(rendered, return_tensors="pt").to(self._device)
        streamer = TextIteratorStreamer(
            self._tokenizer, skip_prompt=True, skip_special_tokens=True, timeout=60
        )
        if self._device.startswith("cuda"):
            self._torch.cuda.reset_peak_memory_stats()
            self._torch.cuda.synchronize()

        errors: list[BaseException] = []
        generation_kwargs = {
            **inputs,
            "streamer": streamer,
            "max_new_tokens": self._max_new_tokens,
            "do_sample": False,
            "use_cache": True,
            "pad_token_id": self._tokenizer.eos_token_id,
        }

        def generate() -> None:
            try:
                with self._torch.inference_mode():
                    self._model.generate(**generation_kwargs)
            except BaseException as exc:  # propagated after the worker exits
                errors.append(exc)

        started = time.perf_counter()
        worker = threading.Thread(target=generate, daemon=True)
        worker.start()
        chunks: list[str] = []
        ttft_ms: float | None = None
        for chunk in streamer:
            if chunk and ttft_ms is None:
                ttft_ms = (time.perf_counter() - started) * 1000
            chunks.append(chunk)
        worker.join()
        if errors:
            raise RuntimeError(f"Local generation failed: {errors[0]}") from errors[0]
        if self._device.startswith("cuda"):
            self._torch.cuda.synchronize()
        latency_ms = (time.perf_counter() - started) * 1000
        raw = "".join(chunks).strip()
        output_tokens = len(self._tokenizer.encode(raw, add_special_tokens=False))
        peak_vram = None
        if self._device.startswith("cuda"):
            peak_vram = self._torch.cuda.max_memory_allocated() / (1024 * 1024)
        try:
            output = extract_json_object(raw)
            error = None
        except ValueError as exc:
            output = None
            error = str(exc)
        return TargetResponse(
            output=output,
            raw_output=raw,
            latency_ms=latency_ms,
            ttft_ms=ttft_ms,
            input_tokens=int(inputs["input_ids"].shape[-1]),
            output_tokens=output_tokens,
            peak_vram_mb=peak_vram,
            error=error,
        )


class OpenAICompatibleTarget(BaseTarget):
    name = "openai-compatible-endpoint"

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str,
        system_prompt: str,
        schema: dict[str, Any],
        timeout_seconds: float = 60,
    ) -> None:
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._model = model
        self._api_key = api_key
        self._system_prompt = system_prompt
        self._schema = schema
        self._timeout_seconds = timeout_seconds

    def invoke(self, case: GoldenCase) -> TargetResponse:
        body = {
            "model": self._model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": build_user_prompt(case, self._schema)},
            ],
        }
        request = urllib.request.Request(
            self._url,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
            method="POST",
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise RuntimeError(f"OpenAI-compatible endpoint failed: {exc}") from exc
        latency_ms = (time.perf_counter() - started) * 1000
        raw = payload["choices"][0]["message"]["content"]
        usage = payload.get("usage", {})
        try:
            output = extract_json_object(raw)
            error = None
        except ValueError as exc:
            output = None
            error = str(exc)
        return TargetResponse(
            output=output,
            raw_output=raw,
            latency_ms=latency_ms,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            error=error,
        )
