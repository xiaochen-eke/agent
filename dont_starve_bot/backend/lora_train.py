"""
《饥荒》游戏攻略领域 LoRA 微调脚本

用法:
  1. 生成数据集:  python backend/build_lora_dataset.py
  2. 开始训练:    python backend/lora_train.py
  3. 快速测试:    python backend/lora_train.py --fast        (1 epoch, 100 steps)
  4. 生产训练:    python backend/lora_train.py --model Qwen/Qwen2.5-1.5B

数据集: backend/lora_data/dataset.jsonl
模型输出: backend/lora_model/
"""

import os
import sys

# ---- 必须在 import huggingface_hub 之前设置 ----
# 绕过 Windows 代理 + 使用国内镜像
os.environ["no_proxy"] = "*"
os.environ["NO_PROXY"] = "*"
# 使用 HuggingFace 国内镜像（hf-mirror.com）
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
import json
import argparse
import warnings
from pathlib import Path

if sys.platform == 'win32':
    try: sys.stdout.reconfigure(encoding='utf-8')
    except: pass

warnings.filterwarnings("ignore")

# ======================
# 确保路径正确
# ======================
BASE_DIR = Path(__file__).parent
LORA_DATA_DIR = BASE_DIR / "lora_data"
LORA_MODEL_DIR = BASE_DIR / "lora_model"
DATASET_PATH = LORA_DATA_DIR / "dataset.jsonl"


def check_prerequisites():
    """检查依赖和数据集"""
    missing = []
    try:
        import torch
    except ImportError:
        missing.append("torch")
    try:
        import transformers
    except ImportError:
        missing.append("transformers")
    try:
        import peft
    except ImportError:
        missing.append("peft")
    try:
        import datasets
    except ImportError:
        missing.append("datasets")

    if missing:
        print(f"❌ 缺少依赖: {', '.join(missing)}")
        print(f"   安装命令: pip install {' '.join(missing)}")
        return False

    if not DATASET_PATH.exists():
        print(f"❌ 数据集不存在: {DATASET_PATH}")
        print(f"   请先运行: python backend/build_lora_dataset.py")
        return False

    return True


def load_and_prepare_dataset(tokenizer, max_length=256):
    """加载 JSONL 数据并 tokenize"""
    from datasets import load_dataset

    dataset = load_dataset("json", data_files=str(DATASET_PATH))["train"]

    def preprocess(example):
        text = f"### 问题: {example['instruction']}\n### 回答: {example['output']}"
        tokens = tokenizer(
            text,
            truncation=True,
            padding="max_length",
            max_length=max_length,
        )
        tokens["labels"] = tokens["input_ids"].copy()
        return tokens

    dataset = dataset.map(preprocess, desc="Tokenizing")
    return dataset


def train(args):
    """主训练流程"""
    import torch
    from transformers import (
        AutoTokenizer,
        AutoModelForCausalLM,
        TrainingArguments,
        Trainer,
    )
    from peft import LoraConfig, get_peft_model

    # ======================
    # 1. 加载模型和分词器
    # ======================
    print(f"\n{'='*60}")
    print(f"🎮 饥荒攻略领域 LoRA 微调")
    print(f"{'='*60}")
    print(f"   基座模型: {args.model}")
    print(f"   数据集:   {DATASET_PATH}")
    print(f"   输出目录: {LORA_MODEL_DIR}")
    print(f"   Epochs:   {args.epochs}")
    print(f"   学习率:   {args.lr}")
    print(f"{'='*60}\n")

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    print("📦 加载模型...")
    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        torch_dtype=torch.float16 if args.fp16 else torch.float32,
        device_map="auto" if torch.cuda.is_available() else None,
    )

    # ======================
    # 2. LoRA 配置
    # ======================
    lora_config = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        bias="none",
        task_type="CAUSAL_LM",
    )

    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # ======================
    # 3. 加载并处理数据
    # ======================


    # ======================
    # 4. 训练参数
    # ======================
    training_args = TrainingArguments(
        output_dir=str(LORA_MODEL_DIR),
        per_device_train_batch_size=args.batch_size,
        num_train_epochs=args.epochs,
        learning_rate=args.lr,
        logging_steps=max(1, len(dataset) // args.batch_size // 5),
        save_steps=max(1, len(dataset) // args.batch_size // 2),
        save_total_limit=2,
        fp16=args.fp16 and torch.cuda.is_available(),
        gradient_accumulation_steps=args.grad_accum,
        warmup_steps=50,
        report_to="none",  # 不上传 wandb
        remove_unused_columns=True,
    )

    # ======================
    # 5. Trainer
    # ======================
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        processing_class=tokenizer,
    )

    # ======================
    # 6. 训练
    # ======================
    print("\n🚀 开始 LoRA 训练...\n")
    trainer.train()

    # ======================
    # 7. 保存
    # ======================
    os.makedirs(LORA_MODEL_DIR, exist_ok=True)
    model.save_pretrained(str(LORA_MODEL_DIR))
    tokenizer.save_pretrained(str(LORA_MODEL_DIR))

    # 写一个标记文件，pipeline 通过它判断 LoRA 是否可用
    info = {
        "base_model": args.model,
        "dataset_size": len(dataset),
        "lora_r": args.lora_r,
        "trained": True,
    }
    with open(LORA_MODEL_DIR / "lora_info.json", "w") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)

    print(f"\n✅ LoRA 微调完成！模型保存至: {LORA_MODEL_DIR}")
    print(f"   💡 重启后端即可自动加载 LoRA 权重")


def main():
    parser = argparse.ArgumentParser(description="🎮 饥荒攻略 LoRA 微调")

    parser.add_argument("--model", default="Qwen/Qwen2.5-0.5B",
                        help="基座模型 (默认: Qwen/Qwen2.5-0.5B)")
    parser.add_argument("--epochs", type=int, default=1,
                        help="训练轮数 (默认: 1)")
    parser.add_argument("--batch-size", type=int, default=2,
                        help="批次大小 (默认: 2)")
    parser.add_argument("--lr", type=float, default=2e-4,
                        help="学习率 (默认: 2e-4)")
    parser.add_argument("--max-length", type=int, default=512,
                        help="最大 token 长度 (默认: 512)")
    parser.add_argument("--lora-r", type=int, default=8,
                        help="LoRA rank (默认: 8)")
    parser.add_argument("--lora-alpha", type=int, default=16,
                        help="LoRA alpha (默认: 16)")
    parser.add_argument("--lora-dropout", type=float, default=0.05,
                        help="LoRA dropout (默认: 0.05)")
    parser.add_argument("--fp16", action="store_true",
                        help="启用混合精度训练 (需要GPU，--force-cpu 时自动禁用)")
    parser.add_argument("--grad-accum", type=int, default=2,
                        help="梯度累积步数 (默认: 2)")
    parser.add_argument("--fast", action="store_true",
                        help="快速测试模式: 1 epoch")
    parser.add_argument("--force-cpu", action="store_true",
                        help="强制使用 CPU（自动禁用 fp16）")

    args = parser.parse_args()

    # 默认启用 fp16，--force-cpu 时自动禁用
    if args.force_cpu:
        args.fp16 = False
    elif '--fp16' not in sys.argv:
        args.fp16 = True

    if args.fast:
        args.epochs = 1

    if not check_prerequisites():
        sys.exit(1)

    # CPU 模式
    if args.force_cpu:
        os.environ["CUDA_VISIBLE_DEVICES"] = ""
        args.fp16 = False

    train(args)


if __name__ == "__main__":
    main()
