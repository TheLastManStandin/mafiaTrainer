"""Short, isolated GUI check for source and frozen builds. All windows close automatically."""
from pathlib import Path
import json
import tempfile
import traceback

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from .core import Library, Session
from .ui import MainWindow, QuestionEditor, STYLE


def run(output):
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=True)
    scratch=tempfile.TemporaryDirectory(prefix='mafia-smoke-')
    app=QApplication([]);app.setStyle('Fusion');app.setStyleSheet(STYLE)
    library=Library(Path(scratch.name)/'data');window=MainWindow(library);window.show()
    editor=None
    code=0
    def home():
        window.grab().save(str(out/'01-home.png'))
        q=next(q for q in library.active() if q.media.endswith('g21.gif'))
        window.session=Session([q]);window.game()
    def gesture():
        window.grab().save(str(out/'02-gesture.png'))
        q=next(q for q in library.active() if q.kind=='review' and q.board)
        window.session=Session([q]);window.game()
        window.response_edit.setPlainText('Один из двух — настоящий комиссар. Сравню обе версии.')
        window.submit()
    def review():
        window.grab().save(str(out/'03-review.png'))
        window.mark_review(True);window.next_question()
    def results():
        nonlocal editor
        window.grab().save(str(out/'04-results.png'))
        editor=QuestionEditor(library,window);editor.show()
    def finish():
        editor.grab().save(str(out/'05-editor.png'))
        q=library.active()[0];library.delete(q)
        assert q.id in Library(library.directory).deleted
        library.restore(q.id)
        assert len(Library(library.directory).active())==180
        print(json.dumps({'status':'ok','questions':len(library.active()),'screenshots':5,'isolated_storage':True}),flush=True)
        editor.close();window.close();app.quit()
    steps=iter([home,gesture,review,results,finish])
    def step():
        nonlocal code
        try:next(steps)()
        except StopIteration:return
        except Exception:
            code=1;traceback.print_exc();app.closeAllWindows();app.quit();return
        QTimer.singleShot(350,step)
    QTimer.singleShot(200,step)
    app.exec();scratch.cleanup();return code
