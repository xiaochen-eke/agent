"""
从知识库 .md 文件自动生成 LoRA 三段式训练数据集

输出格式:
{
  "instruction": "冬季怎么生存？",
  "output": "【阶段1 准备】...\n【阶段2 执行】...\n【阶段3 应急】..."
}
"""

import os
import sys
import json
import re
import random
from typing import List, Dict

if sys.platform == 'win32':
    try: sys.stdout.reconfigure(encoding='utf-8')
    except: pass


# ========== 从 .md 提取实体 ==========

def extract_entities(md_text: str) -> List[Dict]:
    """从 markdown 提取 ## 条目及其属性，自动跳过标题/分类行"""
    # 要跳过的标题类（不是真正的实体）
    SKIP_PATTERNS = [
        r'烹饪.*配方.*所有.*菜肴',
        r'低级.*菜肴.*炉灶',
        r'高级.*菜肴.*烹饪锅',
        r'基础.*工具',
        r'高级.*工具',
        r'防具',
        r'基础.*建筑',
        r'工业.*建筑',
        r'防御.*设施',
        r'魔法.*装备',
        r'魔法.*物品',
        r'炼金.*物品',
        r'建筑.*配方',
        r'工具.*配方',
        r'装备.*配方',
        r'防具.*配方',
        r'核心.*区域',
        r'工具类',
        r'食物.*链',
        r'核心.*机制',
        r'推荐.*战斗.*装备',
        r'武器类',
        r'科技类',
        r'防具类',
        r'工具类',
        r'食物类',
        r'资源类',
        r'全角色',
        r'食物.*属性.*速查',
    ]
    items = []
    sections = re.split(r'\n##\s+', md_text)
    for sec in sections:
        lines = sec.strip().split('\n')
        name = lines[0].strip() if lines else ''
        if not name or name.startswith('#'):
            continue
        # 跳过标题类
        skip = False
        for pat in SKIP_PATTERNS:
            if re.search(pat, name):
                skip = True
                break
        if skip:
            continue
        props = {}
        for line in lines[1:]:
            m = re.match(r'-\s*([^：:]+)[：:]\s*(.+)', line)
            if m:
                props[m.group(1).strip()] = m.group(2).strip()
        if props:
            items.append({'name': name, 'props': props})
    return items


# ========== 三段式模板 ==========

def make_output(stage1: str, stage2: str, stage3: str) -> str:
    return f'【阶段1 准备】{stage1}\n【阶段2 执行】{stage2}\n【阶段3 应急】{stage3}'


# ========== 种子数据 ==========

def generate_seed_pairs() -> List[Dict]:
    pairs = []
    pairs.append({'instruction': '饥荒理智值怎么管理？', 'output': make_output(
        '了解理智值机制：Sanity 0-200。检查身上有没有恢复理智的物品（花环、太妃糖、蝴蝶松饼）。确保营火燃料充足。',
        '睡袋睡觉一次回满 是最快方式。吃蝴蝶松饼+100理智、太妃糖+15理智。戴高礼帽+6.7/分钟。靠营火挂机、近猪王+0 5/秒。采花临时+5。',
        '理智低于25%且影怪出现：立刻点火把或营火 影怪会消失。不要战斗 影怪免疫物理。没睡袋就吃熟食硬撑。平时避开黑暗和沼泽掉理智的源头。',
    )})
    pairs.append({'instruction': '饥荒饥饿值怎么管理？', 'output': make_output(
        'Hunger 0-150。每天准备至少100饱食度的食物。建冰箱防腐。前期肉丸过渡 后期上肉汤和火龙果派。',
        '正常活动每分钟-0.6 奔跑-1.5/秒。肉丸+62.5饱食度最划算。建食物来源：农场+养蜂+杀蜘蛛换大肉。干燥架做腊肉长期保存。',
        '饥饿低于0每秒掉0.25血 很快死。紧急时 生吃怪物肉也比饿死强。杀蝴蝶吃翅膀活命。食物腐坏了临时吃一口拖时间 赶紧找别的。',
    )})
    pairs.append({'instruction': '饥荒冬季怎么生存？', 'output': make_output(
        '秋季就要囤物资：木头至少2组、食物储备3000+饱食度（腊肉和肉丸）。做冬帽（树枝x2+蜘蛛丝x6）和保温石。多建几个精炼火堆围圈。',
        '全程穿冬帽+保温石 体温低于10度立刻点火。每天维护火堆 检查食物库存 采集冬草做保暖衣。地下洞穴冬天最安全 可下去采矿。',
        '黑手党Deerclops第10天左右出现！提前在基地外建陷阱。听到怪声立刻远离基地 它拆建筑极快。没准备好就躲地下洞穴避战。冻到濒死：先点火回温再吃东西回血 顺序不能反！',
    )})
    pairs.append({'instruction': '饥荒肉丸怎么做？', 'output': make_output(
        '任意肉1份（小肉/怪物肉/大肉）+ 填充物3个（树枝、蔬菜、浆果、冰块）。确保有烹饪锅（科学机器解锁：铁矿x3+石头x1+树枝x6）。',
        '材料全放进烹饪锅 等20秒。属性：+62.5饱食 +12.5理智。性价比全游戏最高 前期批量做。注意：怪物肉最多放1个 否则变怪物千层面！',
        '没烹饪锅时生吃 小肉生吃回12.5饱食。打完蜘蛛捡怪物肉别扔 4个怪物肉喂猪王变1大肉 做大肉丸！',
    )})
    pairs.append({'instruction': '新手前期应该做什么？', 'output': make_output(
        '第1天：砍树采草挖石头 做斧头+镐子。黄昏前必须建营火。第2-3天：沿地图边缘探路 标记牛群猪村矿区。不要打蜘蛛巢先标记。',
        '第4-5天：建科学机器（金子x1+木头x4+石头x4）解锁背包铲子烹饪锅。选址建基地（靠近兔子和牛群）。建冰箱+烹饪锅+干燥架。开始种菜养蜂。',
        '晚上迷路：举火把看地图找虫洞跳回。遇蜘蛛群别硬打 引到牛群/猪人那边。血量低于30立刻吃食物回血。理智低摘花硬撑。翻车后尸体在死亡点 先回去补血再捡。',
    )})
    return pairs


