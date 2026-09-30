"""
扩展 LoRA 训练数据集
- 种子数据 + 模板扩展 → 目标 2000 条
- 合并已有 extra_seed.jsonl
- 输出: lora_data/dataset.jsonl
"""

import os
import sys
import json
import random
import hashlib

if sys.platform == 'win32':
    try: sys.stdout.reconfigure(encoding='utf-8')
    except: pass

# =========================
# 1. 种子数据
# =========================

SEEDS = [
    # survival
    ("冬天如何避免冻死？", "优先制作保暖石并靠近火源，夜间保持火堆燃烧，避免长时间暴露在户外。"),
    ("理智值太低怎么办？", "食用太妃糖或蝴蝶松饼，在科学机器旁解锁新配方恢复理智。"),
    ("夜晚怎么安全生存？", "必须携带火把或提灯，避免进入完全黑暗区域防止查理攻击。"),
    ("食物不够怎么办？", "优先制作肉丸（肉+浆果+填充物），性价比最高。"),
    ("如何防止掉San？", "避免黑暗、怪物威压和洞穴环境，佩戴高礼帽或贝雷帽。"),
    # building
    ("基地应该建在哪里？", "优先靠近草、树枝、浆果群和猪王道路附近，方便资源循环。"),
    ("科技路线怎么走？", "优先科学机器->炼金引擎->冰箱->烹饪锅体系。"),
    ("冰箱有什么用？", "延长食物保质期，是中期生存核心建筑。"),
    ("如何高效采集资源？", "使用铲子移植草和浆果，建立可再生资源区。"),
    # combat
    ("如何无伤打蜘蛛？", "引一只后走A攻击，避免被群殴。"),
    ("巨鹿怎么打？", "引到空旷区域风筝攻击，避免建筑被破坏。"),
    ("狗群怎么处理？", "提前准备长矛和护甲，引导到牛群或猪人帮忙。"),
    ("影怪怎么打？", "保持移动，逐个击破，避免被包围。"),
    # resources
    ("齿轮怎么获取？", "击杀发条生物或探索遗迹获得。"),
    ("蜂蜜怎么稳定获取？", "建立蜂箱并定期采集。"),
    ("噩梦燃料怎么刷？", "降低理智值后击杀影怪掉落。"),
    ("木头怎么循环？", "种植常青树并使用树枝循环采集。"),
    # advanced
    ("如何刷影怪？", "主动降低理智值至低于15%触发影怪刷新。"),
    ("WX-78怎么玩？", "优先吃齿轮提升属性，并避免潮湿环境。"),
    ("温蒂怎么玩？", "利用阿比盖尔辅助战斗，降低正面冲突压力。"),
    ("如何极限生存？", "限制资源获取并依靠最小生存链维持生命。"),
]

PREFIX = [
    "新手", "中期", "高端玩家", "冬季", "洞穴探险",
    "联机模式中", "单人模式下", "WX-78使用时", "温蒂玩家",
]

SUFFIX = [
    "怎么处理？", "怎么办？", "生存策略是什么？", "最佳方法是什么？",
    "有什么技巧？", "需要注意什么？",
]

# 额外生成用的饥荒核心词库
NOUNS = ["保暖石", "太妃糖", "肉丸", "冰箱", "烹饪锅", "长矛", "木甲",
         "齿轮", "影怪", "蜘蛛", "巨鹿", "蜂箱", "噩梦燃料", "高礼帽",
         "贝雷帽", "火把", "猪王", "牛群", "矿灯帽", "草甲"]
ACTIONS = ["制作", "获取", "击败", "建造", "采集", "应对", "处理", "使用"]


def expand(instruction, output):
    results = []
    for p in PREFIX:
        for s in SUFFIX:
            results.append((f"{p}{instruction}{s}", output))
    return results


def generate_extra(count):
    """随机组合生成更多问答"""
    extra = []
    for _ in range(count):
        n1, n2 = random.sample(NOUNS, 2)
        act = random.choice(ACTIONS)
        q = f"饥荒{n1}和{n2}有什么区别？{act}哪个更好？"
        a = f"【阶段1 准备】了解{n1}和{n2}的属性与获取方式。\n【阶段2 执行】根据当前季节和资源情况选择{act}优先级。\n【阶段3 应急】如果{n1}不可用，用{n2}替代。"
        extra.append((q, a))
    return extra


# =========================
# 主逻辑
# =========================

def build_expanded(target=2000):
    BASE = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = os.path.join(BASE, 'lora_data')
    os.makedirs(DATA_DIR, exist_ok=True)

    seen = set()

    def add(ins, out):
        h = hashlib.md5(ins.encode()).hexdigest()
        if h not in seen:
            seen.add(h)
            return True
        return False

    all_pairs = []

    # 1. 种子扩展
    pool = []
    for ins, out in SEEDS:
        pool.append((ins, out))
        pool.extend(expand(ins, out))
    random.shuffle(pool)
    for ins, out in pool:
        if add(ins, out):
            all_pairs.append({"instruction": ins, "output": out})

    # 2. 加载旧有的 extra_seed.jsonl（41条高级问答）
    extra_path = os.path.join(DATA_DIR, 'extra_seed.jsonl')
    if os.path.exists(extra_path):
        with open(extra_path, 'r', encoding='utf-8') as f:
            for line in f:
                p = json.loads(line.strip())
                if p.get('instruction') and p.get('output'):
                    if add(p['instruction'], p['output']):
                        all_pairs.append(p)
        print(f"Loaded extra_seed: {len(all_pairs)} total so far")

    # 3. 随机组合补到 target
    if len(all_pairs) < target:
        extra = generate_extra(target - len(all_pairs))
        for ins, out in extra:
            if add(ins, out):
                all_pairs.append({"instruction": ins, "output": out})

    random.shuffle(all_pairs)
    all_pairs = all_pairs[:target]

    # 写 JSONL
    out_path = os.path.join(DATA_DIR, 'dataset.jsonl')
    with open(out_path, 'w', encoding='utf-8') as f:
        for p in all_pairs:
            f.write(json.dumps(p, ensure_ascii=False) + '\n')

    print(f"Done: {len(all_pairs)} pairs ({target} target)")
    print(f"  Seed expand: ~200 | extra_seed: 41+ | random: ~{target-241}")
    print(f"  {out_path}")


if __name__ == '__main__':
    target = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    build_expanded(target)
