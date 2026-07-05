"""
盲盒开箱系统
"""
import os, json, random, re
from io import BytesIO
from pathlib import Path
from datetime import datetime
from PIL import Image

BASE_DIR = Path(__file__).parent
INFO_DIR = BASE_DIR / "info"
LEVEL_DIR = BASE_DIR / "level"

from card_image import (get_level_image, find_attribute_icon, find_type_icon, composite_card)

# ========== PIL 图片缓存 ==========
_PIL_CACHE = {}  # {"path_str": PIL.Image对象(RGBA)}

def _pil_open(path):
    """带缓存的图片加载，返回RGBA副本"""
    key = str(path)
    if key not in _PIL_CACHE:
        _PIL_CACHE[key] = Image.open(path).convert('RGBA')
    return _PIL_CACHE[key].copy()

def _qq():
    """获取qq_bot_ws模块引用（优先__main__，避免模块双重加载）"""
    import sys
    if '__main__' in sys.modules and hasattr(sys.modules['__main__'], 'BOX_SESSIONS'):
        return sys.modules['__main__']
    import qq_bot_ws
    return qq_bot_ws

# ========== 盲盒开箱系统 ==========
def draw_mystery_box(characters: list, user_id: str = None, is_pity: bool = False) -> dict:
    """
    抽取一个盲盒（未开的盒子）
    返回: {"stars": 星级, "is_mystery": 是否黑色盲盒, "character": 角色对象(如果是黑色盲盒则为None)}
    
    参数:
        characters: 角色列表
        user_id: 用户ID（用于判断保底）
        is_pity: 是否触发保底
    """
    # 如果是保底抽卡，跳过黑色盲盒，直接生成3星
    if is_pity:
        # 保底必定出3星，并且是FES限定
        character = select_3star_character(characters, is_fes_pity=True)
        return {
            "stars": 3,
            "is_mystery": False,
            "character": character
        }
    
    # 先判断是否是黑色盲盒
    is_mystery = random.random() < _qq().MYSTERY_BOX_CHANCE
    
    if is_mystery:
        # 黑色盲盒概率（从配置读取）
        stars = random.choices([2, 3], weights=[_qq().MYSTERY_BOX_2STAR_PROB, _qq().MYSTERY_BOX_3STAR_PROB], k=1)[0]
        return {
            "stars": stars,
            "is_mystery": True,
            "character": None  # 黑色盲盒还没开，所以没有角色
        }
    else:
        # 正常盲盒概率（从配置读取）
        stars = random.choices([1, 2, 3], weights=[_qq().NORMAL_BOX_1STAR_PROB, _qq().NORMAL_BOX_2STAR_PROB, _qq().NORMAL_BOX_3STAR_PROB], k=1)[0]
        
        # 如果是3星，根据限定种类概率分配
        if stars == 3:
            character = select_3star_character(characters, is_fes_pity=False)
        else:
            # 1星或2星，按原逻辑抽取
            available = [c for c in characters if c["stars"] == stars]
            if available:
                character = random.choice(available)
            else:
                character = random.choice(characters)
        
        return {
            "stars": stars,
            "is_mystery": False,
            "character": character
        }


def select_3star_character(characters: list, is_fes_pity: bool = False) -> dict:
    """
    根据限定种类概率选择三星角色
    期間限定35%，フェス限定25%，其余三星40%
    如果是フェス保底，则必定返回フェス限定角色
    """
    # 获取所有三星角色
    all_3stars = [c for c in characters if c["stars"] == 3]
    if not all_3stars:
        return random.choice(characters)
    
    # 如果是フェス保底，直接返回フェス限定角色
    if is_fes_pity:
        fes_chars = [c for c in all_3stars if c.get("limit_type") == "フェス限定"]
        if fes_chars:
            return random.choice(fes_chars)
        # 如果没有フェス限定，返回任意三星
        return random.choice(all_3stars)
    
    # 按限定种类分类
    period_limited = [c for c in all_3stars if c.get("limit_type") == "期間限定"]
    fes_limited = [c for c in all_3stars if c.get("limit_type") == "フェス限定"]
    other_3stars = [c for c in all_3stars if c.get("limit_type") not in ["期間限定", "フェス限定"]]
    
    # 概率分配（从配置读取）
    categories = []
    weights = []
    
    if period_limited:
        categories.append(period_limited)
        weights.append(_qq().PERIOD_LIMIT_PROB)
    if fes_limited:
        categories.append(fes_limited)
        weights.append(_qq().FES_LIMIT_PROB)
    if other_3stars:
        categories.append(other_3stars)
        weights.append(_qq().OTHER_3STAR_PROB)
    
    if not categories:
        return random.choice(all_3stars)
    
    # 按权重选择类别，再从该类别中随机选择角色
    selected_category = random.choices(categories, weights=weights, k=1)[0]
    return random.choice(selected_category)


