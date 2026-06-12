from ruamel.yaml import YAML
import os
import pickle
import openpyxl

DEBUG = False

max_col = 23

def load_cards():
    os.chdir(os.path.dirname(__file__))
    workbook = openpyxl.load_workbook(r'.\cards_completed.xlsx')
    bsheet = workbook['b卡']
    asheet = workbook['a卡']
    bcards, acards = [], []
    for sheet, cards in (bsheet, bcards), (asheet, acards):
        cards.extend([None]*len(sheet._images))
        for img in sheet._images:
            d = img._data()
            row = img.anchor._from.row+1
            cards[row-2] = [d]+[sheet.cell(row, col).value for col in range(2, max_col+1)]
        cards.reverse()
    sheet = workbook['杂项']
    card_params = { }
    for i in range(2, 12):
        card_params[sheet['A%d'%i].value] = sheet['B%d'%i].value
            
    return bcards, acards, card_params


#找到程序所需的文件并读取数据
def load():
    yaml = YAML()
    
    with open(r'.\params.yaml', encoding='utf-8') as f:
        calc_params = yaml.load(f)
        
    with open(r'.\faction', 'rb') as f:
        faction_dict = pickle.load(f)
        
    return calc_params, faction_dict

def calc_faction(rank_list, side):
    fs = [{'物理':faction_dict[rank_list[i]]['str'], '异能':faction_dict[rank_list[i]]['inte']} for i in range(3)]
    if side == '科学魔法':
        return {k:fs[0][k]+fs[1][k] for k in ('物理', '异能')}
    return fs[['科学', '魔法', '其他'].index(side)]

