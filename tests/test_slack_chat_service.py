from src.integrations.slack.slack_chat_service import SlackChatService


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeSlackClient:
    def __init__(self):
        self.messages = []
        self._counter = 0

    def _next_ts(self):
        self._counter += 1
        return str(self._counter)

    def chat_postMessage(self, channel: str, text: str, thread_ts: str = None):
        ts = self._next_ts()
        payload = {"channel": channel, "text": text, "ts": ts}
        if thread_ts:
            payload["thread_ts"] = thread_ts
        self.messages.append(payload)
        return FakeResponse(payload)

    def conversations_history(self, channel: str, limit: int = 200):
        # Slack history is newest first.
        return FakeResponse({"messages": list(reversed(self.messages))[:limit]})

    def conversations_replies(self, channel: str, ts: str, limit: int = 200):
        root = None
        replies = []
        for msg in self.messages:
            if msg.get("ts") == ts and not msg.get("thread_ts"):
                root = msg
            elif msg.get("thread_ts") == ts:
                replies.append(msg)
        ordered = [root] + replies if root else replies
        return FakeResponse({"messages": ordered[:limit]})


def test_send_message_uses_session_thread():
    fake = FakeSlackClient()
    svc = SlackChatService(token="x", channel="C1", client=fake)

    out = svc.send_message(chat_id="sess-1", message="hello from client", sender="client")

    assert out["chat_id"] == "sess-1"
    assert out["thread_ts"] == "1"
    assert len(fake.messages) == 2
    assert fake.messages[0]["text"].startswith("[system][chat_id:sess-1]")
    assert fake.messages[1]["thread_ts"] == "1"
    assert fake.messages[1]["text"] == "[client][chat_id:sess-1] hello from client"


def test_receive_messages_returns_only_session_thread_messages():
    fake = FakeSlackClient()
    svc = SlackChatService(token="x", channel="C1", client=fake)

    svc.send_message(chat_id="sess-1", message="first", sender="client")
    svc.send_message(chat_id="sess-1", message="reply", sender="agent")
    svc.send_message(chat_id="sess-2", message="other-session", sender="client")

    msgs = svc.receive_messages("sess-1")

    assert len(msgs) == 2
    assert all(m["chat_id"] == "sess-1" for m in msgs)
    assert [m["sender"] for m in msgs] == ["client", "agent"]
    assert all("[chat_id:sess-1]" in (m["text"] or "") for m in msgs)
    assert all("message" in m for m in msgs)


def test_unprefixed_human_reply_is_detected_as_agent():
    fake = FakeSlackClient()
    svc = SlackChatService(token="x", channel="C1", client=fake)
    svc.send_message(chat_id="sess-9", message="client hello", sender="client")

    # Simulate a human agent typing directly in Slack thread (no prefix).
    fake.messages.append(
        {
            "channel": "C1",
            "text": "Sure, I can help with that.",
            "ts": "99",
            "thread_ts": "1",
            "user": "UAGENT1",
        }
    )

    msgs = svc.receive_messages("sess-9")
    direct = [m for m in msgs if m["ts"] == "99"][0]
    assert direct["sender"] == "agent"
    assert direct["message"] == "Sure, I can help with that."
