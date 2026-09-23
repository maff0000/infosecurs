#!/usr/bin/env python3
"""
Disposable stub OpenAI-compatible /v1/chat/completions server for the M002
Phase 3f audit's real-browser "Ask AI to review drafts" step.

Mimics ONLY what ai_platform/gateway.py's LiteLLMGateway.interpret() needs:
- POST /v1/chat/completions with {"model", "messages", "response_format"}
- messages[1] (the "user" message) content is:
    "Interpret the following ... \n\n" + json.dumps({"candidates": [...]})
- Response envelope: {"choices":[{"message":{"content": <JSON-encoded string>}}],
  "model": ..., "usage": {"prompt_tokens":..., "completion_tokens":...}}
- The message content string must itself be JSON matching
  ai_platform/interpretation_contracts.py's InterpretationResponse.from_response_dict:
    {"interpretations": [{"index":int,"suggested_impact":int,
      "suggested_likelihood":int,"rationale":str,"suggested_treatment":str,
      "clarification_questions":[],"priority_note":null}, ...],
     "additional_observations": []}
  with EXACTLY one interpretation per candidate index actually sent - no
  more, no fewer, no duplicates, no invented indices (from_response_dict
  enforces this and rejects the whole response otherwise).

Every response is logged to stub_log.jsonl (request candidates in, response
sent out) so the audit evidence can show the stub's exact behaviour and
reference it as the "faithful stand-in" record.
"""
from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

LOG_PATH = sys.argv[2] if len(sys.argv) > 2 else "stub_log.jsonl"
_log_lock = threading.Lock()


def _log(entry: dict) -> None:
    with _log_lock:
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")


class StubHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # quiet default stderr logging
        pass

    def do_POST(self):
        if self.path != "/v1/chat/completions":
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"not found")
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length)
        auth_header = self.headers.get("Authorization", "")

        try:
            body = json.loads(raw_body)
            messages = body["messages"]
            user_content = None
            for m in messages:
                if m.get("role") == "user":
                    user_content = m["content"]
                    break
            if user_content is None:
                raise ValueError("no user message found")

            # The user content is "<preamble text>\n\n<json>" - split on the
            # first "{" to recover the JSON payload robustly.
            json_start = user_content.index("{")
            candidates_payload = json.loads(user_content[json_start:])
            candidates = candidates_payload["candidates"]

            interpretations = []
            for c in candidates:
                idx = c["index"]
                cur_impact = c["current_impact"]
                cur_likelihood = c["current_likelihood"]
                # Visibly different from the deterministic starting point so
                # a before/after browser screenshot shows a real change -
                # bounded 1-5 per PID MIN_RATING/MAX_RATING.
                new_impact = cur_impact + 1 if cur_impact < 5 else cur_impact - 1
                new_likelihood = (
                    cur_likelihood + 1 if cur_likelihood < 5 else cur_likelihood - 1
                )
                interpretations.append(
                    {
                        "index": idx,
                        "suggested_impact": new_impact,
                        "suggested_likelihood": new_likelihood,
                        "rationale": (
                            f"[STUB] AI interpretation for '{c['title']}': "
                            f"exposure '{c['exposure']}' combined with threat "
                            f"event '{c['threat_event']}' on a "
                            f"{c['asset_category']} asset justifies adjusting "
                            f"impact to {new_impact} and likelihood to "
                            f"{new_likelihood}."
                        ),
                        "suggested_treatment": (
                            f"[STUB] Refined treatment for '{c['title']}': "
                            "prioritise remediation and document an owner and "
                            "target date."
                        ),
                        "clarification_questions": [],
                        "priority_note": None,
                    }
                )

            response_content_obj = {
                "interpretations": interpretations,
                "additional_observations": [
                    "[STUB] disposable audit stub - not a real model response"
                ],
            }

            envelope = {
                "id": "stub-chatcmpl-1",
                "object": "chat.completion",
                "model": body.get("model", "trinity-core"),
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(response_content_obj),
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": len(raw_body),
                    "completion_tokens": len(json.dumps(response_content_obj)),
                },
            }

            out = json.dumps(envelope).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

            _log(
                {
                    "auth_header_present": bool(auth_header),
                    "request_candidate_indices": [c["index"] for c in candidates],
                    "request_candidate_titles": [c["title"] for c in candidates],
                    "response_interpretation_indices": [
                        i["index"] for i in interpretations
                    ],
                    "response_envelope_shape": {
                        "choices[0].message.content": "JSON-encoded string",
                        "top_level_keys": list(envelope.keys()),
                    },
                }
            )
        except Exception as exc:  # noqa: BLE001 - stub: any failure -> 500 + log
            _log({"error": repr(exc), "raw_body": raw_body.decode("utf-8", "replace")})
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(exc).encode("utf-8"))


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    server = HTTPServer(("0.0.0.0", port), StubHandler)
    print(f"STUB_LISTENING_ON_PORT={server.server_address[1]}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
