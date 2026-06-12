# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'myuiZFNecR.ui'
##
## Created by: Qt User Interface Compiler version 6.7.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QAction, QBrush, QColor, QConicalGradient,
    QCursor, QFont, QFontDatabase, QGradient,
    QIcon, QImage, QKeySequence, QLinearGradient,
    QPainter, QPalette, QPixmap, QRadialGradient,
    QTransform)
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFrame,
    QGridLayout, QLabel, QMainWindow, QMenu,
    QMenuBar, QPlainTextEdit, QPushButton, QSizePolicy,
    QSpinBox, QStatusBar, QWidget)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(960, 720)
        font = QFont()
        font.setPointSize(15)
        MainWindow.setFont(font)
        self.font_action = QAction(MainWindow)
        self.font_action.setObjectName(u"font_action")
        self.win_action = QAction(MainWindow)
        self.win_action.setObjectName(u"win_action")
        self.calc_def_action = QAction(MainWindow)
        self.calc_def_action.setObjectName(u"calc_def_action")
        self.level_action = QAction(MainWindow)
        self.level_action.setObjectName(u"level_action")
        self.max_level_action = QAction(MainWindow)
        self.max_level_action.setObjectName(u"max_level_action")
        self.actionaaa = QAction(MainWindow)
        self.actionaaa.setObjectName(u"actionaaa")
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.gridLayoutWidget_2 = QWidget(self.centralwidget)
        self.gridLayoutWidget_2.setObjectName(u"gridLayoutWidget_2")
        self.gridLayoutWidget_2.setGeometry(QRect(610, 10, 331, 81))
        self.gridLayout_2 = QGridLayout(self.gridLayoutWidget_2)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.gridLayout_2.setContentsMargins(0, 0, 0, 0)
        self.science_checkBox = QCheckBox(self.gridLayoutWidget_2)
        self.science_checkBox.setObjectName(u"science_checkBox")
        self.science_checkBox.setFont(font)

        self.gridLayout_2.addWidget(self.science_checkBox, 0, 0, 1, 1)

        self.neutral_checkBox = QCheckBox(self.gridLayoutWidget_2)
        self.neutral_checkBox.setObjectName(u"neutral_checkBox")
        self.neutral_checkBox.setFont(font)

        self.gridLayout_2.addWidget(self.neutral_checkBox, 0, 2, 1, 1)

        self.magic_checkBox = QCheckBox(self.gridLayoutWidget_2)
        self.magic_checkBox.setObjectName(u"magic_checkBox")
        self.magic_checkBox.setFont(font)

        self.gridLayout_2.addWidget(self.magic_checkBox, 0, 1, 1, 1)

        self.physical_checkBox = QCheckBox(self.gridLayoutWidget_2)
        self.physical_checkBox.setObjectName(u"physical_checkBox")
        self.physical_checkBox.setFont(font)

        self.gridLayout_2.addWidget(self.physical_checkBox, 1, 0, 1, 1)

        self.mental_checkBox = QCheckBox(self.gridLayoutWidget_2)
        self.mental_checkBox.setObjectName(u"mental_checkBox")
        self.mental_checkBox.setFont(font)

        self.gridLayout_2.addWidget(self.mental_checkBox, 1, 1, 1, 1)

        self.gridLayoutWidget = QWidget(self.centralwidget)
        self.gridLayoutWidget.setObjectName(u"gridLayoutWidget")
        self.gridLayoutWidget.setGeometry(QRect(10, 10, 561, 81))
        self.gridLayout = QGridLayout(self.gridLayoutWidget)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        self.green_checkBox = QCheckBox(self.gridLayoutWidget)
        self.green_checkBox.setObjectName(u"green_checkBox")
        self.green_checkBox.setFont(font)

        self.gridLayout.addWidget(self.green_checkBox, 0, 1, 1, 1)

        self.sred_checkBox = QCheckBox(self.gridLayoutWidget)
        self.sred_checkBox.setObjectName(u"sred_checkBox")
        self.sred_checkBox.setFont(font)

        self.gridLayout.addWidget(self.sred_checkBox, 1, 0, 1, 1)

        self.red_checkBox = QCheckBox(self.gridLayoutWidget)
        self.red_checkBox.setObjectName(u"red_checkBox")
        self.red_checkBox.setFont(font)

        self.gridLayout.addWidget(self.red_checkBox, 0, 0, 1, 1)

        self.yellow_checkBox = QCheckBox(self.gridLayoutWidget)
        self.yellow_checkBox.setObjectName(u"yellow_checkBox")
        self.yellow_checkBox.setFont(font)

        self.gridLayout.addWidget(self.yellow_checkBox, 0, 3, 1, 1)

        self.blue_checkBox = QCheckBox(self.gridLayoutWidget)
        self.blue_checkBox.setObjectName(u"blue_checkBox")
        self.blue_checkBox.setFont(font)

        self.gridLayout.addWidget(self.blue_checkBox, 0, 2, 1, 1)

        self.purple_checkBox = QCheckBox(self.gridLayoutWidget)
        self.purple_checkBox.setObjectName(u"purple_checkBox")
        self.purple_checkBox.setFont(font)

        self.gridLayout.addWidget(self.purple_checkBox, 0, 4, 1, 1)

        self.sgreen_checkBox = QCheckBox(self.gridLayoutWidget)
        self.sgreen_checkBox.setObjectName(u"sgreen_checkBox")
        self.sgreen_checkBox.setFont(font)

        self.gridLayout.addWidget(self.sgreen_checkBox, 1, 1, 1, 1)

        self.sblue_checkBox = QCheckBox(self.gridLayoutWidget)
        self.sblue_checkBox.setObjectName(u"sblue_checkBox")
        self.sblue_checkBox.setFont(font)

        self.gridLayout.addWidget(self.sblue_checkBox, 1, 2, 1, 1)

        self.syellow_checkBox = QCheckBox(self.gridLayoutWidget)
        self.syellow_checkBox.setObjectName(u"syellow_checkBox")
        self.syellow_checkBox.setFont(font)

        self.gridLayout.addWidget(self.syellow_checkBox, 1, 3, 1, 1)

        self.spurple_checkBox = QCheckBox(self.gridLayoutWidget)
        self.spurple_checkBox.setObjectName(u"spurple_checkBox")
        self.spurple_checkBox.setFont(font)

        self.gridLayout.addWidget(self.spurple_checkBox, 1, 4, 1, 1)

        self.frame = QFrame(self.centralwidget)
        self.frame.setObjectName(u"frame")
        self.frame.setGeometry(QRect(580, 0, 21, 101))
        self.frame.setFrameShape(QFrame.Shape.VLine)
        self.frame.setFrameShadow(QFrame.Shadow.Raised)
        self.frame_2 = QFrame(self.centralwidget)
        self.frame_2.setObjectName(u"frame_2")
        self.frame_2.setGeometry(QRect(10, 90, 951, 21))
        self.frame_2.setFrameShape(QFrame.Shape.HLine)
        self.frame_2.setFrameShadow(QFrame.Shadow.Raised)
        self.gridLayoutWidget_3 = QWidget(self.centralwidget)
        self.gridLayoutWidget_3.setObjectName(u"gridLayoutWidget_3")
        self.gridLayoutWidget_3.setGeometry(QRect(10, 110, 382, 521))
        self.gridLayout_3 = QGridLayout(self.gridLayoutWidget_3)
        self.gridLayout_3.setObjectName(u"gridLayout_3")
        self.gridLayout_3.setContentsMargins(0, 0, 0, 0)
        self.b3_level_spinBox = QSpinBox(self.gridLayoutWidget_3)
        self.b3_level_spinBox.setObjectName(u"b3_level_spinBox")
        self.b3_level_spinBox.setFont(font)
        self.b3_level_spinBox.setMaximum(999)

        self.gridLayout_3.addWidget(self.b3_level_spinBox, 2, 2, 1, 1)

        self.p3_comboBox = QComboBox(self.gridLayoutWidget_3)
        self.p3_comboBox.setObjectName(u"p3_comboBox")
        self.p3_comboBox.setFont(font)

        self.gridLayout_3.addWidget(self.p3_comboBox, 8, 2, 1, 1)

        self.a1_level_spinBox = QSpinBox(self.gridLayoutWidget_3)
        self.a1_level_spinBox.setObjectName(u"a1_level_spinBox")
        self.a1_level_spinBox.setFont(font)
        self.a1_level_spinBox.setMaximum(999)

        self.gridLayout_3.addWidget(self.a1_level_spinBox, 6, 0, 1, 1)

        self.b1_level_spinBox = QSpinBox(self.gridLayoutWidget_3)
        self.b1_level_spinBox.setObjectName(u"b1_level_spinBox")
        self.b1_level_spinBox.setFont(font)
        self.b1_level_spinBox.setMaximum(999)

        self.gridLayout_3.addWidget(self.b1_level_spinBox, 2, 0, 1, 1)

        self.b2_atk_spinBox = QSpinBox(self.gridLayoutWidget_3)
        self.b2_atk_spinBox.setObjectName(u"b2_atk_spinBox")
        self.b2_atk_spinBox.setFont(font)
        self.b2_atk_spinBox.setMaximum(99999)

        self.gridLayout_3.addWidget(self.b2_atk_spinBox, 1, 1, 1, 1)

        self.b3_label = QLabel(self.gridLayoutWidget_3)
        self.b3_label.setObjectName(u"b3_label")

        self.gridLayout_3.addWidget(self.b3_label, 3, 2, 1, 1)

        self.a2_level_spinBox = QSpinBox(self.gridLayoutWidget_3)
        self.a2_level_spinBox.setObjectName(u"a2_level_spinBox")
        self.a2_level_spinBox.setFont(font)
        self.a2_level_spinBox.setMaximum(999)

        self.gridLayout_3.addWidget(self.a2_level_spinBox, 6, 1, 1, 1)

        self.b1_label = QLabel(self.gridLayoutWidget_3)
        self.b1_label.setObjectName(u"b1_label")

        self.gridLayout_3.addWidget(self.b1_label, 3, 0, 1, 1)

        self.p1_comboBox = QComboBox(self.gridLayoutWidget_3)
        self.p1_comboBox.setObjectName(u"p1_comboBox")
        self.p1_comboBox.setFont(font)

        self.gridLayout_3.addWidget(self.p1_comboBox, 8, 0, 1, 1)

        self.p2_comboBox = QComboBox(self.gridLayoutWidget_3)
        self.p2_comboBox.setObjectName(u"p2_comboBox")
        self.p2_comboBox.setFont(font)

        self.gridLayout_3.addWidget(self.p2_comboBox, 8, 1, 1, 1)

        self.a3_level_spinBox = QSpinBox(self.gridLayoutWidget_3)
        self.a3_level_spinBox.setObjectName(u"a3_level_spinBox")
        self.a3_level_spinBox.setFont(font)
        self.a3_level_spinBox.setMaximum(999)

        self.gridLayout_3.addWidget(self.a3_level_spinBox, 6, 2, 1, 1)

        self.b2_label = QLabel(self.gridLayoutWidget_3)
        self.b2_label.setObjectName(u"b2_label")

        self.gridLayout_3.addWidget(self.b2_label, 3, 1, 1, 1)

        self.b1_comboBox = QComboBox(self.gridLayoutWidget_3)
        self.b1_comboBox.setObjectName(u"b1_comboBox")
        self.b1_comboBox.setFont(font)
        self.b1_comboBox.setIconSize(QSize(100, 20))

        self.gridLayout_3.addWidget(self.b1_comboBox, 0, 0, 1, 1)

        self.a1_label = QLabel(self.gridLayoutWidget_3)
        self.a1_label.setObjectName(u"a1_label")

        self.gridLayout_3.addWidget(self.a1_label, 7, 0, 1, 1)

        self.a2_atk_spinBox = QSpinBox(self.gridLayoutWidget_3)
        self.a2_atk_spinBox.setObjectName(u"a2_atk_spinBox")
        self.a2_atk_spinBox.setFont(font)
        self.a2_atk_spinBox.setMaximum(99999)

        self.gridLayout_3.addWidget(self.a2_atk_spinBox, 5, 1, 1, 1)

        self.b1_atk_spinBox = QSpinBox(self.gridLayoutWidget_3)
        self.b1_atk_spinBox.setObjectName(u"b1_atk_spinBox")
        self.b1_atk_spinBox.setFont(font)
        self.b1_atk_spinBox.setMaximum(99999)

        self.gridLayout_3.addWidget(self.b1_atk_spinBox, 1, 0, 1, 1)

        self.a3_label = QLabel(self.gridLayoutWidget_3)
        self.a3_label.setObjectName(u"a3_label")

        self.gridLayout_3.addWidget(self.a3_label, 7, 2, 1, 1)

        self.a1_comboBox = QComboBox(self.gridLayoutWidget_3)
        self.a1_comboBox.setObjectName(u"a1_comboBox")
        self.a1_comboBox.setFont(font)
        self.a1_comboBox.setIconSize(QSize(100, 20))

        self.gridLayout_3.addWidget(self.a1_comboBox, 4, 0, 1, 1)

        self.b2_level_spinBox = QSpinBox(self.gridLayoutWidget_3)
        self.b2_level_spinBox.setObjectName(u"b2_level_spinBox")
        self.b2_level_spinBox.setFont(font)
        self.b2_level_spinBox.setMaximum(999)

        self.gridLayout_3.addWidget(self.b2_level_spinBox, 2, 1, 1, 1)

        self.a3_atk_spinBox = QSpinBox(self.gridLayoutWidget_3)
        self.a3_atk_spinBox.setObjectName(u"a3_atk_spinBox")
        self.a3_atk_spinBox.setFont(font)
        self.a3_atk_spinBox.setMaximum(99999)

        self.gridLayout_3.addWidget(self.a3_atk_spinBox, 5, 2, 1, 1)

        self.b2_comboBox = QComboBox(self.gridLayoutWidget_3)
        self.b2_comboBox.setObjectName(u"b2_comboBox")
        self.b2_comboBox.setFont(font)
        self.b2_comboBox.setIconSize(QSize(100, 20))

        self.gridLayout_3.addWidget(self.b2_comboBox, 0, 1, 1, 1)

        self.a2_comboBox = QComboBox(self.gridLayoutWidget_3)
        self.a2_comboBox.setObjectName(u"a2_comboBox")
        self.a2_comboBox.setFont(font)
        self.a2_comboBox.setIconSize(QSize(100, 20))

        self.gridLayout_3.addWidget(self.a2_comboBox, 4, 1, 1, 1)

        self.b3_atk_spinBox = QSpinBox(self.gridLayoutWidget_3)
        self.b3_atk_spinBox.setObjectName(u"b3_atk_spinBox")
        self.b3_atk_spinBox.setFont(font)
        self.b3_atk_spinBox.setMaximum(99999)

        self.gridLayout_3.addWidget(self.b3_atk_spinBox, 1, 2, 1, 1)

        self.b3_comboBox = QComboBox(self.gridLayoutWidget_3)
        self.b3_comboBox.setObjectName(u"b3_comboBox")
        self.b3_comboBox.setFont(font)
        self.b3_comboBox.setIconSize(QSize(100, 20))

        self.gridLayout_3.addWidget(self.b3_comboBox, 0, 2, 1, 1)

        self.a1_atk_spinBox = QSpinBox(self.gridLayoutWidget_3)
        self.a1_atk_spinBox.setObjectName(u"a1_atk_spinBox")
        self.a1_atk_spinBox.setFont(font)
        self.a1_atk_spinBox.setMaximum(99999)

        self.gridLayout_3.addWidget(self.a1_atk_spinBox, 5, 0, 1, 1)

        self.a3_comboBox = QComboBox(self.gridLayoutWidget_3)
        self.a3_comboBox.setObjectName(u"a3_comboBox")
        self.a3_comboBox.setFont(font)
        self.a3_comboBox.setIconSize(QSize(100, 20))

        self.gridLayout_3.addWidget(self.a3_comboBox, 4, 2, 1, 1)

        self.a2_label = QLabel(self.gridLayoutWidget_3)
        self.a2_label.setObjectName(u"a2_label")

        self.gridLayout_3.addWidget(self.a2_label, 7, 1, 1, 1)

        self.gridLayoutWidget_4 = QWidget(self.centralwidget)
        self.gridLayoutWidget_4.setObjectName(u"gridLayoutWidget_4")
        self.gridLayoutWidget_4.setGeometry(QRect(430, 110, 331, 111))
        self.gridLayout_4 = QGridLayout(self.gridLayoutWidget_4)
        self.gridLayout_4.setObjectName(u"gridLayout_4")
        self.gridLayout_4.setContentsMargins(0, 0, 0, 0)
        self.leader1_spinBox = QSpinBox(self.gridLayoutWidget_4)
        self.leader1_spinBox.setObjectName(u"leader1_spinBox")
        self.leader1_spinBox.setFont(font)

        self.gridLayout_4.addWidget(self.leader1_spinBox, 1, 1, 1, 1)

        self.label_8 = QLabel(self.gridLayoutWidget_4)
        self.label_8.setObjectName(u"label_8")
        self.label_8.setFont(font)

        self.gridLayout_4.addWidget(self.label_8, 0, 0, 1, 1)

        self.label_11 = QLabel(self.gridLayoutWidget_4)
        self.label_11.setObjectName(u"label_11")
        self.label_11.setFont(font)

        self.gridLayout_4.addWidget(self.label_11, 1, 0, 1, 1)

        self.label_9 = QLabel(self.gridLayoutWidget_4)
        self.label_9.setObjectName(u"label_9")
        self.label_9.setFont(font)

        self.gridLayout_4.addWidget(self.label_9, 0, 1, 1, 1)

        self.label_10 = QLabel(self.gridLayoutWidget_4)
        self.label_10.setObjectName(u"label_10")
        self.label_10.setFont(font)

        self.gridLayout_4.addWidget(self.label_10, 0, 2, 1, 1)

        self.leader2_spinBox = QSpinBox(self.gridLayoutWidget_4)
        self.leader2_spinBox.setObjectName(u"leader2_spinBox")
        self.leader2_spinBox.setFont(font)

        self.gridLayout_4.addWidget(self.leader2_spinBox, 1, 2, 1, 1)

        self.label_12 = QLabel(self.gridLayoutWidget_4)
        self.label_12.setObjectName(u"label_12")
        self.label_12.setFont(font)

        self.gridLayout_4.addWidget(self.label_12, 2, 0, 1, 1)

        self.leader1_level_spinbox = QSpinBox(self.gridLayoutWidget_4)
        self.leader1_level_spinbox.setObjectName(u"leader1_level_spinbox")
        self.leader1_level_spinbox.setFont(font)
        self.leader1_level_spinbox.setMaximum(999)

        self.gridLayout_4.addWidget(self.leader1_level_spinbox, 2, 1, 1, 1)

        self.leader2_level_spinbox = QSpinBox(self.gridLayoutWidget_4)
        self.leader2_level_spinbox.setObjectName(u"leader2_level_spinbox")
        self.leader2_level_spinbox.setFont(font)
        self.leader2_level_spinbox.setMaximum(999)

        self.gridLayout_4.addWidget(self.leader2_level_spinbox, 2, 2, 1, 1)

        self.horizontalLayoutWidget = QWidget(self.centralwidget)
        self.horizontalLayoutWidget.setObjectName(u"horizontalLayoutWidget")
        self.horizontalLayoutWidget.setGeometry(QRect(430, 240, 501, 291))
        self.gridLayout_5 = QGridLayout(self.horizontalLayoutWidget)
        self.gridLayout_5.setObjectName(u"gridLayout_5")
        self.gridLayout_5.setContentsMargins(0, 0, 0, 0)
        self.plainTextEdit_2 = QPlainTextEdit(self.horizontalLayoutWidget)
        self.plainTextEdit_2.setObjectName(u"plainTextEdit_2")

        self.gridLayout_5.addWidget(self.plainTextEdit_2, 0, 1, 1, 1)

        self.plainTextEdit_1 = QPlainTextEdit(self.horizontalLayoutWidget)
        self.plainTextEdit_1.setObjectName(u"plainTextEdit_1")

        self.gridLayout_5.addWidget(self.plainTextEdit_1, 0, 0, 1, 1)

        self.plainTextEdit_3 = QPlainTextEdit(self.horizontalLayoutWidget)
        self.plainTextEdit_3.setObjectName(u"plainTextEdit_3")

        self.gridLayout_5.addWidget(self.plainTextEdit_3, 0, 2, 1, 1)

        self.skill1_comboBox = QComboBox(self.horizontalLayoutWidget)
        self.skill1_comboBox.setObjectName(u"skill1_comboBox")
        self.skill1_comboBox.setFont(font)
        self.skill1_comboBox.setIconSize(QSize(100, 20))

        self.gridLayout_5.addWidget(self.skill1_comboBox, 1, 0, 1, 1)

        self.skill2_comboBox = QComboBox(self.horizontalLayoutWidget)
        self.skill2_comboBox.setObjectName(u"skill2_comboBox")
        self.skill2_comboBox.setFont(font)
        self.skill2_comboBox.setIconSize(QSize(100, 20))

        self.gridLayout_5.addWidget(self.skill2_comboBox, 1, 1, 1, 1)

        self.skill3_comboBox = QComboBox(self.horizontalLayoutWidget)
        self.skill3_comboBox.setObjectName(u"skill3_comboBox")
        self.skill3_comboBox.setFont(font)
        self.skill3_comboBox.setIconSize(QSize(100, 20))

        self.gridLayout_5.addWidget(self.skill3_comboBox, 1, 2, 1, 1)

        self.show_inf_pushButton = QPushButton(self.centralwidget)
        self.show_inf_pushButton.setObjectName(u"show_inf_pushButton")
        self.show_inf_pushButton.setGeometry(QRect(540, 570, 91, 35))
        self.show_inf_pushButton.setFont(font)
        self.frame_5 = QFrame(self.centralwidget)
        self.frame_5.setObjectName(u"frame_5")
        self.frame_5.setGeometry(QRect(410, 540, 551, 21))
        self.frame_5.setFrameShape(QFrame.Shape.HLine)
        self.frame_5.setFrameShadow(QFrame.Shadow.Raised)
        self.calc_dmg_pushButton = QPushButton(self.centralwidget)
        self.calc_dmg_pushButton.setObjectName(u"calc_dmg_pushButton")
        self.calc_dmg_pushButton.setGeometry(QRect(540, 610, 91, 35))
        self.calc_dmg_pushButton.setFont(font)
        self.enemy_color_comboBox = QComboBox(self.centralwidget)
        self.enemy_color_comboBox.setObjectName(u"enemy_color_comboBox")
        self.enemy_color_comboBox.setGeometry(QRect(800, 110, 131, 31))
        self.enemy_color_comboBox.setFont(font)
        self.enemy_side_comboBox = QComboBox(self.centralwidget)
        self.enemy_side_comboBox.setObjectName(u"enemy_side_comboBox")
        self.enemy_side_comboBox.setGeometry(QRect(800, 150, 131, 31))
        self.enemy_side_comboBox.setFont(font)
        self.frame_3 = QFrame(self.centralwidget)
        self.frame_3.setObjectName(u"frame_3")
        self.frame_3.setGeometry(QRect(400, 100, 21, 561))
        self.frame_3.setFrameShape(QFrame.Shape.VLine)
        self.frame_3.setFrameShadow(QFrame.Shadow.Raised)
        self.enemy_def_spinBox = QSpinBox(self.centralwidget)
        self.enemy_def_spinBox.setObjectName(u"enemy_def_spinBox")
        self.enemy_def_spinBox.setGeometry(QRect(800, 190, 131, 33))
        self.enemy_def_spinBox.setFont(font)
        self.enemy_def_spinBox.setMaximum(999999999)
        self.frame_4 = QFrame(self.centralwidget)
        self.frame_4.setObjectName(u"frame_4")
        self.frame_4.setGeometry(QRect(770, 100, 21, 131))
        self.frame_4.setFrameShape(QFrame.Shape.VLine)
        self.frame_4.setFrameShadow(QFrame.Shadow.Raised)
        self.dmg_times_spinBox = QSpinBox(self.centralwidget)
        self.dmg_times_spinBox.setObjectName(u"dmg_times_spinBox")
        self.dmg_times_spinBox.setGeometry(QRect(660, 570, 88, 31))
        self.dmg_times_spinBox.setFont(font)
        self.dmg_times_spinBox.setMaximum(999999999)
        self.dmg_times_spinBox.setValue(1)
        self.label = QLabel(self.centralwidget)
        self.label.setObjectName(u"label")
        self.label.setGeometry(QRect(740, 570, 41, 31))
        self.damage_label = QLabel(self.centralwidget)
        self.damage_label.setObjectName(u"damage_label")
        self.damage_label.setGeometry(QRect(790, 570, 141, 31))
        self.sp_label = QLabel(self.centralwidget)
        self.sp_label.setObjectName(u"sp_label")
        self.sp_label.setGeometry(QRect(790, 610, 141, 31))
        self.break_checkBox = QCheckBox(self.centralwidget)
        self.break_checkBox.setObjectName(u"break_checkBox")
        self.break_checkBox.setGeometry(QRect(660, 610, 121, 30))
        self.save_pushButton = QPushButton(self.centralwidget)
        self.save_pushButton.setObjectName(u"save_pushButton")
        self.save_pushButton.setGeometry(QRect(430, 570, 91, 35))
        self.save_pushButton.setFont(font)
        self.load_pushButton = QPushButton(self.centralwidget)
        self.load_pushButton.setObjectName(u"load_pushButton")
        self.load_pushButton.setGeometry(QRect(430, 610, 91, 35))
        self.load_pushButton.setFont(font)
        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 960, 33))
        font1 = QFont()
        font1.setFamilies([u"SimSun-ExtB"])
        font1.setPointSize(15)
        font1.setBold(False)
        self.menubar.setFont(font1)
        self.menu = QMenu(self.menubar)
        self.menu.setObjectName(u"menu")
        self.menu_2 = QMenu(self.menubar)
        self.menu_2.setObjectName(u"menu_2")
        font2 = QFont()
        font2.setFamilies([u"SimSun-ExtB"])
        font2.setPointSize(15)
        font2.setBold(False)
        font2.setKerning(True)
        self.menu_2.setFont(font2)
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.menubar.addAction(self.menu.menuAction())
        self.menubar.addAction(self.menu_2.menuAction())
        self.menu.addAction(self.font_action)
        self.menu.addAction(self.win_action)
        self.menu.addAction(self.level_action)
        self.menu_2.addAction(self.calc_def_action)
        self.menu_2.addAction(self.max_level_action)

        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"MainWindow", None))
        self.font_action.setText(QCoreApplication.translate("MainWindow", u"\u5b57\u4f53\u5927\u5c0f", None))
        self.win_action.setText(QCoreApplication.translate("MainWindow", u"\u7a97\u53e3\u6bd4\u4f8b", None))
        self.calc_def_action.setText(QCoreApplication.translate("MainWindow", u"\u8ba1\u7b97\u9632\u5fa1", None))
        self.level_action.setText(QCoreApplication.translate("MainWindow", u"\u9635\u8425\u7b49\u7ea7", None))
        self.max_level_action.setText(QCoreApplication.translate("MainWindow", u"\u6700\u5927\u7b49\u7ea7", None))
        self.actionaaa.setText(QCoreApplication.translate("MainWindow", u"\u8ba1\u7b97SP", None))
        self.science_checkBox.setText(QCoreApplication.translate("MainWindow", u"\u79d1\u5b66", None))
        self.neutral_checkBox.setText(QCoreApplication.translate("MainWindow", u"\u5176\u4ed6", None))
        self.magic_checkBox.setText(QCoreApplication.translate("MainWindow", u"\u9b54\u6cd5", None))
        self.physical_checkBox.setText(QCoreApplication.translate("MainWindow", u"\u7269\u7406", None))
        self.mental_checkBox.setText(QCoreApplication.translate("MainWindow", u"\u5f02\u80fd", None))
        self.green_checkBox.setText(QCoreApplication.translate("MainWindow", u"\u7eff", None))
        self.sred_checkBox.setText(QCoreApplication.translate("MainWindow", u"\u8d85\u7ea2", None))
        self.red_checkBox.setText(QCoreApplication.translate("MainWindow", u"\u7ea2", None))
        self.yellow_checkBox.setText(QCoreApplication.translate("MainWindow", u"\u9ec4", None))
        self.blue_checkBox.setText(QCoreApplication.translate("MainWindow", u"\u84dd", None))
        self.purple_checkBox.setText(QCoreApplication.translate("MainWindow", u"\u7d2b", None))
        self.sgreen_checkBox.setText(QCoreApplication.translate("MainWindow", u"\u8d85\u7eff", None))
        self.sblue_checkBox.setText(QCoreApplication.translate("MainWindow", u"\u8d85\u84dd", None))
        self.syellow_checkBox.setText(QCoreApplication.translate("MainWindow", u"\u8d85\u9ec4", None))
        self.spurple_checkBox.setText(QCoreApplication.translate("MainWindow", u"\u8d85\u7d2b", None))
        self.b3_label.setText("")
        self.b1_label.setText("")
        self.b2_label.setText("")
        self.a1_label.setText("")
