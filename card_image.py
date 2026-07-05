"""
卡牌图片合成模块
"""
import os
from io import BytesIO
from datetime import datetime
from pathlib import Path
from PIL import Image

BASE_DIR = Path(__file__).parent
ICON_DIR = BASE_DIR / "iconimage"
LEVEL_DIR = BASE_DIR / "level"
OUTPUT_DIR = BASE_DIR / "output"

CROP_LEFT_RATIO = 0.25
CROP_RIGHT_RATIO = 0.75
CROP_TOP_RATIO = 0.15
CROP_BOTTOM_RATIO = 0.65

def get_level_image(stars, layer_type):
    star_idx = stars - 1
    layer_idx = 0 if layer_type == "bg" else 1
    filename = f"gacha_tmb_{star_idx:02d}_{layer_idx:02d}"
    if stars == 3 and layer_type == "bg":
        filename += "_b"
    path = LEVEL_DIR / f"{filename}.png"
    return str(path) if path.exists() else None

def find_attribute_icon(attribute):
    if not attribute: return None
    attr_name = str(attribute).strip()
    attr_mapping = {"红":"赤","绿":"緑","蓝":"青","黄":"黄","紫":"紫",
                    "超红":"超赤","超绿":"超緑","超蓝":"超青","超黄":"超黄","超紫":"超紫"}
    mapped = attr_mapping.get(attr_name, attr_name)
    for p in [f"common_tmb_label_element_{mapped}.png",f"common_tmb_label_element_{attr_name}.png",
              f"attr_{attr_name}.png",f"attribute_{attr_name}.png",f"type_{attr_name}.png",
              f"{attr_name}_attr.png",f"{attr_name}.png"]:
        path = LEVEL_DIR / p
        if path.exists(): return str(path)
    return None

def find_type_icon(card_type):
    if not card_type: return None
    tn = str(card_type).strip().lower()
    ln = "battle" if tn == "battle" else "assist"
    for p in [f"gacha_tmb_label_{ln}.png",f"battle_{tn}.png",f"{tn}_icon.png",f"{tn}.png"]:
        path = LEVEL_DIR / p
        if path.exists(): return str(path)
    return None

def composite_card(character):
    from qq_bot_ws import find_character_icon
    stars = character["stars"]
    icon_path = character.get("icon_path") or find_character_icon(character["chara_id"], stars)
    if not icon_path or not os.path.exists(icon_path):
        img = Image.new('RGBA', (150, 150), (100, 100, 100, 255))
        bio = BytesIO(); img.save(bio, format='PNG'); return bio.getvalue()
    try:
        bg = Image.open(get_level_image(stars,"bg")).convert('RGBA')
        frame = Image.open(get_level_image(stars,"frame")).convert('RGBA')
        char = Image.open(icon_path).convert('RGBA')
        CARD=122
        cw,ch=char.size
        cl,cr,ct,cb=int(cw*CROP_LEFT_RATIO),int(cw*CROP_RIGHT_RATIO),int(ch*CROP_TOP_RATIO),int(ch*CROP_BOTTOM_RATIO)
        cc=char.crop((cl,ct,cr,cb))
        ccw,cch=cc.size; ratio=ccw/cch
        if ratio>1: tw=int(CARD*0.85); th=int(tw/ratio)
        else: th=int(CARD*0.85); tw=int(th*ratio)
        cr=cc.resize((tw,th),Image.Resampling.LANCZOS)
        out=Image.new('RGBA',(CARD,CARD),(0,0,0,0))
        cx,cy=(CARD-tw)//2,(CARD-th)//2
        out.paste(bg,(0,0)); out.paste(cr,(cx,cy),cr); out.paste(frame,(0,0),frame)
        attr=character.get("attribute")
        if attr:
            ap=find_attribute_icon(attr)
            if ap and os.path.exists(ap):
                ai=Image.open(ap).convert('RGBA'); aw,ah=ai.size
                out.paste(ai,(5,CARD-ah-5),ai)
        tp=find_type_icon(character.get("type","battle"))
        if tp and os.path.exists(tp):
            ti=Image.open(tp).convert('RGBA'); tw2,th2=ti.size
            out.paste(ti,((CARD-tw2)//2,CARD-th2),ti)
        bio=BytesIO(); out.save(bio,format='PNG'); return bio.getvalue()
    except: return None

def save_card_image(card_data, output_idx):
    if not card_data: return None
    try:
        if len(card_data)==1:
            ib=composite_card(card_data[0])
            if not ib: return None
            fn=f"gacha_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{output_idx}.png"
            fp=OUTPUT_DIR/fn
            with open(fp,'wb') as f: f.write(ib)
            return str(fp)
        else:
            imgs=[]
            for ch in card_data:
                ib=composite_card(ch)
                if ib: imgs.append(Image.open(BytesIO(ib)))
            if not imgs: return None
            cw,ch=imgs[0].size; gap=18
            tw2=cw*5+gap*4; th=ch*2+gap
            out=Image.new('RGBA',(tw2,th),(50,50,50,255))
            for idx,img in enumerate(imgs):
                r,c=idx//5,idx%5
                x=c*(cw+gap); y=r*(ch+gap)
                out.paste(img,(x,y),img if img.mode=='RGBA' else None)
            or2=Image.new('RGB',out.size,(255,255,255))
            or2.paste(out,(0,0),out)
            fn=f"gacha_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{output_idx}.jpg"
            fp=OUTPUT_DIR/fn
            or2.save(str(fp),format='JPEG',optimize=True,quality=60)
            return str(fp)
    except: return None
