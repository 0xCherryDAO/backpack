from asyncio import run, set_event_loop_policy, gather, create_task, sleep
import random
import asyncio
from typing import Awaitable, Callable
import logging
import sys

from questionary import select, Choice
from loguru import logger

from config import *
from src.utils.data.helper import private_keys, proxies, recipients, filter_and_update_proxies
from src.database.generate_database import generate_database
from src.database.models import init_models, engine
from src.utils.data.mappings import module_handlers
from src.utils.manage_tasks import manage_tasks, manage_fork
from src.utils.retrieve_route import get_routes, get_forks_tasks
from src.models.route import Route
from src.utils.tg_app.telegram_notifications import TGApp
from src.utils.runner import process_multiple_deposit_addresses, process_forks_database_creation, process_fork

logging.getLogger("asyncio").setLevel(logging.CRITICAL)

logging.basicConfig(level=logging.CRITICAL)

if sys.platform == 'win32':
    set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def get_module():
    result = select(
        message="Choose module",
        choices=[
            Choice(title="1) Generate new database", value=1),
            Choice(title="2) Work with existing database", value=2),
            Choice(title="3) Forks mode", value=3),
            Choice(title="4) Get deposit addresses", value=4),
        ],
        qmark="⚙️ ",
        pointer="✅ "
    ).ask()
    return result


async def process_task(routes: list[Route]) -> None:
    if not routes:
        logger.success(f'All tasks are completed')
        return

    tasks = []
    for route in routes:
        tasks.append(create_task(process_route(route)))

        time_to_pause = random.randint(PAUSE_BETWEEN_WALLETS[0], PAUSE_BETWEEN_WALLETS[1]) \
            if isinstance(PAUSE_BETWEEN_WALLETS, list) else PAUSE_BETWEEN_WALLETS
        logger.info(f'Sleeping {time_to_pause} seconds before next wallet...')
        await sleep(time_to_pause)

    await gather(*tasks)


async def process_route(route: Route) -> None:
    if route.wallet.proxy:
        if route.wallet.proxy.proxy_url and MOBILE_PROXY and ROTATE_IP:
            await route.wallet.proxy.change_ip()

    private_key = route.wallet.private_key

    for task in route.tasks:
        completed = await module_handlers[task](route)

        if completed:
            await manage_tasks(private_key, task)

        time_to_pause = random.randint(PAUSE_BETWEEN_MODULES[0], PAUSE_BETWEEN_MODULES[1]) \
            if isinstance(PAUSE_BETWEEN_MODULES, list) else PAUSE_BETWEEN_MODULES

        logger.info(f'Sleeping {time_to_pause} seconds before next module...')
        await sleep(time_to_pause)

    if TG_BOT_TOKEN and TG_USER_ID:
        tg_app = TGApp(
            token=TG_BOT_TOKEN,
            tg_id=TG_USER_ID,
            private_key=private_key
        )
        await tg_app.send_message()


async def main(module: Callable) -> None:
    await init_models(engine)
    if module == 1:
        if SHUFFLE_WALLETS:
            random.shuffle(private_keys)
        logger.debug("Generating new database")
        await generate_database(engine, private_keys, proxies, recipients)
    elif module == 2:
        logger.debug("Working with the database")
        routes = await get_routes(private_keys)
        await process_task(routes)
    elif module == 3:
        result = await select(
            message="Choose module",
            choices=[
                Choice(title="1) Generate new forks database", value=1),
                Choice(title="2) Work with existing forks database", value=2),
            ],
            qmark="⚙️ ",
            pointer="✅ "
        ).ask_async()
        if result == 1:
            await process_forks_database_creation(private_keys, proxies)
        elif result == 2:
            tasks = await get_forks_tasks()
            if not tasks:
                logger.success(f'All forks are completed. Create new database.')
                return
            for task in tasks:
                completed = await process_fork(task)
                if completed:
                    await manage_fork(task.id)

                time_to_sleep = random.randint(PAUSE_BETWEEN_WALLETS[0], PAUSE_BETWEEN_WALLETS[1])
                logger.info(f'Sleeping {time_to_sleep} seconds before next fork...')
                await sleep(time_to_sleep)
    elif module == 4:
        logger.debug("Getting deposit addresses for all wallets")
        await process_multiple_deposit_addresses(private_keys, proxies)

    else:
        print("Wrong choice")
        return


def start_event_loop(awaitable: Awaitable[None]) -> None:
    run(awaitable)


if __name__ == '__main__':
    module = get_module()
    start_event_loop(main(module))
