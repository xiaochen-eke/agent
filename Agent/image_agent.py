# import os
# import sys
# import json
# import requests
# from PIL import Image
# import torch
# import torchvision.transforms as T
# import torchvision.models as models

# ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY")
# # 可通过环境变量覆盖模型名
# DEFAULT_MODEL = os.getenv('ZHIPU_MODEL') or os.getenv('MODEL_NAME') or 'glm-4-flash'

# def call_zhipu_api(messages, model=None, tools=None):
#     # 选择模型：函数参数优先，其次环境变量 DEFAULT_MODEL
#     model = model or DEFAULT_MODEL
#     url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
#     headers = {
#         "Authorization": ZHIPU_API_KEY,
#         "Content-Type": "application/json"
#     }
#     data = {"model": model, "messages": messages, "temperature": 1.0}
#     if tools:
#         data["tools"] = tools
#         data["tool_choice"] = "auto"
#     response = requests.post(url, headers=headers, json=data)
#     if response.status_code == 200:
#         return response.json()
#     else:
#         raise Exception(f"API调用失败: {response.status_code}, {response.text}")


# # ---- Tool 定义：图片分类 ----
# TOOLS = [
#     {
#         "type": "function",
#         "function": {
#             "name": "classify_image",
#             "description": "对给定本地图片路径进行分类，返回 topk 预测（索引、概率和可选标签）。",
#             "parameters": {
#                 "type": "object",
#                 "properties": {
#                     "image_path": {"type": "string", "description": "本地图片路径"},
#                     "topk": {"type": "integer", "description": "返回前 K 个预测", "default": 3}
#                 },
#                 "required": ["image_path"]
#             }
#         }
#     }
# ]


# _MODEL = None
# _DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# def _load_model():
#     global _MODEL
#     if _MODEL is None:
#         # 使用预训练 ResNet50
#         _MODEL = models.resnet50(weights=models.ResNet50_Weights.IMAGENET1K_V2)
#         _MODEL.eval()
#         _MODEL.to(_DEVICE)
#     return _MODEL


# def _ensure_imagenet_labels(path="imagenet_classes.txt"):
#     if os.path.exists(path):
#         with open(path, encoding='utf-8') as f:
#             return [l.strip() for l in f.readlines()]
#     # 尝试从远端获取
#     url = "https://raw.githubusercontent.com/pytorch/hub/master/imagenet_classes.txt"
#     try:
#         r = requests.get(url, timeout=10)
#         r.raise_for_status()
#         labels = r.text.strip().splitlines()
#         with open(path, "w", encoding="utf-8") as f:
#             f.write("\n".join(labels))
#         return labels
#     except Exception:
#         return None


# def _preprocess_image(image_path):
#     img = Image.open(image_path).convert('RGB')
#     preprocess = T.Compose([
#         T.Resize(256),
#         T.CenterCrop(224),
#         T.ToTensor(),
#         T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
#     ])
#     return preprocess(img).unsqueeze(0).to(_DEVICE)


# def execute_tool_call(tool_call):
#     func_name = tool_call["function"]["name"]
#     func_args = json.loads(tool_call["function"]["arguments"])

#     if func_name == "classify_image":
#         image_path = func_args.get("image_path")
#         topk = int(func_args.get("topk", 3))
#         if not os.path.exists(image_path):
#             return f"错误：找不到图片路径 {image_path}"
#         try:
#             model = _load_model()
#             input_tensor = _preprocess_image(image_path)
#             with torch.no_grad():
#                 out = model(input_tensor)
#                 probs = torch.nn.functional.softmax(out[0], dim=0)
#                 top_probs, top_idxs = torch.topk(probs, topk)
#                 labels = _ensure_imagenet_labels()
#                 results = []
#                 for p, idx in zip(top_probs.cpu().numpy(), top_idxs.cpu().numpy()):
#                     label = labels[idx] if labels and idx < len(labels) else str(int(idx))
#                     results.append({"label": label, "index": int(idx), "prob": float(p)})
#                 return json.dumps({"image_path": image_path, "predictions": results}, ensure_ascii=False)
#         except Exception as e:
#             return f"分类失败：{e}"

#     return f"未知工具: {func_name}"


