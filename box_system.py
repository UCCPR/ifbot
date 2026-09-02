"""
盲盒开箱系统
"""
import os, json, random, re
from io import BytesIO
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageDraw, ImageFilter
from image_cache import load_shared_image

BASE_DIR = Path(__file__).parent
INFO_DIR = BASE_DIR / "info"
LEVEL_DIR = BASE_DIR / "level"

from card_image import (get_level_image, find_attribute_icon, find_type_icon, composite_card)

def _pil_open(path):
    """从共享压缩LRU加载图片，返回独立RGBA对象。"""
    return load_shared_image(path, 'RGBA')


def _draw_result_slot(canvas: Image.Image, x: int, y: int, size: int, stars: int):
    """绘制原作风格的半透明卡槽和稀有度光晕。"""
    glow_colors = {
        1: (145, 194, 255, 105),
        2: (105, 190, 255, 145),
        3: (255, 193, 42, 185),
    }
    border_colors = {
        1: (211, 226, 255, 230),
        2: (135, 218, 255, 245),
        3: (255, 214, 74, 255),
    }
    glow_color = glow_colors.get(int(stars or 1), glow_colors[1])
    border_color = border_colors.get(int(stars or 1), border_colors[1])

    # 光晕只在卡槽附近的小图层上处理，避免每张卡都模糊整张 1920x936 画布。
    blur_radius = 14
    pad = 15
    margin = pad + blur_radius * 2
    glow_size = size + margin * 2
    glow = Image.new('RGBA', (glow_size, glow_size), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.rounded_rectangle(
        [margin - pad, margin - pad, margin + size + pad, margin + size + pad],
        radius=26, fill=glow_color
    )
    glow = glow.filter(ImageFilter.GaussianBlur(blur_radius))
    canvas.alpha_composite(glow, (x - margin, y - margin))

    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle(
        [x - 11, y - 11, x + size + 11, y + size + 11],
        radius=22,
        fill=(218, 239, 255, 85),
        outline=(235, 247, 255, 205),
        width=4,
    )
    draw.rounded_rectangle(
        [x - 5, y - 5, x + size + 5, y + size + 5],
        radius=15, outline=border_color, width=4
    )

def _draw_new_badge(canvas: Image.Image, x: int, y: int, card_size: int):
    badge = load_shared_image(LEVEL_DIR / "common_quest_icon_new.png", 'RGBA')
    if badge is None:
        return
    # 素材原生94×34；右侧略微越过卡框，与原作结果页的位置一致。
    tx = x + card_size - badge.width + 18
    ty = y - 20
    canvas.alpha_composite(badge, (tx, ty))

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
    return composite_card(character, result_style=True)


def create_box_summary_image(boxes: list, opened_indices: list, characters: list) -> bytes:
    """
    创建盲盒汇总图片（带背景）
    boxes: 所有盲盒列表
    opened_indices: 已开的盲盒索引列表
    """
    if not boxes:
        return None
    
    count = len(boxes)
    cols = min(5, count)
    rows = 1 if count <= 5 else 2

    bg_path = LEVEL_DIR / "gacha_tmb_bg_11.png"
    if bg_path.exists():
        output = _pil_open(bg_path).convert('RGBA')
    else:
        output = Image.new('RGBA', (1920, 936), (180, 220, 250, 255))

    # 在 1920x936 原始 UI 坐标上合成，最后统一缩小，避免先缩背景再导致卡牌布局错位。
    card_size = 190
    gap_x = 68
    row_y = [215, 490]
    total_width = card_size * cols + gap_x * (cols - 1)
    start_x = (output.width - total_width) // 2

    for i, box in enumerate(boxes):
        row = i // cols
        col = i % cols
        if row >= rows:
            break

        if i in opened_indices:
            img_bytes = create_opened_box_card(box)
        else:
            img_bytes = create_box_card(box, characters)

        if img_bytes:
            with Image.open(BytesIO(img_bytes)) as source:
                card_img = source.convert('RGBA')
                card_img.load()
            source_w, source_h = card_img.size
            target_h = max(card_size, round(card_size * source_h / source_w))
            card_img = card_img.resize((card_size, target_h), Image.Resampling.LANCZOS)
            x = start_x + col * (card_size + gap_x)
            # 单抽按包含类型标签的完整卡图居中；十连继续使用固定两行布局。
            y = (output.height - target_h) // 2 if count == 1 else row_y[row]

            _draw_result_slot(output, x, y, card_size, box.get("stars", 1))
            output.alpha_composite(card_img, (x, y))
            if i in opened_indices and box.get("is_new", False):
                _draw_new_badge(output, x, y, card_size)

    # QQ 发送用尺寸：保留足够清晰度，同时控制文件体积。
    final_size = (1280, 624)
    output = output.convert('RGB').resize(final_size, Image.Resampling.LANCZOS)
    bio = BytesIO()
    output.save(bio, format='JPEG', optimize=False, quality=82, subsampling=1)
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


def cleanup_expired_box_sessions(max_age_seconds: int = 1800) -> int:
    """按最后创建时间淘汰放弃的盲盒会话，适用于所有机器人入口。"""
    sessions = _qq().BOX_SESSIONS
    now = datetime.now()
    expired = []
    for uid, session in list(sessions.items()):
        created_at = session.get("created_at") if isinstance(session, dict) else None
        if isinstance(created_at, datetime) and (now - created_at).total_seconds() > max_age_seconds:
            expired.append(uid)
    for uid in expired:
        sessions.pop(uid, None)
    return len(expired)


def create_box_session(user_id: str, boxes: list):
    """创建盲盒会话"""
    cleanup_expired_box_sessions()
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