def apply_mutation(box_info: dict, characters: list) -> tuple:
    """
    对盲盒结果应用突变，并在突变后重新抽取对应星级的角色
    返回: (突变后的box_info, 是否发生突变, 突变描述)
    """
    if box_info["is_mystery"]:
        # 黑色盲盒不受突变影响
        return box_info, False, None
    
    original_stars = box_info["stars"]
    roll = random.random()
    new_stars = original_stars
    mutation_occurred = False
    mutation_text = None
    
    if original_stars == 1:
        if roll < _qq().MUTATION_1_TO_2:
            new_stars = 2
            mutation_occurred = True
            mutation_text = "1星→2星"
        elif roll > 1 - _qq().MUTATION_1_TO_3:
            new_stars = 3
            mutation_occurred = True
            mutation_text = "1星→3星"
    elif original_stars == 2:
        if roll < _qq().MUTATION_2_TO_3:
            new_stars = 3
            mutation_occurred = True
            mutation_text = "2星→3星"
    
    if mutation_occurred and new_stars != original_stars:
        box_info["stars"] = new_stars
        # 重新抽取对应新星级的角色
        available = [c for c in characters if c["stars"] == new_stars]
        if available:
            box_info["character"] = random.choice(available)
        else:
            box_info["character"] = random.choice(characters)
    
    return box_info, mutation_occurred, mutation_text


def get_mystery_box_image(stars: int) -> str:
    """获取盲盒图片路径（使用02图层作为盲盒封面）"""
    star_idx = stars - 1
    # 盲盒使用02图层
    filename = f"gacha_tmb_{star_idx:02d}_02.png"
    path = LEVEL_DIR / filename
    if path.exists():
        return str(path)
    
    # 如果02不存在，尝试用01（框）作为后备
    filename = f"gacha_tmb_{star_idx:02d}_01.png"
    path = LEVEL_DIR / filename
    if path.exists():
        return str(path)
    
    _qq().log_error(f"找不到图片: gacha_tmb_{star_idx:02d}_02")
    return None


def get_black_box_image() -> str:
    """获取黑色盲盒图片路径"""
    filename = "gacha_tmb_04_02.png"
    path = LEVEL_DIR / filename
    if path.exists():
        return str(path)
    _qq().log_error(f"找不到黑色图片: {filename}")
    return None


