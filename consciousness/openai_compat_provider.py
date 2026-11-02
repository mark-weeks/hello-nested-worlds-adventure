"""OpenAI-compatible Chat Completions transport. No world or player rules.

The operator supplies the base URL. One adapter can then reach any server
that speaks this dialect, for evaluation. Registering it does not approve a
data destination and does not select a model. There is no default model id
and no vendor SDK. The base URL and the API key are never logged and never
placed in an exception message.

``configured`` is false until the base URL is acceptable and a key is
present, unless the host is loopback. An optional setting that is present
but not one of the allowed values also makes ``configured`` false, so the
voice handler does not spend the voice budget on a typo. Moderation does
not check ``configured`` before it classifies; ``generate`` still raises,
and the screen holds.

Only a finished ``stop`` with non-blank string content and no refusal is
``complete``. Empty or whitespace-only content is not complete. Every
other finish leaves ``complete`` false. ``length`` keeps partial text,
matching the Anthropic adapter. ``content_filter``, ``refusal``, tool
calls, xAI's ``end_turn``, and any unknown finish set text to None.
Voice publishes any non-None text through ``require_text`` without
reading ``complete``, so those finishes must not carry text until a live
check shows what the server meant. ADR-035 (Proposed) records the
dialect choice; this module does not ratify it.
"""
from __future__ import annotations

from dataclasses import dataclass
import http.client
import io
import json
import math
import os
import socket
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from consciousness.runtime import Completion, SystemBlock, TokenUsage


# Operator settings. None of these names is OPENAI_* or XAI_*.
BASE_URL_ENV = "NESTED_WORLDS_OPENAI_COMPATIBLE_BASE_URL"
API_KEY_ENV = "NESTED_WORLDS_OPENAI_COMPATIBLE_API_KEY"
# The name must not contain TOKEN. model_check treats TOKEN as a secret
# and would redact the parameter name from the startup report.
MAX_OUTPUT_PARAM_ENV = "NESTED_WORLDS_OPENAI_COMPATIBLE_MAX_OUTPUT_PARAM"
STRUCTURED_OUTPUTS_ENV = "NESTED_WORLDS_OPENAI_COMPATIBLE_STRUCTURED_OUTPUTS"
SEND_STORE_FALSE_ENV = "NESTED_WORLDS_OPENAI_COMPATIBLE_SEND_STORE_FALSE"
REASONING_EFFORT_ENV = "NESTED_WORLDS_OPENAI_COMPATIBLE_REASONING_EFFORT"
TIMEOUT_ENV = "NESTED_WORLDS_OPENAI_COMPATIBLE_TIMEOUT_SECONDS"

DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_MAX_TOKENS_PARAM = "max_completion_tokens"
_MAX_TOKENS_PARAMS = frozenset({"max_completion_tokens", "max_tokens"})
# Closed set. An unknown token is not forwarded: a pasted secret must not
# leave the process as a sampling field.
_REASONING_EFFORTS = frozenset({"none", "minimal", "low", "medium", "high"})
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_SCHEMA_NAME = "enfolded_output"
# Chat replies for this game are small. A larger body is not a completion.
MAX_RESPONSE_BYTES = 1_048_576
_READ_CHUNK = 65536


class OpenAICompatError(Exception):
    """Adapter failure. The message names the failure, never a payload."""


class ProviderHTTPError(OpenAICompatError):
    """HTTP status only. The response body is not stored."""

    def __init__(self, status: int) -> None:
        self.status = status
        super().__init__(f"HTTP {status}")


class ProviderTimeout(OpenAICompatError):
    def __init__(self) -> None:
        super().__init__("timed out")


class ProviderConnectionError(OpenAICompatError):
    def __init__(self) -> None:
        super().__init__("connection failed")


class MalformedProviderResponse(OpenAICompatError):
    def __init__(self) -> None:
        super().__init__("malformed response")


class ProviderNotConfigured(OpenAICompatError):
    def __init__(self) -> None:
        super().__init__("provider is not configured")


