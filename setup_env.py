#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
setup_env.py - Настройка окружения для Russia Mobile VPN Aggregator
Запустите этот скрипт ОДИН РАЗ перед первым запуском main.py
"""

import os
import re
import sys

def main():
    print("=" * 60)
    print("Настройка окружения для Russia Mobile VPN Aggregator")
    print("=" * 60)
    print()
    
    # Запрашиваем raw-ссылку на GitHub репозиторий
    print("Введите raw-ссылку на ваш GitHub-репозиторий")
    print("(например: https://raw.githubusercontent.com/ВАШНИК/russia-mobile-vpn-aggregator/main/)")
    print("Если не хотите указывать - просто нажмите Enter")
    raw_url = input("Raw URL: ").strip()
    
    # Запрашиваем GitHub Token
    print()
    print("Введите GitHub Token (ghp_...)")
    print("Нужен для автообновления через GitHub Actions")
    print("Получить можно тут: https://github.com/settings/tokens")
    print("Если не хотите указывать - просто нажмите Enter")
    token = input("GitHub Token: ").strip()
    
    # Парсим raw URL для извлечения owner и repo
    owner = ""
    repo = ""
    
    if raw_url:
        # Паттерн: https://raw.githubusercontent.com/OWNER/REPO/...
        match = re.search(r'raw\.githubusercontent\.com/([^/]+)/([^/]+)', raw_url)
        if match:
            owner, repo = match.groups()
            print(f"✓ Распознано: владелец={owner}, репозиторий={repo}")
        else:
            print("⚠ Не удалось распознать владельца и репозиторий из URL")
            owner = input("Введите имя владельца вручную: ").strip()
            repo = input("Введите имя репозитория вручную: ").strip()
    
    # Создаем .env файл
    env_lines = []
    
    if token:
        env_lines.append(f"GITHUB_TOKEN={token}")
    
    if owner:
        env_lines.append(f"GITHUB_REPO_OWNER={owner}")
    
    if repo:
        env_lines.append(f"GITHUB_REPO_NAME={repo}")
    
    # Записываем .env
    if env_lines:
        with open('.env', 'w', encoding='utf-8') as f:
            f.write('\n'.join(env_lines) + '\n')
        print()
        print("✓ Файл .env создан успешно!")
        print("Содержимое:")
        for line in env_lines:
            # Маскируем токен для вывода
            if line.startswith('GITHUB_TOKEN=') and len(line) > 20:
                print(f"  GITHUB_TOKEN={'*' * 10}")
            else:
                print(f"  {line}")
    else:
        print()
        print("⚠ Ничего не введено, .env не создан")
    
    print()
    print("=" * 60)
    print("Настройка завершена!")
    print()
    print("Теперь вы можете запустить:")
    print("  python main.py")
    print()
    print("Для автообновления через GitHub Actions:")
    print("1. Загрузите этот репозиторий на GitHub")
    print("2. Добавьте GITHUB_TOKEN в Settings → Secrets → Actions")
    print("3. Actions будут запускаться автоматически каждый час")
    print("=" * 60)

if __name__ == "__main__":
    main()
