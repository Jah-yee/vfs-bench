"""A completed agent loop does not imply that the upstream grader passed."""
import json
import os
import sys
import tempfile
import unittest
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "agent"))
import dataset  # noqa: E402
import dump  # noqa: E402
import grading  # noqa: E402
import run_agent  # noqa: E402
from agents.usage import Usage  # noqa: E402


class Outcome(unittest.IsolatedAsyncioTestCase):

    def test_deepseek_uses_native_thinking_requests(self):
        enabled = {"thinking": {"type": "enabled"}}
        for requested, native in (("low", "minimal"), ("medium", "high"),
                                  ("high", "high"), ("xhigh",
                                                     "high"), ("max", "max")):
            with self.subTest(requested=requested):
                self.assertEqual(
                    run_agent.reasoning_request("deepseek/deepseek-v4.1-flash",
                                                requested), {
                                                    "reasoning_effort": native,
                                                    "extra_body": enabled,
                                                })
        self.assertEqual(
            run_agent.reasoning_request("deepseek/deepseek-v4.1-flash",
                                        "none"),
            {"extra_body": {
                "thinking": {
                    "type": "disabled"
                }
            }})
        self.assertEqual(
            run_agent.reasoning_request("deepseek/deepseek-v4.1-flash",
                                        "default"), {})

    def test_other_reasoning_requests_are_unchanged(self):
        self.assertEqual(
            run_agent.reasoning_request("openai/gpt-5.6-luna", "medium"),
            {"reasoning_effort": "medium"})
        self.assertEqual(
            run_agent.reasoning_request("openai/gpt-5.6-luna", "none"),
            {"reasoning_effort": "none"})
        self.assertEqual(
            run_agent.reasoning_request("openai/gpt-5.6-luna", "max"),
            {"reasoning_effort": "max"})

    def test_gemini_asks_for_its_highest_thinking_level(self):
        for requested, sent in (("max", "high"), ("xhigh", "high"),
                                ("high", "high"), ("low", "low")):
            with self.subTest(requested=requested):
                self.assertEqual(
                    run_agent.reasoning_request("google/gemini-3.8-flash",
                                                requested),
                    {"reasoning_effort": sent})

    def test_atlas_caps_only_gemini_effort(self):
        # The Atlas loop hands the effort to LiteLLM, whose Gemini adapter
        # raises on `max`; every other model's is sent as asked.
        for model, requested, sent in (
            ("google/gemini-3.8-flash", "max", {
                "reasoning_effort": "high"
            }),
            ("google/gemini-3.8-flash", "medium", {
                "reasoning_effort": "medium"
            }),
            ("google/gemini-3.8-flash", "default", {}),
            ("openai/gpt-5.6-luna", "max", {
                "reasoning_effort": "max"
            }),
            ("deepseek/deepseek-v4.1-flash", "medium", {
                "reasoning_effort": "medium"
            }),
        ):
            with self.subTest(model=model, requested=requested):
                self.assertEqual(run_agent.atlas_effort(model, requested),
                                 sent)

    async def test_toolathlon_gemini_reaches_the_native_endpoint(self):
        """Only the gateway's spelling changes, never a call's arguments."""
        import gemini
        import httpx
        sent = {}

        def native(request):
            sent.update(json.loads(request.content))
            return httpx.Response(200,
                                  json={
                                      "candidates": [{
                                          "content": {
                                              "parts": [{
                                                  "functionCall": {
                                                      "name": "shell",
                                                      "args": {
                                                          "command": None
                                                      }
                                                  }
                                              }]
                                          },
                                          "safetyRatings": None
                                      }]
                                  })

        body = {
            "system_instruction": {
                "parts": [{
                    "text": "the workspace"
                }]
            },
            "generationConfig": {
                "max_output_tokens": 8,
                "thinkingConfig": {
                    "thinkingLevel": "high"
                }
            },
            "tools": [{
                "function_declarations": [{
                    "name": "shell"
                }]
            }],
            "contents": [{
                "parts": [{
                    "function_call": {
                        "name": "shell",
                        "args": {
                            "command": "print('a\\nb')"
                        }
                    }
                }]
            }],
        }
        transport = gemini.NativeGemini()
        transport.inner = httpx.MockTransport(native)
        response = await transport.handle_async_request(
            httpx.Request("POST", "https://gateway/v1/models/m:x", json=body))
        received = json.loads(await response.aread())

        self.assertIn("systemInstruction", sent)
        self.assertEqual(sent["generationConfig"], {
            "maxOutputTokens": 8,
            "thinkingConfig": {
                "thinkingLevel": "high"
            }
        })
        self.assertIn("functionDeclarations", sent["tools"][0])
        self.assertEqual(sent["contents"][0]["parts"][0]["functionCall"],
                         body["contents"][0]["parts"][0]["function_call"])
        self.assertNotIn("safetyRatings", received["candidates"][0])
        self.assertEqual(
            received["candidates"][0]["content"]["parts"][0]["functionCall"], {
                "name": "shell",
                "args": {
                    "command": None
                }
            })
        transport.inner = httpx.MockTransport(lambda request: self.fail(
            "a request the gateway would misread was sent"))
        with self.assertRaises(ValueError):
            await transport.handle_async_request(
                httpx.Request(
                    "POST",
                    "https://gateway/v1/models/m:x",
                    json={"contents": [{
                        "parts": [{
                            "inline_data": {}
                        }]
                    }]}))

    def test_toolathlon_gemini_client_rides_the_settings(self):
        """The SDK copies and serialises its settings; the client survives."""
        import copy

        import gemini
        from agents import ModelSettings
        with patch.dict(os.environ, {"LITELLM_LOCAL_MODEL_COST_MAP": "True"}):
            model, handler = gemini.native_model("google/gemini-3.8-flash",
                                                 "https://gateway/v1", "key",
                                                 60,
                                                 run_agent.UpstreamToolNames)
        settings = ModelSettings(extra_args={"client": handler})
        self.assertEqual(model.model, "gemini/google/gemini-3.8-flash")
        self.assertIs(copy.deepcopy(settings).extra_args["client"], handler)
        self.assertEqual(settings.to_json_dict()["extra_args"],
                         {"client": "native Gemini"})
        self.assertIsInstance(handler.client._transport, gemini.NativeGemini)

    async def test_a_toolathlon_gemini_request_reaches_generate_content(self):
        """One SDK request, through the runner's own model and settings."""
        import gemini
        import httpx
        import litellm
        from agents import ModelSettings, ModelTracing
        asked = []

        def native(request):
            asked.append(request)
            return httpx.Response(200,
                                  json={
                                      "candidates": [{
                                          "content": {
                                              "role": "model",
                                              "parts": [{
                                                  "text": "done"
                                              }]
                                          },
                                          "finishReason": "STOP"
                                      }],
                                      "usageMetadata": {
                                          "promptTokenCount": 3,
                                          "candidatesTokenCount": 1,
                                          "totalTokenCount": 4
                                      }
                                  })

        # The model's capabilities as LiteLLM's live table lists them, which
        # the runner reads on import; the copy packed into the locked release
        # predates the model and would refuse its `reasoning_effort`.
        listed = {
            "litellm_provider": "gemini",
            "mode": "chat",
            "supports_function_calling": True,
            "supports_reasoning": True,
            "supports_system_messages": True,
        }
        with patch.dict(os.environ,
                        {"LITELLM_LOCAL_MODEL_COST_MAP": "True"}), patch.dict(
                            litellm.model_cost,
                            {"gemini/google/gemini-3.8-flash": listed}):
            model, handler = gemini.native_model("google/gemini-3.8-flash",
                                                 "https://gateway/v1", "key",
                                                 60,
                                                 run_agent.UpstreamToolNames)
            handler.client._transport.inner = httpx.MockTransport(native)
            reasoning = run_agent.reasoning_request("google/gemini-3.8-flash",
                                                    "max")
            await model.get_response(system_instructions="the workspace",
                                     input="hi",
                                     model_settings=ModelSettings(
                                         max_tokens=64,
                                         extra_args={
                                             **reasoning, "client": handler
                                         }),
                                     tools=[],
                                     output_schema=None,
                                     handoffs=[],
                                     tracing=ModelTracing.DISABLED)
            await handler.client.aclose()

        (request, ) = asked
        body = json.loads(request.content)
        self.assertEqual(request.url.path,
                         "/v1/models/google/gemini-3.8-flash:generateContent")
        self.assertEqual(
            body["generationConfig"]["thinkingConfig"]["thinkingLevel"],
            "high")
        self.assertEqual(body["generationConfig"]["maxOutputTokens"], 64)
        self.assertEqual(body["systemInstruction"],
                         {"parts": [{
                             "text": "the workspace"
                         }]})

    async def test_a_toolathlon_claude_turn_goes_back_whole(self):
        """A turn's two calls return as one turn, its thinking still on it."""
        import claude
        import httpx
        from agents import ModelSettings, ModelTracing, function_tool
        from litellm.llms.custom_httpx.http_handler import AsyncHTTPHandler
        from openai.types.shared import Reasoning
        from pydantic_core import SchemaSerializer, core_schema
        asked = []

        def messages(request):
            asked.append(json.loads(request.content))
            return httpx.Response(200,
                                  json={
                                      "id":
                                      "msg_1",
                                      "type":
                                      "message",
                                      "role":
                                      "assistant",
                                      "model":
                                      "claude-haiku-5-5",
                                      "content": [{
                                          "type": "thinking",
                                          "thinking": "",
                                          "signature": "signed"
                                      }, {
                                          "type": "tool_use",
                                          "id": "toolu_a",
                                          "name": "shell",
                                          "input": {
                                              "command": "ls"
                                          }
                                      }, {
                                          "type": "tool_use",
                                          "id": "toolu_b",
                                          "name": "shell",
                                          "input": {
                                              "command": "pwd"
                                          }
                                      }],
                                      "stop_reason":
                                      "tool_use",
                                      "stop_sequence":
                                      None,
                                      "usage": {
                                          "input_tokens": 3,
                                          "output_tokens": 1
                                      }
                                  })

        class Handler(AsyncHTTPHandler):
            __pydantic_serializer__ = SchemaSerializer(
                core_schema.any_schema(
                    serialization=core_schema.
                    plain_serializer_function_ser_schema(lambda _: "mock")))

            def __deepcopy__(self, memo):
                return self

        @function_tool
        def shell(command: str) -> str:
            """Run a command."""
            return command

        with patch.dict(os.environ, {"LITELLM_LOCAL_MODEL_COST_MAP": "True"}):
            model, _ = claude.claude_model("anthropic/claude-haiku-5-5",
                                           "https://api.anthropic.com", "key",
                                           httpx.Timeout(600),
                                           run_agent.UpstreamModel)
        handler = Handler()
        handler.client = httpx.AsyncClient(
            transport=httpx.MockTransport(messages))
        settings = ModelSettings(max_tokens=64,
                                 parallel_tool_calls=True,
                                 reasoning=Reasoning(effort="max"),
                                 extra_args={"client": handler})
        asks = dict(system_instructions="the workspace",
                    model_settings=settings,
                    tools=[shell],
                    output_schema=None,
                    handoffs=[],
                    tracing=ModelTracing.DISABLED)
        first = await model.get_response(input="hi", **asks)
        await model.get_response(input=[{
            "role": "user",
            "content": "hi"
        }, *first.to_input_items(), *({
            "type": "function_call_output",
            "call_id": call,
            "output": call
        } for call in ("toolu_a", "toolu_b"))],
                                 **asks)
        await handler.client.aclose()

        sent, replayed = asked
        self.assertEqual(sent["thinking"], {"type": "adaptive"})
        self.assertEqual(sent["output_config"], {"effort": "max"})
        turn, results = replayed["messages"][1:]
        self.assertEqual(turn["content"][0], {
            "type": "thinking",
            "thinking": "",
            "signature": "signed"
        })
        self.assertEqual([block.get("id") for block in turn["content"][1:]],
                         ["toolu_a", "toolu_b"])
        self.assertEqual(
            [block["tool_use_id"] for block in results["content"]],
            ["toolu_a", "toolu_b"])

    def test_dump_retains_requested_deepseek_effort(self):
        args = SimpleNamespace(model="deepseek/deepseek-v4.1-flash",
                               base_url="https://llm.onerouter.pro/v1",
                               api_key_env="INFRON_API_KEY",
                               tools="vfs",
                               loop="agents",
                               reasoning_effort="medium",
                               max_turns=200,
                               max_tokens=4096,
                               parallel_tool_calls=True)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            dump.write_dump(path, args,
                            REPO / "task/toolathlon/wandb-best-score",
                            "completed", "done", Usage(), [], [])
            record = json.loads(path.read_text())
        self.assertEqual(record["reasoning_effort"], "medium")

    async def test_each_loop_propagates_failed_grade(self):
        for name, loop in (("toolathlon/wandb-best-score", "agents"),
                           ("mcpatlas/fantasy-sports-average", "atlas")):
            dataset.use(name.split("/")[0])
            task = REPO / "task" / name
            for code in (0, 1):
                with self.subTest(loop=loop, grade=code), \
                        tempfile.TemporaryDirectory() as tmp, \
                        ExitStack() as patches, redirect_stdout(StringIO()):
                    patches.enter_context(
                        patch.dict(os.environ, INFRON_API_KEY="fixture"))
                    patches.enter_context(
                        patch.object(sys, "argv", [
                            "run_agent.py", name, "--dump",
                            str(Path(tmp) / "run.json")
                        ]))
                    patches.enter_context(
                        patch.object(run_agent,
                                     "resolve_task",
                                     return_value=task))
                    patches.enter_context(
                        patch.object(run_agent, "load_stack_env"))
                    patches.enter_context(
                        patch.object(run_agent, "seed", return_value=0))
                    active = []

                    def grade(*args):
                        self.assertEqual(active, [True])
                        return code

                    patches.enter_context(
                        patch.object(run_agent, "grade", side_effect=grade))
                    patches.enter_context(
                        patch.object(run_agent,
                                     "workspaces_dir",
                                     return_value=Path(tmp)))
                    patches.enter_context(
                        patch.object(run_agent, "AsyncOpenAI"))
                    patches.enter_context(patch.object(run_agent, "Agent"))
                    patches.enter_context(
                        patch.object(run_agent, "OpenAIChatCompletionsModel"))

                    async def build_arm(args, task, stack, *rest):
                        active.append(True)
                        stack.callback(active.clear)
                        return {
                            "name": "fixture",
                            "instructions": "",
                            "tools": []
                        }

                    patches.enter_context(
                        patch.object(run_agent, "build_arm", build_arm))
                    drawn = {
                        "status": "completed",
                        "final_output": "done",
                        "items": [],
                        "usage": Usage(),
                        "tool_calls": []
                    }
                    patches.enter_context(
                        patch.object(run_agent.atlas, "serve",
                                     AsyncMock(return_value=("app", []))))
                    patches.enter_context(
                        patch.object(run_agent.atlas, "run",
                                     AsyncMock(return_value=drawn)))
                    result = SimpleNamespace(
                        final_output="done",
                        new_items=[],
                        context_wrapper=SimpleNamespace(usage=Usage()))
                    patches.enter_context(
                        patch.object(run_agent.Runner, "run",
                                     AsyncMock(return_value=result)))
                    self.assertEqual(await run_agent.main(), code)
                    self.assertEqual(active, [])
                    record = json.loads((Path(tmp) / "run.json").read_text())
                    self.assertEqual(record["loop"], loop)
                    if loop == "agents":
                        self.assertIn("submodule/mirage",
                                      record["provenance"]["git"])
                        self.assertIn("vendor/wandb-mcp/uv.lock",
                                      record["provenance"]["sha256"])

    def test_evaluator_result_is_preserved_in_dump(self):
        dataset.use("toolathlon")
        task = REPO / "task/toolathlon/wandb-best-score"
        for code in (0, 1):
            with self.subTest(
                    grade=code), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "run.json"
                path.write_text('{"status":"completed","items":[]}')
                evaluator = SimpleNamespace(
                    digest=lambda _: "fixture-sha",
                    main=lambda _: code,
                )
                with patch.object(grading,
                                  "entrypoint",
                                  return_value=evaluator), redirect_stdout(
                                      StringIO()):
                    self.assertEqual(grading.grade(task, path), code)
                record = json.loads(path.read_text())
                self.assertEqual(record["status"], "completed")
                self.assertEqual(
                    record["evaluation"], {
                        "evaluator_sha": "fixture-sha",
                        "exit_code": code,
                        "run_status": "completed"
                    })

    def test_a_run_that_did_not_finish_is_not_graded(self):
        """Upstream reports `pass: None` for those; the evaluator never runs.

        `TaskEvaluator.evaluate_one` refuses a run whose status is not
        `SUCCESS` before it builds the evaluator command, so a timed-out
        arm is never measured against a fixture it did not finish
        changing. A grader run there scores whatever the arm left
        half-done, which is neither the answer nor a wrong answer.
        """
        dataset.use("toolathlon")
        task = REPO / "task/toolathlon/wandb-best-score"
        for status in ("WallClockExceeded", "MaxTurnsExceeded"):
            with self.subTest(status=status), \
                    tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "run.json"
                path.write_text(json.dumps({"status": status, "items": []}))
                called = []
                evaluator = SimpleNamespace(
                    digest=lambda _: "fixture-sha",
                    main=lambda argv: called.append(argv) or 0,
                )
                with patch.object(grading,
                                  "entrypoint",
                                  return_value=evaluator), redirect_stdout(
                                      StringIO()):
                    self.assertEqual(grading.grade(task, path), 1)
                self.assertEqual(called, [],
                                 "the evaluator ran for an unfinished run")
                record = json.loads(path.read_text())
                self.assertEqual(record["evaluation"], {
                    "evaluator_sha": None,
                    "exit_code": None,
                    "run_status": status
                })

    def test_a_dataset_whose_upstream_has_no_gate_still_grades(self):
        """Atlas scores the last thing the agent said, finished or not.

        `run_eval.py:186` walks the trajectory back to the last assistant
        message with content and scores that against the row's claims. It
        has no notion of a run status -- even a timeout is kept as a row --
        so a turn-limited run that still answered has an answer to grade.
        Toolathlon's `pass: None` is Toolathlon's rule, and applying it
        here would discard that answer.
        """
        dataset.use("mcpatlas")
        task = REPO / "task/mcpatlas/fantasy-sports-average"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            path.write_text(
                json.dumps({
                    "status": "MaxTurnsExceeded",
                    "items": []
                }))
            called = []
            evaluator = SimpleNamespace(
                digest=lambda _: "fixture-sha",
                main=lambda argv: called.append(argv) or 0,
            )
            with patch.object(grading, "entrypoint",
                              return_value=evaluator), redirect_stdout(
                                  StringIO()):
                self.assertEqual(grading.grade(task, path), 0)
            self.assertEqual(
                len(called), 1,
                "the evaluator was skipped for an unfinished run")
            record = json.loads(path.read_text())
            self.assertEqual(
                record["evaluation"], {
                    "evaluator_sha": "fixture-sha",
                    "exit_code": 0,
                    "run_status": "MaxTurnsExceeded"
                }, "a graded run was written down as having finished")

    def test_the_judge_is_asked_on_the_runs_own_key(self):
        """A run drawn on `--api-key-env`'s key is graded on that key too.

        The Atlas grader reaches its judge through the gateway the run used,
        and it used to send `INFRON_API_KEY` whatever the run had chosen: a
        `KeyError` after a finished run where that was unset, the wrong key
        where it was set.
        """
        dataset.use("mcpatlas")
        task = REPO / "task/mcpatlas/fantasy-sports-average"
        grader = grading.entrypoint(task.parent / "script" / "grade_task.py")
        answered = SimpleNamespace(returncode=0,
                                   stdout=json.dumps({
                                       "coverage_score": 1.0,
                                       "per_claim": []
                                   }),
                                   stderr="")
        args = SimpleNamespace(model="openai/gpt-5.6-luna",
                               base_url="https://llm.onerouter.pro/v1",
                               api_key_env="OTHER_GATEWAY_KEY",
                               tools="vfs",
                               loop="atlas",
                               reasoning_effort="medium",
                               max_turns=20,
                               max_tokens=None,
                               parallel_tool_calls=None)
        other = {"OTHER_GATEWAY_KEY": "other"}
        # Whether the dump names the variable, what is set beside the
        # default, and what grading then sends and answers.
        cases = (
            (True, other, ["other"], 0),
            (False, other, ["default"], 0),
            (True, {}, [], 2),
        )
        for recorded, extra, sent, code in cases:
            with self.subTest(recorded=recorded, extra=sorted(extra)), \
                    tempfile.TemporaryDirectory() as tmp, \
                    patch.dict(os.environ, INFRON_API_KEY="default"), \
                    redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                os.environ.pop("OTHER_GATEWAY_KEY", None)
                os.environ.update(extra)
                path = Path(tmp) / "run.json"
                dump.write_dump(path, args, task, "completed", "done", Usage(),
                                [], [])
                record = json.loads(path.read_text())
                self.assertEqual(record["api_key_env"], "OTHER_GATEWAY_KEY")
                if not recorded:
                    # A dump written before the variable was.
                    del record["api_key_env"]
                    path.write_text(json.dumps(record))
                sends = []

                def scorer(argv, **kwargs):
                    sends.append(kwargs["env"]["EVAL_LLM_API_KEY"])
                    return answered

                with patch.object(grader.subprocess, "run", scorer):
                    self.assertEqual(
                        grader.main([task.name, "--dump",
                                     str(path)]), code)
                self.assertEqual(sends, sent)

    def test_a_claude_run_is_judged_on_the_gateway(self):
        """Anthropic's API serves no judge, so the gateway judges the run."""
        dataset.use("mcpatlas")
        task = REPO / "task/mcpatlas/fantasy-sports-average"
        grader = grading.entrypoint(task.parent / "script" / "grade_task.py")
        answered = SimpleNamespace(returncode=0,
                                   stdout=json.dumps({
                                       "coverage_score": 1.0,
                                       "per_claim": []
                                   }),
                                   stderr="")
        args = SimpleNamespace(model="anthropic/claude-haiku-5-5",
                               base_url="https://api.anthropic.com",
                               api_key_env="ANTHROPIC_API_KEY",
                               tools="vfs",
                               loop="atlas",
                               reasoning_effort="max",
                               max_turns=20,
                               max_tokens=None,
                               parallel_tool_calls=None)
        with tempfile.TemporaryDirectory() as tmp, \
                patch.dict(os.environ, INFRON_API_KEY="default",
                           ANTHROPIC_API_KEY="anthropic"), \
                redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            path = Path(tmp) / "run.json"
            dump.write_dump(path, args, task, "completed", "done", Usage(), [],
                            [])
            sends = []

            def scorer(argv, **kwargs):
                sends.append((kwargs["env"]["EVAL_LLM_BASE_URL"],
                              kwargs["env"]["EVAL_LLM_API_KEY"]))
                return answered

            with patch.object(grader.subprocess, "run", scorer):
                self.assertEqual(grader.main([task.name, "--dump",
                                              str(path)]), 0)
            self.assertEqual(sends,
                             [(grader.GATEWAY.removesuffix("/v1"), "default")])
            judge = json.loads(path.read_text())["judge"]
            self.assertEqual((judge["base_url"], judge["api_key_env"]),
                             (grader.GATEWAY, "INFRON_API_KEY"))

    async def test_claude_is_asked_on_anthropics_api(self):
        """Address, key, timeout, effort, tools and turns reach LiteLLM."""
        from atlas import gateway
        from openai import AsyncOpenAI
        client = AsyncOpenAI(base_url="https://api.anthropic.com/",
                             api_key="anthropic",
                             timeout=30)
        messages = [{
            "role": "user",
            "content": "the task"
        }, {
            "role":
            "assistant",
            "tool_calls": [{
                "id": "c1",
                "type": "function",
                "function": {
                    "name": "shell",
                    "arguments": "{\"command\": \"ls /\"}"
                }
            }]
        }, {
            "role": "tool",
            "tool_call_id": "c1",
            "content": "data"
        }]
        tools = [{"type": "function", "function": {"name": "shell"}}]
        completion = AsyncMock(return_value="reply")
        with patch("litellm.acompletion", completion):
            self.assertEqual(
                await
                gateway.ask(client, "anthropic/claude-haiku-5-5", messages,
                            tools, {"reasoning_effort": "max"}), "reply")
        completion.assert_awaited_once_with(
            model="anthropic/claude-haiku-5-5",
            api_base="https://api.anthropic.com",
            api_key="anthropic",
            messages=messages,
            tools=tools,
            timeout=30,
            reasoning_effort="max")

    def test_dump_keeps_the_reasoning_share(self):
        """The completion count includes thinking; the dump says how much."""
        from agents.usage import (InputTokensDetails, OutputTokensDetails,
                                  RequestUsage)
        entry = RequestUsage(
            input_tokens=24,
            output_tokens=79,
            total_tokens=103,
            input_tokens_details=InputTokensDetails(cached_tokens=0,
                                                    cache_write_tokens=0),
            output_tokens_details=OutputTokensDetails(reasoning_tokens=72))
        usage = Usage(
            requests=1,
            input_tokens=24,
            output_tokens=79,
            total_tokens=103,
            output_tokens_details=OutputTokensDetails(reasoning_tokens=72),
            request_usage_entries=[entry])
        block = dump.token_usage(usage)
        self.assertEqual(
            block["output_tokens"], 79,
            "the total must stay the provider's completion count")
        self.assertEqual(block["reasoning_tokens"], 72)
        self.assertEqual(block["per_request"][0]["reasoning_tokens"], 72)

    def test_raw_loops_carry_the_reasoning_share(self):
        """Atlas reads reasoning tokens from the provider usage block."""
        from atlas import gateway
        from openai.types.completion_usage import (CompletionTokensDetails,
                                                   CompletionUsage)
        response = SimpleNamespace(usage=CompletionUsage(
            prompt_tokens=22,
            completion_tokens=346,
            total_tokens=368,
            completion_tokens_details=CompletionTokensDetails(
                reasoning_tokens=344)))
        usage = gateway.usage_of(response)
        self.assertEqual(usage.output_tokens, 346)
        self.assertEqual(usage.output_tokens_details.reasoning_tokens, 344)

    async def test_gemini_reaches_the_gateway_in_its_spelling(self):
        """Only the gateway's spelling changes, never a tool's or a call's."""
        import httpx
        from atlas import gateway
        sent = {}

        def native(request):
            sent.update(json.loads(request.content))
            return httpx.Response(200,
                                  json={
                                      "candidates": [{
                                          "content": {
                                              "parts": [{
                                                  "functionCall": {
                                                      "name": "scrape",
                                                      "args": {
                                                          "render": None
                                                      }
                                                  }
                                              }]
                                          },
                                          "safetyRatings": None
                                      }],
                                      "usageMetadata": {
                                          "cacheTokensDetails": None
                                      }
                                  })

        schema = {"properties": {"output_format": {"enum": [None, "md"]}}}
        body = {
            "system_instruction": {
                "parts": [{
                    "text": "the workspace"
                }]
            },
            "tools": [{
                "function_declarations": [{
                    "name": "scrape",
                    "parameters": schema
                }]
            }],
            "contents": [{
                "parts": [{
                    "function_call": {
                        "name": "scrape",
                        "args": {}
                    }
                }]
            }, {
                "parts": [{
                    "function_response": {
                        "name": "scrape",
                        "response": {}
                    }
                }]
            }],
        }
        transport = gateway.GeminiTransport()
        transport.inner = httpx.MockTransport(native)
        response = await transport.handle_async_request(
            httpx.Request("POST", "https://gateway/v1/models/m:x", json=body))
        received = json.loads(await response.aread())

        self.assertEqual(sent["systemInstruction"],
                         {"parts": [{
                             "text": "the workspace"
                         }]})
        self.assertEqual(
            sent["tools"][0]["functionDeclarations"][0]["parameters"], schema)
        self.assertIn("functionCall", sent["contents"][0]["parts"][0])
        self.assertIn("functionResponse", sent["contents"][1]["parts"][0])
        self.assertEqual(received["usageMetadata"], {})
        self.assertNotIn("safetyRatings", received["candidates"][0])
        self.assertEqual(
            received["candidates"][0]["content"]["parts"][0]["functionCall"], {
                "name": "scrape",
                "args": {
                    "render": None
                }
            })

    async def test_a_field_the_gateway_cannot_read_fails_the_request(self):
        """The gateway drops such a field silently, so it must not reach it."""
        import httpx
        from atlas import gateway
        transport = gateway.GeminiTransport()
        transport.inner = httpx.MockTransport(lambda request: self.fail(
            "a request the gateway would misread was sent"))
        for body in ({
                "generationConfig": {
                    "max_output_tokens": 8
                }
        }, {
                "contents": [{
                    "parts": [{
                        "inline_data": {}
                    }]
                }]
        }):
            with self.subTest(body=body), self.assertRaises(ValueError):
                await transport.handle_async_request(
                    httpx.Request("POST",
                                  "https://gateway/v1/models/m:x",
                                  json=body))

    async def test_upstreams_harness_answers_as_upstreams_does(self):
        """What the model reads back is the harness's and the app's text.

        Upstream's own TypeScript harness, driven against a stand-in for its
        app and a stand-in model: an empty result reads `success`, arguments
        that do not parse read V8's own error, the app's error body reaches
        the model whole, and each call that reached the app is timed.
        """
        import shutil

        from atlas import constants, harness, serving
        from openai.types.chat import ChatCompletion
        from starlette.applications import Starlette
        from starlette.responses import JSONResponse
        from starlette.routing import Route

        if not (constants.HARNESS_DIR / "node_modules").is_dir():
            self.skipTest(f"no harness installed; {constants.SETUP}")
        if shutil.which("node") is None:
            self.skipTest("no node")

        async def listed(request):
            return JSONResponse([{
                "name": "shell",
                "description": "run",
                "inputSchema": {
                    "type": "object"
                }
            }])

        async def called(request):
            asked = (await request.json())["tool_args"]["command"]
            if asked == "fail":
                return JSONResponse(
                    {"detail": "Failed to call tool 'shell': no"},
                    status_code=500)
            return JSONResponse([{
                "type": "text",
                "text": "" if asked == "true" else "hi"
            }])

        async def healthy(request):
            return JSONResponse({"message": "MCP Agent Environment API"})

        app = Starlette(routes=[
            Route("/", healthy),
            Route("/list-tools", listed, methods=["POST"]),
            Route("/call-tool", called, methods=["POST"]),
        ])
        script = [[("echo hi", '{"command": "echo hi"}')],
                  [("true", '{"command": "true"}')],
                  [("broken", '{"command": ')],
                  [("fail", '{"command": "fail"}')], []]
        sent = []

        async def create(model, messages, tools, **extra):
            sent.append((messages, tools, extra))
            calls = script[len(sent) - 1]
            message = {
                "role": "assistant",
                "content": None if calls else "done"
            }
            if calls:
                message["tool_calls"] = [{
                    "id": f"call-{name}",
                    "type": "function",
                    "function": {
                        "name": "shell",
                        "arguments": arguments
                    }
                } for name, arguments in calls]
            return ChatCompletion.model_validate({
                "id":
                "r",
                "object":
                "chat.completion",
                "created":
                0,
                "model":
                model,
                "choices": [{
                    "index": 0,
                    "finish_reason": "tool_calls" if calls else "stop",
                    "message": message
                }],
                "usage": {
                    "prompt_tokens": 3,
                    "completion_tokens": 1,
                    "total_tokens": 4
                }
            })

        client = SimpleNamespace(chat=SimpleNamespace(
            completions=SimpleNamespace(create=create)))
        from contextlib import AsyncExitStack
        with tempfile.TemporaryDirectory() as tmp, \
                redirect_stderr(StringIO()):
            async with AsyncExitStack() as stack:
                sandbox = await serving.listen(app, stack)
                drawn = await harness.run(client,
                                          "stub/model", [{
                                              "role": "user",
                                              "content": "task"
                                          }], ["shell"],
                                          sandbox,
                                          task_id="t",
                                          extra={},
                                          max_turns=256,
                                          timeout=120,
                                          logs=Path(tmp))
        told = {
            item["tool_call_id"]: item["content"][0]["text"]
            for item in drawn["items"] if item["role"] == "tool"
        }
        self.assertEqual(
            told, {
                "call-echo hi": "hi",
                "call-true": "success",
                "call-broken": "Error: Unexpected end of JSON input",
                "call-fail": '{"detail":"Failed to call tool \'shell\': no"}',
            })
        self.assertEqual((drawn["status"], drawn["final_output"]),
                         ("completed", "done"))
        self.assertEqual([call["id"] for call in drawn["tool_calls"]],
                         ["call-echo hi", "call-true", "call-fail"])
        self.assertEqual(drawn["usage"].requests, 5)
        self.assertEqual(sent[0][1], [{
            "type": "function",
            "function": {
                "name": "shell",
                "description": "run",
                "parameters": {
                    "type": "object"
                },
                "strict": False
            }
        }])
        self.assertEqual(sent[0][2], {})

    async def test_a_cut_off_run_keeps_what_the_app_answered(self):
        """A result the harness never passed on is still in the dump.

        The deadline falls while the model is thinking about a tool result,
        so the transcript ends at the call, and the app's answer to it is
        kept beside it.
        """
        import asyncio
        import shutil
        from contextlib import AsyncExitStack

        from atlas import constants, harness, serving
        from openai.types.chat import ChatCompletion
        from starlette.applications import Starlette
        from starlette.responses import JSONResponse
        from starlette.routing import Route

        if not (constants.HARNESS_DIR / "node_modules").is_dir():
            self.skipTest(f"no harness installed; {constants.SETUP}")
        if shutil.which("node") is None:
            self.skipTest("no node")

        async def listed(request):
            return JSONResponse([{
                "name": "shell",
                "description": "run",
                "inputSchema": {
                    "type": "object"
                }
            }])

        async def called(request):
            return JSONResponse([{"type": "text", "text": "hi"}])

        async def healthy(request):
            return JSONResponse({})

        app = Starlette(routes=[
            Route("/", healthy),
            Route("/list-tools", listed, methods=["POST"]),
            Route("/call-tool", called, methods=["POST"]),
        ])
        asked = []

        async def create(model, messages, tools, **extra):
            asked.append(messages)
            if len(asked) > 1:
                await asyncio.sleep(60)
            return ChatCompletion.model_validate({
                "id":
                "r",
                "object":
                "chat.completion",
                "created":
                0,
                "model":
                model,
                "choices": [{
                    "index": 0,
                    "finish_reason": "tool_calls",
                    "message": {
                        "role":
                        "assistant",
                        "tool_calls": [{
                            "id": "call-1",
                            "type": "function",
                            "function": {
                                "name": "shell",
                                "arguments": "{}"
                            }
                        }]
                    }
                }]
            })

        client = SimpleNamespace(chat=SimpleNamespace(
            completions=SimpleNamespace(create=create)))
        with tempfile.TemporaryDirectory() as tmp, \
                redirect_stderr(StringIO()):
            async with AsyncExitStack() as stack:
                sandbox = await serving.listen(app, stack)
                drawn = await harness.run(client,
                                          "stub/model", [{
                                              "role": "user",
                                              "content": "task"
                                          }], ["shell"],
                                          sandbox,
                                          task_id="t",
                                          extra={},
                                          max_turns=256,
                                          timeout=10,
                                          logs=Path(tmp))
        self.assertEqual(drawn["status"], "WallClockExceeded")
        self.assertEqual([item["role"] for item in drawn["items"]],
                         ["user", "assistant"])
        (call, ) = drawn["tool_calls"]
        self.assertEqual((call["id"], call["answer"]["status"]),
                         ("call-1", 200))
        self.assertEqual(json.loads(call["answer"]["body"]), [{
            "type": "text",
            "text": "hi"
        }])

    async def test_a_long_shell_output_is_cut_only_where_upstream_cuts_it(
            self):
        """Toolathlon cuts and saves a long result; Atlas passes it whole."""
        import arms
        long = "x" * (arms.MAX_TOOL_OUTPUT + 1)

        class Workspace:

            async def execute_result_async(self, command, cwd=None):
                return {"stdout": long, "stderr": ""}

            async def save_overflow(self, text):
                return "saved"

        def whole(task, command, stdout, stderr):
            return stdout

        for name, told in (("toolathlon", "saved"), ("mcpatlas", long)):
            with self.subTest(dataset=name), patch.object(dataset.use(name),
                                                          "shell_output",
                                                          whole,
                                                          create=True):
                shell = arms.make_ts_shell(Workspace(), [], "a-task")
                self.assertEqual(await shell("find /data -type f"), told)

    async def test_a_failed_command_says_so_where_upstream_says_it(self):
        """Atlas's shell ends a failure with `cli-mcp-server`'s status line.

        A `grep` with no match prints nothing and exits 1, and an empty reply
        reached the model as the harness's `success`. A success answers as it
        did, and Toolathlon's shell is not changed.
        """
        import arms

        class Workspace:

            def __init__(self, stdout, code):
                self.result = {
                    "stdout": stdout,
                    "stderr": "",
                    "exit_code": code
                }

            async def execute_result_async(self, command, cwd=None):
                return self.result

        failed = "\nCommand completed with return code: 1"
        for name, told in (("toolathlon", ("", "hi\n")), ("mcpatlas",
                                                          (failed, "hi\n"))):
            with self.subTest(dataset=name):
                dataset.use(name)
                log = []
                silent = arms.make_ts_shell(Workspace("", 1), log, "a-task")
                found = arms.make_ts_shell(Workspace("hi\n", 0), log, "a-task")
                self.assertEqual(
                    (await silent("grep zz f"), await found("grep hi f")),
                    told)
                # The log keeps what the command printed; the status line is
                # only in what the model was sent.
                self.assertEqual([entry["output"] for entry in log],
                                 ["", "hi\n"])

    async def test_an_idle_connection_to_the_proxy_stays_open(self):
        # The harness reuses its connection after a tool call; one uvicorn
        # closed as idle in the meantime fails with ECONNRESET.
        import asyncio
        from contextlib import AsyncExitStack

        from atlas import serving

        async def app(scope, receive, send):
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-length", b"2")]
            })
            await send({"type": "http.response.body", "body": b"ok"})

        async with AsyncExitStack() as stack:
            host, port = (await serving.listen(app, stack,
                                               60)).split("//")[1].split(":")
            reader, writer = await asyncio.open_connection(host, int(port))
            for wait in (6, 0):  # past uvicorn's own 5
                writer.write(b"GET / HTTP/1.1\r\nHost: x\r\n\r\n")
                await writer.drain()
                self.assertTrue(
                    (await
                     reader.readuntil(b"ok")).startswith(b"HTTP/1.1 200"))
                await asyncio.sleep(wait)
            writer.close()

    async def test_the_relay_gives_each_call_a_connection_of_its_own(self):
        # The app is uvicorn, which closes a connection idle for 5 s; a call
        # the relay sent on a pooled one just then came back `Server
        # disconnected without sending a response.` (least-liked-strategy-game,
        # five calls), and with a 4 s pool whenever an answer came in late.
        from contextlib import AsyncExitStack

        import httpx
        from atlas import serving
        from atlas.relay import Relay

        ports = []

        async def app(scope, receive, send):
            ports.append(scope["client"][1])
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-length", b"2")]
            })
            await send({"type": "http.response.body", "body": b"ok"})

        async with AsyncExitStack() as stack:
            relay = Relay(await serving.listen(app, stack))
            stack.push_async_callback(relay.close)
            harness = await stack.enter_async_context(
                httpx.AsyncClient(transport=httpx.ASGITransport(relay.app()),
                                  base_url="http://relay"))
            for _ in range(2):
                self.assertEqual((await harness.post("/list-tools",
                                                     content=b"{}")).text,
                                 "ok")
        self.assertNotEqual(*ports)

    async def test_a_call_the_harness_gave_up_on_is_stopped(self):
        """A command still running when the harness stops waiting is stopped.

        Through the tool server, the shell and a real Mirage workspace. The
        harness never aborts the request, so a command left running held the
        shell's session and the model's next command waited behind it
        (reyes-family-post-game-menu: a `find | head` took 16 seconds after
        an `rg` the harness had given up on).
        """
        import time
        from contextlib import AsyncExitStack

        import arms
        import workspace as workspace_backend
        from atlas import serving, tools
        from atlas.constants import TOOL_SERVER_PATH
        from mcp import ClientSession
        from mcp.client.streamable_http import streamable_http_client

        if not workspace_backend.DAEMON.is_file():
            self.skipTest("mirage's TypeScript packages are not built")
        dataset.use("mcpatlas")
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "workspace.yaml"
            config.write_text("mode: EXEC\nruntimes: [workspace]\n"
                              "mounts:\n  /tmp:\n    vfs: ram\n")
            ws = workspace_backend.Workspace.create(config)
        log = []
        try:
            shell = arms.make_ts_shell(ws, log, "fantasy-sports-average")
            with patch.object(tools, "TOOL_CALL_TIMEOUT", .5):
                async with AsyncExitStack() as stack:
                    url = await serving.listen(tools.tool_server([shell]),
                                               stack)
                    read, write, _ = await stack.enter_async_context(
                        streamable_http_client(f"{url}{TOOL_SERVER_PATH}"))
                    session = await stack.enter_async_context(
                        ClientSession(read, write))
                    await session.initialize()
                    began = time.monotonic()
                    stopped = await session.call_tool("shell",
                                                      {"command": "sleep 30"})
                    after = await session.call_tool("shell",
                                                    {"command": "echo next"})
                    waited = time.monotonic() - began
        finally:
            ws.close()
        self.assertEqual(
            (stopped.isError, stopped.content[0].text),
            (True, "stopped after 0.5s, when the harness stopped waiting"))
        # Neither the stop nor the next command waited out the sleep: the
        # job was deleted and the session freed.
        self.assertEqual(after.content[0].text, "next\n")
        self.assertLess(waited, 5)
        # The stopped command never answered, so the shell's log has only
        # the next one; the transcript keeps the call and the harness's
        # timeout, and the relay how long it ran.
        self.assertEqual(log, [{
            "command": "echo next",
            "output": "next\n",
            "model_output": "next\n"
        }])

    async def test_an_undeclared_argument_is_dropped_as_upstream_drops_it(
            self):
        """`timeout` beside a command runs the command, as on the MCP arm.

        The MCP arm's servers strip or ignore an argument their schema does
        not declare; the SDK's check against the strict schema refused the
        whole call (colombia-road-trip-distance: four `timeout`s, four
        requests). What the schema declares is still checked.
        """
        from contextlib import AsyncExitStack

        from atlas import serving, tools
        from atlas.constants import TOOL_SERVER_PATH
        from mcp import ClientSession
        from mcp.client.streamable_http import streamable_http_client

        ran = []

        async def shell(command: str) -> str:
            """Run a shell command.

            Args:
                command: the command line.
            """
            ran.append(command)
            return "ok"

        async with AsyncExitStack() as stack:
            url = await serving.listen(tools.tool_server([shell]), stack)
            read, write, _ = await stack.enter_async_context(
                streamable_http_client(f"{url}{TOOL_SERVER_PATH}"))
            session = await stack.enter_async_context(
                ClientSession(read, write))
            await session.initialize()
            (listed, ) = (await session.list_tools()).tools
            extra = await session.call_tool("shell", {
                "command": "ls",
                "timeout": 120000
            })
            missing = await session.call_tool("shell", {"timeout": 1})
            mistyped = await session.call_tool("shell", {"command": 1})
        self.assertFalse(listed.inputSchema["additionalProperties"])
        self.assertEqual((extra.isError, extra.content[0].text), (False, "ok"))
        self.assertEqual(ran, ["ls"])
        self.assertEqual(
            (missing.isError, missing.content[0].text),
            (True, "Input validation error: 'command' is a required property"))
        self.assertEqual(
            (mistyped.isError, mistyped.content[0].text),
            (True, "Input validation error: 1 is not of type 'string'"))

    async def test_an_openai_model_is_asked_on_the_responses_endpoint(self):
        """Every turn goes over item for item, and the reply comes back."""
        from atlas import gateway
        conversation = [
            {
                "role": "system",
                "content": "be brief"
            },
            {
                "role": "user",
                "content": "task"
            },
            {
                "role":
                "assistant",
                "content":
                None,
                "tool_calls": [{
                    "id": "c1",
                    "type": "function",
                    "function": {
                        "name": "shell",
                        "arguments": "{\"a\":1}"
                    }
                }]
            },
            {
                "role":
                "tool",
                "tool_call_id":
                "c1",
                "content": [{
                    "type": "text",
                    "text": '{\n  "zebra": "<@U1>"\n}'
                }, {
                    "type": "text",
                    "text": "and more"
                }]
            },
        ]
        output = [
            SimpleNamespace(type="reasoning"),
            SimpleNamespace(
                type="message",
                content=[SimpleNamespace(type="output_text",
                                         text="checking")]),
            SimpleNamespace(type="function_call",
                            call_id="c2",
                            name="shell",
                            arguments="{}"),
        ]
        create = AsyncMock(return_value=SimpleNamespace(
            id="r1",
            created_at=1.0,
            model="gpt",
            status="completed",
            incomplete_details=None,
            output=output,
            usage=SimpleNamespace(input_tokens=10,
                                  output_tokens=5,
                                  total_tokens=15,
                                  input_tokens_details=SimpleNamespace(
                                      cached_tokens=2),
                                  output_tokens_details=SimpleNamespace(
                                      reasoning_tokens=3))))
        client = SimpleNamespace(responses=SimpleNamespace(create=create))
        tool = {
            "type": "function",
            "function": {
                "name": "shell",
                "description": "run",
                "parameters": {},
                "strict": False
            }
        }
        reply = await gateway.ask_openai(client, "openai/gpt", conversation,
                                         [tool],
                                         {"reasoning_effort": "medium"})
        sent = create.call_args.kwargs
        self.assertEqual(sent["input"], [
            {
                "role": "system",
                "content": "be brief"
            },
            {
                "role": "user",
                "content": "task"
            },
            {
                "type": "function_call",
                "call_id": "c1",
                "name": "shell",
                "arguments": "{\"a\":1}"
            },
            {
                "type":
                "function_call_output",
                "call_id":
                "c1",
                "output": [{
                    "type": "input_text",
                    "text": '{\n  "zebra": "<@U1>"\n}'
                }, {
                    "type": "input_text",
                    "text": "and more"
                }]
            },
        ])
        self.assertEqual(sent["tools"], [{
            "type": "function",
            "name": "shell",
            "description": "run",
            "parameters": {},
            "strict": False
        }])
        self.assertEqual(sent["reasoning"], {"effort": "medium"})
        message = reply.choices[0].message
        self.assertEqual(message.content, "checking")
        self.assertEqual([(c.id, c.function.name, c.function.arguments)
                          for c in message.tool_calls],
                         [("c2", "shell", "{}")])
        self.assertEqual(reply.choices[0].finish_reason, "tool_calls")
        # Cut off before any call: what Chat Completions would call `length`.
        create.return_value.status = "incomplete"
        create.return_value.incomplete_details = SimpleNamespace(
            reason="max_output_tokens")
        create.return_value.output = output[:2]
        cut = await gateway.ask_openai(client, "openai/gpt", conversation,
                                       [tool], {})
        self.assertEqual(
            (cut.choices[0].finish_reason, cut.choices[0].message.content),
            ("length", "checking"))
        usage = gateway.usage_of(reply)
        self.assertEqual((usage.input_tokens, usage.output_tokens,
                          usage.output_tokens_details.reasoning_tokens),
                         (10, 5, 3))
        with self.assertRaises(ValueError):
            await gateway.ask_openai(client, "openai/gpt", conversation,
                                     [tool], {"temperature": 0})


