from colorama import Fore
from aiohttp import ClientSession
import asyncio
from asyncio import Semaphore

with open('config.py', 'r', encoding='utf-8-sig') as file:
    module_config = file.read()

exec(module_config)

with open('wallets.txt', 'r', encoding='utf-8-sig') as file:
    private_keys = [line.strip() for line in file]

with open('proxies.txt', 'r', encoding='utf-8-sig') as file:
    proxies = [line.strip() for line in file]
    if not proxies:
        proxies = [None for _ in range(len(private_keys))]

with open('recipients.txt', 'r', encoding='utf-8-sig') as file:
    recipients = [line.strip() for line in file]
    if not recipients:
        recipients = [None for _ in range(len(private_keys))]

print(Fore.BLUE + f'Loaded {len(private_keys)} wallets:')
print('\033[39m')


async def check_proxy(proxy: str, semaphore: Semaphore) -> bool:
    test_url = "https://lisk.drpc.org"
    async with semaphore:
        try:
            async with ClientSession() as session:
                async with session.get(test_url, proxy=f"http://{proxy}", timeout=8) as response:
                    if response.status == 200:
                        return True
        except Exception as ex:
            pass
        return False


async def filter_and_update_proxies(proxies: list[str], max_concurrent_tasks: int = 50) -> list[str]:
    semaphore = Semaphore(max_concurrent_tasks)
    tasks = [check_proxy(proxy, semaphore) for proxy in proxies]
    results = await asyncio.gather(*tasks)

    working_proxies = [proxy for proxy, is_working in zip(proxies, results) if is_working]

    with open('proxies.txt', 'w', encoding='utf-8-sig') as file:
        file.write("\n".join(working_proxies))

    print(Fore.BLUE + f"Количество рабочих прокси: {len(working_proxies)}")
    print(Fore.BLUE + f"Количество нерабочих прокси: {len(proxies) - len(working_proxies)}")
    print('\033[39m')

    return working_proxies