# PERSONA_CONFIG = {
#     "buddy":   ("小A - 你的电脑管家",     "Agent/Agent_v2.md",           "拜拜！有需要随时找我哦~ 👋"),
#     "teacher": ("王老师 - 计算机教学助手", "Agent/persona_teacher_v2.md",  "下课！回去记得复习今天的知识点哦~"),
#     "strict":  ("SysAdmin - 系统管理员",   "Agent/persona_strict_v2.md",   "会话结束。"),
# }


# def main():
#     persona_name = "buddy"
#     args = sys.argv[1:]
#     for i, arg in enumerate(args):
#         if arg == "--persona" and i + 1 < len(args):
#             persona_name = args[i + 1]

#     if persona_name not in PERSONA_CONFIG:
#         print(f"错误：未知的人设 '{persona_name}'")
#         sys.exit(1)

#     display_name, persona_file, goodbye_msg = PERSONA_CONFIG[persona_name]
#     if not os.path.exists(persona_file):
#         print(f"错误：人设文件 '{persona_file}' 不存在")
#         sys.exit(1)

#     messages = [{"role": "system", "content": open(persona_file, encoding="utf-8").read()}]

#     print("=" * 60)
#     print(f"🤖 Image Agent 已加载：{display_name}")
#     print(f"   当前驱动模型: {DEFAULT_MODEL}")
#     print(f"   工具模式: 原生 Function Calling（{len(TOOLS)} 个工具）")
#     print("=" * 60)

#     while True:
#         user_input = input("\n你: ")
#         if user_input.lower() in ["退出", "exit", "quit"]:
#             print(f"Agent: {goodbye_msg}")
#             break
#         messages.append({"role": "user", "content": user_input})

#         while True:
#             try:
#                 result = call_zhipu_api(messages, tools=TOOLS)
#             except Exception as e:
#                 print(f"[ERROR] API 调用异常: {e}")
#                 break

#             if not result.get("choices"):
#                 print("[ERROR] API 返回异常：choices 为空")
#                 break

#             msg = result["choices"][0]["message"]

#             # 模型选择调用工具
#             if msg.get("tool_calls"):
#                 messages.append(msg)
#                 for tc in msg["tool_calls"]:
#                     print(f"[Tool] 调用 {tc['function']['name']}({tc['function']['arguments']})")
#                     tool_result = execute_tool_call(tc)
#                     messages.append({
#                         "role": "tool",
#                         "tool_call_id": tc.get("id"),
#                         "content": tool_result
#                     })
#                 continue

#             # 直接文本回复
#             if msg.get("content"):
#                 messages.append(msg)
#                 print(f"Agent: {msg['content']}")
#                 break

#             print("[ERROR] 模型返回异常：content 和 tool_calls 均为空")
#             break


# if __name__ == '__main__':
#     main()


# # import os
# # import sys
# # import json
# # import requests
# # from PIL import Image
# # import torch
# # import torchvision.transforms as T
# # import torchvision.models as models

# # # ============================================================


# # # 简单的 .env 加载器（不会覆盖已存在的环境变量）
# # def _load_dotenv(path=None):
# #     if path is None:
# #         path = os.path.join(os.path.dirname(__file__), '.env')
# #     if not os.path.exists(path):
# #         return
# #     try:
# #         with open(path, encoding='utf-8') as f:
# #             for raw in f:
# #                 line = raw.strip()
# #                 if not line or line.startswith('#'):
# #                     continue
# #                 if '=' not in line:
# #                     continue
# #                 k, v = line.split('=', 1)
# #                 k = k.strip()
# #                 v = v.strip().strip('"').strip("'")
# #                 if k and k not in os.environ:
# #                     os.environ[k] = v
# #     except Exception:
# #         pass


# # # 尝试从 Agent 目录下加载 .env（如果存在）
# # _load_dotenv()
# # # 基础配置切换（优先使用环境变量）
# # ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY")
# # # DEEPSEEK API key 可由环境变量指定，或者回退到 ZHIPU_API_KEY（你提供的 key）
# # DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY") or ZHIPU_API_KEY

# # # API URL：优先使用 ZHIPU_API_BASE 或 DEEPSEEK_API_URL 环境变量，否则回退到 open.bigmodel.cn 的默认路径
# # DEEPSEEK_API_URL = os.getenv("ZHIPU_API_BASE") or os.getenv("DEEPSEEK_API_URL") or "https://open.bigmodel.cn/api/paas/v4/chat/completions"

