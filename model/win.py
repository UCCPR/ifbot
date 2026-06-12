from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *
import os, sys
import traceback
import openpyxl
from ruamel.yaml import YAML
from myui import Ui_MainWindow
import trans_skill as ts
import calc_dmg as cl


def make_icon(buffer):
    pic = QPixmap()
    pic.loadFromData(buffer)
    icon = QIcon(pic)
    return icon

class Calc(object):
    def __init__(self, ui:Ui_MainWindow, win:QMainWindow):
        self.ui = ui
        self.win = win

        # 设置窗口属性
        self.config_fname = r'.\config'
        try:
            if os.path.isfile(self.config_fname):
                with open(self.config_fname, 'r') as f:
                    self.config = eval(f.read())
            else:
                self.config = {'winscale':1.0, 'fontsize':11, 'faction_level':[160, 160, 160], 'calc_faction_level':[160, 160, 160], 'max_level':160}
                with open(self.config_fname, 'w') as f:
                    f.write(str(self.config))
        except Exception as e:
            self.show_message(e)
        
        # 读取Excel数据
        try:
            self.bcards, self.acards = cl.bcards, cl.acards
            self.bicons, self.aicons = [make_icon(c[0]) for c in self.bcards], [make_icon(c[0]) for c in self.acards]
            
        except Exception as e:
            self.show_message(e)

        # 设置复选框事件
        self.attr_checkboxes = [self.ui.red_checkBox, self.ui.sred_checkBox,
                                self.ui.green_checkBox, self.ui.sgreen_checkBox,
                                self.ui.blue_checkBox, self.ui.sblue_checkBox,
                                self.ui.yellow_checkBox, self.ui.syellow_checkBox,
                                self.ui.purple_checkBox, self.ui.spurple_checkBox,
                                self.ui.science_checkBox, self.ui.magic_checkBox,
                                self.ui.neutral_checkBox, 
                                self.ui.physical_checkBox, self.ui.mental_checkBox
                                ]
        for box in self.attr_checkboxes:
            box.clicked.connect(self.check_color_side)
        for box in self.attr_checkboxes[10:]:
            box.setChecked(True)
        hotkeys = ['alt+r', 'alt+shift+r', 'alt+g', 'alt+shift+g', 'alt+b', 'alt+shift+b', 'alt+y', 'alt+shift+y', 'alt+p', 'alt+shift+p',
                   'alt+s', 'alt+m', 'alt+n', 'ctrl+p', 'ctrl+m']
        for box, key in zip(self.attr_checkboxes, hotkeys):
            box.setShortcut(key)

        # 设置卡牌选择标签事件
        self.image_size = 100
        self.card_comboboxes = [self.ui.b1_comboBox, self.ui.b2_comboBox, self.ui.b3_comboBox,
                                self.ui.a1_comboBox, self.ui.a2_comboBox, self.ui.a3_comboBox
                                ]
        self.card_labels = [self.ui.b1_label, self.ui.b2_label, self.ui.b3_label,
                            self.ui.a1_label, self.ui.a2_label, self.ui.a3_label
                            ]
        self.card_index = [None]*6
        for i, box in enumerate(self.card_comboboxes, 1):
            box.setMaximumSize(200, box.size().height())
            box.currentIndexChanged.connect(self.update_choosed_cards)
            shortcut = QShortcut(QKeySequence('alt+%d'%i), self.ui.centralwidget)
            shortcut.activated.connect(box.showPopup)

        # 设置潜能选择
        self.passive_comboboxes = [self.ui.p1_comboBox, self.ui.p2_comboBox, self.ui.p3_comboBox]
        for box in self.passive_comboboxes:
            box.addItems(['2/2', '1/1', '1/2', '2/1'])
            box.setToolTip('潜能数b/a')

        # 设置等级, 攻击
        self.level_spinboxes = [self.ui.b1_level_spinBox, self.ui.b2_level_spinBox, self.ui.b3_level_spinBox,
                                self.ui.a1_level_spinBox, self.ui.a2_level_spinBox, self.ui.a3_level_spinBox
                                ]
        self.attack_spinboxes = [self.ui.b1_atk_spinBox, self.ui.b2_atk_spinBox, self.ui.b3_atk_spinBox,
                                 self.ui.a1_atk_spinBox, self.ui.a2_atk_spinBox, self.ui.a3_atk_spinBox
                                 ]
        for box in self.level_spinboxes:
            box.setToolTip('卡牌等级')
        for box in self.attack_spinboxes:
            box.setToolTip('卡牌攻击')

        # 设置队长等级
        self.leader_spinboxes = [self.ui.leader1_level_spinbox, self.ui.leader1_spinBox,
                                 self.ui.leader2_level_spinbox, self.ui.leader2_spinBox]

        # 设置技能/必杀下拉框
        self.skill_comboboxes = [self.ui.skill1_comboBox, self.ui.skill2_comboBox, self.ui.skill3_comboBox]
        for box in self.skill_comboboxes:
            box.addItems(['必杀', '超必杀', '技能', '二技能'])

        # 设置敌方下拉框
        self.ui.enemy_color_comboBox.addItems(list('红绿蓝黄紫'))
        self.ui.enemy_side_comboBox.addItems(['科学', '魔法', '其他'])

        # 设置卡牌信息输出框
        self.text_edits = [self.ui.plainTextEdit_1, self.ui.plainTextEdit_2, self.ui.plainTextEdit_3]
        for edit in self.text_edits:
            edit.setLineWrapMode(edit.LineWrapMode.NoWrap)

        # 保存按钮事件
        self.ui.save_pushButton.clicked.connect(self.save_cards)

        # 加载按钮事件
        self.ui.load_pushButton.clicked.connect(self.load_cards)

        # 显示按钮事件
        self.ui.show_inf_pushButton.clicked.connect(self.display_inf)

        # 计算按钮事件
        self.ui.calc_dmg_pushButton.clicked.connect(self.show_damage)

        # 更改窗口比例菜单
        self.ui.win_action.triggered.connect(self.win_action_event)
        
        # 更改字体大小菜单
        self.ui.font_action.triggered.connect(self.font_action_event)

        # 更改阵营等级菜单
        self.ui.level_action.triggered.connect(self.level_action_event)

        # 设置为最大等级
        self.ui.max_level_action.triggered.connect(self.max_level_action_event)

        # 计算防御菜单
        self.ui.calc_def_action.triggered.connect(self.calc_def_action_event)

        #设置窗口字体
        self.win_init()
        

    def show_message(self, msg):
        traceback.print_exc()
        QMessageBox.warning(self.ui.centralwidget, 'Error', str(msg))

    def win_init(self):
        winscale, fontsize = self.config['winscale'], self.config['fontsize']
        self.image_size = int(winscale*self.image_size)

        w, h = self.win.size().width(), self.win.size().height()
        self.win.resize(int(winscale*w), int(winscale*h))
        
        for k, v in self.ui.__dict__.items():
            if isinstance(v, QWidget):
                rect = v.geometry()
                x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
                x, y, w, h = [int(winscale*n) for n in (x, y, w, h)]
                v.setGeometry(x, y, w, h)

                font = QFont()
                font.setPointSize(fontsize)
                v.setFont(font)
                

    def dict_to_yaml(self, data):
        with open('_.yaml', 'w') as f:
            YAML().dump(data, f)
        with open('_.yaml', 'r') as f:
            return f.read()

    def yaml_to_dict(self, text):
        with open('_.yaml', 'w') as f:
            f.write(text)
        with open('_.yaml', 'r') as f:
            return YAML().load(f)


    def check_color_side(self):
        '''获取选择的属性, 更新下拉框'''
        try:
            choosed_attr = []
            for box in self.attr_checkboxes:
                if box.isChecked():
                    choosed_attr.append(box.text())
            if '科学' in choosed_attr and '魔法' in choosed_attr:
                choosed_attr.append('科学魔法')
                

            f = lambda card:card[ts.color_index] in choosed_attr and card[ts.type_index] in choosed_attr and card[ts.side_index] in choosed_attr
            choosed_bcards = list(filter(f, self.bcards))
            choosed_acards = list(filter(f, self.acards))
            
            for i, box in enumerate(self.card_comboboxes):
                box.clear()
                box.setIconSize(QSize(self.image_size, self.image_size))
                box.addItem('')
                cards, icons, choosed_cards = (self.bcards, self.bicons, choosed_bcards) if i < 3 else (self.acards, self.aicons, choosed_acards)
                for j, card in enumerate(choosed_cards):
                    index = cards.index(card)
                    box.addItem(str(index))
                    box.setItemIcon(j+1, icons[index])
                    
        except Exception as e:
            self.show_message(e)
            

    def update_choosed_cards(self):
        '''选择卡牌后, 更新标签'''
        try:
            for i, (box, label) in enumerate(zip(self.card_comboboxes, self.card_labels)):
                current_index = box.currentIndex()
                if not current_index in (-1, 0):
                    label.setPixmap(box.itemIcon(current_index).pixmap(self.image_size, self.image_size))
                    self.card_index[i] = int(box.currentText())
                    box.setCurrentIndex(0)

                    if i < 3:
                        c = self.bcards[self.card_index[i]]
                    else:
                        c = self.acards[self.card_index[i]]
                    label.setToolTip('\n'.join([' '.join([c[ts.color_index], c[ts.side_index], str(c[ts.dire_index])]),
                                                c[ts.skill1_index], str(c[ts.skill2_index]), str(c[ts.skill3_index]),
                                                c[ts.passive1_index], str(c[ts.passive2_index])]))

        except Exception as e:
            self.show_message(e)


    def save_cards(self):
        '''存储卡牌列表'''
        try:
            filename = QFileDialog.getSaveFileName(ui.centralwidget)[0]
            if filename:
                index = self.card_index
                atk = [x.value() for x in self.attack_spinboxes]
                level = [x.value() for x in self.level_spinboxes]
                pas = [box.currentIndex() for box in self.passive_comboboxes]
                spe = [box.currentIndex() for box in self.skill_comboboxes]
                leaders = [box.value() for box in self.leader_spinboxes]
                enemy = [self.ui.enemy_color_comboBox.currentIndex(), self.ui.enemy_side_comboBox.currentIndex(), self.ui.enemy_def_spinBox.value()]
                
                text = str((index, atk, level, pas, spe, leaders, enemy))
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(text)

        except Exception as e:
            self.show_message(e)
            

    def load_cards(self):
        '''从文件读取卡牌列表'''
        try:
            filename = QFileDialog.getOpenFileName(ui.centralwidget)[0]
            if filename:
                with open(filename, encoding='utf-8') as f:
                    text = f.read()
                    
                index, atk, level, pas, spe, leaders, enemy = eval(text)
                
                self.card_index = index
                for i, (c, label) in enumerate(zip(self.card_index, self.card_labels)):
                    if i < 3:
                        cards = self.bcards
                    else:
                        cards = self.acards
                    p = QPixmap()
                    p.loadFromData(cards[c][0])
                    label.setPixmap(p)

                for v, box in zip(atk+level+leaders, self.attack_spinboxes+self.level_spinboxes+self.leader_spinboxes):
                    box.setValue(v)
                    
                for v, box in zip(pas+spe, self.passive_comboboxes+self.skill_comboboxes):
                    box.setCurrentIndex(v)

                for i, box in enumerate([self.ui.enemy_color_comboBox, self.ui.enemy_side_comboBox, self.ui.enemy_def_spinBox]):
                    if i < 2:
                        box.setCurrentIndex(enemy[i])
                    else:
                        box.setValue(enemy[i])

        except Exception as e:
            self.show_message(e)


    def display_inf(self):
        try:
            battle_cards, assist_cards = [], []
            for i in range(3):
                b_index, a_index = self.card_index[i], self.card_index[i+3]
                b, a = self.bcards[b_index], self.acards[a_index]
                battle_cards.append([0]+b[1:])
                assist_cards.append([0]+a[1:])

            skill_types = [x.currentText() for x in self.skill_comboboxes]

            card_levels = [x.value() for x in self.level_spinboxes]
            card_attacks = [x.value() for x in self.attack_spinboxes]
            passives = [x.currentText() for x in self.passive_comboboxes]
            leaders = [['队长中', self.ui.leader1_level_spinbox.value(), self.ui.leader1_spinBox.value()]]
            leaders.append(['队长大', self.ui.leader2_level_spinbox.value(), self.ui.leader2_spinBox.value()])
            enemy = [self.ui.enemy_color_comboBox.currentText(), self.ui.enemy_side_comboBox.currentText(), self.ui.enemy_def_spinBox.value()]

            #print(*battle_cards, *assist_cards, sep='\n')
            
            # 将卡牌信息转为计算用信息
            all_inf = bcard_args, acard_args, buff_args, enemy_arg = ts.trans_all_inf(assist_cards, battle_cards, skill_types, card_attacks, card_levels, enemy, passives, leaders)
            for i in range(3):
                inf = [x[i] for x in all_inf[:3]]+[all_inf[3]]
                inf_text = self.dict_to_yaml(inf)
                self.text_edits[i].setPlainText(inf_text)
   
        except Exception as e:
            self.show_message(e)


    def show_damage(self):
        '''计算当前总伤并显示'''
        try:
            t, inf = self.get_inf()
            dmg, total_sp = self.get_total_damage(t, inf)
            self.ui.damage_label.setText(str(dmg))
            self.ui.sp_label.setText(str(total_sp))
        
        except Exception as e:
            self.show_message(e)

    def get_inf(self):
        '''读取显示的yaml信息, 返回倍数和卡牌信息'''
        try:
            t = self.ui.dmg_times_spinBox.value()
            inf = [self.yaml_to_dict(self.text_edits[i].toPlainText()) for i in range(3)]
            return t, inf
        
        except Exception as e:
            self.show_message(e)

    def get_total_damage(self, t, inf):
        '''根据所有卡牌信息计算总伤与总SP'''
        try:
            dmg = 0
            total_sp = 0
            for i in range(3):
                bcard_arg, acard_arg, buff_arg, enemy_arg = inf[i]
                add, warning_text = cl.calc_damage(bcard_arg, acard_arg, self.config['calc_faction_level'], buff_arg, enemy_arg)
                dmg += add
                total_sp += cl.calc_sp(bcard_arg, acard_arg, buff_arg)
                if warning_text:
                    self.show_message(str(i)+': '+warning_text)
            if self.ui.break_checkBox.isChecked():
                total_sp += 8
            return dmg*t, total_sp
        
        except Exception as e:
            self.show_message(e)
            return None, None


    def win_action_event(self):
        try:
            self.config['winscale'] = QInputDialog.getDouble(self.ui.centralwidget, '', '设置窗口大小(重新运行程序后生效):',
                                                             self.config['winscale'], 0.5, 3.0)[0]
            with open(self.config_fname, 'w') as f:
                f.write(str(self.config))
        except Exception as e:
            self.show_message(e)
            
    def font_action_event(self):
        try:
            self.config['fontsize'] = QInputDialog.getInt(self.ui.centralwidget, '', '设置字体大小(重新运行程序后生效):',
                                                          self.config['fontsize'], 5, 20)[0]
            with open(self.config_fname, 'w') as f:
                f.write(str(self.config))
        except Exception as e:
            self.show_message(e)

    def level_action_event(self):
        try:
            default_text = '%d,%d,%d'%tuple(self.config['faction_level'])
            text = QInputDialog.getText(self.ui.centralwidget, '', '设置阵营等级(3个数, 逗号分隔):', text=default_text)[0]
            levels = eval(text.replace('，', ','))
            if all([isinstance(x, int) for x in levels]) and len(levels) == 3:
                self.config['faction_level'] = levels
                self.config['calc_faction_level'] = levels[:]
            else:
                raise ValueError('Not valid input')
            with open(self.config_fname, 'w') as f:
                f.write(str(self.config))
        except Exception as e:
            self.show_message(e)

    def max_level_action_event(self):
        try:
            self.config['calc_faction_level'] = [cl.card_params['最大等级']]*3
            for box in self.level_spinboxes:
                box.setValue(cl.card_params['最大等级'])
                
            for i, box in enumerate(self.attack_spinboxes):
                index = self.card_index[i]
                if i < 3:
                    card = self.bcards[index]
                else:
                    card = self.acards[index]
                box.setValue(max(card[ts.max_atk_index], card[ts.max_spa_index]))
                
        except Exception as e:
            self.show_message(e)

    def calc_def_action_event(self):
        '''根据伤害计算防御'''
        def dmg(defence, t, inf):
            for i in range(3):
                bcard_arg, acard_arg, buff_arg, enemy_arg = inf[i]
                enemy_arg['防御'] = defence
            return self.get_total_damage(t, inf)[0]
        
        try:
            real_dmg = QInputDialog.getInt(self.ui.centralwidget, '', '实际总伤害:')[0]
            t, inf = self.get_inf()
            defence = 0
            d = 10000
            for i in range(5):# 10000到1
                for j in range(10):
                    defence += d
                    if not ((d < 0) ^ (dmg(defence, t, inf) > real_dmg)):
                        # 同或, 防御减少至伤害大于实际伤害, 或防御增加至伤害小于实际伤害
                        break
                d = -d//10

            QMessageBox.about(self.ui.centralwidget, '', '防御: %d\n伤害: %d'%(defence, dmg(defence, t, inf)))
            
                
        except Exception as e:
            self.show_message(e)
            
            

if __name__ == '__main__':
    #加载主窗口
    app = QApplication(sys.argv)
    main_window = QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(main_window)

    # 将ui输入calc以实现功能
    calc = Calc(ui, main_window)
    
    main_window.show()

    #固定窗口大小
    main_window.setMaximumSize(main_window.size())
    main_window.setMinimumSize(main_window.size())

    #检测退出
    ex = app.exec()
    sys.exit(ex)