class UnknownTools(unittest.IsolatedAsyncioTestCase):
    """The agents loop resolves and answers tool names as upstream's does."""

    @staticmethod
    def call(name):
        from openai.types.responses import ResponseFunctionToolCall
        return ResponseFunctionToolCall(type="function_call",
                                        call_id="call_1",
                                        name=name,
                                        arguments="{}")

    async def test_an_unknown_tool_is_answered_and_the_run_goes_on(self):
        # Gemini called `find_python` in excel-market-research and the SDK's
        # default ended the run; upstream answers the call and carries on.
        from agents import Agent, Runner, function_tool
        from agents.items import ModelResponse
        from agents.models.interface import Model
        from openai.types.responses import (ResponseOutputMessage,
                                            ResponseOutputText)

        replies = [
            [self.call("find_python")],
            [
                ResponseOutputMessage(id="m",
                                      type="message",
                                      role="assistant",
                                      status="completed",
                                      content=[
                                          ResponseOutputText(
                                              type="output_text",
                                              text="done",
                                              annotations=[])
                                      ])
            ],
        ]
        seen = []

        class Scripted(Model):

            async def get_response(self, *args, **kwargs):
                seen.append(kwargs["input"])
                return ModelResponse(output=replies.pop(0),
                                     usage=Usage(),
                                     response_id=None)

            def stream_response(self, *args, **kwargs):
                raise NotImplementedError

        @function_tool
        def local_python_execute(code: str) -> str:
            """Run Python."""
            return code

        agent = Agent(name="toolathlon-mcp-agent",
                      model=Scripted(),
                      tools=[local_python_execute])
        result = await Runner.run(agent,
                                  "task",
                                  run_config=run_agent.run_config(
                                      None, agent.name))
        self.assertEqual(result.final_output, "done")
        answer = [
            item for item in seen[1] if isinstance(item, dict)
            and item.get("type") == "function_call_output"
        ]
        self.assertEqual(
            answer[0]["output"],
            "Tool find_python not found in agent toolathlon-mcp-agent")

    async def test_a_provider_normalized_name_resolves_to_its_tool(self):
        from agents.items import ModelResponse

        registered = [
            SimpleNamespace(name="local-python_execute"),
            SimpleNamespace(name="filesystem-read_file"),
            SimpleNamespace(name="filesystem_read_file"),
        ]
        replies = [
            self.call("local_python_execute"),
            self.call("filesystem_read_file"),
            self.call("find_python"),
        ]
        model = run_agent.ChatCompletions(model="m", openai_client=None)
        with patch.object(
                run_agent.OpenAIChatCompletionsModel, "get_response",
                AsyncMock(return_value=ModelResponse(
                    output=replies, usage=Usage(), response_id=None))):
            response = await model.get_response(tools=registered, handoffs=[])
        # One match is renamed; an exact name stays; no match is left for
        # the not-found answer.
        self.assertEqual(
            [item.name for item in response.output],
            ["local-python_execute", "filesystem_read_file", "find_python"])