# ========== 按类别生成 ==========

def generate_pairs(md_path: str, fname: str) -> List[Dict]:
    with open(md_path, 'r', encoding='utf-8') as f:
        text = f.read()

    pairs = []
    base = fname.lower()

    # 食谱类
    if '食谱' in fname or 'recipe' in base:
        for item in extract_entities(text):
            props_str = '；'.join(f'{k}：{v}' for k, v in item.get('props', {}).items())
            pairs.append({'instruction': f'{item["name"]}怎么做？', 'output': make_output(
                f'查看{item["name"]}配方：{props_str}。备齐所有材料。',
                f'把所有材料放入烹饪锅 等待完成。{item["name"]}效果：{props_str}。按当前需求选择食用时机。',
                f'没锅时生吃看效果 扣血多别吃。材料不全找替代品或先去采集。',
            )})

    # 怪物类
    elif '怪物' in fname:
        for item in extract_entities(text):
            props_str = '；'.join(f'{k}：{v}' for k, v in item.get('props', {}).items())
            pairs.append({'instruction': f'{item["name"]}怎么打？', 'output': make_output(
                f'了解{item["name"]}属性：{props_str}。准备对应武器和防具。',
                f'用风筝打法保持距离。利用{item["name"]}弱点攻击。注意躲避特殊技能。',
                f'血量低于30立刻逃跑别贪刀。死了不掉装备 先去捡尸体。打不过就引到牛群/猪人帮忙。',
            )})

    # 角色类
    elif '角色' in fname:
        for item in extract_entities(text):
            if '全角色' in item.get('name', ''):
                continue
            props_str = '；'.join(f'{k}：{v}' for k, v in item.get('props', {}).items())
            pairs.append({'instruction': f'{item["name"]}有什么特点？怎么玩？', 'output': make_output(
                f'了解{item["name"]}属性：{props_str}。认清角色定位和优势。',
                f'利用{item["name"]}特长发挥最大作用。根据三围和技能选择合适玩法路线。',
                f'遇到角色弱点时保守应对 利用道具弥补短板。新手建议先玩威尔逊熟悉机制。',
            )})

    # 配方类
    elif '配方' in fname or '合成' in fname:
        for item in extract_entities(text):
            props_str = '；'.join(f'{k}：{v}' for k, v in item.get('props', {}).items())
            pairs.append({'instruction': f'{item["name"]}怎么合成？', 'output': make_output(
                f'准备材料：{props_str}。确认对应工作台已建造且科技等级已解锁。',
                f'在正确的制作台点击合成。检查背包是否有足够空间存放成品。',
                f'缺材料时检查是否有替代品 或先去采集关键资源。工具断了用铁砧修复。',
            )})

    # 基地类
    elif '基地' in fname:
        snippet = text[:300].strip()
        pairs.append({'instruction': '饥荒基地怎么布局？', 'output': make_output(
            f'规划基地分区：{snippet}。选址靠牛群兔子 远离蜘蛛巢沼泽。',
            '先建核心区（冰箱+烹饪锅+科学机器）再建防御区（围墙+陷阱）最后扩张区（农场+蜂箱+干燥架）。',
            '基地着火立刻灭火器或扑打。被怪物入侵引出基地再打。核心建筑被拆优先重建冰箱和火堆。',
        )})

    # 季节类
    elif '季节' in fname or 'season' in base:
        for season in ['春季', '夏季', '秋季', '冬季']:
            if season in text:
                pat = re.compile(rf'##\s+{season}.*?(?=\n##\s+[春夏秋冬]|\Z)', re.DOTALL)
                m = pat.search(text)
                snippet = (m.group(0) if m else text[:250]).strip()[:400]
                tips = {'春季': '做雨伞防潮 蜘蛛青蛙大量繁殖 趁机刷资源','夏季': '冰箱+冰火+西瓜帽 避开中午烈日 防野火','秋季': '囤木头食物 准备冬季 制作冬帽保温衣','冬季': '保暖+食物+防Boss 地下洞穴最安全'}
                pairs.append({'instruction': f'饥荒{season}怎么生存？', 'output': make_output(
                    f'{snippet}。{season}到来前检查库存。',
                    f'{tips.get(season, "")}。按攻略要点逐条执行。',
                    f'遇到季节灾难立刻用应对手段 不要硬扛。{season}结束前开始为下一季准备。',
                )})

    # 基础知识/机制类
    elif 'game_basics' in base or '基础' in fname:
        for stat in ['理智值', '饥饿值', '血量']:
            if stat in text:
                pat = re.compile(rf'###\s+\d+\.\s*{stat}.*?(?=###\s+\d+\.|\Z)', re.DOTALL)
                m = pat.search(text)
                if m:
                    snippet = m.group(0).strip()[:300]
                    restores = {'理智值': '睡觉>熟食>花环>营火','饥饿值': '肉丸>肉汤>火龙果派','血量': '烤肉>急救包>休息'}
                    pairs.append({'instruction': f'饥荒{stat}怎么管理？', 'output': make_output(
                        f'{snippet}。了解{stat}正常范围和消耗速度。',
                        f'恢复优先级：{restores.get(stat, "")}。维持{stat}在安全线以上。',
                        f'{stat}触底时停下手头一切 优先抢救。用最高效的恢复手段 不要抠门。',
                    )})

    # 生存/战术类
    elif 'survival' in base or 'advanced' in base or '生存' in fname:
        # 去掉 markdown 标题
        clean = re.sub(r'^#.*\n', '', text[:400]).strip()[:300]
        pairs.append({'instruction': '饥荒前期怎么快速发育？', 'output': make_output(
            f'{clean}。第1天做工具建营火 第3天探图标记资源 第5天建科学机器 第7天进化基地。',
            '时间节点：探图→建基地→科技升级→食物链→防御。每个阶段先做最优先的事。',
            '翻车不要慌 尸体保留 先去补血再捡。晚上没火把立刻做 没材料钻虫洞传送。',
        )})

    # 兜底
    if not pairs:
        title = os.path.splitext(fname)[0]
        pairs.append({'instruction': f'饥荒{title}相关信息', 'output': make_output(
            f'{text[:250]}。查看{title}的前置条件和所需资源。',
            f'按{title}攻略步骤依次执行操作。',
            f'遇到意外先回退到安全状态再重试 不要贪进度。',
        )})

    return pairs


