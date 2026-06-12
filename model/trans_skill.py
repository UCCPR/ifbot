import re
import pprint

DEBUG = False

skill1_index, skill2_index, skill3_index = 8, 10, 12
color_index = 5
type_index = 6
side_index = 3
dire_index = 4
passive1_index, passive2_index = 14, 15
max_atk_index, max_spa_index = 16, 17

count_color_list = ['红绿', '绿蓝', '蓝红', '黄紫', '紫黄']

all_time_list = ['行动开始时', '敌方行动开始时',
                 '(我方一对角色|自身以外的我方|自身)(必杀|技能|对敌方暴击|对敌方造成伤害)时'
                 ]

all_area_list = ['范围内', '三方向', '正面', '左侧', '右侧', '[前左右]+', '同色与有利色敌全体', '(同色|有利色)敌全体', '..侧敌全体', '(.色与)?.色敌全体', '敌全体', '该敌方角色',
                 '同色我方', '该我方角色', '(.色与)?.色我方全体', '自身以外的我方全体', '我方全体', '其他我方', '自身与两邻', '自身', '两邻']

all_buff_list = ['盾', '矢量操作', '强制咏唱待机', '全能神', '嘲讽', '强耐', '弱耐', '不屈', '预测不能', '天罚', r'攻击方向\+.', 
                 '必暴', r'物攻提升\(.+?\)', r'异攻提升\(.+?\)', r'物防提升\(.+?\)', r'异防提升\(.+?\)', r'暴击防御提升\(.+?\)', 
                 r'暴击率提升\(.+?\)', r'回避率提升\(.+?\)', r'暴伤提升\(.+?\)', r'必杀威力提升\(.+?\)', r'技能威力提升\(.+?\)',
                 r'SP获得量提升\(.+?\)', r'[^【]*减伤\(.+?\)', r'对.色威力提升\(.+?\)',
                 ]

all_debuff_list = ['强化妨害', '攻击提升妨害', 'HP回复妨害', '弱体化解除妨害',
                   r'持续被害\(.+?\)', '感电', '气绝', '移动不能', '制御不能', 'a卡封印', r'攻击方向\-.', '技能封印', '必杀封印', 
                   r'物攻下降\(.+?\)', r'异攻下降\(.+?\)', r'物防下降\(.+?\)', r'异防下降\(.+?\)', r'必杀威力下降\(.+?\)', 
                   r'暴击率下降\(.+?\)', r'回避率下降\(.+?\)', r'暴击防御下降\(.+?\)',
                   r'技能/必杀耐性下降\(.+?\)', r'.色耐性下降\(.+?\)',
                   ]

all_attack_list = ['((对(魔法|科学)|自身HP最大时|自身HP少于一半时|强化数|弱体数|自身HP[多少])(非常)?(大)?上升)?(?:必暴)?(超?特?大|中|小)威力(物理|异能)攻击']

all_sp_list = ['SP([0-9]+)上升', '根据(..侧|.色)数量SP(大)?上升']


def in_list(x, l):
    return any([re.fullmatch(p, x) for p in l])

def load_assist(text):
    '''读取a卡技能: [[触发次数, 触发条件, 作用范围, 效果, ...], ...]'''
    l = []
    for key in all_time_list + all_area_list + all_buff_list + all_debuff_list + all_sp_list:
        for x in re.finditer(key, text):
            l.append((x.span(), x.group()))
    l.sort(key=lambda x:x[0][0]+x[0][1]/100)
    new_l = [l[0]]
    for x in l[1:]:
        if x[0][0] == new_l[-1][0][0]:
            new_l.pop()
            new_l.append(x)
        elif x[0][1] <= new_l[-1][0][1]:
            pass
        else:
            new_l.append(x)
    l = [x[1] for x in new_l]

    times = re.search(r'\((.)次\)', text)
    if times:
        times = int(times.groups()[0])
    else:
        times = 100

    current_time = ''
    buff_list = []
    if DEBUG: print('assist: ', l)
    for x in l:
        if in_list(x, all_time_list):
            current_time = x
        elif in_list(x, all_area_list):
            buff_list.append([times, current_time, x])
        elif in_list(x, all_buff_list + all_debuff_list + all_sp_list):
            if len(buff_list) > 0:
                buff_list[-1].append(x)
            else:
                buff_list.append([times, current_time, '自身', x])

    buff_list = [x for x in buff_list if len(x) > 3]
    return buff_list
            
