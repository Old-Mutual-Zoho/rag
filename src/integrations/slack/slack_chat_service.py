try:
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError
except ModuleNotFoundError:  # pragma: no cover - handled in __init__
    WebClient = None  # type: ignore[assignment]
    SlackApiError = Exception  # type: ignore[assignment]


class SlackChatService:
    def __init__(self, token: str, channel: str, client: WebClient = None):
        if client is None and WebClient is None:
            raise ImportError("slack_sdk is required to use SlackChatService without a custom client")
        self.client = client or WebClient(token=token)  # type: ignore[misc]
        self.channel = channel
        self._thread_cache = {}

    def _chat_tag(self, chat_id: str) -> str:
        return f"[chat_id:{chat_id}]"

    def _message_prefix(self, sender: str, chat_id: str) -> str:
        return f"[{sender}]{self._chat_tag(chat_id)}"

    def _find_thread_ts(self, chat_id: str):
        cached = self._thread_cache.get(chat_id)
        if cached:
            return cached
        history = self.client.conversations_history(channel=self.channel, limit=200)
        tag = self._chat_tag(chat_id)
        for msg in history.data.get("messages", []):
            text = msg.get("text") or ""
            # Root message has ts and no parent thread_ts.
            if tag in text and not msg.get("thread_ts"):
                ts = msg.get("ts")
                if ts:
                    self._thread_cache[chat_id] = ts
                    return ts
        return None

    def _ensure_thread(self, chat_id: str) -> str:
        existing = self._find_thread_ts(chat_id)
        if existing:
            return existing
        root = self.client.chat_postMessage(
            channel=self.channel,
            text=f"[system]{self._chat_tag(chat_id)} Session opened",
        )
        ts = root.data.get("ts")
        if not ts:
            raise Exception("Slack API error: missing_thread_ts")
        self._thread_cache[chat_id] = ts
        return ts

    def send_message(self, chat_id: str, message: str, sender: str = "agent"):
        try:
            thread_ts = self._ensure_thread(chat_id)
            response = self.client.chat_postMessage(
                channel=self.channel,
                thread_ts=thread_ts,
                text=f"{self._message_prefix(sender, chat_id)} {message}",
            )
            data = response.data
            data["thread_ts"] = thread_ts
            data["chat_id"] = chat_id
            return data
        except SlackApiError as e:
            raise Exception(f"Slack API error: {self._extract_slack_error(e)}")

    def receive_messages(self, chat_id: str):
        try:
            thread_ts = self._find_thread_ts(chat_id)
            if not thread_ts:
                return []
            response = self.client.conversations_replies(channel=self.channel, ts=thread_ts, limit=200)
            out = []
            for msg in response.data.get("messages", []):
                if msg.get("ts") == thread_ts:
                    continue
                text = msg.get("text") or ""
                out.append(
                    {
                        "chat_id": chat_id,
                        "thread_ts": thread_ts,
                        "ts": msg.get("ts"),
                        "text": text,
                        "sender": self._extract_sender(text),
                        "user": msg.get("user"),
                        "bot_id": msg.get("bot_id"),
                    }
                )
            return out
        except SlackApiError as e:
            raise Exception(f"Slack API error: {self._extract_slack_error(e)}")

    @staticmethod
    def _extract_sender(text: str) -> str:
        if text.startswith("[") and "]" in text:
            return text[1 : text.find("]")]
        return "unknown"

    @staticmethod
    def _extract_slack_error(exc: Exception) -> str:
        response = getattr(exc, "response", None)
        if isinstance(response, dict):
            return str(response.get("error", "unknown_error"))
        try:
            return str(response["error"])  # type: ignore[index]
        except Exception:
            return str(exc)
