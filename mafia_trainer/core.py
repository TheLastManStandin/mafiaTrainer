from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from collections import Counter
from contextlib import contextmanager
import fcntl
import json
import os
import random
import re
import shutil
import tempfile
import unicodedata
import uuid

CATEGORIES = {
    'gestures': ('Жесты и термины', 'Распознавание и язык общения'),
    'roles': ('Роли и проверки', 'Возможности карт и результаты проверок'),
    'day': ('Дневная игра', 'Речи, выставление, лучший ход'),
    'voting': ('Голосование', 'Голоса, равенство и переголосование'),
    'night': ('Ночная игра', 'Договорка, отстрел и проверки'),
    'fouls': ('Фолы и этика', 'Нарушения и поведение за столом'),
    'special': ('Особые случаи', 'Исключения и нестандартные партии'),
    'logic': ('Логика и тактика', 'Версии, аргументы и решения'),
}
LEVELS = {1: 'Лёгкий', 2: 'Средний', 3: 'Сложный'}
PDF_NAME = 'Классика Школа 21.pdf'
VK_URL = 'https://vk.ru/@msu.mafia-dictionary'
ASSETS = Path(__file__).resolve().parent / 'assets'
IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.gif', '.webp')
IMAGE_SIZE_LIMIT = 30 * 1024 * 1024


def normalize(value: str) -> str:
    value = unicodedata.normalize('NFKC', value).lower().replace('ё', 'е')
    return ' '.join(re.sub(r'[^\w\s]', ' ', value).split())


@dataclass
class Question:
    id: str
    level: int
    topics: list[str]
    kind: str
    prompt: str
    answer: str
    explanation: str
    aliases: list[str] = field(default_factory=list)
    options: list[str] = field(default_factory=list)
    media: str = ''
    source: str = ''
    page: int = 0
    numeric_set: bool = False
    board: list[int] = field(default_factory=list)
    glossary: str = ''

    def validate(self):
        if self.level not in LEVELS or not self.topics or any(t not in CATEGORIES for t in self.topics):
            raise ValueError('Выберите уровень и хотя бы одну известную тему.')
        if self.kind not in ('choice', 'short', 'review'):
            raise ValueError('Неизвестный формат задания.')
        if not self.id or not self.prompt.strip() or not self.answer.strip() or not self.explanation.strip():
            raise ValueError('Заполните вопрос, ответ и объяснение.')
        if self.kind == 'choice':
            if len(self.options) != 4 or len({normalize(o) for o in self.options}) != 4:
                raise ValueError('Нужны четыре различных непустых варианта ответа.')
            if any(not normalize(o) for o in self.options) or self.answer not in self.options:
                raise ValueError('Правильный ответ должен совпадать с одним из вариантов.')

    def check(self, value: str) -> bool:
        if not value.strip():
            return False
        if self.numeric_set:
            # Full-string validation prevents "2, 4, but maybe 9" matching a numeric answer.
            if not re.fullmatch(r'[\d\s,;№.\-и]+', value.lower()):
                return False
            got = re.findall(r'\d+', value)
            expected = re.findall(r'\d+', self.answer)
            return bool(got) and len(got) == len(set(got)) and set(got) == set(expected)
        return normalize(value) in {normalize(a) for a in [self.answer, *self.aliases]}


def load_builtin() -> list[Question]:
    raw = json.loads((ASSETS / 'questions.json').read_text(encoding='utf-8'))
    questions = [Question(**q) for q in raw]
    ids = set()
    for q in questions:
        q.validate()
        if q.id in ids:
            raise ValueError(f'Повтор идентификатора: {q.id}')
        ids.add(q.id)
        if q.media and not (ASSETS / q.media).is_file():
            raise ValueError(f'Отсутствует изображение: {q.media}')
    return questions


