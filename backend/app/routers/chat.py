from fastapi import APIRouter
from pydantic import BaseModel
import os
import requests

router = APIRouter(prefix="/chat", tags=["chat"])

class ChatReq(BaseModel):
    message: str

@router.post("/")
def chat(req: ChatReq):
    try:
        api_key = os.getenv("GROQ_API_KEY")

        # 🔴 Check API key
        if not api_key:
            return {"response": "Error: GROQ_API_KEY not found in .env"}

        url = "https://api.groq.com/openai/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        data = {
    "model": "llama-3.1-8b-instant",
    "messages": [
        {"role": "user", "content": req.message}
    ]
}

        response = requests.post(url, headers=headers, json=data)

        result = response.json()

        # 🔍 DEBUG (check terminal)
        print("FULL RESPONSE:", result)  

        # ✅ Safe handling
        if "choices" in result:
            reply = result["choices"][0]["message"]["content"]
            return {"response": reply}
        else:
            return {"response": f"API Error: {result}"}

    except Exception as e:
        return {"response": f"Error: {str(e)}"}