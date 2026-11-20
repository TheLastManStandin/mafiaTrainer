from __future__ import annotations

import math
import random
import uuid
from shiboken6 import isValid
from collections import Counter
from pathlib import Path

from PySide6.QtCore import Qt, QSize, QUrl, QTimer
from PySide6.QtGui import QColor, QDesktopServices, QFont, QImageReader, QMovie, QPainter, QPen, QPixmap, QShortcut, QKeySequence, QIcon
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog, QFileDialog,
    QFormLayout, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QScrollArea,
    QSizePolicy, QVBoxLayout, QWidget,
)
from .core import ASSETS, CATEGORIES, LEVELS, VK_URL, Library, Question, Session, select_questions

STYLE = '''
* { font-family: "DejaVu Sans"; font-size: 13px; }
QMainWindow, QDialog { background: #141619; color: #f2f0eb; }
QWidget { color: #f2f0eb; }
QWidget#rail { background: #101113; border-right: 1px solid #2a2b2f; }
QScrollArea, QScrollArea > QWidget > QWidget { background: #141619; border: none; }
QLabel { background: transparent; }
QLabel#muted { color: #999ba4; }
QLabel#eyebrow { color: #d98072; font-size: 11px; font-weight: bold; }
QLabel#title { font-size: 36px; font-weight: bold; }
QLabel#subtitle { font-size: 22px; font-weight: bold; }
QLabel#question { font-size: 21px; font-weight: bold; }
QLabel#stat { font-size: 30px; font-weight: bold; }
QFrame#card { background: #1d1f23; border: 1px solid #33353b; border-radius: 14px; }
QFrame#feedback { background: #1b2723; border: 1px solid #3e6654; border-radius: 12px; }
QFrame#wrong { background: #30231f; border: 1px solid #805143; border-radius: 12px; }
QPushButton { background: #292c32; border: 1px solid #393c44; padding: 11px 16px; border-radius: 8px; text-align: center; }
QPushButton:hover { background: #353943; border-color: #686b75; }
QPushButton:pressed { background: #454952; }
QPushButton:focus { border: 2px solid #e3aa8f; }
QPushButton:disabled { color: #656770; background: #25272b; border-color: #303238; }
QPushButton#primary { background: #bd5444; color: white; border: 1px solid #cf705f; font-weight: bold; }
QPushButton#primary:hover { background: #d06551; }
QPushButton#primary:disabled { background: #593c36; color: #8c7770; border-color: #593c36; }
QPushButton#nav { text-align: left; padding: 13px; border: none; background: transparent; color: #a4a5ad; }
QPushButton#nav:checked { background: #2c211f; color: #f0ad99; border-left: 3px solid #d97661; }
QPushButton#level { text-align: left; min-height: 57px; background: #1d1f23; }
QPushButton#level:checked { background: #33241f; border: 1px solid #c37560; }
QPushButton#option { text-align: left; padding: 15px; min-height: 22px; }
QPushButton#option:checked { background: #3a2a24; border-color: #d98b6d; }
QPushButton#danger { background: transparent; border-color: #614037; color: #e7a18f; }
QCheckBox { spacing: 9px; font-weight: bold; }
QCheckBox::indicator { width: 18px; height: 18px; border: 1px solid #666975; border-radius: 4px; background: #17191d; }
QCheckBox::indicator:checked { background: #c66a53; border: 2px solid #e8ad94; image: none; }
QLineEdit, QPlainTextEdit, QComboBox { color: #f1eee8; background: #121417; border: 1px solid #43464f; border-radius: 7px; padding: 10px; selection-background-color: #9f503f; }
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus { border-color: #d89578; }
QComboBox QAbstractItemView { color: #f1eee8; background: #23262c; selection-background-color: #694236; }
QProgressBar { border: none; background: #303238; border-radius: 3px; max-height: 6px; min-height: 6px; }
QProgressBar::chunk { background: #cb725c; border-radius: 3px; }
QScrollBar:vertical { background: #17191c; width: 10px; }
QScrollBar::handle:vertical { background: #4a4d55; min-height: 32px; border-radius: 4px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QToolTip { background: #30333a; color: white; border: 1px solid #555; padding: 6px; }
'''


def label(text='', style='', wrap=True):
    w = QLabel(text)
    w.setTextFormat(Qt.TextFormat.PlainText)
    w.setWordWrap(wrap)
    if style:
        w.setObjectName(style)
    w.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return w


def button(text, callback=None, style=''):
    w = QPushButton(text)
    w.setCursor(Qt.CursorShape.PointingHandCursor)
    if style:
        w.setObjectName(style)
    if callback:
        w.clicked.connect(callback)
    return w