class Library:
    """Only authored library changes persist; practice history never reaches disk."""
    def __init__(self, data_dir: Path | None = None):
        self.directory = (data_dir or Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'mafia-trainer').resolve()
        self.path = self.directory / 'library.json'
        self.builtin = load_builtin()
        self.reload()

    def reload(self):
        custom = []
        deleted = set()
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if data.get('version') != 1:
                raise ValueError('Неизвестная версия пользовательской базы. Исходный файл сохранён.')
            custom = [Question(**q) for q in data['custom']]
            for q in custom:
                q.validate()
            ids = [q.id for q in [*self.builtin, *custom]]
            if len(ids) != len(set(ids)):
                raise ValueError('Повтор идентификаторов в пользовательской базе.')
            deleted = set(data['deleted'])
        self.custom = custom
        self.deleted = deleted

    @contextmanager
    def _edit(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        with (self.directory / '.library.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            self.reload()
            previous_custom = self.custom.copy()
            previous_deleted = self.deleted.copy()
            try:
                yield
                self.save()
            except Exception:
                self.custom = previous_custom
                self.deleted = previous_deleted
                raise

    def active(self):
        return [q for q in [*self.builtin, *self.custom] if q.id not in self.deleted]

    def save(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        data = dict(version=1, custom=[asdict(q) for q in self.custom], deleted=sorted(self.deleted))
        fd, name = tempfile.mkstemp(prefix='.library-', suffix='.json', dir=self.directory)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(name, self.path)
        finally:
            if Path(name).exists():
                Path(name).unlink()

    def delete(self, question: Question):
        with self._edit():
            self.deleted.add(question.id)

    def restore(self, identifier: str):
        with self._edit():
            self.deleted.discard(identifier)

    def add(self, question: Question, attachment: Path | None = None):
        question.validate()
        if attachment:
            if attachment.suffix.lower() not in IMAGE_EXTENSIONS:
                raise ValueError('Поддерживаются PNG, JPEG, GIF и WebP.')
            if attachment.stat().st_size > IMAGE_SIZE_LIMIT:
                raise ValueError('Размер изображения должен быть меньше 30 МБ.')
        copied = None
        previous_media = question.media
        try:
            with self._edit():
                if any(q.id == question.id for q in [*self.builtin, *self.custom]):
                    raise ValueError('Такой идентификатор уже существует.')
                if attachment:
                    folder = self.directory / 'media'
                    folder.mkdir(parents=True, exist_ok=True)
                    copied = folder / (uuid.uuid4().hex + attachment.suffix.lower())
                    shutil.copyfile(attachment, copied)
                    question.media = str(copied)
                self.custom.append(question)
        except Exception:
            if copied:
                copied.unlink(missing_ok=True)
                question.media = previous_media
            raise


def select_questions(questions: list[Question], level: int, topics: list[str], count: int, rng=None):
    rng = rng or random.Random()
    available = [q for q in questions if q.level == level and set(q.topics) & set(topics)]
    rng.shuffle(available)
    result = []
    used = Counter()
    while available and (count == 0 or len(result) < count):
        eligible = [t for t in topics if any(t in q.topics for q in available)]
        if not eligible:
            break
        least = min(used[t] for t in eligible)
        topic = rng.choice([t for t in eligible if used[t] == least])
        q = next(q for q in available if topic in q.topics)
        available.remove(q)
        result.append(q)
        used[topic] += 1
    return result


@dataclass
class Result:
    question: Question
    response: str
    status: str
    hinted: bool = False
    manual: bool = False


class Session:
    def __init__(self, questions: list[Question]):
        self.queue = list(questions)
        self.total = len(questions)
        self.results: list[Result] = []
        self.pending: Result | None = None

    @property
    def current(self):
        return self.queue[0] if self.queue else None

    def submit(self, response: str, hinted=False, skip=False):
        if not self.current or self.pending:
            raise ValueError('Этот вопрос уже проверен.')
        q = self.current
        status = 'skipped' if skip else 'review' if q.kind == 'review' else 'correct' if q.check(response) else 'wrong'
        self.pending = Result(q, response, status, hinted)
        return self.pending

    def advance(self):
        if not self.pending:
            raise ValueError('Сначала ответьте или пропустите вопрос.')
        if self.pending.status == 'review':
            raise ValueError('Сначала отметьте результат разбора.')
        self.results.append(self.pending)
        self.pending = None
        self.queue.pop(0)

    def delete_current(self):
        if not self.current:
            return
        self.queue.pop(0)
        self.pending = None
        self.total -= 1