#if QT_CONFIG(tooltip)
        self.b1_atk_spinBox.setToolTip(QCoreApplication.translate("MainWindow", u"<html><head/><body><p><br/></p></body></html>", None))
#endif // QT_CONFIG(tooltip)
        self.a3_label.setText("")
        self.a2_label.setText("")
        self.label_8.setText(QCoreApplication.translate("MainWindow", u"\u961f\u957f", None))
        self.label_11.setText(QCoreApplication.translate("MainWindow", u"\u4e2a\u6570", None))
        self.label_9.setText(QCoreApplication.translate("MainWindow", u"\u4e2d", None))
        self.label_10.setText(QCoreApplication.translate("MainWindow", u"\u5927", None))
        self.label_12.setText(QCoreApplication.translate("MainWindow", u"\u7b49\u7ea7", None))
        self.show_inf_pushButton.setText(QCoreApplication.translate("MainWindow", u"\u663e\u793a", None))
        self.calc_dmg_pushButton.setText(QCoreApplication.translate("MainWindow", u"\u8ba1\u7b97", None))
        self.label.setText(QCoreApplication.translate("MainWindow", u"\u500d", None))
        self.damage_label.setText("")
        self.sp_label.setText("")
        self.break_checkBox.setText(QCoreApplication.translate("MainWindow", u"\u6253\u5f31\u70b9", None))
        self.save_pushButton.setText(QCoreApplication.translate("MainWindow", u"\u4fdd\u5b58", None))
        self.load_pushButton.setText(QCoreApplication.translate("MainWindow", u"\u52a0\u8f7d", None))
        self.menu.setTitle(QCoreApplication.translate("MainWindow", u"\u8bbe\u7f6e", None))
        self.menu_2.setTitle(QCoreApplication.translate("MainWindow", u"\u5176\u5b83", None))
    # retranslateUi