class ProviderConfigError(OpenAICompatError):
    def __init__(self) -> None:
        super().__init__("provider setting is invalid")


class UnsupportedCapability(OpenAICompatError):
    """A requested schema cannot be honored. Callers serve the authored fallback."""

    def __init__(self) -> None:
        super().__init__("structured outputs are not enabled")


@dataclass(frozen=True)
class ParsedBase:
    """Normalized base URL. ``loopback`` is the key exemption."""

    url: str
    loopback: bool


@dataclass(frozen=True)
class TransportRequest:
    """One POST. ``repr`` omits the URL, the key, and the body."""

    method: str
    url: str
    headers: tuple[tuple[str, str], ...]
    body: bytes
    timeout: float

    def __repr__(self) -> str:
        return (
            f"TransportRequest(method={self.method!r}, timeout={self.timeout!r}, "
            f"body_bytes={len(self.body)})"
        )


def _flag(name: str) -> bool:
    return os.environ.get(name, "").strip() == "1"


def _api_key() -> str | None:
    # Strip, then reject internal whitespace and control characters so a
    # key cannot inject a header line. The value is never logged.
    raw = os.environ.get(API_KEY_ENV)
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    if any(ch.isspace() or ord(ch) < 32 or ord(ch) == 127 for ch in text):
        return None
    return text


def parse_base_url(raw: str | None) -> ParsedBase | None:
    """Accept https, or http on loopback. Reject userinfo, query, and fragment.

    Returns None for anything else. Does not log ``raw``.
    """
    if raw is None:
        return None
    text = raw.strip()
    if not text or any(ch.isspace() or ord(ch) < 32 or ord(ch) == 127 for ch in text):
        return None
    if "\\" in text:
        return None
    try:
        parts = urlsplit(text)
        port = parts.port
    except ValueError:
        return None
    if parts.username is not None or parts.password is not None:
        return None
    if parts.query or parts.fragment:
        return None
    host = parts.hostname
    if not host or not parts.netloc:
        return None
    if "@" in parts.netloc:
        return None
    scheme = parts.scheme.lower()
    loopback = host.lower() in _LOOPBACK_HOSTS
    if scheme == "http":
        if not loopback:
            return None
    elif scheme != "https":
        return None
    path = parts.path or ""
    if ".." in path.split("/"):
        return None
    # ``port`` is read so a non-numeric port fails above. Rebuild from the
    # parsed netloc so userinfo cannot hide in a second @.
    del port
    url = f"{scheme}://{parts.netloc}{path}".rstrip("/")
    return ParsedBase(url, loopback)


def chat_completions_url(base: str) -> str:
    """Join ``/chat/completions`` onto a base that may already end in a path.

    ``urljoin`` would drop the last segment of a base that has no trailing
    slash (``https://api.example/v1`` would become ``https://api.example/chat``).
    """
    return base.rstrip("/") + "/chat/completions"


def _max_tokens_param() -> str | None:
    raw = os.environ.get(MAX_OUTPUT_PARAM_ENV)
    if raw is None or not raw.strip():
        return DEFAULT_MAX_TOKENS_PARAM
    text = raw.strip()
    if text in _MAX_TOKENS_PARAMS:
        return text
    return None


def _reasoning_effort() -> tuple[str | None, bool]:
    """``(value, invalid)``. Unset is ``(None, False)`` and sends nothing."""
    raw = os.environ.get(REASONING_EFFORT_ENV)
    if raw is None or not raw.strip():
        return None, False
    text = raw.strip()
    if text in _REASONING_EFFORTS:
        return text, False
    return None, True


def _default_timeout() -> float:
    raw = os.environ.get(TIMEOUT_ENV)
    if raw is None or not raw.strip():
        return DEFAULT_TIMEOUT_SECONDS
    try:
        value = float(raw.strip())
    except ValueError:
        return DEFAULT_TIMEOUT_SECONDS
    if not math.isfinite(value) or value <= 0:
        return DEFAULT_TIMEOUT_SECONDS
    return value


