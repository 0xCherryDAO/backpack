from abc import ABC, abstractmethod
from asyncio import sleep
import random
from typing import Callable, Optional

import ccxt
from loguru import logger

from config import RETRIES, PAUSE_BETWEEN_RETRIES, OKXWithdrawSettings
from src.models.cex import CEXConfig
from src.modules.backpack.backpack_account import BackpackAccount
from src.utils.proxy_manager import Proxy
from src.utils.request_client.client import RequestClient

from src.utils.common.wrappers.decorators import retry


class CEX(ABC, BackpackAccount, RequestClient):
    def __init__(
            self,
            private_key: str,
            proxy: Proxy | None,
            config: CEXConfig
    ):
        self.amount = None
        self.token = None
        self.chain: Optional[str] = None
        self.to_address = None
        self.keep_balance = None
        self.api_key = None
        self.api_secret = None
        self.passphrase = None
        self.password = None
        self.proxy = None
        self.exchange_instance = None

        self.config = config
        if config.okx_config:
            self.setup_exchange(exchange_config=config.okx_config, exchange_type='okx')
        elif config.binance_config:
            self.setup_exchange(exchange_config=config.binance_config, exchange_type='binance')
        elif config.bitget_config:
            self.setup_exchange(exchange_config=config.bitget_config, exchange_type='bitget')
        if isinstance(self.chain, list):
            self.chain = random.choice(self.chain)

        BackpackAccount.__init__(self, api_key=private_key, proxy=proxy)
        RequestClient.__init__(self, proxy=self.proxy)

    @abstractmethod
    def call_withdraw(self, exchange_instance) -> Optional[bool]:
        """Calls withdraw function"""

    @abstractmethod
    async def call_sub_transfer(
            self, token: str, api_key: str, api_secret: str, api_passphrase: Optional[str],
            api_password: Optional[str], request_func: Callable
    ):
        """Calls transfer from sub-account to main-account"""

    async def okx_withdraw(self) -> Optional[bool]:
        balance_before_withdraw = await self.get_balance_before_withdrawal()
        if balance_before_withdraw >= OKXWithdrawSettings.min_usdc_balance:
            logger.debug(
                f'На кошельке уже есть {round(balance_before_withdraw, 5)} {self.token}. '
                f'Вывод не требуется.'
            )
            return True

        logger.debug(f'Checking sub-accounts balances before withdrawal...')
        await self.call_sub_transfer(
            self.token, self.api_key, self.api_secret, self.passphrase, self.password, self.make_request
        )
        await sleep(10)
        withdrawn = self.call_withdraw(self.exchange_instance)
        if withdrawn:
            await self.wait_for_withdrawal(balance_before_withdraw)
            return True

    @retry(retries=RETRIES, delay=PAUSE_BETWEEN_RETRIES, backoff=1.5)
    async def deposit(self) -> Optional[bool]:
        try:
            usdc_balance = await self.get_balances("USDC")

            if usdc_balance <= self.keep_balance:
                logger.info(
                    f"Current USDC balance {usdc_balance} is less than or equal to keep_balance {self.keep_balance}. "
                    f"Skipping deposit."
                )
                return True

            amount_to_deposit = usdc_balance - self.keep_balance

            logger.info(
                f"Depositing {amount_to_deposit} USDC to {self.to_address} on {self.chain}"
            )

            withdraw_result = await self.backpack_withdraw(
                amount_to_deposit=amount_to_deposit,
                blockchain=self.chain,
                symbol="USDC",
                address=self.to_address,
            )

            if withdraw_result:
                logger.success(
                    f"Successfully deposited USDC to {self.to_address} on {self.chain}"
                )
                return True
            else:
                logger.error(f"Failed to deposit USDC to {self.to_address}")
                return None

        except Exception as ex:
            logger.error(f"Error during deposit operation: {ex}")
            raise

    async def wait_for_withdrawal(self, balance_before_withdraw: float) -> None:
        logger.info(f'Waiting for {self.token} to arrive...')
        while True:
            try:
                usdc_balance = await self.get_balances("USDC")
                if usdc_balance > balance_before_withdraw:
                    logger.success(f'{self.token} has arrived | [{self.to_address}]')
                    break
                await sleep(20)
            except Exception as ex:
                logger.error(f'Something went wrong {ex}')
                await sleep(10)
                continue

    async def get_balance_before_withdrawal(self) -> float:
        usdc_balance = await self.get_balances("USDC")
        return usdc_balance

    def setup_exchange(self, exchange_config, exchange_type):
        if exchange_config.withdraw_settings:
            self.amount = exchange_config.withdraw_settings.calculated_amount
            self.token = exchange_config.withdraw_settings.token
            self.chain = exchange_config.withdraw_settings.chain
            self.to_address = exchange_config.withdraw_settings.to_address

        self.api_key = exchange_config.API_KEY
        self.api_secret = exchange_config.API_SECRET
        self.proxy = exchange_config.PROXY

        if exchange_type == 'okx':
            self.passphrase = exchange_config.PASSPHRASE
            self.exchange_instance = ccxt.okx({
                'apiKey': self.api_key,
                'secret': self.api_secret,
                'password': self.passphrase,
                'enableRateLimit': True,
                'proxies': self.get_proxies(self.proxy)
            })
        elif exchange_type == 'binance':
            self.exchange_instance = ccxt.binance({
                'apiKey': self.api_key,
                'secret': self.api_secret,
                'enableRateLimit': True,
                'proxies': self.get_proxies(self.proxy),
                'options': {'defaultType': 'spot'}
            })
        elif exchange_type == 'bitget':
            self.password = exchange_config.PASSWORD
            self.exchange_instance = ccxt.bitget({
                'apiKey': self.api_key,
                'secret': self.api_secret,
                'password': self.password,
                'enableRateLimit': True,
                'proxies': self.get_proxies(self.proxy),
                'options': {'defaultType': 'spot'}
            })

        if exchange_config.deposit_settings:
            self.token = exchange_config.deposit_settings.token
            self.chain = exchange_config.deposit_settings.chain
            self.to_address = exchange_config.deposit_settings.to_address
            self.keep_balance = exchange_config.deposit_settings.calculated_keep_balance

    @staticmethod
    def get_proxies(proxy: str | None) -> dict[str, str | None]:
        return {
            'http': proxy if proxy else None,
            'https': proxy if proxy else None
        }
