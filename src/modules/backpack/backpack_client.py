from decimal import Decimal
from typing import Optional, List, TypedDict, cast, Dict, Any, Tuple

from loguru import logger

from src.utils.request_client.client import RequestClient
from src.utils.proxy_manager import Proxy


class OrderBookResponse(TypedDict):
    lastUpdateId: int
    bids: List[List[str]]
    asks: List[List[str]]


class BackpackClient(RequestClient):
    def __init__(
            self,
            proxy: Optional[Proxy] = None,
    ):
        RequestClient.__init__(self, proxy=proxy)
        self.backpack_api_url: str = 'https://api.backpack.exchange/'
        self.logger = logger.bind(client="BackpackClient")

    async def get_token_price(self, symbol: str) -> Decimal:
        url = f'{self.backpack_api_url}api/v1/ticker?symbol={symbol}'

        response, status = await self.make_request(
            method="GET",
            url=url,
        )

        if status != 200 or not response:
            self.logger.error(f"Failed to get price for {symbol}: Status {status}")
            raise ValueError(f"Failed to get price data for {symbol}")
        try:
            price = Decimal(response['lastPrice'])
            self.logger.info(f"Current price for {symbol}: {price}")
            return price
        except (KeyError, ValueError) as ex:
            self.logger.error(f"Error parsing price for {symbol}: {ex}")
            raise ValueError(f"Invalid price data for {symbol}: {ex}")

    async def get_order_book_depth(self, symbol: str) -> OrderBookResponse:
        url = f'{self.backpack_api_url}api/v1/depth?symbol={symbol}'

        response, status = await self.make_request(
            method="GET",
            url=url,
        )

        if status != 200 or not response:
            self.logger.error(f"Failed to get order book for {symbol}: Status {status}")
            raise ValueError(f"Failed to get order book data for {symbol}")

        try:
            if not isinstance(response, dict) or 'asks' not in response or 'bids' not in response:
                raise ValueError("Invalid order book response format")

            order_book: OrderBookResponse = cast(OrderBookResponse, response)
            return order_book
        except Exception as ex:
            self.logger.error(f"Error parsing order book for {symbol}: {ex}")
            raise ValueError(f"Invalid order book data for {symbol}: {ex}")

    async def get_token_decimals(self, symbol: str) -> Optional[int]:
        try:
            order_book = await self.get_order_book_depth(symbol)

            if not order_book['asks'] or len(order_book['asks']) == 0:
                self.logger.warning(f"No asks in order book for {symbol}")
                return None

            amount = order_book['asks'][0][1]

            decimals = len(str(amount).split('.')[1]) if '.' in str(amount) else 0
            return decimals

        except (IndexError, KeyError, TypeError, ValueError) as ex:
            self.logger.error(f"Error determining decimals for {symbol}: {ex}")
            return None

    async def get_markets(self) -> List[Dict[str, Any]]:
        url = f'{self.backpack_api_url}api/v1/markets'

        response, status = await self.make_request(
            method="GET",
            url=url,
        )

        if status != 200 or not response:
            self.logger.error(f"Failed to get markets: Status {status}")
            raise ValueError("Failed to get markets data")

        try:
            usdc_markets = [market for market in response if market.get('quoteSymbol') == 'USDC']

            self.logger.info(f"Found {len(usdc_markets)} USDC markets")
            return usdc_markets
        except Exception as ex:
            self.logger.error(f"Error parsing markets data: {ex}")
            raise ValueError(f"Invalid markets data: {ex}")

    async def get_usdc_symbols(self) -> Tuple[List[str], List[str]]:
        """
        Returns:
            Tuple containing two lists:
            - List of spot market symbols (e.g. ["SOL_USDC", "BTC_USDC", ...])
            - List of perpetual futures symbols (e.g. ["SOL_USDC_PERP", "BTC_USDC_PERP", ...])
        """
        markets = await self.get_markets()
        symbols = [market['symbol'] for market in markets]

        spot_symbols = [s for s in symbols if s.endswith('_USDC') and not s.endswith('_USDC_PERP')]
        perp_symbols = [s for s in symbols if s.endswith('_USDC_PERP')]

        self.logger.info(f"Found {len(spot_symbols)} spot markets and {len(perp_symbols)} perpetual futures markets")

        return spot_symbols, perp_symbols

    async def get_spot_symbols(self) -> List[str]:
        spot_symbols, _ = await self.get_usdc_symbols()
        return spot_symbols

    async def get_perp_symbols(self) -> List[str]:
        _, perp_symbols = await self.get_usdc_symbols()
        return perp_symbols
