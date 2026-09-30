import os
import json
import shutil
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(
    api_key=os.getenv("ZHIPU_API_KEY"),
    base_url="https://open.bigmodel.cn/api/paas/v4"
)

# 1. 定义我们的工具：移动文件
def move_file(source: str, destination: str):
    """
    将文件或文件夹从 source 移动到 destination。
    如果目标路径包含不存在的文件夹，会自动创建。
    """
    try:
        # 确保目标目录存在
        dest_dir = os.path.dirname(destination)
        if dest_dir and not os.path.exists(dest_dir):
            os.makedirs(dest_dir)
        shutil.move(source, destination)
        return f"成功将 {source} 移动到 {destination}"
    except Exception as e:
        return f"移动文件失败: {str(e)}"

# 2. 将工具描述成 LLM 能理解的 JSON Schema (OpenAI 函数格式)
tools = [
    {
        "type": "function",
        "function": {
            "name": "move_file",
            "description": "移动一个文件或文件夹到指定位置。如果目标路径中的文件夹不存在，会自动创建。",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "description": "需要移动的源文件路径，例如 'a.txt' 或 '/home/user/docs/a.txt'"
                    },
                    "destination": {
                        "type": "string",
                        "description": "目标路径，可以是文件路径或目录路径。例如 'archive/a.txt' 或 'archive/'"
                    }
                },
                "required": ["source", "destination"]
            }
        }
    }
]

# 3. 核心 Agent 循环
def run_agent(user_input: str):
    messages = [
        {"role": "system", "content": "你是一个文件管理助手，可以使用 move_file 函数来移动文件。请根据用户的指令调用函数。"},
        {"role": "user", "content": user_input}
    ]

    # 循环直到 LLM 不再需要调用工具
    while True:
        response = client.chat.completions.create(
            model="glm-4-flash",  # 或其他支持 function calling 的模型
            messages=messages,
            tools=tools,
            tool_choice="auto"  # 让模型自己决定是否调用工具
        )

        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls

        # 如果模型认为任务完成，不再调用工具，则退出循环
        if not tool_calls:
            # 最后输出模型的自然语言回复
            print("Agent 最终回复:", response_message.content)
            break

        # 否则，执行工具调用
        # 将模型的工具调用请求加入消息历史
        messages.append(response_message)

        # 遍历每一个工具调用（大多数情况只有一个）
        for tool_call in tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)

            print(f"🔧 调用工具: {function_name}, 参数: {function_args}")

            # 执行工具函数
            if function_name == "move_file":
                function_response = move_file(**function_args)
            else:
                function_response = f"错误：未知工具 {function_name}"

            # 将工具执行结果封装成一条消息，告诉模型“工具返回了什么”
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": function_name,
                "content": function_response
            })

# 4. 测试我们的手动 Agent
if __name__ == "__main__":
    # 请先确保当前目录下有 test.txt，以及 archive 文件夹（移动时会自动创建，但最好有个测试环境）
    run_agent("把 test.txt 移动到 archive 文件夹里")