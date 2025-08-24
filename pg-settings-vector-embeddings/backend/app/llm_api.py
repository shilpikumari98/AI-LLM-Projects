# backend/app/llm_api.py

import requests

OPENAI_API_KEY = "your_api_key"
OPENAI_API_BASE = "https://api.sambanova.ai/v1"
OPENAI_MODEL_NAME = "Llama-4-Maverick-17B-128E-Instruct"

def ask_setting_via_llm(question: str) -> str | None:
    # Prompt to get SETTINGS info from Google:
    system_prompt = (
        "You are an expert PostgreSQL assistant. "
        "Whenever a user asks about a PostgreSQL setting, look up the setting details via Google search. "
        "Gather information such as its purpose, usage, default and recommended values, effect on performance/security, "
        "and any real-world recommendations from DBAs or community forums. "
        "Provide a rich, concise answer summarizing the setting and citing best practices whenever possible."
    )
    url = f"{OPENAI_API_BASE}/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "stream": False,
        "model": OPENAI_MODEL_NAME,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"{system_prompt}\n\n{question}"}
                ]
            }
        ]
    }
    try:
        response = requests.post(url, headers=headers, json=data, timeout=20)
        response.raise_for_status()
        resp_json = response.json()
        # Assuming typical OpenAI format response
        answer = resp_json['choices'][0]['message']['content'].strip()
        return answer
    except Exception as e:
        print(f"LLM API error: {e}")
        return None