def _call_timeout(caller: float | None) -> float:
    if caller is None:
        return _default_timeout()
    try:
        value = float(caller)
    except (TypeError, ValueError):
        return _default_timeout()
    if not math.isfinite(value) or value <= 0:
        return _default_timeout()
    return value


@dataclass(frozen=True)
class _Settings:
    base: ParsedBase | None
    api_key: str | None
    max_tokens_param: str | None
    structured_outputs: bool
    send_store_false: bool
    reasoning_effort: str | None
    reasoning_invalid: bool

    @property
    def usable(self) -> bool:
        if self.base is None or self.max_tokens_param is None or self.reasoning_invalid:
            return False
        if self.api_key is None and not self.base.loopback:
            return False
        return True


def _settings() -> _Settings:
    effort, invalid = _reasoning_effort()
    return _Settings(
        base=parse_base_url(os.environ.get(BASE_URL_ENV)),
        api_key=_api_key(),
        max_tokens_param=_max_tokens_param(),
        structured_outputs=_flag(STRUCTURED_OUTPUTS_ENV),
        send_store_false=_flag(SEND_STORE_FALSE_ENV),
        reasoning_effort=effort,
        reasoning_invalid=invalid,
    )


def build_request(
    *,
    model: str,
    system: tuple[SystemBlock, ...],
    messages: list[dict[str, str]],
    max_tokens: int,
    json_schema: dict | None,
    max_tokens_param: str,
    structured_outputs: bool,
    send_store_false: bool,
    reasoning_effort: str | None,
) -> dict:
    """JSON body. One system message, caller order, no sampling fields.

    A schema is sent only when structured outputs are enabled. Otherwise
    this raises ``UnsupportedCapability`` and the caller sends nothing.
    ``n`` and ``stream`` are never sent: the adapter reads only the first
    choice, and a stream is not a single completion.
    """
    wired: list[dict] = []
    if system:
        wired.append({
            "role": "system",
            "content": "\n\n".join(block.text for block in system),
        })
    for message in messages:
        item: dict = {}
        if "role" in message:
            item["role"] = message["role"]
        if "content" in message:
            item["content"] = message["content"]
        wired.append(item)
    body: dict = {
        "model": model,
        "messages": wired,
        max_tokens_param: max_tokens,
    }
    if json_schema is not None:
        if not structured_outputs:
            raise UnsupportedCapability()
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": _SCHEMA_NAME,
                "schema": json_schema,
                "strict": True,
            },
        }
    if send_store_false:
        body["store"] = False
    if reasoning_effort is not None:
        body["reasoning_effort"] = reasoning_effort
    return body


def _nonneg_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value < 0:
        return None
    return value


def _usage(raw: object) -> TokenUsage | None:
    """Ordinary input excludes reported cache reads and writes.

    ``cache_write_tokens`` absent counts as zero in that subtraction and
    stays None on the result, because the server did not report a write.
    ``cached_tokens`` absent leaves ordinary input unknown: prompt tokens
    on this dialect include cached tokens when the server breaks them out,
    and a missing split is not evidence that the cache was zero. Output is
    ``total_tokens - prompt_tokens`` when both exist, so reasoning tokens
    that one server folds into ``completion_tokens`` and another leaves
    outside it are both billed. Without both of those fields, output is
    unknown. ``completion_tokens`` is not a substitute: it can omit
    reasoning. A negative result is unknown.
    """
    if not isinstance(raw, dict):
        return None
    prompt = _nonneg_int(raw.get("prompt_tokens"))
    total = _nonneg_int(raw.get("total_tokens"))
    details = raw.get("prompt_tokens_details")
    cached: int | None = None
    cached_known = False
    cache_write: int | None = None
    write_blocked = False
    if isinstance(details, dict):
        if "cached_tokens" in details and details.get("cached_tokens") is not None:
            cached = _nonneg_int(details.get("cached_tokens"))
            cached_known = cached is not None
        if "cache_write_tokens" in details and details.get("cache_write_tokens") is not None:
            cache_write = _nonneg_int(details.get("cache_write_tokens"))
            write_blocked = cache_write is None
    input_tokens: int | None = None
    if prompt is not None and cached_known and not write_blocked:
        ordinary = prompt - cached - (cache_write or 0)
        input_tokens = ordinary if ordinary >= 0 else None
    output_tokens: int | None = None
    if prompt is not None and total is not None:
        output = total - prompt
        output_tokens = output if output >= 0 else None
    return TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cached if cached_known else None,
        cache_write_tokens=cache_write,
    )