# ========== 主程序 ==========

def build_dataset(kb_dir: str = None, output_path: str = None):
    if kb_dir is None:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        kb_dir = os.path.join(base, 'knowledge_base')
    if output_path is None:
        out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lora_data')
        os.makedirs(out_dir, exist_ok=True)
        output_path = os.path.join(out_dir, 'dataset.jsonl')

    all_pairs = generate_seed_pairs()
    seen = {p['instruction'] for p in all_pairs}

    # 加载额外种子数据（extra_seed.jsonl）
    extra_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lora_data', 'extra_seed.jsonl')
    if os.path.exists(extra_path):
        extra_count = 0
        with open(extra_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    p = json.loads(line.strip())
                    if p.get('instruction') and p.get('output'):
                        all_pairs.append({'instruction': p['instruction'], 'output': p['output']})
                        extra_count += 1
                except json.JSONDecodeError:
                    continue
        print(f'   加载额外种子数据: {extra_count} 条')

    if os.path.isdir(kb_dir):
        for fname in sorted(os.listdir(kb_dir)):
            if not fname.endswith('.md'): continue
            pairs = generate_pairs(os.path.join(kb_dir, fname), fname)
            for p in pairs:
                if p['instruction'] not in seen:
                    seen.add(p['instruction'])
                    all_pairs.append(p)

    random.shuffle(all_pairs)

    with open(output_path, 'w', encoding='utf-8') as f:
        for p in all_pairs:
            # 确保不超 512 tokens 约 1000 字
            p['output'] = p['output'][:1000]
            f.write(json.dumps(p, ensure_ascii=False) + '\n')

    print(f'Done: {len(all_pairs)} 条三段式问答')
    print(f'  Seed: {len(generate_seed_pairs())}  KB: {len(all_pairs)-len(generate_seed_pairs())}')
    print(f'  {output_path}')
    return output_path


if __name__ == '__main__':
    build_dataset()
