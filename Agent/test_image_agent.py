import sys
import json
from image_agent import execute_tool_call

def main():
    if len(sys.argv) < 2:
        print("用法: python test_image_agent.py <image_path>")
        sys.exit(1)

    image_path = sys.argv[1]
    tool_call = {
        "function": {
            "name": "classify_image",
            "arguments": json.dumps({"image_path": image_path, "topk": 3}, ensure_ascii=False)
        }
    }

    result = execute_tool_call(tool_call)
    try:
        parsed = json.loads(result)
        print(json.dumps(parsed, ensure_ascii=False, indent=2))
    except Exception:
        print(result)

if __name__ == '__main__':
    main()