def calc_damage(bcard, acard, faction_ranks, buff_list, enemy, 暴击=True, 限制突破=False):
    if not '必杀' in bcard:# 不攻击
        return 0, ''

    warning_text = []
    
    弱体强化扣除数 = []
    def 扣除(加成名称):
        '''因溢出导致实际数量减少'''
        if not bcard['必杀']['威力上升幅度'] in (None, '无', 0):
            # 有根据弱体/强化数威力上升的词条
            if bcard['必杀']['威力上升幅度'][:2] == '强化' and 加成名称 in ('攻击', '必杀威力', '暴伤'):
                弱体强化扣除数.append(加成名称)
            elif bcard['必杀']['威力上升幅度'][:2] == '弱体' and 加成名称 in ('防御', '暴击防御', '必杀耐性', '颜色耐性'):
                弱体强化扣除数.append(加成名称)
        if DEBUG:print(弱体强化扣除数)
        
    
    # 计算buff加成
    def 计算加成(buff_list, 加成名称):
        倍率, 附加 = 0, 0
        if '上限' in calc_params[加成名称]:
            倍率上限, 严格上限 = calc_params[加成名称]['上限']
        else:
            倍率上限, 严格上限 = 1e5, False
        for 加成 in buff_list:
            # 加成 = [名称, 幅度, 等级]
            if 加成[0] == 加成名称:
                if (倍率 < 倍率上限) or (not 严格上限 and 倍率 <= 倍率上限):
                    加成数值 = calc_params[加成名称][加成[1]]# 倍率上升, 数值上升每级
                    倍率 += 加成数值[0]
                    附加 += 加成数值[1]*(加成[2]-1)
                else:
                    扣除(加成名称)
                    warning_text.append(str(加成)+'溢出 (上限%.2f)'%倍率上限)
        if 严格上限 and 倍率 > 倍率上限:
            倍率 = 倍率上限
        return 倍率, 附加

    # ********读取计算参数********
    # 同色, 限界1, 潜能攻击, 攻击倍率, 附加攻击, 潜能倍率, 基础倍率, 上升倍率, 必杀附加攻击, buff倍率, buff附加攻击,
    # 防御倍率, 附加防御, 克制色, 超属性克制, 暴伤倍率, 附加伤害, 暴击防御倍率, 降防附加伤害, 颜色倍率, 颜色附加伤害, 耐性倍率, 耐性附加伤害, 颜色威力倍率, 颜色威力附加伤害
    # 同色
    颜色b, 颜色a = bcard['颜色'], acard['颜色']
    同色 = 颜色b[-1] == 颜色a[-1]
    超属性 = 颜色b[0] == '超' or 同色 and 颜色a[0] == '超'

    # 限界1
    限界1 = bcard['必杀']['限界1'] == '是'

    # 潜能攻击
    潜能攻击 = 0
    for 潜能 in bcard['潜能']+acard['潜能']:
        if 潜能[0] in calc_params['攻击潜能']:
            # 潜能 = [类型, 等级]
            潜能攻击 += calc_params['攻击潜能'][潜能[0]]*潜能[1]

    # 攻击倍率, 附加攻击
    攻击倍率, 附加攻击 = 计算加成(buff_list, '攻击')

    # 潜能倍率
    潜能倍率 = 1
    for 潜能 in bcard['潜能']:
        if 潜能[0] in calc_params['潜能倍率']:
            # 潜能 = [类型]
            潜能倍率 += calc_params['潜能倍率'][潜能[0]]

    # buff倍率, buff附加攻击
    buff倍率, buff附加攻击 = 计算加成(buff_list, '必杀威力')

    # 防御倍率, 附加防御
    防御倍率, 附加防御 = 计算加成(buff_list, '防御')

    # 克制倍率, 超属性克制
    克制列表 = ('红绿', '绿蓝', '蓝红', '黄紫', '紫黄')
    if bcard['颜色'][-1]+enemy['颜色'][-1] in 克制列表:
        克制倍率 = 1.5
    elif enemy['颜色'][-1]+bcard['颜色'][-1] in 克制列表:
        克制倍率 = 0.6
    else:
        克制倍率 = 1.0
    超属性克制 = 超属性 and not enemy['颜色'][0] == '超'

    # 暴伤倍率, 附加伤害, 暴击防御倍率, 降防附加伤害
    暴伤倍率, 附加伤害 = 计算加成(buff_list, '暴伤')
    暴击防御倍率, 降防附加伤害 = 计算加成(buff_list, '暴击防御')

    # 颜色倍率, 颜色附加伤害, 耐性倍率, 耐性附加伤害, 颜色威力倍率, 颜色威力附加伤害
    颜色倍率, 颜色附加伤害 = 计算加成(buff_list, '颜色耐性')
    耐性倍率, 耐性附加伤害 = 计算加成(buff_list, '必杀耐性')
    颜色威力倍率, 颜色威力附加伤害 = 计算加成(buff_list, '颜色威力')

    # 基础倍率, 上升倍率, 必杀附加攻击
    必杀 = bcard['必杀']
    基础倍率 = calc_params['必杀基础倍率'][必杀['威力']]
    上升倍率 = 0
    if not 必杀['威力上升幅度'] in (None, '无', 0):
        # 有根据弱体/强化数威力上升的词条
        if DEBUG: print(弱体强化扣除数)
        上升倍率 += (必杀['上升个数']-len(弱体强化扣除数)) * calc_params['上升幅度'][必杀['威力上升幅度'][2:]]
    上升倍率 += calc_params['其他倍率'][必杀['其他倍率加成']]
    必杀附加攻击 = calc_params['必杀附加攻击'][bcard['必杀']['威力']]*(bcard['必杀']['等级']-1)


    if DEBUG: print(同色, 潜能攻击, (攻击倍率, 附加攻击), 潜能倍率, (基础倍率, 上升倍率, buff倍率, 必杀附加攻击, buff附加攻击),
                    (防御倍率, 附加防御), 克制倍率, 超属性克制, (暴伤倍率, 暴击防御倍率, 附加伤害, 降防附加伤害), (颜色倍率, 耐性倍率, 颜色威力倍率), (颜色附加伤害, 耐性附加伤害, 颜色威力附加伤害))

    # ********计算伤害********
    # 计算攻击面板
    攻击面板b, 阵营加成b = bcard['攻击'], calc_faction(faction_ranks, bcard['阵营'])[bcard['类型']]
    攻击面板a, 阵营加成a = acard['攻击'], calc_faction(faction_ranks, acard['阵营'])[bcard['类型']]

    # 处理同色加成
    if not 同色:
        攻击面板 = 攻击面板b + 攻击面板a
    else:
        #攻击面板 = (攻击面板b-阵营加成b+攻击面板a-阵营加成a)*1.05+阵营加成b+阵营加成a
        攻击面板 = (攻击面板b + 攻击面板a)*1.05
    攻击面板 = int(攻击面板)
    
    # 计算带潜能的面板 
    攻击面板 += 潜能攻击

    # 攻击buff
    攻击 = 攻击面板*(1+攻击倍率)+附加攻击
    攻击 = int(攻击)

    # 潜能倍率
    攻击 *= 潜能倍率
    攻击 = int(攻击)

    # 计算必杀
    攻击 += 必杀附加攻击+buff附加攻击
    攻击 *= 基础倍率+上升倍率+buff倍率
    攻击 = int(攻击)

    # 计算防御
    防御 = enemy['防御']
    防御 = max(防御*(1-防御倍率)-附加防御, 0)

    # 计算伤害
    伤害 = 攻击**2/(攻击+防御)
    伤害 = int(伤害)

    # 计算颜色, 超属性加成
    伤害 = 伤害*克制倍率
    伤害 = int(伤害)
    
    if 超属性克制:
        伤害 = 伤害*1.2
        伤害 = int(伤害)

    # 计算暴击
    if 暴击:
        伤害 = 伤害*(1.5+暴伤倍率+暴击防御倍率)+附加伤害+降防附加伤害
        伤害 = int(伤害)

    # 计算颜色, 必杀耐性
    伤害 = int(伤害*(1+颜色倍率+耐性倍率+颜色威力倍率)+颜色附加伤害+耐性附加伤害+颜色威力附加伤害)

    # 计算限界1发动效果
    if 限界1:
        伤害 = int(伤害*1.1)
    
    return 伤害, '\n'.join(warning_text)

def calc_sp(bcard, acard, buff_list, break_atk=False):
    '''计算SP'''
    total_sp = 0
    sp_rate = 1
    
    for 潜能 in bcard['潜能']+acard['潜能']:
        if 潜能[0] in calc_params['潜能SP']:
            sp_rate += calc_params['潜能SP'][潜能[0]]
    if DEBUG: print(sp_rate)
    for b in buff_list:
        val = calc_params[b[0]]
        if b[0] == 'SP获得':
            sp_rate += val[b[1]]
        elif b[0] == 'SP':
            if b[1] in val:
                total_sp += int(sp_rate*val[b[1]])
            else:
                total_sp += int(sp_rate*b[1])
        elif b[0] == '攻击SP':
            t, s = val[b[1]]
            total_sp += t
            total_sp += int(sp_rate*s)
            
    if break_atk:
        total_sp += 8
    if DEBUG: print(total_sp)
    return total_sp

        


bcards, acards, card_params = load_cards()
calc_params, faction_dict = load()

# n次中a次时, 中的概率为p的概率为
# pp = p**a*(1-p)**(n-a)*comb(n, a)*(n+1)*dp
