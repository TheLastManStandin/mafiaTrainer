from __future__ import annotations

import base64
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ipaddress import IPv4Address
import json
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import quote, unquote, urlsplit
import uuid

from .core import (
    ASSETS, CATEGORIES, IMAGE_SIZE_LIMIT, LEVELS, VK_URL, Library, Question,
    select_questions,
)

WEB = Path(__file__).with_name('web_assets')
FILES = {
    '/': (WEB / 'index.html', 'text/html; charset=utf-8'),
    '/app.js': (WEB / 'app.js', 'text/javascript; charset=utf-8'),
    '/style.css': (WEB / 'style.css', 'text/css; charset=utf-8'),
    '/icon.svg': (ASSETS / 'icon.svg', 'image/svg+xml'),
    '/rules.pdf': (ASSETS / 'rules.pdf', 'application/pdf'),
}
IMAGES = {
    '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
    '.gif': 'image/gif', '.webp': 'image/webp',
}
BODY_LIMIT = IMAGE_SIZE_LIMIT * 4 // 3 + 256 * 1024


class RequestError(Exception):
    def __init__(self, message, status=HTTPStatus.BAD_REQUEST):
        super().__init__(message)
        self.status = status


def question_path(question):
    return '/api/questions/' + quote(question.id, safe='')


def media_fields(question):
    if not question.media:
        return {}
    return {
        'media': question_path(question) + '/image',
        'animated': Path(question.media).suffix.lower() == '.gif',
    }


def source_fields(question):
    if question.page:
        return {
            'source': f'Правила Школы 21 · стр. {question.page}',
            'sourceUrl': f'/rules.pdf#page={question.page}',
        }
    if question.source == VK_URL:
        return {'source': 'MSU Mafia · Словарь по жестикуляции', 'sourceUrl': VK_URL}
    source = question.source or 'Авторский разбор по заданным условиям'
    result = {'source': source}
    if source.startswith(('https://', 'http://')):
        result['sourceUrl'] = source
    return result


def question_card(question):
    options = list(question.options)
    random.shuffle(options)
    return {
        'id': question.id, 'topics': question.topics, 'kind': question.kind,
        'prompt': question.prompt, 'options': options, 'board': question.board,
        **media_fields(question),
    }


def bank(library):
    return {
        'levels': LEVELS,
        'topics': CATEGORIES,
        'active': [
            {'id': q.id, 'level': q.level, 'topics': q.topics} for q in library.active()
        ],
        'customCount': len(library.custom),
        'library': [
            {'id': q.id, 'level': q.level, 'prompt': q.prompt, 'deleted': q.id in library.deleted}
            for q in [*library.builtin, *library.custom]
            if q in library.custom or q.id in library.deleted
        ],
        'glossary': [
            {'title': q.glossary, 'explanation': q.explanation, **media_fields(q), **source_fields(q)}
            for q in library.builtin if q.glossary
        ],
        'dictionaryUrl': VK_URL,
    }


def text_field(data, field):
    value = data.get(field, '')
    if not isinstance(value, str):
        raise RequestError('Ожидалось текстовое поле.')
    if len(value) > 12000:
        raise RequestError('Слишком длинный текст. Максимум 12 000 символов на поле.')
    return value.strip()


def topic_list(data):
    topics = data.get('topics')
    if not isinstance(topics, list) or any(not isinstance(t, str) or t not in CATEGORIES for t in topics):
        raise RequestError('Выбери известные темы.')
    return list(dict.fromkeys(topics))


def level_number(data):
    level = data.get('level')
    if type(level) is not int or level not in LEVELS:
        raise RequestError('Выбери уровень сложности.')
    return level


def pick_questions(library, data):
    active = library.active()
    if 'retry' in data:
        ids = data['retry']
        if not isinstance(ids, list) or any(not isinstance(qid, str) for qid in ids):
            raise RequestError('Неверный список вопросов для повтора.')
        requested = set(ids)
        questions = [q for q in active if q.id in requested]
        random.shuffle(questions)
    else:
        count = data.get('count')
        if type(count) is not int or count < 0:
            raise RequestError('Выбери количество вопросов.')
        questions = select_questions(active, level_number(data), topic_list(data), count)
    return [question_card(q) for q in questions]