def load_battle(text):
    '''读取b卡技能: [[作用范围, 效果, ...], ...]'''
    l = []
    for key in all_area_list + all_buff_list + all_debuff_list + all_attack_list + all_sp_list:
        for x in re.finditer(key, text):
            l.append((x.span(), x.group()))
    l.sort(key=lambda x:x[0][0]+x[0][1]/100)
    new_l = [l[0]]
    for x in l[1:]:
        if x[0][0] == new_l[-1][0][0]:
            new_l.pop()
            new_l.append(x)
        elif x[0][1] <= new_l[-1][0][1]:
            pass
        else:
            new_l.append(x)
    l = [x[1] for x in new_l]
##    print(l)

    move_list = []
    for x in l:
        if in_list(x, all_area_list):
            move_list.append([x])
        elif in_list(x, all_buff_list + all_debuff_list + all_attack_list + all_sp_list):
            move_list[-1].append(x)

    move_list = [x for x in move_list if len(x) > 1]
    return move_list


def add_buff(card_type, i, area, buff, bcards, enemy, buff_lists):
    '''
    i号位上card_type卡的buff, 添加到buff_lists
    enemy: [颜色, 阵营, 防御]
    '''
##    print(i, area, buff)
    buff = (card_type, i, buff)

    if re.search('SP.{0,3}上升', buff[2]):
        m = re.match('SP([0-9]+)上升', buff[2])
        if m:
            buff_lists[i].append(buff)
        m = re.match('根据(..侧|.色)数量(SP(?:大)?上升)', buff[2])
        if m:
            for j in range(3):
                if m.groups()[0][:-1] in (bcards[j][color_index][-1], bcards[j][side_index]):
                    buff_lists[j].append((card_type, i, m.groups()[1]))
        return

    loc_index = None

    if '我方全体' in area or '自身与两邻' in area:
        loc_index = [0, 1, 2]
            
    elif '其他我方' in area or '两邻' in area:
        loc_index = [0, 1, 2]
        loc_index.remove(i)
            
    elif '自身' in area:
        loc_index = [i]

    elif '该我方角色' in area:
        loc_index = []
        

    else:# 敌方
        if re.search('((科学|魔法)侧)|([红绿蓝黄紫]色)', area):
            if not (enemy[1] in area or enemy[0][-1] in area):
                # 不符合阵营/颜色
                if DEBUG: print('addbuff: 不符合', card_type, i, area, buff, enemy)
                return
        elif '同色' in area or '有利色' in area:
            if not ('同色' in area and enemy[0][-1] == bcards[i][color_index][-1] or
                    '有利色' in area and bcards[i][color_index][-1]+enemy[0][-1] in count_color_list):
                # 不符合同色/有利颜色
                if DEBUG: print('addbuff: 不符合', card_type, i, area, buff, enemy)
                return
        else:
            # 没有限定
            pass
        
        for j in range(3):
            if not re.search(r'\((小|中|大|特大)\)', buff[2]) and\
               any([b[2] == buff[2] for b in buff_lists[j] if isinstance(b, tuple)]):
                # 已经上过的异常状态
                continue
            m = re.match('(.)色耐性下降', buff[2])
            if m and m.groups()[0] != bcards[j][color_index][-1]:
                # 颜色耐性颜色不对
                continue
            buff_lists[j].append(buff)
        return

    # 我方
    if re.search('((科学|魔法)侧)|([红绿蓝黄紫]色)', area):
        for j in range(3):
##            print(area, bcards[j][color_index])
            if j in loc_index and not (bcards[j][side_index] in area or bcards[j][color_index][-1] in area):
                loc_index.remove(j)

    elif '同色我方全体' in area:
        for j in range(3):
            if j in loc_index and bcards[j][color_index][-1] != bcards[i][color_index][-1]:
                loc_index.remove(j)

    m = re.match('对(.)色威力提升', buff[2])
    if not m or m.groups()[0] == enemy[0][-1]:
        for j in loc_index:
            buff_lists[j].append(buff)
        

def check_assist(assists, i, skill_type, damage):
    '''返回i号位技能可以触发的a卡技能'''
    l = []
    for j, sk in enumerate(assists):
        for s in sk:
            if DEBUG: print('check', i, skill_type, j, s)
            add = False
            # 技能/必杀/伤害触发
            if s[0] > 0 and (skill_type[-2:] in s[1] or (re.search('对敌方(暴击|造成伤害)时', s[1]) and damage)):
                if '我方一对角色' in s[1]:
                    add = True
                elif '自身以外的我方' in s[1]:
                    if i != j:
                        add = True
                elif '自身' in s[1] and i == j:
                    add = True
            
            if add:
                l.append((j, s[2:]))
                s[0] -= 1
    return l

