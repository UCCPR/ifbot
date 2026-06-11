"""
配队系统 - 让玩家能够用抽到的三星卡配置队伍
第一行是6个BattleCard角色，每个BattleCard角色都能搭配一个AssistCard放在第二行
使用和抽卡一样的背景图配置，角色图的框使用gacha_tmb_frame.png
"""

import os
import json
import random
from datetime import datetime
from io import BytesIO
from pathlib import Path

from PIL import Image


# ========== 日志模块 ==========
def log_info(message: str):
    """记录普通信息到info目录"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_file = INFO_DIR / "gacha_info.log"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] [INFO] {message}\n")
    print(f"[INFO] {message}")


def log_error(message: str):
    """记录错误信息到info目录"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_file = INFO_DIR / "gacha_error.log"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] [ERROR] {message}\n")
    print(f"[ERROR] {message}")


# ========== 配置 ==========
BASE_DIR = Path(__file__).parent
LEVEL_DIR = BASE_DIR / "level"
INFO_DIR = BASE_DIR / "info"
OUTPUT_DIR = BASE_DIR / "output"

# 队伍配置
BATTLE_CARD_COUNT = 6  # 战斗卡数量
ASSIST_CARD_COUNT = 6  # 支援卡数量（与战斗卡一一对应）


# 确保目录存在
INFO_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)


# ========== 队伍数据存储 ==========
def get_team_file(user_id: str) -> Path:
    """获取用户队伍配置文件路径"""
    return INFO_DIR / f"team_{user_id}.json"