def create_box_card(box_info: dict, characters: list) -> bytes:
    """
    创建盲盒卡牌图片（未开的样子）
    对于黑色盲盒，使用gacha_tmb_04_02作为中心图
    对于3星卡，如果是フェス限定，使用gacha_tmb_03_02_b.png
    """
    stars = box_info["stars"]
    is_mystery = box_info.get("is_mystery", False)
    character = box_info.get("character", None)
    
    # 获取背景和框
    if is_mystery:
        # 黑色盲盒使用04_00和04_01
        bg_path = LEVEL_DIR / "gacha_tmb_04_00.png"
        frame_path = LEVEL_DIR / "gacha_tmb_04_01.png"
        center_path = LEVEL_DIR / "gacha_tmb_04_02.png"
    else:
        bg_path = get_level_image(stars, "bg")
        frame_path = get_level_image(stars, "frame")
        # 盲盒使用02图层作为中心
        star_idx = stars - 1
        
        # 判断是否是フェス限定3星
        is_fes = False
        if character and stars == 3:
            limit_type = character.get("limit_type", "")
            if limit_type == "フェス限定":
                is_fes = True
        
        # 根据是否是フェス限定选择不同的盲盒图
        if is_fes:
            # フェス限定3星使用特殊盲盒图
            center_path = LEVEL_DIR / "gacha_tmb_03_02_b.png"
            # 如果不存在则使用普通3星盲盒图
            if not center_path.exists():
                center_path = LEVEL_DIR / f"gacha_tmb_{star_idx:02d}_02.png"
        else:
            center_path = LEVEL_DIR / f"gacha_tmb_{star_idx:02d}_02.png"
    
    if not bg_path or not frame_path or not center_path:
        _qq().log_error(f"盲盒图片不全: bg={bg_path}, frame={frame_path}, center={center_path}")
        return None
    
    bg_img = _pil_open(bg_path)
    frame_img = _pil_open(frame_path)
    center_img = _pil_open(center_path)
    
    bg_width, bg_height = bg_img.size
    
    # 创建输出画布
    output = Image.new('RGBA', (bg_width, bg_height), (0, 0, 0, 0))
    output.paste(bg_img, (0, 0))
    
    # 调整中心图大小以适应框
    center_width, center_height = center_img.size
    center_ratio = center_width / center_height
    frame_ratio = bg_width / bg_height
    
    if center_ratio > frame_ratio:
        target_width = int(bg_width * 0.85)
        target_height = int(target_width / center_ratio)
    else:
        target_height = int(bg_height * 0.85)
        target_width = int(target_height * center_ratio)
    
    center_resized = center_img.resize((target_width, target_height), Image.Resampling.LANCZOS)
    center_x = (bg_width - target_width) // 2
    center_y = (bg_height - target_height) // 2
    
    output.paste(center_resized, (center_x, center_y), center_resized)
    output.paste(frame_img, (0, 0), frame_img)
    
    # 转换为RGB
    output_rgb = Image.new('RGB', (bg_width, bg_height), (255, 255, 255))
    output_rgb.paste(output, (0, 0), output)
    
    bio = BytesIO()
    output_rgb.save(bio, format='JPEG', optimize=True, quality=60)
    return bio.getvalue()


def open_mystery_box(box_info: dict, characters: list) -> dict:
    """
    开黑色盲盒，获取实际角色
    """
    if not box_info["is_mystery"]:
        # 不是黑色盲盒，直接返回（突变在调用处处理）
        return box_info
    
    # 黑色盲盒：3星40%，2星60%（stars已在创建时确定）
    stars = box_info["stars"]
    available = [c for c in characters if c["stars"] == stars]
    if available:
        character = random.choice(available)
    else:
        character = random.choice(characters)
    
    box_info["character"] = character
    box_info["opened"] = True
    
    return box_info


def create_opened_box_card(box_info: dict) -> bytes:
    """创建已开盲盒的卡牌图片（显示角色）"""
    if box_info["is_mystery"] and not box_info.get("opened"):
        # 黑色盲盒还没开，应该用未开的图片
        return create_box_card(box_info, [])
    
    stars = box_info["stars"]
    character = box_info.get("character")
    
    if not character:
        _qq().log_error("已开盲盒没有角色信息")
        return create_box_card(box_info, [])
    
    # 使用正常的卡牌合成逻辑
    return composite_card(character)