def trans_passive(text, level, atk_type, enemy):
    passives = text.strip().split('+')
    transed = []
    last_direct = None
    for p in passives:
        m = re.fullmatch(r'(.)攻向上(\(.+\))?', p)
        if m and m.groups()[0] == atk_type[0]:
            if not m.groups()[1]:
                s = '攻击中'
            else:
                s = '攻击%s'%m.groups()[1][1:-1]
            if len(passives) == 1:
                s = '单'+s
            transed.append([s, level])
            continue

        m = re.fullmatch(r'(..)解析\((.)\)', p)
        if m:
            if (m.groups()[0], enemy[1]) in [('构造', '科学'), ('术式', '魔法')]:
                transed.append(['解析'+m.groups()[1]])
                continue

        m = re.fullmatch(r'(.+)方向攻击强化(\(.+\))?', p)
        if m:
            if last_direct == None or re.fullmatch(last_direct, r'方向中') and m.groups()[1][1:-1] == '大':
                last_direct = '方向'
                if not m.groups()[1]:
                    last_direct += '中'
                else:
                    last_direct += m.groups()[1][1:-1]

        m = re.fullmatch(r'SP获得量向上(\(.+\))?', p)
        if m:
            if not m.groups()[0]:
                s = 'SP小'
            else:
                s = 'SP%s'%m.groups()[0][1:-1]
            if len(passives) == 2:
                s = '单'+s
            transed.append([s])
            continue
            
    if last_direct:
        transed.append([last_direct])
##    print(text, atk_type, enemy, transed)
    return transed



def trans_buff(texts, levels, bcard_arg):
    if not bcard_arg:
        return []
    b = []
    for (text, level) in zip(texts, levels):
        m = re.fullmatch(r'.攻提升\((.+?)\)', text)
        if m and bcard_arg['类型'][0] == text[0]:
            b.append(['攻击', m.groups()[0], level])
            continue
        
        m = re.fullmatch(r'.防下降\((.+?)\)', text)
        if m and bcard_arg['类型'][0] == text[0]:
            b.append(['防御', m.groups()[0], level])
            continue
        
        m = re.fullmatch(r'暴伤提升\((.+?)\)', text)
        if m:
            b.append(['暴伤', m.groups()[0], level])
            continue

        m = re.fullmatch(r'对.色威力提升\((.+?)\)', text)
        if m:
            b.append(['颜色威力', m.groups()[0], level])
            continue
        
        m = re.fullmatch(r'暴击防御下降\((.+?)\)', text)
        if m:
            b.append(['暴击防御', m.groups()[0], level])
            continue
        
        m = re.fullmatch(r'.色耐性下降\((.+?)\)', text)
        if m and bcard_arg['颜色'][-1] == text[0]:
            b.append(['颜色耐性', m.groups()[0], level])
            continue

        m = re.fullmatch(r'技能/必杀耐性下降\((.+?)\)', text)
        if m:
            b.append(['必杀耐性', m.groups()[0], level])
            continue

        m = re.fullmatch(r'(技能|必杀)威力提升\((.+?)\)', text)
        if m and '必杀' in bcard_arg and (m.groups()[0]=='技能')==('技能' in bcard_arg['必杀']['威力']):
            b.append(['必杀威力', m.groups()[1], level])
            continue

        m = re.fullmatch(r'SP获得量提升\((.+?)\)', text)
        if m:
            b.append(['SP获得', m.groups()[0]])
            continue

        if in_list(text, all_attack_list):
            b.append(['攻击SP', len(bcard_arg['方向'])])
            continue

        m = re.fullmatch(r'SP([0-9]+)上升', text)
        if m:
            b.append(['SP', int(m.groups()[0])])
            continue

        m = re.fullmatch(r'SP(大)?上升', text)
        if m:
            if m.groups()[0]:
                b.append(['SP', m.groups()[0]])
            else:
                b.append(['SP', '中'])
            continue
        
            
    return b



