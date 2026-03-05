from openai import OpenAI

client = OpenAI(
    base_url="https://api.jiekou.ai/openai",
    api_key="sk_qC61Zova4QrK5o6TQeKvPdpMkI2XSTUK2HXxqZlSCNg",
)

model      = "claude-sonnet-4-20250514"
max_tokens = 4096
stream     = True

# 系统提示（可自行修改）
system_prompt = "You are a helpful assistant. Please respond in the same language as the user."

# 对话历史（自动维护上下文）
history = [{"role": "system", "content": system_prompt}]

print("=" * 50)
print(f"  AI 对话助手  |  模型: {model}")
print("  输入 'exit' 或 'quit' 退出")
print("  输入 'clear' 清空对话历史")
print("=" * 50)
print()

while True:
    try:
        user_input = input("你: ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\n再见！")
        break

    if not user_input:
        continue

    if user_input.lower() in ("exit", "quit", "退出"):
        print("再见！")
        break

    if user_input.lower() in ("clear", "清空"):
        history = [{"role": "system", "content": system_prompt}]
        print("--- 对话历史已清空 ---\n")
        continue

    # 将用户消息加入历史
    history.append({"role": "user", "content": user_input})

    print("AI: ", end="", flush=True)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=history,
            max_tokens=max_tokens,
            stream=stream,
        )

        assistant_reply = ""

        if stream:
            for chunk in response:
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    if hasattr(delta, "content") and delta.content:
                        print(delta.content, end="", flush=True)
                        assistant_reply += delta.content
        else:
            assistant_reply = response.choices[0].message.content
            print(assistant_reply, end="")

        print("\n")  # 换行

        # 将 AI 回复也存入历史，以便下一轮使用
        history.append({"role": "assistant", "content": assistant_reply})

    except Exception as e:
        print(f"\n[错误] {e}\n")
        # 出错时把刚才加入的用户消息移除，避免历史污染
        history.pop()