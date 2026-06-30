#!/usr/bin/env python3
import argparse
import os
import sys
import hashlib
from collections import defaultdict

def parse_arguments():
    """Реализация интерфейса командной строки (CLI)."""
    parser = argparse.ArgumentParser(
        description="Анализ дубликатов файлов в среде Astra Linux.",
        add_help=True
    )
    parser.add_argument(
        "--path", type=str, default=".", 
        help="Путь к директории для поиска дубликатов"
    )
    parser.add_argument(
        "--hash", type=str, default="sha256", choices=["md5", "sha1", "sha256"], 
        help="Алгоритм хеширования файлов (md5, sha1, sha256)"
    )
    parser.add_argument(
        "--export", type=str, 
        help="Путь к файлу для экспорта отчета"
    )
    return parser.parse_args()


def get_potential_duplicates(target_path):
    """Шаг 1: Быстрая группировка файлов по их размеру."""
    size_groups = defaultdict(list)
    print("[*] Сканирование директории: {}...".format(target_path))
    
    try:
        for root, _, files in os.walk(target_path):
            for file in files:
                full_path = os.path.join(root, file)
                try:
                    if os.path.islink(full_path):
                        continue
                    file_size = os.path.getsize(full_path)
                    size_groups[file_size].append(full_path)
                except (PermissionError, FileNotFoundError) as e:
                    print("[Предупреждение] Нет доступа к файлу {}: {}".format(full_path, e), file=sys.stderr)
    except Exception as e:
        print("[Ошибка] Не удалось прочитать директорию {}: {}".format(target_path, e), file=sys.stderr)
        sys.exit(1)

    # Оставляем только те размеры, где файлов больше одного
    return {size: paths for size, paths in size_groups.items() if len(paths) > 1}


def calculate_file_hash(file_path, hash_algo):
    """Шаг 2: Безопасное поблочное чтение файла для расчета его хеш-суммы."""
    hasher = hashlib.new(hash_algo)
    try:
        with open(file_path, 'rb') as f:
            # Читаем блоками по 4096 байт, чтобы не забивать ОЗУ крупными файлами
            for chunk in iter(lambda: f.read(4096), b''):
                hasher.update(chunk)
        return hasher.hexdigest()
    except (PermissionError, FileNotFoundError) as e:
        print("[Предупреждение] Ошибка чтения при хешировании {}: {}".format(file_path, e), file=sys.stderr)
        return None


def find_exact_duplicates(size_groups, hash_algo):
    """Шаг 3: Проверка хешей у файлов с одинаковым размером."""
    exact_duplicates = defaultdict(list)
    print("[*] Вычисление хеш-сумм ({}) для подозрительных файлов...".format(hash_algo))
    
    for size, paths in size_groups.items():
        hash_to_paths = defaultdict(list)
        
        for path in paths:
            file_hash = calculate_file_hash(path, hash_algo)
            if file_hash:
                hash_to_paths[file_hash].append(path)
                
        # Настоящие дубликаты — те, у которых совпал и размер, и хеш
        for file_hash, paths_list in hash_to_paths.items():
            if len(paths_list) > 1:
                # Ключом делаем кортеж (хеш, размер файла)
                exact_duplicates[(file_hash, size)] = paths_list
                
    return exact_duplicates


def main():
    args = parse_arguments()
    
    if not os.path.exists(args.path):
        print("[Ошибка] Указанный путь не существует: {}".format(args.path), file=sys.stderr)
        sys.exit(1)
        
    # 1. Находим файлы с одинаковыми размерами
    potential_duplicates = get_potential_duplicates(args.path)
    
    if not potential_duplicates:
        print("[+] Дубликатов не обнаружено (все файлы имеют уникальный размер).")
        return

    # 2. Находим точные дубликаты по хеш-суммам
    exact_duplicates = find_exact_duplicates(potential_duplicates, args.hash)
    
    if not exact_duplicates:
        print("[+] Дубликатов по хеш-суммам не обнаружено.")
        return

    # 3. Аналитика и вывод результатов на экран (Экранная форма)
    print("\n" + "="*50)
    print("РЕЗУЛЬТАТЫ АНАЛИЗА ДУБЛИКАТОВ")
    print("="*50)
    
    total_freed_space = 0
    group_index = 1
    
    for (file_hash, size), paths in exact_duplicates.items():
        print("\nГруппа №{} (Хеш {}: {})".format(group_index, args.hash, file_hash))
        print("Размер одного файла: {} байт".format(size))
        print("Обнаруженные копии:")
        for path in paths:
            print("  -> {}".format(path))
            
        # Подсчет потенциально освобождаемого места в этой группе
        # Формула: размер * (количество_копий - 1)
        freed_in_group = size * (len(paths) - 1)
        total_freed_space += freed_in_group
        group_index += 1
        
    print("\n" + "="*50)
    print("ИТОГОВАЯ СТАТИСТИКА:")
    print("Всего найдено групп дубликатов: {}".format(len(exact_duplicates)))
    # Переводим байты в мегабайты для удобства восприятия
    mb_saved = total_freed_space / (1024 * 1024)
    print("Потенциально освобождаемое место: {} байт (~ {:.2f} МБ)".format(total_freed_space, mb_saved))
    print("="*50)

if __name__ == "__main__":
    main()
