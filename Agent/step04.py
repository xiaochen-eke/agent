import requests
import json
import os

ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY")
def call_zhipu_api(messages, model="glm-4-flash"):
    url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

    headers = {
        "Authorization": ZHIPU_API_KEY,
        "Content-Type": "application/json"
    }

    data = {
        "model": model,
        "messages": messages,
        "temperature": 1.0
    }

    response = requests.post(url, headers=headers, json=data)

    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"API调用失败: {response.status_code}, {response.text}")

messages = [{"role": "system", "content": open("Agent.md", encoding="utf-8").read()}]

while True:
    user_input = input("你: ")
    if user_input.lower() in ["退出", "exit", "quit"]:
        break
    messages.append({"role": "user", "content": user_input})
    while True:
        result = call_zhipu_api(messages)
        assistant_reply = result['choices'][0]['message']['content']
        messages.append({"role": "assistant", "content": assistant_reply})
       
        if assistant_reply.startswith("完成:"):
            print(f"助手: {assistant_reply.strip().split('完成:')[1].strip()}")
            break    

        command = assistant_reply.strip().split("命令:")[1].strip()
        command_result = os.popen(command).read()
        content = f"执行完毕 {command_result}"
        messages.append({"role": "user", "content": content})