def parse_response(body: dict) -> Completion:
    """Map one Chat Completions object onto ``Completion``.

    A non-null ``error`` raises. More than one choice, or content that is
    present and not a string, raises ``MalformedProviderResponse``. Missing
    choices are an empty completion, not a transport error, so voice raises
    ``NoTextError`` and moderation holds. A missing ``refusal`` is null.
    Empty or whitespace-only content is not complete. See the module
    docstring for which finishes carry text.
    """
    if not isinstance(body, dict) or body.get("error") is not None:
        raise MalformedProviderResponse()
    usage = _usage(body.get("usage"))
    echoed = body.get("model")
    resolved = echoed if isinstance(echoed, str) else None
    choices = body.get("choices")
    if isinstance(choices, list) and len(choices) > 1:
        raise MalformedProviderResponse()
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
        return Completion(
            text=None, complete=False, usage=usage, finish_reason="unknown",
            resolved_model=resolved, provider=OpenAICompatibleProvider.name,
        )
    choice = choices[0]
    message = choice.get("message")
    if not isinstance(message, dict):
        message = {}
    finish = choice.get("finish_reason")
    if not isinstance(finish, str):
        finish = None
    # Absent, or JSON null. Only a present non-null value is a refusal.
    refusal = message.get("refusal") if "refusal" in message else None
    content = message.get("content")
    if content is not None and not isinstance(content, str):
        raise MalformedProviderResponse()
    if isinstance(content, str) and not content.strip():
        content = None
    text = content if isinstance(content, str) else None
    if refusal is not None:
        return Completion(
            text=None, complete=False, usage=usage, finish_reason="refusal",
            resolved_model=resolved, provider=OpenAICompatibleProvider.name,
        )
    if finish == "stop" and isinstance(content, str):
        return Completion(
            text=content, complete=True, usage=usage, finish_reason="complete",
            resolved_model=resolved, provider=OpenAICompatibleProvider.name,
        )
    if finish == "length":
        return Completion(
            text=text, complete=False, usage=usage, finish_reason="length",
            resolved_model=resolved, provider=OpenAICompatibleProvider.name,
        )
    if finish == "content_filter":
        mapped = "filtered"
    elif finish in ("tool_calls", "function_call"):
        mapped = "tool"
    else:
        # Includes end_turn, null, and anything this adapter does not know.
        mapped = "unknown"
    return Completion(
        text=None, complete=False, usage=usage, finish_reason=mapped,
        resolved_model=resolved, provider=OpenAICompatibleProvider.name,
    )


def decode_response(status: int, raw: bytes) -> Completion:
    if isinstance(status, bool) or not isinstance(status, int):
        raise MalformedProviderResponse()
    if status < 200 or status >= 300:
        raise ProviderHTTPError(status)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise MalformedProviderResponse()
    try:
        body = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        raise MalformedProviderResponse() from None
    return parse_response(body)