class ContextReset(unittest.IsolatedAsyncioTestCase):
    """A context the model refuses as too long is cleared as upstream's is."""

    # What the gateway answered Luna in youtube-repo's first MCP attempt.
    REFUSED = ("Error code: 400 - {'error': {'message': 'Your input exceeds "
               "the context window of this model. Please adjust your input "
               "and try again.', 'type': 'invalid_request_error', 'param': "
               "'input', 'code': 'context_length_exceeded'}}")

    async def test_a_refused_request_is_read_as_upstream_reads_it(self):
        model = run_agent.ChatCompletions(model="m", openai_client=None)
        # Upstream's last check reads its phrases in any error, whatever the
        # status, so a gateway timeout that says "too long" is one too.
        for error, expected in ((Exception(self.REFUSED),
                                 run_agent.ContextTooLong),
                                (Exception("Error code: 504 - upstream took "
                                           "too long to respond"),
                                 run_agent.ContextTooLong),
                                (Exception("Error code: 500 - overloaded"),
                                 Exception)):
            with self.subTest(error=str(error)), patch.object(
                    run_agent.OpenAIChatCompletionsModel, "get_response",
                    AsyncMock(side_effect=error)):
                with self.assertRaises(Exception) as caught:
                    await model.get_response(tools=[], handoffs=[])
                self.assertIs(type(caught.exception), expected)

    async def draw(self, max_turns, history):
        # One tool call, then a refused request, then an answer: the third
        # reply comes only if the context is cleared and the run goes on.
        from agents import Agent, function_tool
        from agents.items import ModelResponse
        from agents.models.interface import Model
        from context import Progress
        from openai.types.responses import (ResponseFunctionToolCall,
                                            ResponseOutputMessage,
                                            ResponseOutputText)

        call = ResponseFunctionToolCall(type="function_call",
                                        call_id="call_1",
                                        name="local_python_execute",
                                        arguments='{"code": "1"}')
        answer = ResponseOutputMessage(id="m",
                                       type="message",
                                       role="assistant",
                                       status="completed",
                                       content=[
                                           ResponseOutputText(
                                               type="output_text",
                                               text="done",
                                               annotations=[])
                                       ])
        replies = [[call], Exception(self.REFUSED), [answer]]
        self.seen = []

        class Replies(Model):

            async def get_response(self_, *args, **kwargs):
                self.seen.append(kwargs["input"])
                reply = replies.pop(0)
                if isinstance(reply, Exception):
                    raise reply
                return ModelResponse(output=reply,
                                     usage=Usage(requests=1,
                                                 input_tokens=10,
                                                 output_tokens=1,
                                                 total_tokens=11),
                                     response_id=None)

            def stream_response(self_, *args, **kwargs):
                raise NotImplementedError

        class Scripted(run_agent.UpstreamContextErrors, Replies):
            pass

        @function_tool
        def local_python_execute(code: str) -> str:
            """Run Python."""
            return code

        dataset.use("toolathlon")
        progress = Progress({},
                            root=dataset.root(),
                            history_dir=history,
                            session_id="s",
                            task="task")
        agent = Agent(name="toolathlon-mcp-agent",
                      model=Scripted(),
                      tools=[local_python_execute])
        return progress, await run_agent.run_agents(agent, "task", max_turns,
                                                    progress)

    async def test_a_refused_context_is_cleared_and_the_run_goes_on(self):
        with tempfile.TemporaryDirectory() as history:
            progress, result = await self.draw(4, Path(history))
            records = [
                json.loads(line)
                for line in (Path(history) /
                             "s_history.jsonl").read_text().splitlines()
            ]
        self.assertEqual(result.final_output, "done")
        # The next sequence is one user message: upstream's notice, the
        # task, and its summary of the turns so far.
        [message] = self.seen[2]
        self.assertEqual(message["role"], "user")
        query = message["content"]
        self.assertTrue(query.startswith("[Context reset] The context length"))
        self.assertIn("=== Original User Task ===\ntask\n\n", query)
        self.assertIn("Tool Call: local_python_execute", query)
        self.assertIn(query, [r.get("content") for r in records])
        # The run's record keeps the cleared sequence and both usages.
        items, usage = progress.whole(result.new_items,
                                      result.context_wrapper.usage)
        self.assertEqual(
            [getattr(item, "type", None) or item["role"] for item in items], [
                "tool_call_item", "tool_call_output_item", "user",
                "message_output_item"
            ])
        self.assertEqual((usage.requests, usage.input_tokens), (2, 20))

    async def test_a_turn_with_an_unknown_tool_goes_back_whole(self):
        # Claude Opus called `shell` and an undeclared `web-search` in one
        # turn of identify-all-songs. The SDK answers the unknown call
        # without a tool hook, and the next request carried the turn short
        # its first call, which Bedrock refused for the orphaned result.
        from agents import Agent, function_tool
        from agents.items import ModelResponse
        from agents.models.interface import Model
        from context import Progress
        from openai.types.responses import (ResponseFunctionToolCall,
                                            ResponseOutputMessage,
                                            ResponseOutputText)

        calls = [
            ResponseFunctionToolCall(type="function_call",
                                     call_id=f"call_{name}",
                                     name=name,
                                     arguments="{}")
            for name in ("local_python_execute", "web-search")
        ]
        answer = ResponseOutputMessage(id="m",
                                       type="message",
                                       role="assistant",
                                       status="completed",
                                       content=[
                                           ResponseOutputText(
                                               type="output_text",
                                               text="done",
                                               annotations=[])
                                       ])
        replies = [calls, [answer]]
        seen = []

        class Scripted(Model):

            async def get_response(self_, *args, **kwargs):
                seen.append(kwargs["input"])
                return ModelResponse(output=replies.pop(0),
                                     usage=Usage(),
                                     response_id=None)

            def stream_response(self_, *args, **kwargs):
                raise NotImplementedError

        @function_tool
        def local_python_execute() -> str:
            """Run Python."""
            return "ran"

        dataset.use("toolathlon")
        with tempfile.TemporaryDirectory() as history:
            progress = Progress({},
                                root=dataset.root(),
                                history_dir=Path(history),
                                session_id="s",
                                task="task")
            agent = Agent(name="toolathlon-vfs-agent",
                          model=Scripted(),
                          tools=[local_python_execute])
            result = await run_agent.run_agents(agent, "task", 4, progress)
        self.assertEqual(result.final_output, "done")
        turn = [(item.get("type"), item.get("call_id")) for item in seen[1]
                if isinstance(item, dict) and item.get("call_id")]
        self.assertEqual(turn, [
            ("function_call", "call_local_python_execute"),
            ("function_call", "call_web-search"),
            ("function_call_output", "call_local_python_execute"),
            ("function_call_output", "call_web-search"),
        ])

    async def test_a_reset_with_no_turns_left_ends_the_run(self):
        # The task, the tool call and the refused request are three of
        # upstream's turns, which leaves a budget of three none to go on.
        with tempfile.TemporaryDirectory() as history:
            with self.assertRaises(run_agent.ContextTooLong) as caught:
                await self.draw(3, Path(history))
        self.assertEqual(len(caught.exception.run_data.new_items), 2)
        self.assertEqual(len(self.seen), 2)


if __name__ == "__main__":
    unittest.main()