# # # 3. 指定你要调用的模型名称
# # MODEL_NAME = "DeepSeek-V4-Pro"


# # def call_zhipu_api(messages, model=MODEL_NAME, tools=None):
# #     """
# #     为了完全不改动你底下的 main() 循环，函数名依然保持 call_zhipu_api，
# #     但底层请求已经完全无缝切换到了 DeepSeek 的通道。
# #     """
# #     headers = {
# #         "Authorization": f"Bearer {DEEPSEEK_API_KEY}" if DEEPSEEK_API_KEY else "",
# #         "Content-Type": "application/json"
# #     }
# #     data = {"model": model, "messages": messages, "temperature": 1.0}
# #     if tools:
# #         data["tools"] = tools
# #         data["tool_choice"] = "auto"
# #     # 请求发送给选定的服务网关（打印用于调试）
# #     print(f"[DEBUG] 请求代理变量: HTTP_PROXY={os.environ.get('HTTP_PROXY')} HTTPS_PROXY={os.environ.get('HTTPS_PROXY')} ")
# #     print(f"[DEBUG] 使用 API URL: {DEEPSEEK_API_URL}")
# #     response = requests.post(DEEPSEEK_API_URL, headers=headers, json=data)
# #     if response.status_code == 200:
# #         return response.json()
# #     else:
# #         raise Exception(f"API调用失败: {response.status_code}, {response.text}")


# # # ---- Tool 定义：图片分类 ----
# # TOOLS = [
# #     {
# #         "type": "function",
# #         "function": {
# #             "name": "classify_image",
# #             "description": "对给定本地图片路径进行分类，返回 topk 预测（索引、概率和可选标签）。",
# #             "parameters": {
# #                 "type": "object",
# #                 "properties": {
# #                     "image_path": {"type": "string", "description": "本地图片路径"},
# #                     "topk": {"type": "integer", "description": "返回前 K 个预测", "default": 3}
# #                 },
# #                 "required": ["image_path"]
# #             }
# #         }
# #     }
# # ]


# # _MODEL = None
# # _DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# # def _load_model():
# #     global _MODEL
# #     if _MODEL is None:
# #         # 使用预训练 ResNet50
# #         _MODEL = models.resnet50(weights=models.ResNet50_Weights.IMAGENET1K_V2)
# #         _MODEL.eval()
# #         _MODEL.to(_DEVICE)
# #     return _MODEL


# # def _ensure_imagenet_labels(path="imagenet_classes.txt"):
# #     if os.path.exists(path):
# #         with open(path, encoding='utf-8') as f:
# #             return [l.strip() for l in f.readlines()]
# #     # 尝试从远端获取
# #     url = "https://raw.githubusercontent.com/pytorch/hub/master/imagenet_classes.txt"
# #     try:
# #         r = requests.get(url, timeout=10)
# #         r.raise_for_status()
# #         labels = r.text.strip().splitlines()
# #         with open(path, "w", encoding="utf-8") as f:
# #             f.write("\n".join(labels))
# #         return labels
# #     except Exception:
# #         return None


# # def _preprocess_image(image_path):
# #     img = Image.open(image_path).convert('RGB')
# #     preprocess = T.Compose([
# #         T.Resize(256),
# #         T.CenterCrop(224),
# #         T.ToTensor(),
# #         T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
# #     ])
# #     return preprocess(img).unsqueeze(0).to(_DEVICE)


# # def execute_tool_call(tool_call):
# #     func_name = tool_call["function"]["name"]
# #     func_args = json.loads(tool_call["function"]["arguments"])

# #     if func_name == "classify_image":
# #         image_path = func_args.get("image_path")
# #         topk = int(func_args.get("topk", 3))
# #         if not os.path.exists(image_path):
# #             return f"错误：找不到图片路径 {image_path}"
# #         try:
# #             model = _load_model()
# #             input_tensor = _preprocess_image(image_path)
# #             with torch.no_grad():
# #                 out = model(input_tensor)
# #                 probs = torch.nn.functional.softmax(out[0], dim=0)
# #                 top_probs, top_idxs = torch.topk(probs, topk)
# #                 labels = _ensure_imagenet_labels()
# #                 results = []
# #                 for p, idx in zip(top_probs.cpu().numpy(), top_idxs.cpu().numpy()):
# #                     label = labels[idx] if labels and idx < len(labels) else str(int(idx))
# #                     results.append({"label": label, "index": int(idx), "prob": float(p)})
# #                 return json.dumps({"image_path": image_path, "predictions": results}, ensure_ascii=False)
# #         except Exception as e:
# #             return f"分类失败：{e}"

