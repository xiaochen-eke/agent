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

# 使用示例
messages = [
    {"role": "user", "content": "你好"}
]

result = call_zhipu_api(messages)
print(result['choices'][0]['message']['content'])

