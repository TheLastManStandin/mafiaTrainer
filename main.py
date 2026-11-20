import argparse
from pathlib import Path

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Мафия · Практика — тренажёр для Linux и браузера')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--smoke-test', metavar='DIRECTORY',
                      help='Проверить оконный интерфейс в изолированной базе и сохранить снимки')
    mode.add_argument('--web', action='store_true', help='Запустить веб-версию')
    parser.add_argument('--host', help='Адрес веб-сервера. По умолчанию 127.0.0.1')
    parser.add_argument('--port', type=int, help='Порт веб-сервера. По умолчанию 8000')
    parser.add_argument('--data-dir', type=Path, help='Отдельная папка для базы веб-версии')
    args = parser.parse_args()
    if args.web:
        from mafia_trainer.web import run
        raise SystemExit(run(args.host or '127.0.0.1', 8000 if args.port is None else args.port, args.data_dir))
    if any(value is not None for value in (args.host, args.port, args.data_dir)):
        parser.error('--host, --port и --data-dir используются с --web')
    if args.smoke_test:
        from mafia_trainer.smoke import run
        raise SystemExit(run(args.smoke_test))
    from mafia_trainer.ui import run
    raise SystemExit(run())
