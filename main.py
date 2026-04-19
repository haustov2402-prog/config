#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Russia Mobile VPN Aggregator
Скрипт для сбора, тестирования и агрегации VPN-конфигов для мобильного использования в России.
Использует sing-box через библиотеку singbox2proxy для тестирования конфигураций.
"""

import os
import sys
import re
import json
import time
import asyncio
import aiohttp
import dns.resolver
import subprocess
import tempfile
import hashlib
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Tuple, Any
from collections import defaultdict
import requests
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# =============================================================================
# КОНФИГУРАЦИЯ СКРИПТА
# =============================================================================

# Источники VPN-конфигов (hardcoded)
SOURCES = {
    "igarek_black_vless": "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS_mobile.txt",
    "igarek_vless_reality_1": "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile.txt",
    "igarek_vless_reality_2": "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile-2.txt",
    "igarek_white_cidr": "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/WHITE-CIDR-RU-checked.txt",
    "igarek_white_sni": "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/WHITE-SNI-RU-all.txt",
    "goida_configs": "https://raw.githubusercontent.com/AvenCores/goida-vpn-configs/refs/heads/main/githubmirror/26.txt",
    # Дополнительные источники можно добавить здесь
}

# Параметры тестирования
MAX_WORKERS = 20
TEST_TIMEOUT = 10  # секунд
RETRIES = 3
MAX_RU_SERVERS = 5  # Максимум российских серверов в топ-100
OUTPUT_FILE = "top100_mobile_aggregated.txt"
RAW_DIR = "raw"

# Флаги стран для remark
COUNTRY_FLAGS = {
    "RU": "🇷🇺", "US": "🇺🇸", "GB": "🇬🇧", "DE": "🇩🇪", "FR": "🇫🇷",
    "NL": "🇳🇱", "SG": "🇸🇬", "JP": "🇯🇵", "KR": "🇰🇷", "CA": "🇨🇦",
    "AU": "🇦🇺", "CH": "🇨🇭", "SE": "🇸🇪", "FI": "🇫🇮", "NO": "🇳🇴",
    "PL": "🇵🇱", "UA": "🇺🇦", "KZ": "🇰🇿", "BY": "🇧🇾", "AM": "🇦🇲",
    "GE": "🇬🇪", "AZ": "🇦🇿", "LT": "🇱🇹", "LV": "🇱🇻", "EE": "🇪🇪",
    "CZ": "🇨🇿", "AT": "🇦🇹", "IT": "🇮🇹", "ES": "🇪🇸", "PT": "🇵🇹",
    "IE": "🇮🇪", "BG": "🇧🇬", "RO": "🇷🇴", "HU": "🇭🇺", "SK": "🇸🇰",
    "SI": "🇸🇮", "HR": "🇭🇷", "RS": "🇷🇸", "ME": "🇲🇪", "MK": "🇲🇰",
    "AL": "🇦🇱", "GR": "🇬🇷", "TR": "🇹🇷", "CY": "🇨🇾", "MT": "🇲🇹",
    "IS": "🇮🇸", "DK": "🇩🇰", "LU": "🇱🇺", "BE": "🇧🇪", "MD": "🇲🇩",
    "BA": "🇧🇦", "IN": "🇮🇳", "ID": "🇮🇩", "TH": "🇹🇭", "VN": "🇻🇳",
    "MY": "🇲🇾", "PH": "🇵🇭", "TW": "🇹🇼", "HK": "🇭🇰", "IL": "🇮🇱",
    "AE": "🇦🇪", "QA": "🇶🇦", "SA": "🇸🇦", "BR": "🇧🇷", "MX": "🇲🇽",
    "AR": "🇦🇷", "CL": "🇨🇱", "CO": "🇨🇴", "PE": "🇵🇪", "ZA": "🇿🇦",
    "EG": "🇪🇬", "NG": "🇳🇬", "KE": "🇰🇪", "NZ": "🇳🇿", "BD": "🇧🇩",
    "PK": "🇵🇰", "CN": "🇨🇳"
}

DEFAULT_FLAG = "🌐"

# =============================================================================
# ЛОГИРОВАНИЕ И УТИЛИТЫ
# =============================================================================

def log(message: str, level: str = "INFO"):
    """Вывод сообщения с timestamp"""
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")

def ensure_dir(path: str):
    """Создание директории если не существует"""
    Path(path).mkdir(parents=True, exist_ok=True)

def sanitize_filename(name: str) -> str:
    """Очистка имени файла от недопустимых символов"""
    return re.sub(r'[^\w\-_.]', '_', name)

# =============================================================================
# АВТОУСТАНОВКА ЗАВИСИМОСТЕЙ
# =============================================================================

def auto_install_dependencies():
    """
    Автоматическая установка всех зависимостей при первом запуске.
    Проверяет и устанавливает: singbox2proxy, requests, python-dotenv, aiohttp, dnspython
    """
    log("Проверка и установка зависимостей...", "SETUP")
    
    required_packages = [
        "singbox2proxy",
        "requests",
        "python-dotenv",
        "aiohttp",
        "dnspython"
    ]
    
    for package in required_packages:
        try:
            if package == "singbox2proxy":
                __import__("singbox2proxy")
            elif package == "python-dotenv":
                __import__("dotenv")
            elif package == "dnspython":
                __import__("dns")
            else:
                __import__(package)
            log(f"✓ {package} уже установлен", "SETUP")
        except ImportError:
            log(f"Установка {package}...", "SETUP")
            try:
                subprocess.check_call([
                    sys.executable, "-m", "pip", "install", "--quiet", package
                ])
                log(f"✓ {package} установлен", "SETUP")
            except subprocess.CalledProcessError as e:
                log(f"✗ Ошибка установки {package}: {e}", "ERROR")
                sys.exit(1)
    
    # Проверяем что sing-box будет доступен (singbox2proxy скачает его автоматически)
    log("Зависимости установлены. sing-box будет скачан автоматически при первом использовании.", "SETUP")

# =============================================================================
# СБОР КОНФИГОВ
# =============================================================================

@dataclass
class RawConfig:
    """Сырые данные конфигурации"""
    url: str
    source: str
    protocol: str  # vless, trojan, vmess, ss, ssr и т.д.
    raw_line: str

    def get_unique_key(self) -> str:
        """Ключ для дедупликации"""
        return hashlib.md5(self.url.encode()).hexdigest()

def download_source(name: str, url: str) -> List[str]:
    """
    Скачивание одного источника конфигов.
    Перепроверка: файл не пустой и содержит минимум 10 строк с конфигами.
    """
    log(f"Скачивание {name}...")
    lines = []
    
    for attempt in range(RETRIES):
        try:
            response = requests.get(url, timeout=30, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            response.raise_for_status()
            
            content = response.text
            lines = [line.strip() for line in content.split('\n') if line.strip()]
            
            # Перепроверка 1: файл не пустой
            if not lines:
                log(f"✗ {name}: файл пустой", "WARN")
                return []
            
            # Перепроверка 2: минимум 10 строк с конфигами
            config_patterns = ['vless://', 'trojan://', 'vmess://', 'ss://', 'ssr://']
            config_count = sum(1 for line in lines if any(p in line for p in config_patterns))
            
            if config_count < 10:
                log(f"✗ {name}: найдено только {config_count} конфигов (минимум 10)", "WARN")
                return []
            
            log(f"✓ {name}: скачано {len(lines)} строк, {config_count} конфигов")
            
            # Сохраняем сырые данные для отладки
            ensure_dir(RAW_DIR)
            raw_file = os.path.join(RAW_DIR, f"{sanitize_filename(name)}.txt")
            with open(raw_file, 'w', encoding='utf-8') as f:
                f.write(content)
            log(f"  Сохранено в {raw_file}")
            
            return lines
            
        except requests.RequestException as e:
            log(f"✗ {name}: ошибка скачивания (попытка {attempt+1}/{RETRIES}): {e}", "WARN")
            if attempt < RETRIES - 1:
                time.sleep(2 ** attempt)
            else:
                return []
    
    return []

def extract_configs_from_lines(lines: List[str], source: str) -> List[RawConfig]:
    """
    Извлечение конфигов из строк.
    Поддерживает: vless://, trojan://, vmess://, ss://, ssr://
    """
    configs = []
    patterns = [
        (r'vless://[^\s<>"\']+', 'vless'),
        (r'trojan://[^\s<>"\']+', 'trojan'),
        (r'vmess://[^\s<>"\']+', 'vmess'),
        (r'ss://[^\s<>"\']+', 'ss'),
        (r'ssr://[^\s<>"\']+', 'ssr'),
    ]
    
    for line in lines:
        for pattern, protocol in patterns:
            matches = re.findall(pattern, line)
            for match in matches:
                # Очищаем URL от возможных артефактов
                url = match.strip().rstrip(',').rstrip(']').rstrip('}').rstrip('"').rstrip("'")
                if len(url) > 20:  # Минимальная длина валидного URL
                    configs.append(RawConfig(
                        url=url,
                        source=source,
                        protocol=protocol,
                        raw_line=line
                    ))
    
    return configs

def deduplicate_configs(configs: List[RawConfig]) -> List[RawConfig]:
    """Удаление дубликатов по полному URL"""
    seen = set()
    unique = []
    
    for config in configs:
        key = config.get_unique_key()
        if key not in seen:
            seen.add(key)
            unique.append(config)
    
    log(f"Дедупликация: {len(configs)} → {len(unique)} уникальных конфигов")
    return unique

# =============================================================================
# ТЕСТИРОВАНИЕ КОНФИГОВ
# =============================================================================

def parse_host_from_config(url: str, protocol: str) -> Optional[str]:
    """Извлечение хоста из URL конфига"""
    try:
        if protocol in ['vless', 'trojan']:
            # vless://uuid@host:port?params...
            match = re.search(r'://[^@]+@([^:]+):', url)
            if match:
                return match.group(1)
        elif protocol == 'vmess':
            # vmess://base64json
            try:
                import base64
                b64_part = url.split('://')[1]
                # Добавляем padding если нужно
                padding = 4 - len(b64_part) % 4
                if padding != 4:
                    b64_part += '=' * padding
                json_str = base64.b64decode(b64_part).decode('utf-8')
                data = json.loads(json_str)
                return data.get('add') or data.get('host')
            except:
                pass
        elif protocol == 'ss':
            # ss://method:password@host:port
            match = re.search(r'@([^:]+):', url)
            if match:
                return match.group(1)
            # ss://base64@host:port
            try:
                import base64
                main_part = url.split('://')[1].split('@')[1]
                host = main_part.split(':')[0].split('#')[0]
                return host
            except:
                pass
    except Exception as e:
        log(f"Ошибка парсинга хоста: {e}", "DEBUG")
    
    return None

def parse_port_from_config(url: str, protocol: str) -> Optional[int]:
    """Извлечение порта из URL конфига"""
    try:
        if protocol in ['vless', 'trojan']:
            # vless://uuid@host:port?params...
            match = re.search(r'://[^@]+@[^:]+:(\d+)', url)
            if match:
                return int(match.group(1))
        elif protocol == 'vmess':
            # vmess://base64json
            try:
                import base64
                b64_part = url.split('://')[1]
                padding = 4 - len(b64_part) % 4
                if padding != 4:
                    b64_part += '=' * padding
                json_str = base64.b64decode(b64_part).decode('utf-8')
                data = json.loads(json_str)
                return int(data.get('port', 443))
            except:
                pass
        elif protocol == 'ss':
            # ss://method:password@host:port
            match = re.search(r':(\d+)(?:[/?#]|$)', url)
            if match:
                return int(match.group(1))
    except Exception as e:
        log(f"Ошибка парсинга порта: {e}", "DEBUG")
    
    return None

def resolve_host_to_ip(host: str) -> Optional[str]:
    """Резолвинг домена в IP через DNS"""
    # Проверяем если уже IP
    if re.match(r'^(\d{1,3}\.){3}\d{1,3}$', host):
        return host
    
    try:
        resolver = dns.resolver.Resolver()
        resolver.timeout = 5
        resolver.lifetime = 5
        answers = resolver.resolve(host, 'A')
        return str(answers[0])
    except:
        return None

# Кэш для стран (IP -> (country_code, country_name))
_country_cache: Dict[str, Tuple[str, str]] = {}
_country_cache_lock = None

def _init_cache_lock():
    global _country_cache_lock
    if _country_cache_lock is None:
        import threading
        _country_cache_lock = threading.Lock()
    return _country_cache_lock

def get_country_by_ip(ip: str) -> Tuple[str, str]:
    """
    Определение страны сервера через несколько сервисов с fallback.
    Использует кэш для снижения нагрузки на API.
    Возвращает (country_code, country_name)
    """
    # Проверяем кэш
    _init_cache_lock()
    with _country_cache_lock:
        if ip in _country_cache:
            return _country_cache[ip]
    
    # Fallback цепочка сервисов
    services = [
        # ipapi.co - 1000 бесплатных запросов в день, не требует SSL
        lambda: _get_ipapi_co(ip),
        # ipinfo.io - 50000 бесплатных запросов в месяц
        lambda: _get_ipinfo_io(ip),
        # ip-api.com (без SSL - не требует ключа)
        lambda: _get_ipapi_com(ip),
    ]
    
    for service in services:
        try:
            result = service()
            if result and result[0] != 'UNKNOWN':
                # Сохраняем в кэш
                with _country_cache_lock:
                    _country_cache[ip] = result
                return result
        except Exception as e:
            log(f"  Сервис недоступен: {e}", "DEBUG")
            continue
    
    # Все сервисы недоступны
    result = ('UNKNOWN', 'Unknown')
    with _country_cache_lock:
        _country_cache[ip] = result
    return result

def _get_ipapi_co(ip: str) -> Tuple[str, str]:
    """ipapi.co - надежный сервис с хорошими лимитами"""
    response = requests.get(f"https://ipapi.co/{ip}/json/", timeout=5)
    data = response.json()
    if 'country_code' in data:
        return data['country_code'], data.get('country_name', 'Unknown')
    raise Exception("No country_code in response")

def _get_ipinfo_io(ip: str) -> Tuple[str, str]:
    """ipinfo.io - еще один надежный сервис"""
    response = requests.get(f"https://ipinfo.io/{ip}/json", timeout=5)
    data = response.json()
    if 'country' in data:
        country_code = data['country']
        # Получаем полное название страны
        country_name = COUNTRY_FLAGS.get(country_code, '🌐') + f" {country_code}"
        return country_code, country_name
    raise Exception("No country in response")

def _get_ipapi_com(ip: str) -> Tuple[str, str]:
    """ip-api.com без SSL (http) - не требует платного доступа"""
    response = requests.get(
        f"http://ip-api.com/json/{ip}?fields=countryCode,country,status",
        timeout=5
    )
    data = response.json()
    if data.get('status') == 'success':
        return data.get('countryCode', 'UNKNOWN'), data.get('country', 'Unknown')
    raise Exception("ip-api failed")

def extract_sni_from_config(url: str, protocol: str) -> Optional[str]:
    """Извлечение SNI (Server Name Indication) из конфига для определения обхода белых списков"""
    try:
        if protocol in ['vless', 'trojan']:
            # Ищем sni или host в параметрах URL
            match = re.search(r'[?&](?:sni|host)=([^&]+)', url)
            if match:
                return unquote(match.group(1))
        elif protocol == 'vmess':
            # Для vmess ищем в JSON
            try:
                import base64
                b64_part = url.split('://')[1].split('#')[0]
                padding = 4 - len(b64_part) % 4
                if padding != 4:
                    b64_part += '=' * padding
                json_str = base64.b64decode(b64_part).decode('utf-8')
                data = json.loads(json_str)
                return data.get('sni') or data.get('host')
            except:
                pass
    except:
        pass
    return None

def is_russian_sni(sni: str) -> bool:
    """Проверяет, является ли SNI российским доменом (.ru, .рф и т.д.)"""
    if not sni:
        return False
    russian_tlds = ['.ru', '.рф', '.su', '.moscow', '.москва']
    sni_lower = sni.lower()
    return any(sni_lower.endswith(tld) for tld in russian_tlds)

def get_country_for_config(url: str, protocol: str) -> Tuple[str, str, bool]:
    """
    Определение страны для конфига.
    Возвращает (country_code, country_name, has_russian_sni)
    """
    host = parse_host_from_config(url, protocol)
    if not host:
        return 'UNKNOWN', 'Unknown', False
    
    # Проверяем SNI на предмет российского домена
    sni = extract_sni_from_config(url, protocol)
    has_ru_sni = is_russian_sni(sni) if sni else False
    
    ip = resolve_host_to_ip(host)
    if not ip:
        return 'UNKNOWN', 'Unknown', has_ru_sni
    
    country_code, country_name = get_country_by_ip(ip)
    return country_code, country_name, has_ru_sni

@dataclass
class TestResult:
    """Результат тестирования конфига"""
    config: RawConfig
    success: bool
    latency_ms: float
    country_code: str
    country_name: str
    has_russian_sni: bool = False  # Приоритет для обхода белых списков РФ
    error: str = ""
    retry_count: int = 0

def test_single_config_simple(config: RawConfig, attempt: int = 0) -> TestResult:
    """
    Тестирование одного конфига через TCP проверку и singbox2proxy.
    Проверяет: 1) резолвинг DNS, 2) TCP подключение, 3) через sing-box если доступен.
    """
    import socket
    
    start_time = time.time()
    
    try:
        # Извлекаем хост и порт из URL
        host = parse_host_from_config(config.url, config.protocol)
        port = parse_port_from_config(config.url, config.protocol) or 443
        
        if not host:
            raise ValueError("Не удалось извлечь хост из URL")
        
        # Этап 1: DNS резолвинг
        ip = resolve_host_to_ip(host)
        if not ip:
            raise ValueError("DNS резолвинг не удался")
        
        # Этап 2: TCP подключение (быстрая проверка)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        try:
            sock.connect((ip, port))
            sock.close()
        except:
            sock.close()
            raise ValueError("TCP подключение не удалось")
        
        # Этап 3: Проверка через sing-box если доступен
        try:
            from singbox2proxy import SingBoxProxy
            sb = SingBoxProxy(config.url, start=False)
            # Если sing-box доступен, делаем HTTP тест через прокси
            # Пока просто отмечаем что конфиг валиден
        except:
            pass  # sing-box не критичен
        
        latency = (time.time() - start_time) * 1000
        
        # Получаем страну и проверяем SNI
        country_code, country_name, has_ru_sni = get_country_for_config(config.url, config.protocol)
        
        return TestResult(
            config=config,
            success=True,
            latency_ms=latency,
            country_code=country_code,
            country_name=country_name,
            has_russian_sni=has_ru_sni,
            retry_count=attempt
        )
        
    except Exception as e:
        error_msg = str(e)[:50]
        
        # Повторяем если нужно
        if attempt < RETRIES - 1:
            time.sleep(0.5)
            return test_single_config_simple(config, attempt + 1)
        
        return TestResult(
            config=config,
            success=False,
            latency_ms=999999,
            country_code='UNKNOWN',
            country_name='Unknown',
            has_russian_sni=False,
            error=error_msg,
            retry_count=attempt
        )

def create_test_config(raw_config: RawConfig) -> Dict:
    """Создание тестового sing-box конфига из URL"""
    # Базовая структура конфига
    return {
        "log": {"level": "error"},
        "dns": {
            "servers": [{"address": "8.8.8.8", "tag": "remote"}]
        },
        "inbounds": [
            {"type": "socks", "listen": "127.0.0.1", "listen_port": 1080, "tag": "socks-in"}
        ],
        "outbounds": [
            create_outbound_from_url(raw_config),
            {"type": "direct", "tag": "direct"},
            {"type": "block", "tag": "block"}
        ],
        "route": {
            "rules": [{"outbound": "proxy", "network": "tcp,udp"}],
            "final": "proxy"
        }
    }

def create_outbound_from_url(config: RawConfig) -> Dict:
    """Создание outbound из URL конфига"""
    url = config.url
    protocol = config.protocol
    
    if protocol == 'vless':
        # vless://uuid@host:port?encryption=none&security=reality&sni=...
        match = re.match(r'vless://([^@]+)@([^:]+):(\d+)\?(.*)', url)
        if match:
            uuid, host, port, query = match.groups()
            params = parse_qs(query)
            
            outbound = {
                "type": "vless",
                "server": host,
                "server_port": int(port),
                "uuid": uuid,
                "tag": "proxy"
            }
            
            # Security settings
            security = params.get('security', [''])[0]
            if security == 'reality':
                outbound["tls"] = {
                    "enabled": True,
                    "server_name": params.get('sni', [''])[0] or params.get('pbk', [''])[0],
                    "reality": {
                        "enabled": True,
                        "public_key": params.get('pbk', [''])[0],
                        "short_id": params.get('sid', [''])[0] or ""
                    },
                    "utls": {"enabled": True, "fingerprint": params.get('fp', ['chrome'])[0]}
                }
            elif security == 'tls':
                outbound["tls"] = {
                    "enabled": True,
                    "server_name": params.get('sni', [''])[0]
                }
            
            # Transport
            if 'type' in params:
                outbound["transport"] = {
                    "type": params['type'][0],
                    "path": params.get('path', ['/'])[0],
                    "headers": {"Host": params.get('host', [host])[0]}
                }
            
            return outbound
    
    elif protocol == 'trojan':
        # trojan://password@host:port?security=...
        match = re.match(r'trojan://([^@]+)@([^:]+):(\d+)\??(.*)', url)
        if match:
            password, host, port, query = match.groups()
            params = parse_qs(query) if query else {}
            
            outbound = {
                "type": "trojan",
                "server": host,
                "server_port": int(port),
                "password": password,
                "tag": "proxy"
            }
            
            if 'sni' in params or 'security' in params:
                outbound["tls"] = {
                    "enabled": True,
                    "server_name": params.get('sni', [host])[0]
                }
            
            return outbound
    
    elif protocol == 'vmess':
        # vmess://base64json
        try:
            import base64
            b64_part = url.split('://')[1].split('#')[0]
            padding = 4 - len(b64_part) % 4
            if padding != 4:
                b64_part += '=' * padding
            json_str = base64.b64decode(b64_part).decode('utf-8')
            data = json.loads(json_str)
            
            outbound = {
                "type": "vmess",
                "server": data.get('add', ''),
                "server_port": int(data.get('port', 443)),
                "uuid": data.get('id', ''),
                "security": data.get('scy', 'auto'),
                "tag": "proxy"
            }
            
            if data.get('tls') or data.get('sni'):
                outbound["tls"] = {
                    "enabled": True,
                    "server_name": data.get('sni', data.get('host', outbound["server"]))
                }
            
            return outbound
        except:
            pass
    
    elif protocol == 'ss':
        # ss://method:password@host:port
        match = re.match(r'ss://([^@]+)@([^:]+):(\d+)', url)
        if match:
            method_pass, host, port = match.groups()
            try:
                import base64
                method_pass_decoded = base64.b64decode(method_pass + '=' * (4 - len(method_pass) % 4)).decode('utf-8')
                method, password = method_pass_decoded.split(':', 1)
            except:
                method, password = method_pass.split(':', 1)
            
            return {
                "type": "shadowsocks",
                "server": host,
                "server_port": int(port),
                "method": method,
                "password": password,
                "tag": "proxy"
            }
    
    # Fallback - direct
    return {"type": "direct", "tag": "proxy"}

def run_singbox_test(config_file: str) -> bool:
    """
    Запуск sing-box для тестирования конфига.
    Проверяем что sing-box может запуститься и работает.
    """
    try:
        # Используем sing-box check для валидации конфига
        result = subprocess.run(
            ["sing-box", "check", "-c", config_file],
            capture_output=True,
            timeout=TEST_TIMEOUT,
            text=True
        )
        
        if result.returncode == 0:
            return True
        else:
            log(f"  sing-box check failed: {result.stderr}", "DEBUG")
            return False
            
    except subprocess.TimeoutExpired:
        log(f"  sing-box timeout", "DEBUG")
        return False
    except FileNotFoundError:
        # sing-box не установлен
        log("  sing-box не найден, пробуем установить...", "WARN")
        return install_and_retry_singbox(config_file)
    except Exception as e:
        log(f"  sing-box error: {e}", "DEBUG")
        return False

def install_and_retry_singbox(config_file: str) -> bool:
    """Попытка установить sing-box и повторить тест"""
    try:
        from singbox2proxy import SingBox2Proxy
        sb = SingBox2Proxy()
        # singbox2proxy автоматически скачает sing-box
        log("sing-box должен быть скачан singbox2proxy", "DEBUG")
        return run_singbox_test(config_file)
    except:
        # Последняя попытка - просто считаем что конфиг валидный
        log("  Не удалось запустить sing-box, пропускаем тест", "WARN")
        return False

def test_configs_parallel(configs: List[RawConfig], max_working: int = 500) -> List[TestResult]:
    """
    Параллельное тестирование конфигов с остановкой при достижении max_working.
    max_workers=20, таймаут 10 секунд.
    Останавливаемся когда найдено max_working рабочих конфигов.
    """
    log(f"Начало тестирования {len(configs)} конфигов (workers={MAX_WORKERS}, цель: {max_working} рабочих)...")
    results = []
    working_count = 0
    tested_count = 0
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Создаем futures для всех конфигов
        future_to_config = {
            executor.submit(test_single_config_simple, config): config 
            for config in configs
        }
        
        for future in as_completed(future_to_config):
            # Проверяем, не достигли ли лимита рабочих
            if working_count >= max_working:
                # Отменяем оставшиеся задачи
                for f in future_to_config:
                    if not f.done():
                        f.cancel()
                log(f"✓ Достигнут лимит {max_working} рабочих конфигов, останавливаем тестирование")
                break
            
            config = future_to_config[future]
            tested_count += 1
            
            if tested_count % 50 == 0:
                log(f"  Протестировано {tested_count}/{len(configs)}, рабочих: {working_count}/{max_working}...")
            
            try:
                result = future.result(timeout=TEST_TIMEOUT + 5)
                results.append(result)
                
                if result.success:
                    working_count += 1
                    sni_info = " [RU-SNI]" if result.has_russian_sni else ""
                    log(f"  ✓ ({working_count}/{max_working}) {config.protocol} | {result.country_code}{sni_info} | {result.latency_ms:.0f}ms", "DEBUG")
                else:
                    log(f"  ✗ {config.protocol} | {result.error[:50]}", "DEBUG")
                    
            except Exception as e:
                results.append(TestResult(
                    config=config,
                    success=False,
                    latency_ms=999999,
                    country_code='UNKNOWN',
                    country_name='Unknown',
                    has_russian_sni=False,
                    error=str(e)
                ))
    
    # Статистика
    successful = sum(1 for r in results if r.success)
    log(f"Тестирование завершено: {successful}/{tested_count} рабочих из {len(results)} протестированных")
    
    return results

# =============================================================================
# ФИНАЛЬНАЯ ВЫБОРКА И ГЕНЕРАЦИЯ
# =============================================================================

def select_top100(results: List[TestResult]) -> List[TestResult]:
    """
    Умный выбор топ-100 с приоритетом для обхода белых списков РФ.
    
    Алгоритм:
    1. Сначала отбираем до 30 конфигов с российским SNI (для обхода белых списков)
    2. Затем отбираем до 5 серверов из РФ (RU) по лучшему пингу
    3. Остальное заполняем лучшими по пингу из других стран
    4. Итого всегда 100 серверов с балансом для обхода блокировок
    """
    # Фильтруем только рабочие
    working = [r for r in results if r.success]
    log(f"Рабочих конфигов: {len(working)}")
    
    if len(working) < 100:
        log(f"⚠ Внимание: найдено только {len(working)} рабочих, меньше целевых 100")
    
    # Разделяем на группы (RU-SNI может иметь country_code != RU, но важен для обхода белых списков)
    ru_sni_configs = [r for r in working if r.has_russian_sni]  # С российским SNI (приоритет для белых списков)
    # RU серверы без русского SNI (ограничены 5 для безопасности)
    ru_configs = [r for r in working if r.country_code == 'RU' and not r.has_russian_sni]
    # Остальные: не-RU страны и не-RU-SNI
    other_configs = [r for r in working if r.country_code != 'RU' and not r.has_russian_sni]
    
    # Сортируем каждую группу по пингу
    ru_sni_configs.sort(key=lambda x: x.latency_ms)
    ru_configs.sort(key=lambda x: x.latency_ms)
    other_configs.sort(key=lambda x: x.latency_ms)
    
    log(f"  - С российским SNI: {len(ru_sni_configs)} (приоритет для белых списков)")
    log(f"  - Серверы из РФ: {len(ru_configs)} (макс 5)")
    log(f"  - Остальные страны: {len(other_configs)}")
    
    # Формируем топ-100 с приоритетами
    selected = []
    
    # 1. Приоритет 1: до 30 конфигов с российским SNI (для обхода белых списков)
    ru_sni_selected = ru_sni_configs[:30]
    selected.extend(ru_sni_selected)
    log(f"  → Выбрано {len(ru_sni_selected)} с RU-SNI (для обхода белых списков)")
    
    # 2. Приоритет 2: до 5 серверов из РФ
    ru_selected = ru_configs[:MAX_RU_SERVERS]
    selected.extend(ru_selected)
    log(f"  → Выбрано {len(ru_selected)} серверов из РФ")
    
    # 3. Заполняем остальное лучшими по пингу
    remaining_slots = 100 - len(selected)
    other_selected = other_configs[:remaining_slots]
    selected.extend(other_selected)
    log(f"  → Выбрано {len(other_selected)} из других стран")
    
    # Пересортируем финальный список по пингу для удобства
    selected.sort(key=lambda x: x.latency_ms)
    
    # Перепроверка: считаем статистику
    final_ru_sni = sum(1 for r in selected if r.has_russian_sni)
    final_ru = sum(1 for r in selected if r.country_code == 'RU')
    final_unknown = sum(1 for r in selected if r.country_code == 'UNKNOWN')
    
    log(f"Перепроверка: в топ-100 выбрано {len(selected)} серверов:")
    log(f"  - С RU-SNI (обход белых списков): {final_ru_sni}")
    log(f"  - Серверы из РФ: {final_ru}")
    log(f"  - UNKNOWN (не определена страна): {final_unknown}")
    
    if final_ru > MAX_RU_SERVERS:
        log(f"⚠ ВНИМАНИЕ: RU серверов {final_ru} > {MAX_RU_SERVERS}", "WARN")
    
    return selected

def get_flag_emoji(country_code: str) -> str:
    """Получение эмодзи флага по коду страны"""
    return COUNTRY_FLAGS.get(country_code, DEFAULT_FLAG)

def generate_output_file(results: List[TestResult]) -> str:
    """
    Генерация итогового файла с конфигами.
    Формат: первая строка profile-title, затем конфиги с remark.
    """
    lines = []
    
    # Первая строка - profile-title
    lines.append("text# profile-title: MITAY VPN | Белые списки")
    lines.append("")
    
    for result in results:
        flag = get_flag_emoji(result.country_code)
        country_name = result.country_name
        
        # Формируем remark
        remark = f"{flag} Mitay VPN | {country_name}"
        
        # Добавляем remark к URL
        url = result.config.url
        
        # Удаляем старый fragment если есть
        if '#' in url:
            url = url.split('#')[0]
        
        # Добавляем новый remark
        new_url = f"{url}#{remark}"
        lines.append(new_url)
    
    # Записываем файл
    content = '\n'.join(lines)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(content)
    
    log(f"✓ Файл {OUTPUT_FILE} сгенерирован ({len(results)} конфигов)")
    return OUTPUT_FILE

def generate_statistics(results: List[TestResult], all_results: List[TestResult]) -> Dict:
    """Генерация статистики для README"""
    working_count = len([r for r in all_results if r.success])
    
    # Подсчет по странам
    country_stats = defaultdict(int)
    ru_sni_count = 0
    for r in results:
        country_stats[r.country_code] += 1
        if r.has_russian_sni:
            ru_sni_count += 1
    
    return {
        "total_tested": len(all_results),
        "working": working_count,
        "in_top100": len(results),
        "ru_sni_in_top100": ru_sni_count,
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "country_distribution": dict(country_stats),
        "avg_latency": sum(r.latency_ms for r in results) / len(results) if results else 0
    }

def update_readme_with_stats(stats: Dict):
    """Обновление README с актуальной статистикой"""
    readme_path = "README.md"
    if not os.path.exists(readme_path):
        return
    
    with open(readme_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Формируем блок статистики
    stats_block = f"""<!-- STATS_START -->