def create_box_summary_image(boxes: list, opened_indices: list, characters: list) -> bytes:
    """
    创建盲盒汇总图片（带背景）
    boxes: 所有盲盒列表
    opened_indices: 已开的盲盒索引列表
    """
    if not boxes:
        return None
    
    # 创建单张盲盒图片的尺寸
    single_card_img = None
    for i, box in enumerate(boxes):
        img_bytes = create_box_card(box, characters)
        if img_bytes:
            single_card_img = Image.open(BytesIO(img_bytes))
            break
    
    if not single_card_img:
        return None
    
    card_width, card_height = single_card_img.size
    count = len(boxes)
    
    # 计算行列布局
    if count <= 5:
        cols = count
        rows = 1
    else:
        cols = 5
        rows = (count + 4) // 5

    gap = 18
    cards_total_width = card_width * cols + gap * (cols - 1)
    cards_total_height = card_height * rows + gap * (rows - 1)
    
    # 尝试加载抽卡结果背景图片（使用gacha_tmb_bg_11.png）
    bg_path = None
    for bg_name in ["gacha_tmb_bg_11.png", "gacha_tmb_11_bg.png", "gacha_bg_11.png"]:
        test_path = LEVEL_DIR / bg_name
        if test_path.exists():
            bg_path = str(test_path)
            break
    
    # 如果找不到gacha_tmb_bg_11.png，回退到gacha_tmb_bg_10.png
    if not bg_path:
        for bg_name in ["gacha_tmb_bg_10.png", "gacha_tmb_10_bg.png", "gacha_bg_10.png"]:
            test_path = LEVEL_DIR / bg_name
            if test_path.exists():
                bg_path = str(test_path)
                break
    
    if bg_path:
        # 使用背景图片
        _qq().log_info(f"使用汇总背景图片: {bg_path}")
        bg_img = _pil_open(bg_path).convert('RGB')
        
        # 将背景放大到原来的2倍
        bg_w, bg_h = bg_img.size
        final_w = int(bg_w * 2 * 0.264)
        final_h = int(bg_h * 2 *0.264)
        bg_img_resized = bg_img.resize((final_w, final_h), Image.Resampling.LANCZOS)
        
        # 创建最终画布
        output = Image.new('RGB', (final_w, final_h), (50, 50, 50))
        output.paste(bg_img_resized, (0, 0))
        
        # 计算卡牌居中位置
        cards_x = (final_w - cards_total_width) // 2
        cards_y = (final_h - cards_total_height) // 2
    else:
        # 没有背景，使用纯色背景
        output = Image.new('RGB', (cards_total_width, cards_total_height), (50, 50, 50))
        cards_x = 0
        cards_y = 0
    
    for i, box in enumerate(boxes):
        row = i // cols
        col = i % cols
        
        if i in opened_indices:
            # 已开的盲盒显示角色
            img_bytes = create_opened_box_card(box)
        else:
            # 未开的盲盒显示盲盒封面
            img_bytes = create_box_card(box, characters)
        
        if img_bytes:
            card_img = Image.open(BytesIO(img_bytes))
            x = cards_x + col * (card_width + gap)
            y = cards_y + row * (card_height + gap)
            output.paste(card_img, (x, y))
    
    bio = BytesIO()
    output.save(bio, format='JPEG', optimize=True, quality=60)
    return bio.getvalue()


def has_box_session(user_id: str) -> bool:
    """检查用户是否有未完成的盲盒会话"""
    if user_id not in _qq().BOX_SESSIONS:
        return False
    
    # 检查是否所有盲盒都已开完
    session = _qq().BOX_SESSIONS[user_id]
    boxes = session.get("boxes", [])
    opened = session.get("opened", [])
    
    if len(boxes) == len(opened):
        # 所有盲盒已开完，但保留会话用于详细信息查询
        return False
    
    return True


def get_box_session(user_id: str) -> dict:
    """获取用户的盲盒会话"""
    return _qq().BOX_SESSIONS.get(user_id)


def create_box_session(user_id: str, boxes: list):
    """创建盲盒会话"""
    _qq().BOX_SESSIONS[user_id] = {
        "boxes": boxes,
        "opened": [],  # 已开的盲盒索引
        "characters": None,  # 角色列表引用
        "created_at": datetime.now()
    }


def clear_box_session(user_id: str):
    """清除盲盒会话"""
    if user_id in _qq().BOX_SESSIONS:
        del _qq().BOX_SESSIONS[user_id]


def is_valid_box_index(boxes: list, index_str: str, opened_indices: list = None) -> tuple:
    """
    验证盲盒索引是否合法
    返回: (是否有效, 索引列表或错误信息)
    """
    if opened_indices is None:
        opened_indices = []
    opened_set = set(opened_indices)
    
    index_str = index_str.strip()
    
    if index_str == "全部开":
        return True, list(range(len(boxes)))
    
    if index_str == "剩下的全部开":
        return True, [i for i in range(len(boxes)) if i not in opened_set]
    
    # 解析单个或多个索引，支持"选择1"等格式
    import re
    try:
        indices = []
        parts = index_str.replace("，", ",").split(",")
        
        for part in parts:
            part = part.strip()
            # 使用正则提取数字
            num_match = re.search(r'(\d+)', part)
            if num_match:
                num = int(num_match.group(1))
                idx = num - 1  # 用户输入1-10，转为0-9
                if 0 <= idx < len(boxes):
                    indices.append(idx)
                else:
                    return False, f"索引{num}超出范围(1-{len(boxes)})"
            else:
                return False, f"无效的输入: {part}，请输入数字或「选择数字」"
        
        return True, list(set(indices))  # 去重
    except Exception as e:
        return False, f"解析失败: {str(e)}"