# #     return f"未知工具: {func_name}"


# # PERSONA_CONFIG = {
# #     "buddy":   ("小A - 你的电脑管家",     "Agent/Agent_v2.md",           "拜拜！有需要随时找我哦~ 👋"),
# #     "teacher": ("王老师 - 计算机教学助手", "Agent/persona_teacher_v2.md",  "下课！回去记得复习今天的知识点哦~"),
# #     "strict":  ("SysAdmin - 系统管理员",   "Agent/persona_strict_v2.md",   "会话结束。"),
# # }


# # def main():
# #     persona_name = "buddy"
# #     args = sys.argv[1:]
# #     for i, arg in enumerate(args):
# #         if arg == "--persona" and i + 1 < len(args):
# #             persona_name = args[i + 1]

# #     if persona_name not in PERSONA_CONFIG:
# #         print(f"错误：未知的人设 '{persona_name}'")
# #         sys.exit(1)

# #     display_name, persona_file, goodbye_msg = PERSONA_CONFIG[persona_name]
# #     if not os.path.exists(persona_file):
# #         print(f"错误：人设文件 '{persona_file}' 不存在")
# #         sys.exit(1)

# #     messages = [{"role": "system", "content": open(persona_file, encoding="utf-8").read()}]

# #     print("=" * 60)
# #     print(f"🤖 Image Agent 已加载：{display_name}")
# #     print(f"   当前驱动模型: {MODEL_NAME}")
# #     print(f"   工具模式: 原生 Function Calling（{len(TOOLS)} 个工具）")
# #     print("=" * 60)

# #     while True:
# #         user_input = input("\n你: ")
# #         if user_input.lower() in ["退出", "exit", "quit"]:
# #             print(f"Agent: {goodbye_msg}")
# #             break
# #         messages.append({"role": "user", "content": user_input})

# #         while True:
# #             try:
# #                 # 这里的传参会默认使用头部的 MODEL_NAME 变量
# #                 result = call_zhipu_api(messages, tools=TOOLS)
# #             except Exception as e:
# #                 print(f"[ERROR] API 调用异常: {e}")
# #                 break

# #             if not result.get("choices"):
# #                 print("[ERROR] API 返回异常：choices 为空")
# #                 break

# #             msg = result["choices"][0]["message"]

# #             # 模型选择调用工具
# #             if msg.get("tool_calls"):
# #                 messages.append(msg)
# #                 for tc in msg["tool_calls"]:
# #                     print(f"[Tool] 调用 {tc['function']['name']}({tc['function']['arguments']})")
# #                     tool_result = execute_tool_call(tc)
# #                     messages.append({
# #                         "role": "tool",
# #                         "tool_call_id": tc.get("id"),
# #                         "content": tool_result
# #                     })
# #                 continue

# #             # 直接文本回复
# #             if msg.get("content"):
# #                 messages.append(msg)
# #                 print(f"Agent: {msg['content']}")
# #                 break

# #             print("[ERROR] 模型返回异常：content 和 tool_calls 均为空")
# #             break


# # if __name__ == '__main__':
# #     main()


import requests
import json
import os
import shutil
from PIL import Image
from torchvision import models, transforms
from torchvision.models import ResNet50_Weights
import torch
from dotenv import load_dotenv

# 从 .env 加载环境变量（含 ZHIPU_API_KEY）
load_dotenv()

# ==============================================
# ================= 你必须修改这3项 =================
# ==============================================
# 1. 你的智谱API KEY（已改为从 .env 读取，勿在此硬编码）
ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY")
if not ZHIPU_API_KEY:
    raise SystemExit("未设置 ZHIPU_API_KEY，请在 Agent/.env 中配置后重试。")

# 2. imagenet_classes.txt 本地完整路径
CLASS_FILE_PATH = "D:\\Class materials\\Big_model\\test\\Agent\\imagenet_classes.txt"