def trans_all_inf(assist_cards, battle_cards, skill_types, card_attacks, card_levels, enemy, passives, leaders):
    '''
    return bcard_args, acard_args, buff_args, enemy_arg, total_sp
    
    '''

    skill_levels = card_levels[:]
    for i in range(3):
        if skill_types[i] == '超必杀':
            skill_levels[i] *= 5
    
    buff_lists = [[], [], []]

    # 读取a卡技能
    assist_skills = []
    for a in assist_cards:#
        a_skill = load_assist(a[skill1_index])
        if a[skill2_index]:
            a_skill.extend(load_assist(a[skill2_index]))
        assist_skills.append(a_skill)

    if DEBUG:
        for s in assist_skills:
            print(s)


    # 触发行动开始a卡
    for i, sk in enumerate(assist_skills):
        for s in sk:
            if s[1] == '行动开始时':
                for b in s[3:]:
                    add_buff('a', i, s[2], b, battle_cards, enemy, buff_lists)
            

    if DEBUG:
        print('\n行动开始\n')
        for b in buff_lists:
            for bb in b:
                print(bb)
            print()
            
    # 读取b卡技能并触发a卡
    for i in range(3):
        bcard = battle_cards[i]#
        skill_type = skill_types[i]#
        cause_dmg = False
        bcard_skill = None
        for move in load_battle(bcard[skill1_index if skill_type == '技能' else (skill2_index if '必杀' in skill_type else skill3_index)]):
            if DEBUG:
                print('行动: ', move)
            ar = move[0]
            for b in move[1:]:
                if in_list(b, all_attack_list):
                    buff_lists[i].append(('b', i, b))
                    buff_lists[i].append('完成')
                    cause_dmg = True
                else:
                    add_buff('b', i, ar, b, battle_cards, enemy, buff_lists)
                    
        if cause_dmg and i == 2:
            # 打死了不触发
            continue
        
        buff = check_assist(assist_skills, i, skill_type, cause_dmg)
        if DEBUG:
            print('行动触发')
            for b in buff:
                print(b)
        for b in buff:
            for s in b[1][1:]:
                add_buff('a', b[0], b[1][0], s, battle_cards, enemy, buff_lists)


    if DEBUG:
        print('\n全部bufflist\n')
        for b in buff_lists:
            for bb in b:
                print(bb)
            print()

    # 清除无效buff(攻击后的buff)
    for i in range(3):
        if '完成' in buff_lists[i]:
            j = buff_lists[i].index('完成')
            for k, b in enumerate(buff_lists[i][j:], j):
                if not (isinstance(b, tuple) and re.match(r'SP[大0-9]*上升', b[2])):
                    buff_lists[i][k] = None
                    if DEBUG: print('移除:', b)
            while None in buff_lists[i]:
                buff_lists[i].remove(None)


    if DEBUG:
        print('\n有效bufflist\n')
        for b in buff_lists:
            for bb in b:
                print(bb)
            print()

    
    bcard_args = []# 传入计算函数的参数: 输出b卡
    acard_args = []
    
    for i in range(3):
        bcard = {'颜色':None, '类型':None, '方向':None, '阵营':None, '攻击':None, '潜能':[]}
        acard = {'颜色':None, '阵营':None, '攻击':None, '潜能':[]}
        
        atk_type = battle_cards[i][type_index]
        
        is_spe = [in_list(buff_lists[i][j][2], all_attack_list) for j in range(len(buff_lists[i]))]
        if buff_lists[i] and any(is_spe):
            # 进行攻击
            sp = buff_lists[i][is_spe.index(True)][2]
            rank, atk_type = re.search('(超?特?大|中|小)威力(物理|异能)攻击', sp).groups()
            if skill_types[i] == '技能':
                rank = '技能'+rank

            bcard['必杀'] = dict()
            bcard['必杀']['威力'] = rank
            bcard['必杀']['等级'] = skill_levels[i]
            bcard['必杀']['限界1'] = '是' if battle_cards[i][skill3_index] != None else '否'

            m = re.search('(强化数|弱体数)(.*)上升', sp)
            if m:
                bcard['必杀']['威力上升幅度'] = m.groups()[0][:2]+('中' if m.groups()[1]=='' else m.groups()[1])
                if m.groups()[0] == '强化数':
                    l = all_buff_list
                else:
                    l = all_debuff_list
                n = sum([in_list(x[2], l) for x in buff_lists[i]])
                n = min(n, 10)
                bcard['必杀']['上升个数'] = n
            else:
                m = re.search('([非常大]*)上升', sp)
                if m:
                    bcard['必杀']['其他倍率加成'] = '中' if m.groups()[0]=='' else m.groups()[0]

            for k in '威力上升幅度', '上升个数', '其他倍率加成':
                if not k in bcard['必杀']:
                    bcard['必杀'][k] = '无'

        bcard['颜色'] = battle_cards[i][color_index]
        bcard['类型'] = atk_type
        bcard['方向'] = battle_cards[i][dire_index]
        bcard['阵营'] = battle_cards[i][side_index]
        bcard['攻击'] = card_attacks[i]#
        passive = trans_passive(battle_cards[i][passive1_index], card_levels[i], atk_type, enemy)
        bcard['潜能'] = passive
            
        if passives[i][0] == '2':#
            passive = trans_passive(battle_cards[i][passive2_index], card_levels[i], atk_type, enemy)
            bcard['潜能'].extend(passive)#
            
        for p in leaders:
            for j in range(p[2]):
                bcard['潜能'].append([p[0], p[1]])

        bcard_args.append(bcard)


        # a卡
            
        acard['颜色'] = assist_cards[i][color_index]
        acard['阵营'] = assist_cards[i][side_index]
        acard['攻击'] = card_attacks[i+3]#
        passive = trans_passive(assist_cards[i][passive1_index], card_levels[i+3], atk_type, enemy)
        acard['潜能'] = passive
        if passives[i][2] == '2':#
            passive = trans_passive(assist_cards[i][passive2_index], card_levels[i+3], atk_type, enemy)
            acard['潜能'].extend(passive)#
        acard_args.append(acard)


    # buff
    buff_args = []
    for i in range(3):
        bl = []
        texts = [b[-1] for b in buff_lists[i]]
        levels = [skill_levels[{'b':[0,1,2], 'a':[3,4,5]}[b[0]][b[1]]] for b in buff_lists[i]]
        buff_args.append(trans_buff(texts, levels, bcard_args[i]))

    # 敌方
    enemy_arg = dict()
    enemy_arg['颜色'] = enemy[0]
    enemy_arg['防御'] = enemy[2]
    
    return bcard_args, acard_args, buff_args, enemy_arg

