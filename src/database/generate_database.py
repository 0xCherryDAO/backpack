from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete

from loguru import logger

from src.database.base_models.pydantic_manager import DataBaseManagerConfig
from src.database.models import WorkingWallets, WalletsTasks
from src.database.utils.db_manager import DataBaseUtils
from config import *


async def clear_database(engine) -> None:
    async with AsyncSession(engine) as session:
        async with session.begin():
            for model in [WorkingWallets, WalletsTasks]:
                await session.execute(delete(model))
            await session.commit()
    logger.info("The database has been cleared")


async def generate_database(
        engine,
        private_keys: list[str],
        proxies: list[str],
        recipients: list[str]
) -> None:
    await clear_database(engine)
    tasks = []
    if OKX_WITHDRAW: tasks.append('OKX_WITHDRAW')
    if BACKPACK_SPOT: tasks.append('BACKPACK_SPOT')
    if BACKPACK_FUTURES: tasks.append('BACKPACK_FUTURES')
    if RANDOM_SWAPS: tasks.append('RANDOM_SWAPS')
    if CLOSE_ALL: tasks.append('CLOSE_ALL')
    if SWAP_ALL_TO_USDC: tasks.append('SWAP_ALL_TO_USDC')
    if GET_TICKERS: tasks.append('GET_TICKERS')
    if OKX_DEPOSIT: tasks.append('OKX_DEPOSIT')

    proxy_index = 0
    for private_key in private_keys:
        with open('wallets.txt', 'r') as file:
            file_private_keys = [line.strip() for line in file]

        private_key_index = file_private_keys.index(private_key)
        recipient_address = None
        if OKX_DEPOSIT:
            if len(private_keys) != len(recipients):
                logger.error(f'Количество приватных ключей не соответствует количеству адресов получателей')
                return
            recipient_address = recipients[private_key_index]

        proxy = proxies[proxy_index]
        proxy_index = (proxy_index + 1) % len(proxies)

        proxy_url = None
        change_link = ''

        if proxy:
            if MOBILE_PROXY:
                proxy_url, change_link = proxy.split('|')
            else:
                proxy_url = proxy

        db_utils = DataBaseUtils(
            manager_config=DataBaseManagerConfig(
                action='working_wallets'
            )
        )

        await db_utils.add_to_db(
            private_key=private_key,
            proxy=f'{proxy_url}|{change_link}' if MOBILE_PROXY else proxy_url,
            recipient=recipient_address,
            status='pending',
        )
        for task in tasks:
            db_utils = DataBaseUtils(
                manager_config=DataBaseManagerConfig(
                    action='wallets_tasks'
                )
            )
            await db_utils.add_to_db(
                private_key=private_key,
                status='pending',
                task_name=task
            )
