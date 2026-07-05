#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import os
import sys
import hashlib
import json
import csv
from collections import defaultdict

def parse():
    parser = argparse.ArgumentParser(
        description="Утилита для поиска и анализа файлов-дубликатов в среде Astra Linux.",
        add_help=False
    )
    # добавлние русского языка
    parser.add_argument(
        "-h", "--help",
        action="help",
        help="Показать это справочное сообщение и выйти."
    )

    parser.add_argument(
        "--path",
        type=str,
        default=".",
        help="Путь к целевой директории для сканирования (по умолчанию: текущая директория)."
    )

    parser.add_argument(
        "--hash",
        type=str,
        default="sha256",
        choices=["md5", "sha1", "sha256"],
        help="Алгоритм хеширования для точной проверки файлов (по умолчанию: sha256)."
    )

    parser.add_argument(
        "--export",
        type=str,
        help="Путь к файлу для сохранения отчета. Поддерживаются расширения: .txt, .json, .csv"
    )

    parser._optionals.title = "Доступные параметры"
    return parser.parse_args()

def get_potential_duplicates(target_path):
    """
    Рекурсивный обход директории и предварительная группировка по размеру.
    Позволяет значительно ускорить работу, отсекая заведомо уникальные файлы.
    """
    size_groups = defaultdict(list)
    print("[+] Сканирование директории: {}...".format(target_path))
    try:
        for root, _, files in os.walk(target_path):
            for file in files:
                full_path = os.path.join(root, file)
                try:
                    # игнорируем символические ссылки во избежание зацикливания
                    if os.path.islink(full_path):
                        continue
                    file_size = os.path.getsize(full_path)
                    size_groups[file_size].append(full_path)
                except (PermissionError, FileNotFoundError) as e:
                    # обработка ошибок доступа
                    print("[Предупреждение] Пропуск файла (нет доступа): {} ({})".format(full_path, e), file=sys.stderr)
    except Exception as e:
        print("[Ошибка] Критическая ошибка при чтении каталога {}: {}".format(target_path, e), file=sys.stderr)
        sys.exit(1)
    # оставляем только те группы, где файлов больше 1 (потенциальные дубликаты)
    return {size: paths for size, paths in size_groups.items() if len(paths) > 1}

def calculate_hash(file_path, algo):
    """
    Поблочное чтение файла для расчета хеш-суммы.
    Не загружает файл целиком в память, что предотвращает сбои на больших файлах.
    """
    try:
        hasher = hashlib.new(algo)
        with open(file_path, 'rb') as f:
            # чтение блоками по 4096 байт
            for chunk in iter(lambda: f.read(4096), b''):
                hasher.update(chunk)
        return hasher.hexdigest()
    except (PermissionError, FileNotFoundError) as e:
        print("[Предупреждение] Не удалось вычислить хеш для {}: {}".format(file_path, e), file=sys.stderr)
        return None

def find_exact_duplicates(size_groups, algo):
    # вычисление хешей для файлов со сходящимися размерами.
    exact_duplicates = defaultdict(list)
    print("[+] Вычисление хеш-сумм по алгоритму {}...".format(algo))
    for size, paths in size_groups.items():
        hash_to_paths = defaultdict(list)
        for path in paths:
            file_hash = calculate_hash(path, algo)
            if file_hash:
                hash_to_paths[file_hash].append(path)
        for file_hash, paths_list in hash_to_paths.items():
            if len(paths_list) > 1:
                # ключ - кортеж (хеш, размер)
                exact_duplicates[(file_hash, size)] = paths_list
    return exact_duplicates

