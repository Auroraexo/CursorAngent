import os
import requests

url = os.getenv("OPENAI_API_BASE", "https://api.edgefn.net/v1") + "/chat/completions"
headers = {
    "Authorization": os.getenv("OPENAI_API_KEY", ""),
    "Content-Type": "application/json"
}
data = {
    "model": "GLM-5",
    "messages": [{"role": "user", "content": "Hello, how are you?"}]
}

response = requests.post(url, headers=headers, json=data)
print(response.json())