def card():
    w = QFrame()
    w.setObjectName('card')
    layout = QVBoxLayout(w)
    layout.setContentsMargins(22, 20, 22, 20)
    layout.setSpacing(12)
    return w, layout


def row(*widgets):
    layout = QHBoxLayout()
    layout.setSpacing(10)
    for w in widgets:
        layout.addWidget(w)
    return layout


class TableBoard(QWidget):
    def __init__(self, numbers):
        super().__init__()
        self.numbers = numbers
        self.setFixedHeight(170)
        self.setMinimumWidth(250)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy = self.width()/2, 85
        rx, ry = min(self.width()/2-30, 240), 64
        p.setBrush(QColor('#222d28'))
        p.setPen(QPen(QColor('#425349'), 2))
        p.drawEllipse(int(cx-rx+20), int(cy-ry+12), int(2*rx-40), int(2*ry-24))
        p.setPen(QColor('#99a69b'))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, 'ИГРОВОЙ СТОЛ')
        for i,n in enumerate(self.numbers):
            angle = -math.pi/2 + 2*math.pi*i/len(self.numbers)
            x, y = cx+rx*math.cos(angle), cy+ry*math.sin(angle)
            p.setBrush(QColor('#33383e'))
            p.setPen(QPen(QColor('#7c828a'), 1))
            p.drawEllipse(int(x-16), int(y-16), 32, 32)
            p.setPen(QColor('#f2eee8'))
            p.drawText(int(x-16),int(y-16),32,32,Qt.AlignmentFlag.AlignCenter,str(n))