def export_report(exact_duplicates, algo, export_path, space):
    # форматирование и экспорт отчета в зависимости от расширения файла (.txt, .json, .csv).
    ext = os.path.splitext(export_path)[1].lower()
    print("[+] Экспорт отчета в файл: {}...".format(export_path))
    try:
        if ext == '.json':
            # структурированный JSON формат
            report_data = {
                "summary": {
                    "total_duplicate_groups": len(exact_duplicates),
                    "potential_freed_bytes": space,
                    "hash_algorithm": algo
                },
                "groups": []
            }
            for (file_hash, size), paths in exact_duplicates.items():
                report_data["groups"].append({
                    "hash": file_hash,
                    "file_size_bytes": size,
                    "copies_count": len(paths),
                    "paths": paths
                })
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, ensure_ascii=False, indent=4)
        elif ext == '.csv':
            # табличный CSV формат
            with open(export_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Group_ID", "Hash_Algorithm", "Hash_Value", "File_Size_Bytes", "File_Path"])

                group_id = 1
                for (file_hash, size), paths in exact_duplicates.items():
                    for path in paths:
                        writer.writerow([group_id, algo, file_hash, size, path])
                    group_id += 1
        else:
            # текстовый человекочитаемый формат (по умолчанию)
            with open(export_path, 'w', encoding='utf-8') as f:
                f.write("==================================================\n")
                f.write("ОТЧЕТ АНАЛИЗА ДУБЛИКАТОВ ФАЙЛОВ\n")
                f.write("==================================================\n\n")
                group_id = 1
                for (file_hash, size), paths in exact_duplicates.items():
                    f.write("Группа №{} (Алгоритм: {}, Хеш: {})\n".format(group_id, algo, file_hash))
                    f.write("Размер файла: {} байт\n".format(size))
                    f.write("Копии файла:\n")
                    for path in paths:
                        f.write("  - {}\n".format(path))
                    f.write("\n")
                    group_id += 1
                f.write("==================================================\n")
                f.write("ИТОГОВАЯ СТАТИСТИКА:\n")
                f.write("Всего групп дубликатов: {}\n".format(len(exact_duplicates)))
                f.write("Потенциально освобождаемое место: {} байт (~ {:.2f} МБ)\n".format(
                    space, space / (1024 * 1024)
                ))
                f.write("==================================================\n")
        print("[+] Отчет успешно сохранен.")
    except Exception as e:
        print("[Ошибка] Не удалось записать отчет в файл {}: {}".format(export_path, e), file=sys.stderr)

def main():
    args = parse()
    if not os.path.exists(args.path):
        print("[Ошибка] Указанный путь не существует: {}".format(args.path), file=sys.stderr)
        sys.exit(1)
    # первичный поиск по размерам
    potential_duplicates = get_potential_duplicates(args.path)
    if not potential_duplicates:
        print("[+] Дубликатов не обнаружено (все файлы имеют уникальный размер).")
        return
    # точный поиск по хеш-суммам
    exact_duplicates = find_exact_duplicates(potential_duplicates, args.hash)
    if not exact_duplicates:
        print("[+] Дубликатов по хеш-суммам не обнаружено.")
        return
    # расчет Освобождаемого места
    space = 0
    for (file_hash, size), paths in exact_duplicates.items():
        # Место освобождается, если удалить (N - 1) копий
        space += size * (len(paths) - 1)
    # вывод экранной формы (в консоль)
    print("\n" + "=" * 50)
    print("РЕЗУЛЬТАТЫ АНАЛИЗА ДУБЛИКАТОВ (ЭКРАННАЯ ФОРМА)")
    print("=" * 50)
    group_index = 1
    for (file_hash, size), paths in exact_duplicates.items():
        print("\nГруппа №{} (Размер: {} байт, Хеш ({}): {})".format(group_index, size, args.hash, file_hash))
        for path in paths:
            print("  -> {}".format(path))
        group_index += 1
    print("\n" + "=" * 50)
    print("ИТОГОВАЯ СТАТИСТИКА:")
    print("Всего найдено групп дубликатов: {}".format(len(exact_duplicates)))
    print("Потенциально освобождаемое место: {} байт (~ {:.2f} МБ)".format(
        space, space / (1024 * 1024)
    ))
    print("=" * 50)
    # экспорт в файл при указании параметра --export
    if args.export:
        export_report(exact_duplicates, args.hash, args.export, space)


if __name__ == "__main__":
    main()
