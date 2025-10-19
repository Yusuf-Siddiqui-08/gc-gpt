from typing import List, Dict, Optional, Literal
from ollama import Client
import os

ROLE_USER: Literal["user"] = "user"
ROLE_ASSISTANT: Literal["assistant"] = "assistant"

OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY")

class ChatAgent:
    def __init__(self, model: str, messages: Optional[List[Dict[str, str]]] = None):
        self.model: str = model
        self.messages: List[Dict[str, str]] = list(messages) if messages is not None else []
        self.client: Client = Client(
            host="https://ollama.com",
            headers={'Authorization': 'Bearer ' + OLLAMA_API_KEY}
        )

    def _make_message(self, role: Literal["user", "assistant"], content: str) -> Dict[str, str]:
        return {"role": role, "content": content}

    def _append_message(self, role: Literal["user", "assistant"], content: str) -> None:
        self.messages.append(self._make_message(role, content))

    def send_message(self, message: str) -> Optional[Dict]:
        self._append_message(ROLE_USER, message)
        response = self.client.chat(model=self.model, messages=self.messages)
        # response is a dict with 'message' key containing 'content'
        assistant_content: str = response.get("message", {}).get("content", "")
        self._append_message(ROLE_ASSISTANT, assistant_content)
        return response

    def get_last_assistant_message(self) -> Optional[str]:
        for msg in reversed(self.messages):
            if msg.get("role") == ROLE_ASSISTANT:
                return msg.get("content")
        return None

    @staticmethod
    def filter_relevant_messages(query: str, messages: List[Dict[str, str]], model: str, max_messages: int = 10) -> List[Dict[str, str]]:
        """
        Filter messages to only include those relevant to the current query.
        Uses the LLM to determine relevance based on topic similarity.
        """
        if not messages:
            return []

        # If we have few messages, just return them all
        if len(messages) <= 4:
            return messages

        # Group messages into conversation pairs (user + assistant response)
        conversation_pairs = []
        i = 0
        while i < len(messages):
            if messages[i].get('role') == 'user':
                pair = {'user': messages[i].get('content', ''), 'index': i}
                if i + 1 < len(messages) and messages[i + 1].get('role') == 'assistant':
                    pair['assistant'] = messages[i + 1].get('content', '')
                    i += 2
                else:
                    i += 1
                if pair.get('user'):
                    conversation_pairs.append(pair)
            else:
                i += 1

        if not conversation_pairs:
            return messages

        # Always include the most recent conversation pair for continuity
        # This ensures follow-up questions maintain context
        relevant_indices = set()
        if conversation_pairs:
            relevant_indices.add(len(conversation_pairs) - 1)

        # Use LLM to score relevance of earlier conversation pairs
        client = Client(
            host="https://ollama.com",
            headers={'Authorization': 'Bearer ' + OLLAMA_API_KEY}
        )
        for idx, pair in enumerate(conversation_pairs[:-1]):  # Skip the last one (already added)
            # Create a more precise prompt to check relevance
            relevance_prompt = f"""Analyze if this previous conversation is relevant to the current query.

Current query: "{query}"

Previous conversation:
User: {pair.get('user', '')}
Assistant: {pair.get('assistant', '')[:300]}...

Question: Is the previous conversation about the same topic or directly related topics that would help answer the current query?

Important: 
- Consider if they discuss the same concepts, subjects, or build upon each other
- Don't mark as relevant if they are completely different topics
- "Trigonometric functions" and "polynomial functions" are related (both are types of mathematical functions)
- "Why is the sky blue" and "trigonometric functions" are NOT related

Answer ONLY with 'yes' or 'no'."""

            try:
                relevance_check = client.chat(
                    model=model,
                    messages=[{"role": "user", "content": relevance_prompt}]
                )
                answer = relevance_check.get("message", {}).get("content", "").strip().lower()

                if 'yes' in answer:
                    relevant_indices.add(idx)
            except Exception:
                # If relevance check fails, include the message to be safe
                relevant_indices.add(idx)

        # Sort indices to maintain chronological order
        sorted_indices = sorted(list(relevant_indices))

        # Limit to max_messages most recent relevant pairs
        if len(sorted_indices) > max_messages:
            sorted_indices = sorted_indices[-max_messages:]

        # Reconstruct filtered message list from relevant pairs
        filtered_messages = []
        for idx in sorted_indices:
            if idx < len(conversation_pairs):
                pair = conversation_pairs[idx]
                filtered_messages.append({"role": "user", "content": pair.get('user', '')})
                if pair.get('assistant'):
                    filtered_messages.append({"role": "assistant", "content": pair.get('assistant', '')})

        return filtered_messages if filtered_messages else messages
