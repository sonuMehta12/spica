from functools import lru_cache
from urllib.parse import urlsplit, urlunsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def asyncpg_url(url: str) -> str:
    """A provider's Postgres string, in the form asyncpg takes.

    Neon — like every provider — hands out `postgresql://…?sslmode=require
    &channel_binding=require`. SQLAlchemy passes the query keys straight to
    `asyncpg.connect`, which has neither keyword: its TLS switch is `ssl`, and
    it takes the same modes. So the string is pasted as given and fixed here,
    and anything already right — the local default included — comes out as it
    went in. Other query keys are kept byte for byte. spec/in-progress/deploy.md.
    """
    parts = urlsplit(url)
    scheme = "postgresql+asyncpg" if parts.scheme in ("postgres", "postgresql") else parts.scheme
    query = []
    for pair in filter(None, parts.query.split("&")):
        key, _, value = pair.partition("=")
        if key == "channel_binding":
            continue
        query.append(f"ssl={value}" if key == "sslmode" else pair)
    return urlunsplit(parts._replace(scheme=scheme, query="&".join(query)))


class Settings(BaseSettings):
    """Everything that differs between machines, and nothing that does not."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://cortex:cortex@localhost:5434/cortex"
    #: A connection per transaction, none held between requests: a session
    #: hands its connection back at every commit, and NullPool closes it, so a
    #: request that commits twice connects twice. Set only on Vercel, which
    #: pauses an instance between requests: a pooled connection would be a
    #: dead socket on waking, and an open one keeps Neon's compute awake.
    #: Local development, the tests and the tick keep the pool.
    db_null_pool: bool = False

    @field_validator("database_url")
    @classmethod
    def _asyncpg(cls, url: str) -> str:
        return asyncpg_url(url)

    # Any localhost port: Vite moves to 5174, 5175… whenever one is taken, and
    # a fixed list turns that into a CORS failure that looks like a dead API.
    # Localhost, and the private ranges a phone on the same Wi-Fi arrives from.
    cors_origin_regex: str = (
        r"http://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+"
        r"|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+):\d+"
    )


    # ── sign-in (spec/in-progress/sign-in.md) ────────────────────────────────
    #: The Web application client ID from Google Cloud. Public by design — it
    #: ships inside the page — so it is configuration, not a secret. The client
    #: *secret* is not used at all: the ID-token flow never exchanges a code.
    google_client_id: str = ""
    #: Who may CREATE an account. A comma-separated list, or `*` for anyone
    #: with a verified Google email. An existing user always signs in.
    allowed_emails: str = ""
    #: The model key is server-wide, so an open door is an open tab. Past the
    #: turn limit the agent stops talking for the day and every other route
    #: keeps working — the ledger never goes down over a budget.
    daily_turn_limit: int = 100
    daily_signup_limit: int = 20
    #: The first run's answers, which the chat's limit does not see — screen 3
    #: needs a dozen at most, so forty is room for retries and edits, not a
    #: second chat (spec/done/onboarding-goals.md § A turn).
    onboarding_turn_limit: int = 40

    # ── the MCP server and its OAuth (spec/work-sync.md) ─────────────────────
    #: Where this server is reached from outside — the OAuth issuer, and the
    #: base of the `/mcp` resource URL claude.ai is told about. On Vercel this
    #: is the API project's HTTPS address; locally the dev port.
    public_url: str = "http://localhost:8001"
    #: Where the app is served, for the page that asks the person to approve a
    #: client. The consent screen is part of the app, so it reuses sign-in.
    app_url: str = "http://localhost:5173"
    #: An access token's life. The routine refreshes quietly, so short is free.
    mcp_access_hours: int = 24
    #: A refresh token's life, renewed on every use; a routine that runs daily
    #: never sees it lapse, one left alone for three months has to be re-added.
    mcp_refresh_days: int = 90

    # How much conversation the model is given, and when it gets compacted.
    # Tuning knobs rather than decisions: a bigger window is a better-informed
    # model and a bigger bill, and the right trade differs per model.
    # `chat_window` is the floor a compaction folds back to; `chat_fold_at` is
    # the ceiling the tail is allowed to reach first. Folding in batches keeps
    # the message list append-only in between, which is what a provider's
    # prompt cache rewards. spec/done/prompt-layout.md.
    chat_window: int = 20
    chat_fold_at: int = 40
    #: Word budget for the rolling summary. It is sent once per turn, so this
    #: is cheap; too small and each rewrite has to throw history away.
    chat_summary_words: int = 200

    # Read only by app/llm.py. Switching vendor or model is these lines — the
    # provider, the model, the provider's key — and nothing else: the seam
    # note there says why. Anthropic since 2026-10-11 (spec/llm-provider.md);
    # OpenAI is `LLM_PROVIDER=openai` with `LLM_MODEL=gpt-6-luna`.
    llm_provider: str = "anthropic"       # anthropic | openai
    # Claude Haiku 5.5: the cheap, fast, tool-calling tier — the job Luna did.
    # Its default effort is medium, the level the chat eval settled on.
    llm_model: str = "claude-haiku-5-5"
    # Anthropic's cap on one answer. Thinking counts against it, so it is far
    # above any reply this app writes: a turn's text is a line or two.
    llm_max_tokens: int = 16000
    # How hard the model thinks per call — the agent's, and the default for
    # every other call. **"medium"**, measured 2026-10-10 on the chat eval
    # (spec/done/chat-quality.md): the same day said three times, on the
    # same code, both efforts side by side — medium passed 95.1% of cases and
    # 97.9% of turns, none 93.8% and 97.5%. It costs ~0.3 s at the median and
    # ~2.7 s at p90 (4.7 s / 11.9 s against 4.4 s / 9.2 s) and ~70% more output
    # tokens — about ₹0.0015 a turn. It was "none" from 2026-09-15, when a
    # three-prompt check found no gain; the eval's 79 cases found one — on Luna;
    # rerun the eval on Haiku before trusting the same number there.
    llm_effort: str = "medium"
    # How long one model call may take before it is retried. The SDK's own
    # default is ten minutes: one hung request held an eval turn for 611 s
    # (2026-10-10), which in the app is ten minutes of spinner. A turn's
    # calls take 2-20 s; ninety leaves room for a slow one.
    llm_timeout_seconds: float = 90
    # The nightly categoriser is a second call with its own prompt, so its
    # model and effort move on their own — and medium is measured there: +5 to
    # +8 points over none on the same rows (spec/in-progress/categorise.md
    # § Verified), for one call a night. Empty model means the agent's.
    categorise_model: str = ""
    categorise_effort: str = "medium"
    openai_api_key: str = ""
    anthropic_api_key: str = ""


@lru_cache
def settings() -> Settings:
    return Settings()
