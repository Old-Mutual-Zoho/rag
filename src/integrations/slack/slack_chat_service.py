from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


class SlackChatService:
    def __init__(self, token: str, channel: str):
        self.client = WebClient(token=token)
        self.channel = channel

    def send_message(self, chat_id: str, message: str, sender: str = "agent"):
        try:
            response = self.client.chat_postMessage(
                channel=self.channel,
                text=f"[{sender}] {message}"
            )
            return response.data
        except SlackApiError as e:
            raise Exception(f"Slack API error: {e.response['error']}")

    def receive_messages(self, chat_id: str):
        try:
            response = self.client.conversations_history(
                channel=self.channel,
                limit=10
            )
            return response.data.get('messages', [])
        except SlackApiError as e:
            raise Exception(f"Slack API error: {e.response['error']}")
