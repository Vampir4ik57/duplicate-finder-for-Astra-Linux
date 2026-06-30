#!/usr/bin/env python3
import argparse
import os
import sys
from collections import defaultdict


def parse_arguments():
    """Реализация интерфейса командной строки (CLI) согласно требованиям."""
    parser = argparse.ArgumentParser(
        description="Анализ дубликатов файлов в среде Astra Linux.",
        add_help=True
    )

    # Задаем аргументы, как указано в задании
    parser.add_argument(
        "--path",
        type=str,
        default=".",
        help="Путь к директории для поиска дубликатов (по умолчанию: текущая директория)"
    )
    parser.add_argument(
        "--hash",
        type=str,
        default="sha256",
        choices=["md5", "sha1", "sha256"],
        help="Алгоритм хеширования файлов (по умолчанию: sha256)"
    )
    parser.add_argument(
        "--export",
        type=str,
        help="Путь к файлу для экспорта отчета (например: duplicates.txt)"
    )

    return parser.parse_args()


def get_potential_duplicates(target_path):
    """
    Рекурсивно обходит директорию и группирует файлы по размеру.
    Файлы с уникальным размером отсекаются сразу для экономии времени.
    """
    size_groups = defaultdict(list)

    print(f"[*] Сканирование директории: {target_path}...")

    try:
        for root, _, files in os.walk(target_path):
            for file in files:
                full_path = os.path.join(root, file)

                try:
                    # Игнорируем символические ссылки, чтобы избежать зацикливания
                    if os.path.islink(full_path):
                        continue

                    # Получаем размер файла
                    file_size = os.path.getsize(full_path)
                    size_groups[file_size].append(full_path)

                except (PermissionError, FileNotFoundError) as e:
                    # Корректная обработка ошибок доступа к отдельным файлам (Требование 6)
                    print(f"[Предупреждение] Нет доступа к файлу {full_path}: {e}", file=sys.stderr)

    except Exception as e:
        print(f"[Ошибка] Не удалось прочитать директорию {target_path}: {e}", file=sys.stderr)
        sys.exit(1)

    # Фильтруем: оставляем только те размеры, где нашлось больше 1 файла
    filtered_groups = {size: paths for size, paths in size_groups.items() if len(paths) > 1}

    total_potential_files = sum(len(paths) for paths in filtered_groups.values())
    print(f"[+] Сканирование завершено. Найдено потенциальных дубликатов для проверки: {total_potential_files}")

    return filtered_groups


def main():
    # 1. Получаем аргументы командной строки
    args = parse_arguments()

    # Проверяем существование указанного пути
    if not os.path.exists(args.path):
        print(f"[Ошибка] Указанный путь не существует: {args.path}", file=sys.stderr)
        sys.exit(1)

    # 2. Запускаем предварительную группировку по размеру
    potential_duplicates = get_potential_duplicates(args.path)

    # Временный вывод для отладки текущего этапа
    for size, paths in potential_duplicates.items():
        print(f"Размер: {size} байт -> Файлы: {paths}")


if __name__ == "__main__":
    main()