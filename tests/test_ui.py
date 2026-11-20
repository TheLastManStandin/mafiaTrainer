import os
os.environ['QT_QPA_PLATFORM']='offscreen'

from pathlib import Path
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QImageReader, QMovie
from PySide6.QtWidgets import QApplication, QLabel, QPushButton
from mafia_trainer.core import ASSETS, Library, Session, load_builtin
from mafia_trainer.ui import MainWindow, QuestionEditor, STYLE

@pytest.fixture(scope='module')
def app():
    instance=QApplication.instance() or QApplication([])
    instance.setStyle('Fusion');instance.setStyleSheet(STYLE)
    yield instance

@pytest.fixture
def window(app,tmp_path):
    w=MainWindow(Library(tmp_path/'library'));w.show();app.processEvents()
    yield w
    w.close();w.deleteLater();app.processEvents()


def test_home_filters_and_empty_state(window,app):
    assert window.start_button.isEnabled()
    window.toggle_topics();app.processEvents()
    assert not window.start_button.isEnabled()
    window.topic_boxes['voting'].setChecked(True)
    window.change_level(3)
    assert '7' in window.available_label.text()
    window.start();app.processEvents()
    assert window.session.total==7
    assert all(q.level==3 and q.topics==['voting'] for q in window.session.queue)


def test_game_choice_feedback_and_completion(window,app):
    q=next(q for q in window.library.active() if q.kind=='choice' and not q.media)
    window.session=Session([q]);window.game();app.processEvents()
    for b in window.option_group.buttons():
        if b.property('answer')==q.answer:b.click()
    window.submit();app.processEvents()
    assert window.session.pending.status=='correct'
    window.next_question();app.processEvents()
    assert window.page_name=='results'
    assert len(window.session.results)==1
    window.home();app.processEvents()
    assert any(b.text()=='Результаты последней тренировки' for b in window.findChildren(QPushButton))
    window.previous_results()
    assert window.session.results[0].status=='correct'


def test_review_requires_self_assessment(window,app):
    q=next(q for q in window.library.active() if q.kind=='review')
    window.session=Session([q]);window.game();window.response_edit.setPlainText('Сначала сравню версии.')
    window.submit();app.processEvents()
    assert window.session.pending.status=='review'
    window.mark_review(False);window.next_question();app.processEvents()
    assert window.session.results[0].status=='review_repeat'


def test_delete_undo_and_relaunch(window,app):
    q=window.library.active()[0];window.session=Session([q]);window.game()
    window.delete_question();app.processEvents()
    assert window.page_name=='results' and q.id in Library(window.library.directory).deleted
    assert not window.session.results
    window.undo_delete();app.processEvents()
    assert q.id not in Library(window.library.directory).deleted


def test_add_question_editor_validates_and_persists(window,app):
    editor=QuestionEditor(window.library,window)
    editor.level.setCurrentIndex(1);editor.topics['logic'].setChecked(True)
    editor.prompt.setPlainText('Сколько вариантов?');editor.answer.setPlainText('2')
    editor.explanation.setPlainText('В условии исключены все варианты, кроме двух.')
    editor.save();app.processEvents()
    q=Library(window.library.directory).custom[0]
    assert q.prompt=='Сколько вариантов?' and q.kind=='short' and q.topics==['logic']
    editor.close()


def test_all_original_media_decode_and_animations_have_multiple_frames(app):
    media=[ASSETS/q.media for q in load_builtin() if q.media]
    assert len(media)==36
    for path in media:
        assert QImageReader(str(path)).canRead(),path.name
        if path.suffix=='.gif':
            movie=QMovie(str(path));assert movie.isValid(),path.name
            assert movie.frameCount()>1,path.name
            movie.jumpToFrame(0);first=movie.currentImage()
            for _ in range(movie.frameCount()//2):assert movie.jumpToNextFrame(),path.name
            assert movie.currentImage()!=first,path.name


def test_glossary_search_and_all_screens(window,app):
    window.glossary();app.processEvents()
    window.library_page();app.processEvents()
    window.sources();app.processEvents()
    window.resize(980,700);window.home();app.processEvents()
    assert window.scroll.horizontalScrollBar().maximum()==0


def test_number_keys_are_not_stolen_from_short_answers(window,app):
    from PySide6.QtTest import QTest
    q=next(q for q in window.library.active() if q.kind=='short' and not q.media)
    window.session=Session([q]);window.game();app.processEvents()
    window.response_edit.setFocus();QTest.keyClicks(window.response_edit,'1234');app.processEvents()
    assert window.response_edit.toPlainText()=='1234'