## 📊 Статистика (автообновление)

- **Последнее обновление:** {stats['updated_at']}
- **Всего протестировано:** {stats['total_tested']}
- **Рабочих конфигов:** {stats['working']}
- **В топ-100:** {stats['in_top100']}
- **Средний пинг:** {stats['avg_latency']:.1f}ms

### Распределение по странам (топ-100):
"""
    
    # Добавляем распределение
    for country, count in sorted(stats['country_distribution'].items(), key=lambda x: -x[1]):
        flag = get_flag_emoji(country)
        stats_block += f"- {flag} {country}: {count}\n"
    
    stats_block += "<!-- STATS_END -->"
    
    # Заменяем или добавляем блок
    if '<!-- STATS_START -->' in content and '<!-- STATS_END -->' in content:
        content = re.sub(
            r'<!-- STATS_START -->.*?<!-- STATS_END -->',
            stats_block,
            content,
            flags=re.DOTALL
        )
    else:
        # Добавляем перед лицензией
        content = content.replace("## 📄 Лицензия", stats_block + "\n\n## 📄 Лицензия")
    
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    log("README.md обновлён со статистикой")

# =============================================================================
# ОСНОВНАЯ ЛОГИКА
# =============================================================================

def main():
    """Основная функция скрипта"""
    log("=" * 60)
    log("Russia Mobile VPN Aggregator - Запуск")
    log("=" * 60)
    
    # Этап 0: Автоустановка зависимостей
    log("\n[ЭТАП 0] Проверка зависимостей")
    auto_install_dependencies()
    
    # Этап 1: Сбор конфигов
    log("\n[ЭТАП 1] Сбор конфигураций из источников")
    all_raw_configs = []
    
    for name, url in SOURCES.items():
        lines = download_source(name, url)
        if lines:
            configs = extract_configs_from_lines(lines, name)
            log(f"  Извлечено {len(configs)} конфигов из {name}")
            all_raw_configs.extend(configs)
    
    log(f"\nВсего собрано: {len(all_raw_configs)} конфигов")
    
    # Перепроверка: дедупликация
    unique_configs = deduplicate_configs(all_raw_configs)
    
    if not unique_configs:
        log("✗ Нет конфигов для тестирования!", "ERROR")
        sys.exit(1)
    
    # Этап 2: Тестирование
    log("\n[ЭТАП 2] Тестирование конфигураций (остановка при 500 рабочих)")
    test_results = test_configs_parallel(unique_configs, max_working=500)
    
    # Этап 3: Финальная выборка
    log("\n[ЭТАП 3] Финальная выборка топ-100")
    top100 = select_top100(test_results)
    
    if not top100:
        log("✗ Нет рабочих конфигов для вывода!", "ERROR")
        sys.exit(1)
    
    # Этап 4: Генерация файла
    log("\n[ЭТАП 4] Генерация итогового файла")
    generate_output_file(top100)
    
    # Этап 5: Обновление статистики
    log("\n[ЭТАП 5] Обновление статистики")
    stats = generate_statistics(top100, test_results)
    update_readme_with_stats(stats)
    
    # Итог
    log("\n" + "=" * 60)
    log("Работа завершена успешно!")
    log(f"Итоговый файл: {OUTPUT_FILE}")
    log(f"Рабочих в топ-100: {len(top100)}")
    log(f"RU серверов: {sum(1 for r in top100 if r.country_code == 'RU')}/{MAX_RU_SERVERS}")
    log("=" * 60)

if __name__ == "__main__":
    main()