##if __name__ == '__main__':
##    cards = [[0, '【アイドルの可能性】アレイスター＝クロウリー（少女）', '魔法', '↖↑', '红', '物理', '红色我方全体2次【盾】,【贯通】,【物攻提升(中)】,【攻击方向+1】2回合', 6, '红色我方全体【物攻提升(特大)】,【暴伤提升(小)】2回合,【SP获得量提升(中)】,敌全体【回避率下降(中)】,【暴击防御下降(中)】2回合', 6, '赤防御能力向上(中)+赤对緑赤物攻向上(大)', '赤物理能力向上(大)+赤对緑赤防御向上(大)', 15315, 6348],
##             [0, '【悪魔殲滅者】オティヌス', '魔法', '↑↗', '红', '物理', '范围内中威力物理攻击,范围内红色与绿色【移动不能】,【攻击方向-1】1回合', 3, '正面【红色耐性下降(中)】2回合,特大威力物理攻击,【暴击防御下降(中)】,【回避率下降(大)】2回合', 6, '集中力向上(小)+SP获得量向上', '前右方向攻击强化+HP向上(小)+物攻向上', 16876, 6348],
##             [0, '【サンタのお仕事】オルソラ＝アクィナス', '魔法', '↖↑', '红', '异能', '我方全体弱体状态解除,HP回复(中),【异攻提升(中)】,【SP获得量提升(中)】3回合,根据赤系属性数量SP上升', 4, '范围内【暴击防御下降(小)】,【回避率下降(中)】,【异防下降(小)】3回合,特大威力异能攻击,【红色耐性下降(小)】3回合,根据红色数量SP上升', 5, '异攻向上(中)', 'SP获得量向上(小)+判断力向上(小)+异防向上', 7557, 17326],
##             [0, '【慣れない保護者役】浜面 仕上', '科学', None, '红', '物理', '我方一对角色受到伤害时,同色我方【红色减伤(中)】,【物攻提升(小)】3回合(2次)', 0, None, None, '物攻向上(中)', '判断力向上+物攻向上+SP获得量向上', 12479, 4721],
##             [0, '【クリスマスエスコート】ステイル＝マグヌス', '魔法', None, '红', '异能', '自身必杀时,红色我方全体【必杀威力提升(小)】,【异攻提升(中)】3回合,根据红色数量SP大上升(2次)', 0, None, None, 'HP向上(中)+SP获得量向上', '异攻向上(中)', 3474, 13161],
##             [0, '【メンバー】ショチトル', '魔法', None, '红', '物理', '我方一对角色必杀时,自身SP10上升,紫色与黄色敌全体【物防下降(小)】,【持续被害(小)】2回合(3次)', 0, None, None, '物攻向上(中)', 'HP向上(中)', 12752, 4794],
##             ]
##    assist_cards = cards[3:]
##    battle_cards = cards[:3]
##    skill_types = ['必杀', '必杀', '必杀']
##    card_attacks = [[10000,12000]]*6
##    card_levels = [12,211,12,12,31,13]
##    enemy = ['黄', '科学', 7059]
##    passives = ['2/2', '2/2', '2/2', '2/2']
##    leaders = [['队长中', 122, 2], ['队长大', 122, 4]]
##    
##    pprint.pprint(trans_all_inf(assist_cards, battle_cards, skill_types, card_attacks, card_levels, enemy, passives, leaders))