def load_team_data(user_id: str) -> dict:
    """加载用户的队伍配置数据"""
    team_file = get_team_file(user_id)
    if team_file.exists():
        try:
            with open(team_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return create_default_team()
    return create_default_team()


def create_default_team() -> dict:
    """创建默认队伍配置（空队伍）"""
    return {
        "battle_cards": [None] * BATTLE_CARD_COUNT,  # 6个战斗卡位置
        "assist_cards": [None] * ASSIST_CARD_COUNT    # 6个支援卡位置
    }


def save_team_data(user_id: str, team_data: dict):
    """保存用户的队伍配置数据"""
    team_file = get_team_file(user_id)
    with open(team_file, "w", encoding="utf-8") as f:
        json.dump(team_data, f, indent=2)


# ========== 获取用户的三星卡 ==========
def get_pity_file(user_id: str) -> Path:
    """获取用户抽卡记录文件路径"""
    return INFO_DIR / f"pity_{user_id}.json"


def load_pity_data(user_id: str) -> dict:
    """加载用户的抽卡记录数据"""
    pity_file = get_pity_file(user_id)
    if pity_file.exists():
        try:
            with open(pity_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}


def get_user_3star_cards(user_id: str, characters: list = None) -> list:
    """获取用户拥有的所有三星卡（包含卡类型信息）"""
    pity_data = load_pity_data(user_id)
    card_collection = pity_data.get("card_collection", {})
    
    three_star_cards = []
    for card_id, info in card_collection.items():
        if info.get("stars") == 3:
            # 获取卡类型
            card_type = "battle"
            if characters:
                chara = next((c for c in characters if str(c.get("card_id")) == str(card_id)), None)
                if chara:
                    card_type = chara.get("type", "battle")
            
            three_star_cards.append({
                "card_id": card_id,
                "name": info.get("name", ""),
                "limit_type": info.get("limit_type", ""),
                "count": info.get("count", 1),
                "type": card_type  # 添加卡类型：battle 或 assist
            })
    
    return three_star_cards


def find_attribute_icon(attribute: str) -> str:
    """根据属性名称查找属性图标文件"""
    if not attribute:
        return None
    
    attr_name = str(attribute).strip()
    
    patterns = [
        f"common_tmb_label_element_{attr_name}.png",
        f"attr_{attr_name}.png",
        f"attribute_{attr_name}.png",
        f"type_{attr_name}.png",
        f"{attr_name}_attr.png",
        f"{attr_name}.png"
    ]
    
    for pattern in patterns:
        path = LEVEL_DIR / pattern
        if path.exists():
            return str(path)
    
    return None


def find_type_icon(card_type: str) -> str:
    """根据卡牌类型查找Battle/Assist图标文件"""
    if not card_type:
        return None
    
    type_name = str(card_type).strip().lower()
    
    patterns = [
        f"battle_{type_name}.png",
        f"{type_name}_icon.png",
        f"{type_name}.png"
    ]
    
    for pattern in patterns:
        path = LEVEL_DIR / pattern
        if path.exists():
            return str(path)
    
    return None


# ========== 构建队伍图片 ==========
def composite_team_card(character: dict, is_battle: bool = True) -> bytes:
    """
    合成队伍卡牌图片
    使用gacha_tmb_frame.png作为统一的框
    背景使用透明背景
    添加属性图标（左下角）和类型图标（正下方）
    """
    stars = character.get("stars", 3)
    icon_path = character.get("icon_path")
    
    # 加载统一的框
    frame_path = str(LEVEL_DIR / "gacha_tmb_frame.png")
    if os.path.exists(frame_path):
        frame_img = Image.open(frame_path).convert('RGBA')
    else:
        # 如果找不到统一框，使用星级框
        frame_path_fallback = get_level_image(stars, "frame")
        if frame_path_fallback and os.path.exists(frame_path_fallback):
            frame_img = Image.open(frame_path_fallback).convert('RGBA')
        else:
            # 创建一个简单的白色边框
            frame_img = Image.new('RGBA', (120, 160), (255, 255, 255, 128))
    
    # 加载角色图标
    if icon_path and os.path.exists(icon_path):
        char_img = Image.open(icon_path).convert('RGBA')
    else:
        # 创建占位图
        char_img = Image.new('RGBA', (100, 100), (100, 100, 100, 255))
    
    # 加载属性图标（根据角色属性）
    attribute = character.get("attribute")
    attr_icon_path = find_attribute_icon(attribute) if attribute else None
    attr_img = None
    if attr_icon_path and os.path.exists(attr_icon_path):
        attr_img = Image.open(attr_icon_path).convert('RGBA')
    
    # 加载Battle/Assist图标（根据角色类型）
    card_type = character.get("type", "battle")
    type_icon_path = find_type_icon(card_type)
    type_img = None
    if type_icon_path and os.path.exists(type_icon_path):
        type_img = Image.open(type_icon_path).convert('RGBA')
    
    bg_width, bg_height = frame_img.size
    
    # 裁剪角色图的指定区域（与抽卡一致）
    char_width, char_height = char_img.size
    crop_left = int(char_width * 0.25)
    crop_right = int(char_width * 0.75)
    crop_top = int(char_height * 0.15)
    crop_bottom = int(char_height * 0.65)
    char_img_cropped = char_img.crop((crop_left, crop_top, crop_right, crop_bottom))
    
    # 缩放裁剪后的图片以适应框
    cropped_width, cropped_height = char_img_cropped.size
    cropped_ratio = cropped_width / cropped_height
    frame_ratio = bg_width / bg_height
    
    if cropped_ratio > frame_ratio:
        char_target_width = int(bg_width * 0.85)
        char_target_height = int(char_target_width / cropped_ratio)
    else:
        char_target_height = int(bg_height * 0.85)
        char_target_width = int(char_target_height * cropped_ratio)
    
    char_img_resized = char_img_cropped.resize(
        (char_target_width, char_target_height),
        Image.Resampling.LANCZOS
    )
    
    # 创建输出画布（使用透明背景）
    output = Image.new('RGBA', (bg_width, bg_height), (0, 0, 0, 0))
    
    # 角色图居中放置
    char_x = (bg_width - char_target_width) // 2
    char_y = (bg_height - char_target_height) // 2
    output.paste(char_img_resized, (char_x, char_y), char_img_resized)
    
    # 粘贴框
    output.paste(frame_img, (0, 0), frame_img)
    
    # 添加属性图标（框的左下角，在框之上）
    if attr_img:
        attr_width, attr_height = attr_img.size
        attr_x = 5
        attr_y = bg_height - attr_height - 5
        output.paste(attr_img, (attr_x, attr_y), attr_img)
    
    # 添加Battle/Assist图标（卡牌最底部，在框之上）
    if type_img:
        type_width, type_height = type_img.size
        type_x = (bg_width - type_width) // 2
        type_y = bg_height - type_height
        output.paste(type_img, (type_x, type_y), type_img)
    
    # 转换为RGB（保留透明度）
    output_rgb = Image.new('RGB', (bg_width, bg_height), (255, 255, 255))
    output_rgb.paste(output, (0, 0), output)
    
    bio = BytesIO()
    output_rgb.save(bio, format='PNG', optimize=True, quality=80)
    return bio.getvalue()


def get_level_image(stars: int, layer_type: str) -> str:
    """获取星级框或背景图片"""
    star_idx = stars - 1
    layer_idx = 0 if layer_type == "bg" else 1
    
    filename = f"gacha_tmb_{star_idx:02d}_{layer_idx:02d}"
    if stars == 3 and layer_type == "bg":
        filename += "_b"
    
    path = LEVEL_DIR / f"{filename}.png"
    if path.exists():
        return str(path)
    return None


def build_3star_cards_image(user_id: str, characters: list, page: int = 1, page_size: int = 10) -> tuple:
    """
    构建三星卡展示图片（类似个人记录的三星卡展示）
    :return: (图片路径, 当前页卡牌列表, 总页数)
    """
    user_cards = get_user_3star_cards(user_id, characters)
    
    if not user_cards:
        return None, [], 0
    
    # 分页
    total_cards = len(user_cards)
    total_pages = (total_cards + page_size - 1) // page_size
    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages
    
    start_idx = (page - 1) * page_size
    end_idx = min(start_idx + page_size, total_cards)
    current_page_cards = user_cards[start_idx:end_idx]
    
    # 获取卡牌图片
    card_imgs = []
    for card in current_page_cards:
        card_id = card.get("card_id")
        chara = next((c for c in characters if str(c.get("card_id")) == str(card_id)), None)
        if chara:
            img_bytes = composite_team_card(chara, is_battle=True)
            if img_bytes:
                card_imgs.append({
                    "img": Image.open(BytesIO(img_bytes)),
                    "count": card.get("count", 1),
                    "card_id": card_id,
                    "type": card.get("type", "battle")
                })
    
    if not card_imgs:
        return None, current_page_cards, total_pages
    
    # 使用十连背景图
    bg_path = None
    for bg_name in ["gacha_tmb_bg_10.png", "gacha_tmb_10_bg.png", "gacha_bg_10.png"]:
        test_path = LEVEL_DIR / bg_name
        if test_path.exists():
            bg_path = str(test_path)
            break
    
    if bg_path:
        bg_img = Image.open(bg_path).convert('RGB')
        bg_w, bg_h = bg_img.size
        # 放大到原来的1.5倍
        final_w = int(bg_w * 1.5 * 0.264)
        final_h = int(bg_h * 1.5 * 0.264)
        bg = bg_img.resize((final_w, final_h), Image.Resampling.LANCZOS)
        bg_w, bg_h = final_w, final_h
    else:
        bg = Image.new('RGB', (600, 400), (50, 50, 50))
        bg_w, bg_h = bg.size
    
    # 布局：最多10张卡，2行5列
    max_card_width = 90
    max_card_height = 120
    gap = 10
    cols = min(len(card_imgs), 5)
    rows = (len(card_imgs) + cols - 1) // cols
    
    first_card = card_imgs[0]["img"]
    orig_w, orig_h = first_card.size
    scale = min(max_card_width / orig_w, max_card_height / orig_h)
    card_width = int(orig_w * scale)
    card_height = int(orig_h * scale)
    
    total_w = cols * (card_width + gap) - gap
    total_h = rows * (card_height + gap) - gap
    start_x = (bg_w - total_w) // 2
    start_y = (bg_h - total_h) // 2
    
    # 创建最终画布
    output = Image.new('RGB', (bg_w, bg_h), (50, 50, 50))
    output.paste(bg, (0, 0))
    
    # 粘贴卡牌
    for i, item in enumerate(card_imgs):
        img = item["img"]
        count = item["count"]
        col = i % cols
        row = i // cols
        x = start_x + col * (card_width + gap)
        y = start_y + row * (card_height + gap)
        
        img_copy = img.copy()
        img_copy.thumbnail((card_width, card_height), Image.Resampling.LANCZOS)
        thumb_w, thumb_h = img_copy.size
        
        paste_x = x + (card_width - thumb_w) // 2
        paste_y = y + (card_height - thumb_h) // 2
        
        output.paste(img_copy, (paste_x, paste_y))
        
        # 如果计数大于1，在右下角添加计数标记
        if count > 1:
            from PIL import ImageDraw, ImageFont
            draw = ImageDraw.Draw(output)
            badge_w = 30
            badge_h = 20
            badge_x = paste_x + thumb_w - badge_w - 2
            badge_y = paste_y + thumb_h - badge_h - 2
            draw.rounded_rectangle([badge_x, badge_y, badge_x+badge_w, badge_y+badge_h], radius=4, fill=(0, 0, 0, 200))
            try:
                font = ImageFont.truetype("arial.ttf", 12)
            except:
                font = ImageFont.load_default()
            text = f"x{count}"
            text_bbox = draw.textbbox((0, 0), text, font=font)
            text_w = text_bbox[2] - text_bbox[0]
            text_h = text_bbox[3] - text_bbox[1]
            text_x = badge_x + (badge_w - text_w) // 2
            text_y = badge_y + (badge_h - text_h) // 2
            draw.text((text_x, text_y), text, fill=(255, 255, 255), font=font)
    
    # 保存图片
    output_idx = random.randint(1000, 9999)
    img_path = OUTPUT_DIR / f"team_cards_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{output_idx}.png"
    output.save(img_path, format='PNG', optimize=True)
    
    return str(img_path), current_page_cards, total_pages


def build_team_image(team_data: dict, characters: list) -> str:
    """
    构建队伍展示图片
    第一行：6个BattleCard
    第二行：6个AssistCard（与上方一一对应）
    背景为1920x1080，调整12张卡的位置使其舒适
    """
    battle_cards = team_data.get("battle_cards", [None] * BATTLE_CARD_COUNT)
    assist_cards = team_data.get("assist_cards", [None] * ASSIST_CARD_COUNT)
    
    # 获取卡牌图片
    battle_imgs = []
    assist_imgs = []
    
    for card_id in battle_cards:
        if card_id:
            chara = next((c for c in characters if str(c.get("card_id")) == str(card_id)), None)
            if chara:
                img_bytes = composite_team_card(chara, is_battle=True)
                battle_imgs.append(Image.open(BytesIO(img_bytes)))
            else:
                battle_imgs.append(create_empty_slot_image())
        else:
            battle_imgs.append(create_empty_slot_image())
    
    for card_id in assist_cards:
        if card_id:
            chara = next((c for c in characters if str(c.get("card_id")) == str(card_id)), None)
            if chara:
                img_bytes = composite_team_card(chara, is_battle=False)
                assist_imgs.append(Image.open(BytesIO(img_bytes)))
            else:
                assist_imgs.append(create_empty_slot_image())
        else:
            assist_imgs.append(create_empty_slot_image())
    
    if not battle_imgs and not assist_imgs:
        return None
    
    # 固定背景尺寸：1920x1080
    bg_width = 1920
    bg_height = 1080
    
    # 加载抽卡背景图
    bg_path = None
    for bg_name in ["bg_000001001.png", "gacha_tmb_bg_10.png", "gacha_tmb_10_bg.png", "gacha_bg_10.png"]:
        test_path = LEVEL_DIR / bg_name
        if test_path.exists():
            bg_path = str(test_path)
            break
    
    if bg_path:
        log_info(f"使用队伍背景图片: {bg_path}")
        bg_img = Image.open(bg_path).convert('RGB')
        # 缩放背景图以适应1920x1080
        bg_img_resized = bg_img.resize((bg_width, bg_height), Image.Resampling.LANCZOS)
        output = Image.new('RGB', (bg_width, bg_height), (50, 50, 50))
        output.paste(bg_img_resized, (0, 0))
    else:
        # 没有背景，使用纯色背景
        output = Image.new('RGB', (bg_width, bg_height), (50, 50, 50))
    
    # 获取卡牌尺寸
    first_card = battle_imgs[0] if battle_imgs else assist_imgs[0]
    orig_card_width, orig_card_height = first_card.size
    
    # 计算合适的卡牌大小（适应1920x1080布局）
    # 6列卡牌，每列间距约20像素
    cols = 6
    rows = 2
    gap_x = 20  # 水平间距
    gap_y = 40  # 垂直间距（战斗卡和支援卡之间）
    
    # 计算卡牌最大尺寸
    available_width = bg_width - 100  # 左右各留50像素边距
    available_height = bg_height - 150  # 上下各留75像素边距
    
    max_card_width = (available_width - gap_x * (cols - 1)) // cols
    max_card_height = (available_height - gap_y) // rows
    
    # 缩放卡牌
    scale = min(max_card_width / orig_card_width, max_card_height / orig_card_height)
    card_width = int(orig_card_width * scale)
    card_height = int(orig_card_height * scale)
    
    # 计算卡牌区域总尺寸
    total_width = card_width * cols + gap_x * (cols - 1)
    total_height = card_height * rows + gap_y
    
    # 居中放置卡牌区域
    start_x = (bg_width - total_width) // 2
    start_y = (bg_height - total_height) // 2
    
    # 粘贴BattleCard（第一行）
    for i, img in enumerate(battle_imgs):
        col = i % cols
        x = start_x + col * (card_width + gap_x)
        y = start_y
        
        img_resized = img.resize((card_width, card_height), Image.Resampling.LANCZOS)
        output.paste(img_resized, (x, y))
    
    # 粘贴AssistCard（第二行）
    for i, img in enumerate(assist_imgs):
        col = i % cols
        x = start_x + col * (card_width + gap_x)
        y = start_y + card_height + gap_y
        
        img_resized = img.resize((card_width, card_height), Image.Resampling.LANCZOS)
        output.paste(img_resized, (x, y))
    
    # 保存图片
    output_idx = random.randint(1000, 9999)
    img_path = OUTPUT_DIR / f"team_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{output_idx}.png"
    output.save(img_path, format='PNG', optimize=True, quality=80)
    
    return str(img_path)


def create_empty_slot_image() -> Image.Image:
    """创建空槽位的占位图片"""
    # 使用三星背景作为空槽位背景
    bg_path = get_level_image(3, "bg")
    if bg_path and os.path.exists(bg_path):
        bg_img = Image.open(bg_path).convert('RGB')
    else:
        bg_img = Image.new('RGB', (120, 160), (50, 50, 50))
    
    # 添加"空"字提示
    from PIL import ImageDraw, ImageFont
    
    draw = ImageDraw.Draw(bg_img)
    try:
        font = ImageFont.truetype("arial.ttf", 24)
    except:
        font = ImageFont.load_default()
    
    text = "空"
    text_w, text_h = draw.textsize(text, font=font)
    text_x = (bg_img.width - text_w) // 2
    text_y = (bg_img.height - text_h) // 2
    draw.text((text_x, text_y), text, fill=(150, 150, 150), font=font)
    
    return bg_img


# ========== 队伍操作函数 ==========
def set_team_card(user_id: str, position: int, card_id: str, card_type: str = "battle") -> bool:
    """
    设置队伍卡牌
    :param user_id: 用户ID
    :param position: 位置（1-6）
    :param card_id: 卡牌ID
    :param card_type: battle或assist
    :return: 是否成功
    """
    if position < 1 or position > 6:
        return False
    
    idx = position - 1
    team_data = load_team_data(user_id)
    
    # 验证卡牌是否属于用户且是三星卡
    user_cards = get_user_3star_cards(user_id)
    card_found = any(str(c.get("card_id")) == str(card_id) for c in user_cards)
    
    if not card_found:
        return False
    
    if card_type == "battle":
        team_data["battle_cards"][idx] = card_id
    elif card_type == "assist":
        team_data["assist_cards"][idx] = card_id
    else:
        return False
    
    save_team_data(user_id, team_data)
    return True


def clear_team_card(user_id: str, position: int, card_type: str = "battle") -> bool:
    """
    清除队伍指定位置的卡牌
    :param user_id: 用户ID
    :param position: 位置（1-6）
    :param card_type: battle或assist
    :return: 是否成功
    """
    if position < 1 or position > 6:
        return False
    
    idx = position - 1
    team_data = load_team_data(user_id)
    
    if card_type == "battle":
        team_data["battle_cards"][idx] = None
    elif card_type == "assist":
        team_data["assist_cards"][idx] = None
    else:
        return False
    
    save_team_data(user_id, team_data)
    return True


def clear_all_team(user_id: str):
    """清除整个队伍配置"""
    team_data = create_default_team()
    save_team_data(user_id, team_data)


def get_team_info(user_id: str, characters: list) -> str:
    """获取队伍信息文本"""
    team_data = load_team_data(user_id)
    battle_cards = team_data.get("battle_cards", [])
    assist_cards = team_data.get("assist_cards", [])
    
    info = "⚔️ 战斗卡（第1行）：\n"
    for i, card_id in enumerate(battle_cards, 1):
        if card_id:
            chara = next((c for c in characters if str(c.get("card_id")) == str(card_id)), None)
            if chara:
                limit_badge = ""
                if chara.get("limit_type") == "フェス限定":
                    limit_badge = "🔹"
                elif chara.get("limit_type") == "期間限定":
                    limit_badge = "🔸"
                info += f"  {i}. {limit_badge}{chara.get('name', '未知')}\n"
            else:
                info += f"  {i}. 未知卡牌\n"
        else:
            info += f"  {i}. 空\n"
    
    info += "\n🛡️ 支援卡（第2行）：\n"
    for i, card_id in enumerate(assist_cards, 1):
        if card_id:
            chara = next((c for c in characters if str(c.get("card_id")) == str(card_id)), None)
            if chara:
                limit_badge = ""
                if chara.get("limit_type") == "フェス限定":
                    limit_badge = "🔹"
                elif chara.get("limit_type") == "期間限定":
                    limit_badge = "🔸"
                info += f"  {i}. {limit_badge}{chara.get('name', '未知')}\n"
            else:
                info += f"  {i}. 未知卡牌\n"
        else:
            info += f"  {i}. 空\n"
    
    return info