# 3. 【分类后图片的总根文件夹】（自动创建类别子文件夹）
SAVE_BASE_DIR = "D:\\Class materials\\Big_model\\test\\Agent\\photos"
# ==============================================

# 加载模型（只加载一次，提速）
model = models.resnet50(weights=ResNet50_Weights.DEFAULT)
model.eval()

# 图片预处理
preprocess = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.224, 0.224, 0.225]),
])

# 读取分类标签
with open(CLASS_FILE_PATH, encoding="utf-8") as f:
    categories = [s.strip() for s in f.readlines()]

# ===================== 智谱API调用 =====================
def call_zhipu_api(messages, model="glm-4v-flash", tools=None):
    url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    headers = {
        "Authorization": ZHIPU_API_KEY,
        "Content-Type": "application/json"
    }
    data = {
        "model": model,
        "messages": messages,
        "temperature": 0.1
    }
    if tools:
        data["tools"] = tools
        data["tool_choice"] = "auto"
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"API调用失败：{response.status_code}, {response.text}")

# ===================== 核心：批量图片分类 + 移动 =====================
def batch_classify_images(folder_path):
    if not os.path.isdir(folder_path):
        return f"❌ 文件夹不存在：{folder_path}"

    # 支持的图片格式
    exts = (".jpg", ".jpeg", ".png", ".bmp")
    images = [f for f in os.listdir(folder_path) if f.lower().endswith(exts)]

    if not images:
        return "✅ 文件夹内没有图片"

    success = 0
    total = len(images)

    for img_file in images:
        img_path = os.path.join(folder_path, img_file)
        try:
            # 打开图片
            img = Image.open(img_path).convert("RGB")
            tensor = preprocess(img).unsqueeze(0)

            # 识别
            with torch.no_grad():
                output = model(tensor)
            _, index = output.max(1)
            label = categories[index[0]]

            # 创建分类文件夹
            target_dir = os.path.join(SAVE_BASE_DIR, label)
            os.makedirs(target_dir, exist_ok=True)

            # 【直接移动，不是复制！】
            target_path = os.path.join(target_dir, img_file)
            shutil.move(img_path, target_path)

            success += 1
        except Exception as e:
            print(f"⚠️ 处理失败：{img_file}，原因：{str(e)}")

    return f"✅ 批量分类完成\n总图片：{total} 张\n成功移动：{success} 张\n所有图片已移动到：{SAVE_BASE_DIR}"

# ===================== Function Calling 工具定义 =====================
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "batch_classify_images",
            "description": "输入一个文件夹路径，自动批量分类里面所有图片，并直接移动到对应类别文件夹",
            "parameters": {
                "type": "object",
                "properties": {
                    "folder_path": {
                        "type": "string",
                        "description": "图片所在的文件夹路径，例如 C:/Photos/我的图片"
                    }
                },
                "required": ["folder_path"]
            }
        }
    }
]

# ===================== 工具执行器 =====================
def execute_tool_call(tool_call):
    func_name = tool_call["function"]["name"]
    args = json.loads(tool_call["function"]["arguments"])
    if func_name == "batch_classify_images":
        return batch_classify_images(args["folder_path"])
    return f"未知工具：{func_name}"

# ===================== 主程序 =====================
messages = [{"role": "system", "content": "你是图片批量分类助手，用户输入文件夹路径，你就调用工具批量分类并移动所有图片。"}]

print("=" * 65)
print("🤖 批量图片分类助手（Function Calling）")
print("✅ 功能：输入文件夹路径 → 自动分类所有图片 → 直接移动")
print(f"📂 分类结果保存到：{SAVE_BASE_DIR}")
print("=" * 65)

while True:
    user_input = input("\n你：")
    if user_input.lower() in ["退出", "exit", "quit"]:
        print("✅ 程序退出！")
        break

    messages.append({"role": "user", "content": user_input})

    while True:
        res = call_zhipu_api(messages, tools=TOOLS)
        msg = res["choices"][0]["message"]

        if msg.get("tool_calls"):
            messages.append(msg)
            for tc in msg["tool_calls"]:
                print("[工具] 正在批量分类图片...")
                result = execute_tool_call(tc)
                messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})
            continue

        if msg.get("content"):
            messages.append(msg)
            print(f"AI：{msg['content']}")
            break