def _read_capped(response) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = response.read(_READ_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_RESPONSE_BYTES:
            raise MalformedProviderResponse()
        chunks.append(chunk)
    return b"".join(chunks)


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ProviderTimeout()
    return remaining


class _DeadlineSocket:
    """Re-arm the underlying socket with the time left before each call.

    urllib's ``timeout`` is a limit on one socket operation. A header
    dribbled one byte at a time would otherwise run for many times the
    number the caller passed. The caller's number is the wall-clock
    budget for the whole POST.
    """

    def __init__(self, sock, deadline: float) -> None:
        self._sock = sock
        self._deadline = deadline

    def _arm(self) -> None:
        self._sock.settimeout(_remaining(self._deadline))

    def recv(self, buflen, flags=0):
        self._arm()
        try:
            return self._sock.recv(buflen, flags)
        except (TimeoutError, socket.timeout):
            raise ProviderTimeout() from None

    def recv_into(self, buffer, nbytes=0, flags=0):
        self._arm()
        try:
            return self._sock.recv_into(buffer, nbytes, flags)
        except (TimeoutError, socket.timeout):
            raise ProviderTimeout() from None

    def send(self, data, flags=0):
        self._arm()
        try:
            return self._sock.send(data, flags)
        except (TimeoutError, socket.timeout):
            raise ProviderTimeout() from None

    def sendall(self, data, flags=0):
        view = memoryview(data)
        while view:
            sent = self.send(view, flags)
            view = view[sent:]

    def makefile(self, mode="r", buffering=None, *args, **kwargs):
        raw = socket.SocketIO(self, mode)
        if buffering is None or buffering < 0:
            buffering = io.DEFAULT_BUFFER_SIZE
        if "r" in mode:
            return io.BufferedReader(raw, buffering)
        return io.BufferedWriter(raw, buffering)

    def settimeout(self, value):
        # Callers pass their own per-operation number. Keep the budget.
        self._arm()

    def gettimeout(self):
        return self._sock.gettimeout()

    def fileno(self):
        return self._sock.fileno()

    def close(self):
        self._sock.close()

    def __getattr__(self, name):
        return getattr(self._sock, name)


def _connection(deadline: float, https: bool):
    base = http.client.HTTPSConnection if https else http.client.HTTPConnection

    class Conn(base):
        def __init__(self, host, port=None, timeout=socket._GLOBAL_DEFAULT_TIMEOUT,
                     source_address=None, *, context=None, check_hostname=None,
                     blocksize=8192):
            kwargs = {}
            if https:
                kwargs["context"] = context
                kwargs["check_hostname"] = check_hostname
            super().__init__(
                host, port=port, timeout=_remaining(deadline),
                source_address=source_address, blocksize=blocksize, **kwargs,
            )
            self._deadline = deadline

        def connect(self):
            self.timeout = _remaining(self._deadline)
            super().connect()
            self.sock = _DeadlineSocket(self.sock, self._deadline)

    return Conn


def _exchange(handler, http_class, req, **http_conn_args):
    """One request. The body is read before the socket is closed.

    ``AbstractHTTPHandler.do_open`` closes the socket as soon as the
    status line and headers have been parsed. A server that flushes
    those headers before the body — ``BaseHTTPRequestHandler.end_headers``
    does — can still be writing the body. The later ``read`` then calls
    ``recv`` on a closed descriptor (``EBADF``) and looks like a dropped
    connection. Read the capped body first, then close.
    """
    host = req.host
    if not host:
        raise urllib.error.URLError("no host given")
    connection = http_class(host, timeout=req.timeout, **http_conn_args)
    connection.set_debuglevel(handler._debuglevel)
    headers = dict(req.unredirected_hdrs)
    headers.update({key: value for key, value in req.headers.items() if key not in headers})
    # One request. A kept-alive socket would block the next read.
    headers["Connection"] = "close"
    headers = {name.title(): value for name, value in headers.items()}
    if req._tunnel_host:
        tunnel_headers = {}
        proxy_auth = "Proxy-Authorization"
        if proxy_auth in headers:
            tunnel_headers[proxy_auth] = headers.pop(proxy_auth)
        connection.set_tunnel(req._tunnel_host, headers=tunnel_headers)
    try:
        try:
            connection.request(
                req.get_method(), req.selector, req.data, headers,
                encode_chunked=req.has_header("Transfer-encoding"),
            )
        except OSError as err:
            raise urllib.error.URLError(err) from None
        response = connection.getresponse()
    except Exception:
        connection.close()
        raise
    try:
        announced = response.headers.get("Content-Length")
        if announced is not None:
            try:
                size = int(announced)
            except ValueError:
                size = None
            if size is not None and size > MAX_RESPONSE_BYTES:
                raise MalformedProviderResponse()
        # Copy the body out before closing the descriptor. Leave the
        # response itself open: opener.open is used as a context manager
        # and refuses a response that is already closed.
        response.enfolded_body = _read_capped(response)
    except Exception:
        _close_quietly(connection, response)
        raise
    _close_quietly(connection, None)
    # urllib's error processor reads the reason phrase from msg.
    response.msg = response.reason
    return response


def _close_quietly(connection, response) -> None:
    try:
        if connection.sock is not None:
            connection.sock.close()
            connection.sock = None
        if response is not None:
            response.close()
    except OSError:
        pass


class _Exchange:
    def do_open(self, http_class, req, **http_conn_args):
        return _exchange(self, http_class, req, **http_conn_args)


class _HTTPHandler(_Exchange, urllib.request.HTTPHandler):
    def __init__(self, deadline: float) -> None:
        super().__init__()
        self._deadline = deadline

    def http_open(self, req):
        return self.do_open(_connection(self._deadline, False), req)


class _HTTPSHandler(_Exchange, urllib.request.HTTPSHandler):
    def __init__(self, deadline: float) -> None:
        super().__init__()
        self._deadline = deadline

    def https_open(self, req):
        return self.do_open(
            _connection(self._deadline, True), req,
            context=self._context, check_hostname=self._check_hostname,
        )


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Any 3xx stops here. The key is not copied onto a second request."""

    def http_error_302(self, req, fp, code, msg, headers):
        raise ProviderHTTPError(int(code)) from None

    http_error_301 = http_error_303 = http_error_307 = http_error_308 = http_error_302

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ProviderHTTPError(int(code)) from None


class _Status(urllib.request.HTTPErrorProcessor):
    def http_response(self, request, response):
        code = getattr(response, "code", None)
        if isinstance(code, int) and not isinstance(code, bool) and 300 <= code < 400:
            raise ProviderHTTPError(code) from None
        return super().http_response(request, response)

    https_response = http_response


def urllib_transport(request: TransportRequest) -> tuple[int, tuple[tuple[str, str], ...], bytes]:
    """One POST. No retries, no redirects, no environment proxy.

    A redirect would forward ``Authorization`` to a host the operator did
    not name. ``ProxyHandler({})`` is installed so ``HTTP_PROXY``,
    ``HTTPS_PROXY``, and ``ALL_PROXY`` are not read. The caller's timeout
    is a wall-clock budget for this POST, not urllib's per-socket timeout.
    The body is read before the socket is closed. Failures become adapter
    exceptions whose messages do not include the URL, the body, or the key.
    """
    deadline = time.monotonic() + request.timeout
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        _NoRedirect(),
        _Status(),
        _HTTPHandler(deadline),
        _HTTPSHandler(deadline),
    )
    outgoing = urllib.request.Request(
        request.url,
        data=request.body,
        headers=dict(request.headers),
        method=request.method,
    )
    try:
        with opener.open(outgoing, timeout=request.timeout) as response:
            status = response.getcode()
            if isinstance(status, bool) or not isinstance(status, int):
                raise MalformedProviderResponse()
            if 300 <= status < 400:
                raise ProviderHTTPError(status) from None
            raw = getattr(response, "enfolded_body", None)
            if not isinstance(raw, (bytes, bytearray)):
                raise MalformedProviderResponse()
            pairs = tuple((key, value) for key, value in response.headers.items())
            return status, pairs, bytes(raw)
    except ProviderHTTPError as exc:
        raise ProviderHTTPError(exc.status) from None
    except ProviderTimeout:
        raise ProviderTimeout() from None
    except MalformedProviderResponse:
        raise MalformedProviderResponse() from None
    except ProviderConnectionError:
        raise ProviderConnectionError() from None
    except urllib.error.HTTPError as exc:
        raise ProviderHTTPError(int(exc.code)) from None
    except (TimeoutError, socket.timeout):
        raise ProviderTimeout() from None
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", None)
        if isinstance(reason, (TimeoutError, socket.timeout, ProviderTimeout)):
            raise ProviderTimeout() from None
        raise ProviderConnectionError() from None
    except http.client.HTTPException:
        raise MalformedProviderResponse() from None
    except (ConnectionError, OSError):
        raise ProviderConnectionError() from None


def _invoke_transport(transport, request: TransportRequest) -> tuple[int, object, bytes]:
    try:
        result = transport(request)
    except (
        ProviderHTTPError, ProviderTimeout, MalformedProviderResponse,
        ProviderConnectionError, ProviderNotConfigured, ProviderConfigError,
        UnsupportedCapability,
    ):
        raise
    except (TimeoutError, socket.timeout):
        raise ProviderTimeout() from None
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", None)
        if isinstance(reason, (TimeoutError, socket.timeout)):
            raise ProviderTimeout() from None
        raise ProviderConnectionError() from None
    except (ConnectionError, OSError):
        raise ProviderConnectionError() from None
    if not isinstance(result, tuple) or len(result) != 3:
        raise MalformedProviderResponse()
    status, _headers, raw = result
    if isinstance(status, bool) or not isinstance(status, int):
        raise MalformedProviderResponse()
    if not isinstance(raw, (bytes, bytearray)):
        raise MalformedProviderResponse()
    return status, _headers, bytes(raw)


class OpenAICompatibleProvider:
    name = "openai_compatible"
    # No sdk_module. installation_error stays None; the stdlib is enough.

    def __init__(self, transport=None) -> None:
        self._transport = transport

    def configured(self) -> bool:
        return _settings().usable

    def model_id_validator(self):
        # A gateway alias is not judged by prefix. Structural checks in
        # model_check still apply. None means no soft warning.
        return None

    def cache_reference_tokens(self, model: str) -> int | None:
        return None

    def generate(self, *, model: str, system: tuple[SystemBlock, ...],
                 messages: list[dict[str, str]], max_tokens: int,
                 json_schema: dict | None = None,
                 timeout: float | None = None) -> Completion:
        settings = _settings()
        if settings.base is None or (settings.api_key is None and not settings.base.loopback):
            raise ProviderNotConfigured()
        if settings.max_tokens_param is None or settings.reasoning_invalid:
            raise ProviderConfigError()
        # Build before any socket so a refused schema sends nothing.
        body = build_request(
            model=model,
            system=system,
            messages=messages,
            max_tokens=max_tokens,
            json_schema=json_schema,
            max_tokens_param=settings.max_tokens_param,
            structured_outputs=settings.structured_outputs,
            send_store_false=settings.send_store_false,
            reasoning_effort=settings.reasoning_effort,
        )
        try:
            encoded = json.dumps(body).encode("utf-8")
        except (TypeError, ValueError):
            raise MalformedProviderResponse() from None
        headers = [
            ("Content-Type", "application/json"),
            ("Accept", "application/json"),
        ]
        if settings.api_key is not None:
            headers.append(("Authorization", f"Bearer {settings.api_key}"))
        prepared = TransportRequest(
            method="POST",
            url=chat_completions_url(settings.base.url),
            headers=tuple(headers),
            body=encoded,
            timeout=_call_timeout(timeout),
        )
        transport = self._transport or urllib_transport
        status, _ignored, raw = _invoke_transport(transport, prepared)
        return decode_response(status, raw)


provider = OpenAICompatibleProvider()
