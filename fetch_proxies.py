#!/usr/bin/env python3
"""
Script para fazer scraping de proxies de múltiplas fontes públicas
e guardar numa lista clean em formato ip:porta
"""

import requests
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import datetime
import sys

# Cores para output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

PROXY_SOURCES = {
    "HTTP": [
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http",
        "https://raw.githubusercontent.com/zloi-user/hideip.me/main/http.txt",
        "https://raw.githubusercontent.com/zloi-user/hideip.me/main/https.txt",
        "https://raw.githubusercontent.com/BreakingTechFr/Proxy_Free/main/proxies/http.txt",
        "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/main/proxies/http.txt",
        "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/main/proxies/https.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.txt",
        "https://yakumo.rei.my.id/HTTP",
        "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/master/https.txt",
        "https://raw.githubusercontent.com/officialputuid/KangProxy/KangProxy/http/http.txt",
        "https://raw.githubusercontent.com/officialputuid/KangProxy/KangProxy/https/https.txt",
        "https://sunny9577.github.io/proxy-scraper/generated/http_proxies.txt",
        "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt",
    ],
    "SOCKS4": [
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks4",
        "https://raw.githubusercontent.com/zloi-user/hideip.me/main/socks4.txt",
        "https://raw.githubusercontent.com/BreakingTechFr/Proxy_Free/main/proxies/socks4.txt",
        "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/main/proxies/socks4.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks4/data.txt",
        "https://yakumo.rei.my.id/SOCKS4",
        "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/officialputuid/KangProxy/KangProxy/socks4/socks4.txt",
        "https://sunny9577.github.io/proxy-scraper/generated/socks4_proxies.txt",
        "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks4.txt",
    ],
    "SOCKS5": [
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks5",
        "https://raw.githubusercontent.com/zloi-user/hideip.me/main/socks5.txt",
        "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
        "https://raw.githubusercontent.com/BreakingTechFr/Proxy_Free/main/proxies/socks5.txt",
        "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/main/proxies/socks5.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks5/data.txt",
        "https://yakumo.rei.my.id/SOCKS5",
        "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/officialputuid/KangProxy/KangProxy/socks5/socks5.txt",
        "https://sunny9577.github.io/proxy-scraper/generated/socks5_proxies.txt",
        "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks5.txt",
    ]
}

TIMEOUT = 10
MAX_WORKERS = 10


def fetch_proxies_from_url(url: str, protocol: str) -> list:
    """Faz scraping de proxies de uma URL específica."""
    proxies = []
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, timeout=TIMEOUT, headers=headers)
        response.raise_for_status()
        
        # Regex para encontrar padrões ip:porta
        pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}:\d{1,5}\b'
        matches = re.findall(pattern, response.text)
        
        if matches:
            proxies = matches
            print(f"{BLUE}[{protocol}]{RESET} {url.split('/')[-1]}: {GREEN}{len(proxies)} proxies{RESET}")
        else:
            print(f"{BLUE}[{protocol}]{RESET} {url.split('/')[-1]}: {YELLOW}0 proxies{RESET}")
            
    except requests.Timeout:
        print(f"{BLUE}[{protocol}]{RESET} {url.split('/')[-1]}: {RED}timeout{RESET}")
    except requests.ConnectionError:
        print(f"{BLUE}[{protocol}]{RESET} {url.split('/')[-1]}: {RED}conexão falhou{RESET}")
    except Exception as e:
        print(f"{BLUE}[{protocol}]{RESET} {url.split('/')[-1]}: {RED}{str(e)[:50]}{RESET}")
    
    return proxies


def fetch_all_proxies() -> dict:
    """Faz scraping de todas as fontes em paralelo."""
    all_proxies = {protocol: [] for protocol in PROXY_SOURCES}
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {}
        
        for protocol, urls in PROXY_SOURCES.items():
            for url in urls:
                future = executor.submit(fetch_proxies_from_url, url, protocol)
                futures[future] = (protocol, url)
        
        completed = 0
        for future in as_completed(futures):
            completed += 1
            protocol, url = futures[future]
            try:
                proxies = future.result()
                all_proxies[protocol].extend(proxies)
            except Exception as e:
                print(f"{RED}Erro ao processar {url}: {e}{RESET}")
    
    return all_proxies


def validate_proxy(proxy: str) -> bool:
    """Valida formato da proxy (ip:porta)."""
    try:
        ip, port = proxy.split(':')
        octets = ip.split('.')
        if len(octets) != 4:
            return False
        for octet in octets:
            num = int(octet)
            if num < 0 or num > 255:
                return False
        port_num = int(port)
        if port_num < 1 or port_num > 65535:
            return False
        return True
    except:
        return False


def save_proxies(all_proxies: dict, output_dir: str = "data"):
    """Salva proxies em arquivos separados por protocolo."""
    Path(output_dir).mkdir(exist_ok=True)
    
    total_unique = 0
    
    for protocol, proxies in all_proxies.items():
        # Remover duplicados e validar
        valid_proxies = list(set(p.strip() for p in proxies if validate_proxy(p.strip())))
        valid_proxies.sort()
        
        output_file = f"{output_dir}/proxies_{protocol.lower()}.txt"
        with open(output_file, 'w', encoding='utf-8') as f:
            for proxy in valid_proxies:
                f.write(f"{proxy}\n")
        
        count = len(valid_proxies)
        total_unique += count
        print(f"{GREEN}✓{RESET} {protocol}: {YELLOW}{count} proxies únicas{RESET} → {output_file}")
    
    # Arquivo com todas as proxies
    all_file = f"{output_dir}/proxies_all.txt"
    with open(all_file, 'w', encoding='utf-8') as f:
        for protocol, proxies in all_proxies.items():
            valid_proxies = list(set(p.strip() for p in proxies if validate_proxy(p.strip())))
            for proxy in sorted(valid_proxies):
                f.write(f"{proxy}\n")
    
    print(f"{GREEN}✓{RESET} Todas: {YELLOW}{total_unique} proxies únicas{RESET} → {all_file}")
    
    # Informações extras
    print(f"\n{BLUE}📊 Resumo:{RESET}")
    print(f"   HTTP: {len(set(p.strip() for p in all_proxies.get('HTTP', []) if validate_proxy(p.strip())))}")
    print(f"   SOCKS4: {len(set(p.strip() for p in all_proxies.get('SOCKS4', []) if validate_proxy(p.strip())))}")
    print(f"   SOCKS5: {len(set(p.strip() for p in all_proxies.get('SOCKS5', []) if validate_proxy(p.strip())))}")
    print(f"   Total: {total_unique}")
    print(f"\n   Última atualização: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def main():
    print(f"{BLUE}🌐 Fazendo scraping de proxies...{RESET}\n")
    
    all_proxies = fetch_all_proxies()
    
    print(f"\n{BLUE}💾 Salvando proxies...{RESET}\n")
    save_proxies(all_proxies)
    
    print(f"\n{GREEN}✅ Concluído!{RESET}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}⚠️  Operação cancelada pelo utilizador{RESET}")
        sys.exit(0)
    except Exception as e:
        print(f"\n{RED}❌ Erro: {e}{RESET}")
        sys.exit(1)