def image_extension(data):
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        return '.png'
    if data.startswith(b'\xff\xd8\xff'):
        return '.jpg'
    if data.startswith((b'GIF87a', b'GIF89a')):
        return '.gif'
    if data.startswith(b'RIFF') and data[8:12] == b'WEBP':
        return '.webp'
    raise RequestError('Выбери изображение PNG, JPEG, GIF или WebP.')


def add_question(library, data):
    kind = text_field(data, 'kind')
    question = Question(
        id='custom-' + uuid.uuid4().hex,
        level=level_number(data),
        topics=topic_list(data),
        kind=kind,
        prompt=text_field(data, 'prompt'),
        answer=text_field(data, 'answer'),
        explanation=text_field(data, 'explanation'),
        options=[line.strip() for line in text_field(data, 'options').splitlines() if line.strip()]
        if kind == 'choice' else [],
        aliases=[alias.strip() for alias in text_field(data, 'aliases').split('|') if alias.strip()]
        if kind == 'short' else [],
        numeric_set=kind == 'short' and data.get('numeric_set') is True,
        source=text_field(data, 'source'),
    )
    question.validate()
    encoded = data.get('image')
    if not encoded:
        library.add(question)
        return
    try:
        image = base64.b64decode(encoded, validate=True)
    except (TypeError, ValueError):
        raise RequestError('Не удалось прочитать прикреплённое изображение.') from None
    if len(image) > IMAGE_SIZE_LIMIT:
        raise RequestError('Максимальный размер изображения — 30 МБ.', HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
    with tempfile.TemporaryDirectory(prefix='mafia-image-') as directory:
        attachment = Path(directory) / ('attachment' + image_extension(image))
        attachment.write_bytes(image)
        library.add(question, attachment)


def feedback(question, data):
    action = data.get('action')
    if action == 'hint':
        return {'explanation': question.explanation}
    response = text_field(data, 'response')
    if action == 'skip':
        status = 'skipped'
    elif action != 'answer' or not response:
        raise RequestError('Выбери или введи ответ либо нажми «Не знаю».')
    elif question.kind == 'review':
        status = 'review'
    else:
        status = 'correct' if question.check(response) else 'wrong'
    return {
        'status': status, 'response': response, 'answer': question.answer,
        'explanation': question.explanation, **source_fields(question),
    }


class TrainingServer(ThreadingHTTPServer):
    def __init__(self, address, data_dir):
        self.data_dir = data_dir
        super().__init__(address, TrainingHandler)


class TrainingHandler(BaseHTTPRequestHandler):
    timeout = 30

    def end_headers(self):
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header(
            'Content-Security-Policy',
            "default-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
        )
        super().end_headers()

    def json_response(self, data, status=HTTPStatus.OK):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def send_file(self, path, content_type, cache='no-cache'):
        try:
            stream = path.open('rb')
        except FileNotFoundError:
            raise RequestError('Файл не найден.', HTTPStatus.NOT_FOUND) from None
        with stream:
            size = path.stat().st_size
            self.send_response(HTTPStatus.OK)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(size))
            self.send_header('Cache-Control', cache)
            self.end_headers()
            if self.command != 'HEAD':
                shutil.copyfileobj(stream, self.wfile)

    def request_data(self):
        origin = self.headers.get('Origin')
        if origin and origin != 'http://' + self.headers['Host']:
            raise RequestError('Запрос с другого сайта отклонён.', HTTPStatus.FORBIDDEN)
        if self.headers.get_content_type() != 'application/json':
            raise RequestError('Ожидается JSON.', HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
        try:
            size = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            size = 0
        if size > BODY_LIMIT:
            raise RequestError('Слишком большой файл или вопрос.', HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
        if size <= 0:
            raise RequestError('Пустой запрос.')
        try:
            data = json.loads(self.rfile.read(size))
        except (ValueError, RecursionError):
            raise RequestError('Не удалось прочитать запрос.') from None
        if not isinstance(data, dict):
            raise RequestError('Ожидается JSON-объект.')
        return data

    def dispatch(self):
        try:
            path = urlsplit(self.path).path
            host = self.headers.get('Host', '').partition(':')[0]
            if host != 'localhost':
                try:
                    IPv4Address(host)
                except ValueError:
                    raise RequestError('Открой приложение по IP-адресу компьютера.', HTTPStatus.FORBIDDEN) from None
            if self.command == 'POST':
                self.post(path, self.request_data())
            else:
                self.get(path)
        except RequestError as exc:
            self.json_response({'error': str(exc)}, exc.status)
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            return
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self.log_error('%s', exc)
            self.json_response({'error': 'Не удалось открыть или сохранить базу.'}, HTTPStatus.INTERNAL_SERVER_ERROR)

    do_GET = dispatch
    do_HEAD = dispatch
    do_POST = dispatch

    def get(self, path):
        if path in FILES:
            self.send_file(*FILES[path])
            return
        if path == '/api/bank':
            self.json_response(bank(Library(self.server.data_dir)))
            return
        library, question, action = self.find_question(path)
        if action != 'image' or not question.media:
            raise RequestError('Страница не найдена.', HTTPStatus.NOT_FOUND)
        root = (ASSETS if question in library.builtin else library.directory) / 'media'
        path = (root / Path(question.media).name).resolve()
        content_type = IMAGES.get(path.suffix.lower())
        if path.parent != root.resolve() or not content_type:
            raise RequestError('Изображение не найдено.', HTTPStatus.NOT_FOUND)
        self.send_file(path, content_type, cache='private, max-age=3600')

    def post(self, path, data):
        if path == '/api/training':
            library = Library(self.server.data_dir)
            self.json_response({'questions': pick_questions(library, data)})
            return
        if path == '/api/questions':
            library = Library(self.server.data_dir)
            try:
                add_question(library, data)
            except ValueError as exc:
                raise RequestError(str(exc)) from None
            self.json_response(bank(library), HTTPStatus.CREATED)
            return
        library, question, action = self.find_question(path)
        if action == 'feedback':
            self.json_response(feedback(question, data))
        elif action == 'visibility' and type(data.get('deleted')) is bool:
            if data['deleted']:
                library.delete(question)
            else:
                library.restore(question.id)
            self.json_response(bank(library))
        else:
            raise RequestError('Неизвестное действие.')

    def find_question(self, path):
        if path.startswith('/api/questions/'):
            identifier, _, action = path.removeprefix('/api/questions/').partition('/')
            library = Library(self.server.data_dir)
            for question in [*library.builtin, *library.custom]:
                if question.id == unquote(identifier):
                    return library, question, action
        raise RequestError('Страница или вопрос не найдены.', HTTPStatus.NOT_FOUND)


def lan_addresses():
    try:
        result = subprocess.run(
            ['ip', '-j', '-4', 'address', 'show', 'up', 'scope', 'global'],
            capture_output=True, text=True, check=True, timeout=3,
        )
        return [
            info['local']
            for interface in json.loads(result.stdout)
            if (Path('/sys/class/net') / interface['ifname'] / 'device').exists()
            for info in interface.get('addr_info', [])
        ]
    except (OSError, subprocess.SubprocessError, ValueError):
        return []


def run(host, port, data_dir=None):
    try:
        library = Library(data_dir)
        server = TrainingServer((host, port), library.directory)
    except (OSError, ValueError, KeyError, TypeError, OverflowError) as exc:
        print(f'Не удалось запустить тренажёр. {exc}', file=sys.stderr)
        return 1
    with server:
        address, port = server.server_address
        if address == '0.0.0.0':
            print(f'На этом компьютере http://127.0.0.1:{port}', flush=True)
            for ip in lan_addresses():
                print(f'На телефоне http://{ip}:{port}', flush=True)
        else:
            print(f'Мафия · Практика  http://{address}:{port}', flush=True)
        print('Чтобы остановить сервер, нажми Ctrl+C.', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0
