from zhipuai import ZhipuAI
import os
from dotenv import load_dotenv

load_dotenv()

client = ZhipuAI(
    api_key=os.getenv("ZHIPU_API_KEY")
)

response = client.chat.completions.create(
    model="glm-4-flash",
    messages=[
        {
            "role": "user",
            "content": "今天有什么AI新闻"
        }
    ],
    tools=[
        {
            "type": "web_search",
            "web_search": {
                "enable": True
            }
        }
    ]
)

print(response)