class Media(QWidget):
    def __init__(self, path, max_height=290):
        super().__init__()
        self.movie = None
        self.media_path = Path(path) if Path(path).is_absolute() else ASSETS / path
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        self.view = QLabel()
        self.view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.view.setMinimumHeight(80)
        layout.addWidget(self.view)
        if self.media_path.suffix.lower() == '.gif':
            self.movie = QMovie(str(self.media_path))
            self.movie.jumpToFrame(0)
            size = self.movie.currentPixmap().size()
            size.scale(560,max_height,Qt.AspectRatioMode.KeepAspectRatio)
            self.movie.setScaledSize(size)
            self.view.setMovie(self.movie)
            self.movie.start()
            replay = button('↻  Повторить анимацию', self.replay)
            replay.setMaximumWidth(240)
            layout.addWidget(replay,alignment=Qt.AlignmentFlag.AlignHCenter)
        else:
            pixmap = QPixmap(str(self.media_path))
            if pixmap.isNull():
                self.view.setText('Изображение недоступно. Можно удалить вопрос или пропустить его.')
            else:
                self.view.setPixmap(pixmap.scaled(560,max_height,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
        self.destroyed.connect(self.stop)

    def replay(self):
        if self.movie:
            self.movie.stop(); self.movie.start()

    def stop(self):
        if self.movie:
            self.movie.stop()

    def hideEvent(self,event):
        if self.movie: self.movie.stop()
        super().hideEvent(event)

    def showEvent(self,event):
        if self.movie: self.movie.start()
        super().showEvent(event)


class QuestionEditor(QDialog):
    def __init__(self, library, parent):
        super().__init__(parent)
        self.library = library
        self.attachment = None
        self.setWindowTitle('Добавить вопрос')
        self.resize(760, 780)
        outer = QVBoxLayout(self)
        outer.addWidget(label('Новый вопрос', 'subtitle'))
        outer.addWidget(label('Он появится в выбранных темах и сохранится в твоей базе.', 'muted'))
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        content = QWidget(); form = QFormLayout(content); form.setSpacing(12)
        self.level = QComboBox()
        for n, title in LEVELS.items(): self.level.addItem(title,n)
        self.kind = QComboBox()
        for title, key in [('Тест · четыре варианта','choice'),('Короткий ответ','short'),('Разбор · самооценка','review')]: self.kind.addItem(title,key)
        self.level.currentIndexChanged.connect(lambda: self.kind.setCurrentIndex(0 if self.level.currentData()==1 else 1))
        form.addRow('Сложность',self.level); form.addRow('Формат',self.kind)
        topics=QWidget(); grid=QGridLayout(topics); grid.setContentsMargins(0,0,0,0)
        self.topics={}
        for i,(key,(title,_)) in enumerate(CATEGORIES.items()):
            box=QCheckBox(title);self.topics[key]=box;grid.addWidget(box,i//2,i%2)
        form.addRow('Темы',topics)
        self.prompt=QPlainTextEdit();self.prompt.setPlaceholderText('Условие и всё необходимое для решения');self.prompt.setMinimumHeight(100)
        self.prompt.setMaximumHeight(140);form.addRow('Вопрос',self.prompt)
        self.answer=QPlainTextEdit();self.answer.setMaximumHeight(90);form.addRow('Правильный ответ\nили эталон разбора',self.answer)
        self.options=QPlainTextEdit();self.options.setPlaceholderText('Каждый вариант с новой строки. Один должен точно совпадать с правильным ответом.');self.options.setMaximumHeight(110);form.addRow('4 варианта теста',self.options)
        self.aliases=QLineEdit();self.aliases.setPlaceholderText('шериф | комиссар');form.addRow('Допустимые ответы\nчерез символ |',self.aliases)
        self.numeric=QCheckBox('Ответ — набор номеров, порядок не важен');form.addRow('',self.numeric)
        self.explanation=QPlainTextEdit();self.explanation.setMaximumHeight(120);self.explanation.setMinimumHeight(90);form.addRow('Объяснение',self.explanation)
        self.source=QLineEdit();self.source.setPlaceholderText('Название источника или ссылка');form.addRow('Источник',self.source)
        self.file_label=label('Без изображения','muted');form.addRow('Изображение / GIF',self.file_label)
        form.addRow('',button('Выбрать файл…',self.choose_file))
        self.kind.currentIndexChanged.connect(self.format_changed);self.format_changed()
        scroll.setWidget(content);outer.addWidget(scroll)
        outer.addLayout(row(button('Отмена',self.reject),button('Добавить вопрос',self.save,'primary')))

    def format_changed(self):
        choice=self.kind.currentData()=='choice'
        self.options.setEnabled(choice)
        self.aliases.setEnabled(self.kind.currentData()=='short')
        self.numeric.setEnabled(self.kind.currentData()=='short')

    def choose_file(self):
        path,_=QFileDialog.getOpenFileName(self,'Изображение или анимация','','Изображения (*.png *.jpg *.jpeg *.gif *.webp)')
        if path:
            if not QImageReader(path).canRead():
                QMessageBox.warning(self,'Не удалось прочитать','Выберите исправное изображение или GIF.');return
            self.attachment=Path(path);self.file_label.setText(self.attachment.name)

    def save(self):
        q=Question(id='custom-'+uuid.uuid4().hex,level=self.level.currentData(),topics=[t for t,b in self.topics.items() if b.isChecked()],kind=self.kind.currentData(),prompt=self.prompt.toPlainText().strip(),answer=self.answer.toPlainText().strip(),explanation=self.explanation.toPlainText().strip(),aliases=[x.strip() for x in self.aliases.text().split('|') if x.strip()] if self.kind.currentData()=='short' else [],options=[x.strip() for x in self.options.toPlainText().splitlines() if x.strip()] if self.kind.currentData()=='choice' else [],source=self.source.text().strip() or 'Пользовательский вопрос',numeric_set=self.numeric.isChecked() and self.kind.currentData()=='short')
        try: self.library.add(q,self.attachment)
        except (ValueError,OSError) as e: QMessageBox.warning(self,'Проверь поля',str(e));return
        self.accept()


class MainWindow(QMainWindow):
    def __init__(self, library):
        super().__init__()
        self.library=library;self.level=1;self.topics=set(CATEGORIES);self.length=20
        self.session=None;self.last_session=None;self.hinted=False;self.deleted_question=None;self.page_name='home'
        self.setWindowTitle('Мафия · Практика')
        self.setWindowIcon(QIcon(str(ASSETS/'icon.svg')))
        self.resize(1240,890);self.setMinimumSize(980,700)
        root=QWidget();layout=QHBoxLayout(root);layout.setContentsMargins(0,0,0,0);layout.setSpacing(0)
        rail=QWidget();rail.setObjectName('rail');rail.setFixedWidth(205)
        r=QVBoxLayout(rail);r.setContentsMargins(20,32,20,24);r.setSpacing(10)
        logo=label('◈  МАФИЯ','subtitle');r.addWidget(logo);r.addWidget(label('П Р А К Т И К А','eyebrow'));r.addSpacing(40)
        self.nav={}
        for key,title,callback in [('home','Тренировка',self.home),('glossary','Справочник',self.glossary),('library','Моя база',self.library_page),('sources','Источники',self.sources)]:
            b=button(title,lambda checked=False,cb=callback:self.navigate(cb),'nav');b.setCheckable(True);self.nav[key]=b;r.addWidget(b)
        r.addStretch();r.addWidget(label('Учись понимать стол.\nИ находить свою игру.','muted'));r.addSpacing(18)
        r.addWidget(label('Классическая мафия\nВерсия 1.0 · Linux','muted'))
        self.scroll=QScrollArea();self.scroll.setWidgetResizable(True)
        layout.addWidget(rail);layout.addWidget(self.scroll,1);self.setCentralWidget(root)
        self.shortcut=QShortcut(QKeySequence('Ctrl+Return'),self);self.shortcut.activated.connect(self.keyboard_submit)
        self.number_shortcuts=[]
        for n in range(1,5):
            shortcut=QShortcut(QKeySequence(str(n)),self);shortcut.activated.connect(lambda n=n:self.choose_keyboard(n));self.number_shortcuts.append(shortcut)
        self.home()

    def navigate(self, callback):
        if self.session and self.session.current and self.page_name=='game':
            answer=QMessageBox.question(self,'Закончить тренировку?','Текущая тренировка завершится. Изменения базы вопросов сохранятся.',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)
            if answer!=QMessageBox.StandardButton.Yes: return
        self.session=None;callback()

    def page(self,key):
        self.page_name=key
        for shortcut in self.number_shortcuts:shortcut.setEnabled(False)
        for k,b in self.nav.items(): b.setChecked(k==key or (key in ('game','results') and k=='home'))
        old=self.scroll.takeWidget()
        if old: old.hide();old.deleteLater()
        w=QWidget();v=QVBoxLayout(w);v.setContentsMargins(38,34,38,34);v.setSpacing(20)
        self.scroll.setWidget(w);self.scroll.verticalScrollBar().setValue(0)
        return v

    def home(self):
        self.refresh_library()
        v=self.page('home')
        v.addWidget(label('ТВОЯ ПРАКТИКА ЗА СТОЛОМ','eyebrow'))
        v.addWidget(label('Играй осознанно.','title'))
        v.addWidget(label('Жесты, правила и игровые решения. Выбери, над чем поработать сегодня.','muted'))
        stats=QHBoxLayout()
        for value,title in [(str(len(self.library.active())),'вопросов в твоей базе'),('3','уровня сложности'),('∞','времени на ответ')]:
            c,l=card();l.addWidget(label(value,'stat'));l.addWidget(label(title,'muted'));stats.addWidget(c)
        v.addLayout(stats)
        v.addWidget(label('01   Выбери сложность','subtitle'))
        levels=QHBoxLayout();self.level_group=QButtonGroup(self)
        descriptions={1:'Знакомые жесты и неочевидные основы',2:'Исключения и самостоятельные ответы',3:'Связки, логика и сложные ситуации'}
        for n,title in LEVELS.items():
            b=button(f'{"●"*n}  {title}\n{descriptions[n]}',style='level');b.setCheckable(True);b.setChecked(n==self.level);self.level_group.addButton(b,n);levels.addWidget(b)
        self.level_group.idClicked.connect(self.change_level);v.addLayout(levels)
        main=QHBoxLayout();main.setSpacing(20)
        left=QVBoxLayout();left.addLayout(row(label('02   Выбери темы','subtitle'),button('Все / ни одной',self.toggle_topics)))
        self.topic_boxes={};grid=QGridLayout();grid.setSpacing(10)
        for i,(key,(title,desc)) in enumerate(CATEGORIES.items()):
            c,l=card();l.setContentsMargins(14,14,14,14);l.setSpacing(6)
            box=QCheckBox(title);box.setChecked(key in self.topics);box.toggled.connect(lambda state,key=key:self.change_topic(key,state));self.topic_boxes[key]=box
            l.addWidget(box);l.addWidget(label(desc,'muted'));grid.addWidget(c,i//2,i%2)
        left.addLayout(grid);main.addLayout(left,1)
        c,l=card();c.setFixedWidth(260)
        l.addWidget(label('ТВОЯ ТРЕНИРОВКА','eyebrow'));l.addWidget(label('В своём темпе','subtitle'));l.addWidget(label('После каждого ответа — объяснение. Без таймера и спешки.','muted'))
        l.addWidget(label('Количество вопросов'))
        self.length_box=QComboBox()
        for n in [10,20,30,0]:self.length_box.addItem(str(n) if n else 'Все доступные',n)
        self.length_box.setCurrentIndex([10,20,30,0].index(self.length));self.length_box.currentIndexChanged.connect(self.change_length);l.addWidget(self.length_box)
        self.available_label=label('','muted');l.addWidget(self.available_label)
        self.start_button=button('Начать тренировку  →',self.start,'primary');l.addWidget(self.start_button)
        l.addStretch();l.addWidget(label('Хочешь потренировать своё?','muted'));l.addWidget(button('＋  Добавить вопрос',self.add_question));main.addWidget(c)
        v.addLayout(main);self.add_undo(v)
        if self.last_session:
            v.addWidget(button('Результаты последней тренировки',self.previous_results))
        v.addWidget(label('Правила Школы 21 · жесты MSU Mafia · результаты не сохраняются','muted'));v.addStretch();self.update_available()

    def change_level(self,n):self.level=n;self.update_available()
    def change_topic(self,key,state):
        if state:self.topics.add(key)
        else:self.topics.discard(key)
        self.update_available()
    def change_length(self):self.length=self.length_box.currentData();self.update_available()
    def toggle_topics(self):
        state=len(self.topics)!=len(CATEGORIES)
        for b in self.topic_boxes.values():b.setChecked(state)
    def update_available(self):
        if self.page_name!='home':return
        count=sum(q.level==self.level and bool(set(q.topics)&self.topics) for q in self.library.active())
        actual=min(count,self.length) if self.length else count
        self.available_label.setText(f'Доступно: {count}\nВ тренировке: {actual}' if self.topics else 'Выбери хотя бы одну тему.')
        self.start_button.setEnabled(count>0)
    def add_question(self):
        if QuestionEditor(self.library,self).exec():self.home()
    def refresh_library(self):
        try:
            self.library.reload()
            return True
        except (OSError, ValueError, KeyError, TypeError) as error:
            QMessageBox.warning(self, 'Не удалось обновить базу', str(error))
            return False
    def start(self):
        if not self.refresh_library():return
        self.update_available()
        qs=select_questions(self.library.active(),self.level,[t for t in CATEGORIES if t in self.topics],self.length)
        if not qs:return
        self.last_session=None;self.session=Session(qs);self.hinted=False;self.game()

    def add_undo(self,v):
        if self.deleted_question:
            c,l=card();l.addLayout(row(label('Вопрос удалён из базы.','muted'),button('Отменить удаление',self.undo_delete)));v.addWidget(c)
    def undo_delete(self):
        try:self.library.restore(self.deleted_question.id)
        except OSError as e:QMessageBox.warning(self,'Не удалось сохранить',str(e));return
        self.deleted_question=None
        if self.page_name=='game':self.game()
        elif self.page_name=='results':self.results_page()
        else:self.home()

    def game(self):
        if not self.session.current:self.results_page();return
        q=self.session.current;v=self.page('game')
        v.addLayout(row(label('ТРЕНИРОВКА / '+LEVELS[q.level].upper(),'eyebrow'),button('Завершить',self.end_training)))
        number=len(self.session.results)+1
        v.addLayout(row(label(f'Вопрос {number} из {self.session.total}','muted'),label(' · '.join(CATEGORIES[t][0] for t in q.topics),'muted')))
        progress=QProgressBar();progress.setRange(0,max(1,self.session.total));progress.setValue(len(self.session.results));progress.setTextVisible(False);v.addWidget(progress)
        c,l=card();l.setSpacing(18)
        format_label={'choice':'ВЫБЕРИ ОДИН ОТВЕТ','short':'ОТВЕТЬ САМОСТОЯТЕЛЬНО','review':'РАЗБОР СИТУАЦИИ · САМООЦЕНКА'}
        l.addWidget(label(format_label[q.kind],'eyebrow'));l.addWidget(label(q.prompt,'question'))
        if q.board:l.addWidget(TableBoard(q.board))
        if q.media:l.addWidget(Media(q.media))
        self.option_group=None;self.response_edit=None
        for shortcut in self.number_shortcuts:shortcut.setEnabled(q.kind=='choice' and not self.session.pending)
        if q.kind=='choice':
            self.option_group=QButtonGroup(self);opts=list(q.options);random.shuffle(opts)
            for i,opt in enumerate(opts):
                b=button(f'{i+1}   {opt}',style='option');b.setCheckable(True);b.setProperty('answer',opt);self.option_group.addButton(b,i);l.addWidget(b)
        else:
            self.response_edit=QPlainTextEdit();self.response_edit.setPlaceholderText('Твоё решение и аргументы…' if q.kind=='review' else 'Твой ответ…');self.response_edit.setMaximumHeight(140 if q.kind=='review' else 85);self.response_edit.setMinimumHeight(85);l.addWidget(self.response_edit)
            l.addWidget(label('Ctrl + Enter — проверить ответ','muted'))
        self.error_label=label('','eyebrow');l.addWidget(self.error_label)
        self.answer_controls=QWidget();controls=QHBoxLayout(self.answer_controls);controls.setContentsMargins(0,0,0,0)
        controls.addWidget(button('Показать разбор' if q.kind=='review' else 'Проверить ответ',self.submit,'primary'));controls.addWidget(button('Не знаю',lambda:self.submit(skip=True)));controls.addStretch();controls.addWidget(button('Подсказка',self.hint))
        l.addWidget(self.answer_controls)
        self.feedback_holder=QVBoxLayout();l.addLayout(self.feedback_holder);v.addWidget(c)
        v.addLayout(row(button('Удалить вопрос',self.delete_question,'danger'),label('Удаление сохраняется. Вопрос можно восстановить в «Моей базе».','muted')))
        self.add_undo(v);v.addStretch()
        if self.session.pending:self.show_feedback()

    def keyboard_submit(self):
        if self.page_name!='game':return
        if self.session.pending:
            if self.session.pending.status!='review':self.next_question()
        else:self.submit()
    def choose_keyboard(self,n):
        if self.page_name=='game' and not self.session.pending and self.option_group:
            b=self.option_group.button(n-1)
            if b:b.setChecked(True)
    def hint(self):
        if self.session.pending:return
        self.hinted=True
        q=self.session.current
        d=QDialog(self);d.setWindowTitle('Подсказка');d.resize(630,480);v=QVBoxLayout(d)
        v.addWidget(label('Ответ с подсказкой будет отмечен отдельно.','eyebrow'))
        scroll=QScrollArea();scroll.setWidgetResizable(True);w=QWidget();l=QVBoxLayout(w);l.addWidget(label(q.explanation));l.addStretch();scroll.setWidget(w);v.addWidget(scroll);v.addWidget(button('Вернуться к вопросу',d.accept));d.exec()
    def submit(self,checked=False,skip=False):
        if self.page_name!='game' or self.session.pending:return
        if self.option_group:
            b=self.option_group.checkedButton();response=b.property('answer') if b else ''
        else:response=self.response_edit.toPlainText().strip()
        if not response and not skip:self.error_label.setText('Выбери ответ или нажми «Не знаю».');return
        self.session.submit(response,self.hinted,skip);self.show_feedback()
    def show_feedback(self):
        r=self.session.pending;q=r.question
        for shortcut in self.number_shortcuts:shortcut.setEnabled(False)
        self.answer_controls.hide();self.error_label.hide()
        if self.option_group:
            for b in self.option_group.buttons():b.setEnabled(False);b.setChecked(b.property('answer')==r.response)
        if self.response_edit:self.response_edit.setPlainText(r.response);self.response_edit.setReadOnly(True)
        good=r.status in ('correct','review_good');c=QFrame();c.setObjectName('feedback' if good else 'wrong');l=QVBoxLayout(c);l.setContentsMargins(20,18,20,18);l.setSpacing(12)
        title={'correct':('Зачтено вручную' if r.manual else 'Верно') + (' · с подсказкой' if r.hinted else ''),'wrong':'Ответ не совпал с эталоном','skipped':'Разберём вместе','review':'Сравни своё решение с разбором','review_good':'Разобрался','review_repeat':'Стоит повторить'}[r.status]
        l.addWidget(label(title,'subtitle'))
        if r.response:l.addWidget(label('Твой ответ: '+r.response,'muted'))
        l.addWidget(label(('Возможное решение: ' if q.kind=='review' else 'Ответ: ')+q.answer))
        l.addWidget(label(q.explanation));l.addWidget(label(self.source_text(q),'muted'))
        if q.source==VK_URL or q.page:l.addWidget(button('Открыть источник',lambda:self.open_source(q)))
        if r.status=='review':l.addLayout(row(button('Разобрался',lambda:self.mark_review(True),'primary'),button('Нужно повторить',lambda:self.mark_review(False))))
        else:
            if r.status=='wrong' and q.kind=='short':l.addWidget(button('Мой ответ верный по смыслу',self.accept_semantic))
            l.addWidget(button('К результатам  →' if len(self.session.queue)==1 else 'Следующий вопрос  →',self.next_question,'primary'))
        self.feedback_holder.addWidget(c)
        QTimer.singleShot(50,lambda:self.scroll.ensureWidgetVisible(c,0,40) if isValid(c) and isValid(self.scroll) else None)
    def refresh_feedback(self):
        while self.feedback_holder.count():
            item=self.feedback_holder.takeAt(0)
            if item.widget():item.widget().deleteLater()
        self.show_feedback()
    def mark_review(self,good):self.session.pending.status='review_good' if good else 'review_repeat';self.refresh_feedback()
    def accept_semantic(self):self.session.pending.status='correct';self.session.pending.manual=True;self.refresh_feedback()
    def next_question(self):
        try:self.session.advance()
        except ValueError:return
        self.hinted=False;self.game()
    def end_training(self):
        if self.session.pending and self.session.pending.status!='review':self.session.advance()
        self.results_page()
    def delete_question(self):
        q=self.session.current
        try:self.library.delete(q)
        except OSError as e:QMessageBox.warning(self,'Не удалось удалить',str(e));return
        self.deleted_question=q;self.session.delete_current();self.hinted=False;self.game()

    def previous_results(self):
        self.session=self.last_session;self.results_page()

    def results_page(self):
        self.last_session=self.session
        v=self.page('results');results=self.session.results
        automatic=[r for r in results if r.question.kind!='review']
        correct=sum(r.status=='correct' and not r.hinted for r in automatic)
        v.addWidget(label('ТРЕНИРОВКА ЗАВЕРШЕНА','eyebrow'));v.addWidget(label('Каждый раз — увереннее.','title'))
        v.addWidget(label('Результаты этой сессии доступны до начала следующей тренировки.','muted'))
        statrow=QHBoxLayout()
        for value,title in [(f'{correct} / {len(automatic)}','верно без подсказок'),(str(sum(r.hinted for r in results)),'ответов с подсказкой'),(str(sum(r.question.kind=='review' for r in results)),'заданий с самооценкой')]:
            c,l=card();l.addWidget(label(value,'stat'));l.addWidget(label(title,'muted'));statrow.addWidget(c)
        v.addLayout(statrow)
        for t,(title,_) in CATEGORIES.items():
            subset=[r for r in results if t in r.question.topics]
            if subset:
                facts=[r for r in subset if r.question.kind!='review'];good=sum(r.status=='correct' and not r.hinted for r in facts);reviews=[r for r in subset if r.question.kind=='review']
                extra=f' · разобрался: {sum(r.status=="review_good" for r in reviews)} / {len(reviews)}' if reviews else ''
                v.addWidget(label(f'{title}: {good} / {len(facts)} без подсказок{extra}'))
        retry=[r.question for r in results if r.status in ('wrong','skipped','review_repeat') or r.hinted]
        actions=row(button('Новая тренировка',self.home,'primary'))
        if retry:actions.addWidget(button(f'Повторить ошибки ({len(retry)})',lambda:self.retry(retry)))
        v.addLayout(actions);self.add_undo(v)
        if results:v.addWidget(label('Разбор ответов','subtitle'))
        for r in results:
            c,l=card();l.addWidget(label({'correct':'✓ Верно','wrong':'× Ошибка','skipped':'— Пропущено','review_good':'✓ Разобрался','review_repeat':'↻ Нужно повторить'}[r.status]+(' · с подсказкой' if r.hinted else '')+(' · зачтено вручную' if r.manual else ''),'eyebrow'))
            l.addWidget(label(r.question.prompt));l.addWidget(label('Твой ответ: '+(r.response or 'Не знаю'),'muted'));l.addWidget(label('Эталон: '+r.question.answer));l.addWidget(label(r.question.explanation,'muted'));v.addWidget(c)
        v.addStretch()
    def retry(self,questions):
        active={q.id for q in self.library.active()};qs=[q for q in questions if q.id in active]
        if not qs:self.home();return
        random.shuffle(qs);self.last_session=None;self.session=Session(qs);self.hinted=False;self.game()

    def glossary(self):
        v=self.page('glossary');v.addWidget(label('СПРАВОЧНИК','eyebrow'));v.addWidget(label('Понимай язык игры.','title'));v.addWidget(label('Жесты MSU Mafia и термины. Можно искать по названию или описанию.','muted'))
        search=QLineEdit();search.setPlaceholderText('Найти: проверка, попил, договорка…');v.addWidget(search)
        target=QWidget();listing=QVBoxLayout(target);listing.setContentsMargins(0,0,0,0);v.addWidget(target)
        self.glossary_media=[]
        def render(text):
            for m in self.glossary_media:m.stop()
            self.glossary_media=[]
            while listing.count():
                item=listing.takeAt(0)
                if item.widget():item.widget().hide();item.widget().deleteLater()
            qs=[q for q in self.library.builtin if q.glossary and text.lower().replace('ё','е') in (q.glossary+' '+q.explanation).lower().replace('ё','е')]
            if not qs:listing.addWidget(label('Ничего не найдено. Попробуй другое слово.','muted'))
            for q in qs:
                c,l=card();l.addWidget(label(q.glossary,'subtitle'));l.addWidget(label(q.explanation))
                reveal=button('Показать жест' if q.media else 'Подробнее')
                def show(checked=False,q=q,l=l,b=reveal):
                    b.hide()
                    if q.media:
                        m=Media(q.media,230);self.glossary_media.append(m);l.addWidget(m)
                    l.addWidget(label(self.source_text(q),'muted'))
                reveal.clicked.connect(show);l.addWidget(reveal);listing.addWidget(c)
        search.textChanged.connect(render);render('');v.addStretch()

    def library_page(self):
        self.refresh_library()
        v=self.page('library');v.addWidget(label('ТВОЯ БАЗА','eyebrow'));v.addWidget(label('Подстрой практику под себя.','title'))
        v.addWidget(label(f'Активно: {len(self.library.active())} · своих вопросов: {len(self.library.custom)} · удалено: {len(self.library.deleted)}','muted'))
        v.addWidget(button('＋  Добавить вопрос',self.add_question,'primary'))
        v.addWidget(label('Свои вопросы и удаления сохраняются между запусками. Результаты тренировок — нет.','muted'))
        rows=[q for q in [*self.library.builtin,*self.library.custom] if q.id in self.library.deleted or q.id.startswith('custom-')]
        if not rows:v.addWidget(label('Здесь появятся твои вопросы и вопросы, удалённые во время игры.','muted'))
        for q in rows:
            c,l=card();deleted=q.id in self.library.deleted;l.addWidget(label(('Удалён · ' if deleted else 'Свой вопрос · ')+LEVELS[q.level],'eyebrow'));l.addWidget(label(q.prompt))
            l.addWidget(button('Восстановить' if deleted else 'Удалить из базы',lambda checked=False,q=q,deleted=deleted:self.toggle_library(q,deleted)));v.addWidget(c)
        v.addStretch()
    def toggle_library(self,q,deleted):
        try:self.library.restore(q.id) if deleted else self.library.delete(q)
        except OSError as e:QMessageBox.warning(self,'Ошибка сохранения',str(e));return
        self.library_page()

    @staticmethod
    def source_text(q):
        return ('Правила Школы 21 · стр. '+str(q.page)) if q.page else 'MSU Mafia · Словарь по жестикуляции' if q.source==VK_URL else q.source or 'Авторский разбор по заданным условиям'
    def open_source(self,q):
        url=QUrl.fromLocalFile(str(ASSETS/'rules.pdf')) if q.page else QUrl(q.source)
        if url.isLocalFile() or url.scheme() in ('http','https'):QDesktopServices.openUrl(url)
    def sources(self):
        v=self.page('sources');v.addWidget(label('МАТЕРИАЛЫ','eyebrow'));v.addWidget(label('Откуда взяты задания.','title'))
        for title,text,action in [
            ('Правила Школы 21','Основной регламент тренажёра — документ «Классика Школа 21». Клубные правила могут отличаться от правил других площадок.',lambda:QDesktopServices.openUrl(QUrl.fromLocalFile(str(ASSETS/'rules.pdf')))),
            ('Словарь MSU Mafia','Жесты, фотографии и анимации: MSU Mafia, «Словарь по жестикуляции», 2022. Материалы включены для личного обучения по твоей ссылке. Если исходное видео недоступно, используется текстовая задача по значению термина. Неоднозначные кадры не выдаются за полную анимацию.',lambda:QDesktopServices.openUrl(QUrl(VK_URL))),
        ]:
            c,l=card();l.addWidget(label(title,'subtitle'));l.addWidget(label(text,'muted'));l.addWidget(button('Открыть источник',action));v.addWidget(c)
        c,l=card();l.addWidget(label('Как оцениваются ответы','subtitle'));l.addWidget(label('Короткие ответы сверяются с эталонами и синонимами. Если ответ верен по смыслу, его можно зачесть вручную. Тактические разборы оцениваешь ты сам: несколько решений могут быть разумными. Слова игрока о роли не считаются подтверждённой ролью.'))
        l.addWidget(label('Приложение работает локально. Интернет нужен только для открытия внешнего источника.','muted'));v.addWidget(c);v.addStretch()


def run():
    app=QApplication.instance() or QApplication([])
    app.setApplicationName('Мафия · Практика');app.setOrganizationName('MafiaPractice');app.setStyle('Fusion');app.setStyleSheet(STYLE)
    try:library=Library()
    except (OSError,ValueError,KeyError,TypeError) as e:
        QMessageBox.critical(None,'Не удалось загрузить базу',f'{e}\n\nПользовательский файл не изменён. Проверь ~/.local/share/mafia-trainer/library.json.');return 1
    window=MainWindow(library);window.show()
    return app.exec()
