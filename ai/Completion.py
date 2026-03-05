from openai import OpenAI

client = OpenAI(
    api_key="sk_qC61Zova4QrK5o6TQeKvPdpMkI2XSTUK2HXxqZlSCNg",
    base_url="https://api.jiekou.ai/openai"
)

response = client.chat.completions.create(
    model="claude-sonnet-4-20250514",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"}
    ],
    max_tokens=4096,
    temperature=0.7
)

print(response.choices[0].message.content)