import random
import time
import base64
import asyncio
from decimal import Decimal, ROUND_DOWN
from typing import (
    Optional,
    Dict,
    Any,
    Literal,
    List,
    Union,
    overload,
    cast,
    Tuple
)

from loguru import logger
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.utils.proxy_manager import Proxy
from src.modules.backpack.backpack_client import BackpackClient

T_Balances = Dict[str, Dict[str, Any]]


class BackpackAccount(BackpackClient):
    def __init__(
            self,
            proxy: Optional[Proxy] = None,
            api_key: Optional[str] = None
    ) -> None:
        BackpackClient.__init__(self, proxy=proxy)

        if api_key is None and hasattr(proxy, 'wallet') and hasattr(proxy.wallet, 'api_key'):
            api_key = proxy.wallet.api_key

        if api_key is None:
            self.logger.warning("API key not provided. Authenticated operations will not work.")

        self.api_key = api_key

        if api_key:
            self.signer = Ed25519PrivateKey.from_private_bytes(base64.b64decode(api_key))

            public_key = self.signer.public_key().public_bytes_raw()
            self.public_key_hex = public_key.hex()
            self.public_key_b64 = base64.b64encode(public_key).decode(encoding='utf-8')

            self.logger = logger.bind(account=self.public_key_b64[:8])
        else:
            self.logger = logger.bind(client="BackpackAccount")

    def _sign_message_b64(self, message: str) -> str:
        signed_message = base64.b64encode(self.signer.sign(message.encode('utf-8'))).decode('utf-8')
        return signed_message

    def _generate_headers(self, timestamp: int, signature: str, window: int = 60000) -> Dict[str, str]:
        headers = {
            'X-API-KEY': self.public_key_b64,
            'X-SIGNATURE': signature,
            'X-TIMESTAMP': str(timestamp),
            'X-WINDOW': str(window),
            "Content-Type": "application/json; charset=utf-8"
        }
        return headers

    def _sign_query(
            self,
            instruction_type: Literal[
                'balanceQuery',
                'depositAddressQuery',
                'depositQueryAll',
                'fillHistoryQueryAll',
                'positionQuery',
                'orderCancel',
                'orderCancelAll',
                'orderExecute',
                'orderHistoryQueryAll',
                'orderQuery',
                'orderQueryAll',
                'withdraw',
                'withdrawalQueryAll'
            ],
            timestamp: int,
            query_data: Optional[Union[Dict[str, Any], List[str], Any]] = None,
            window: int = 60000
    ) -> str:
        try:
            if query_data is not None:
                if isinstance(query_data, dict):
                    sorted_data = dict(sorted(query_data.items()))

                    for key, value in sorted_data.items():
                        if isinstance(value, bool):
                            sorted_data[key] = str(value).lower()

                    query_string = '&'.join([f"{key}={value}" for key, value in sorted_data.items()])
                elif isinstance(query_data, list):
                    query_string = '&'.join(query_data)
                else:
                    query_string = str(query_data)

                query_string += f"&timestamp={timestamp}&window={window}"
            else:
                query_string = f"timestamp={timestamp}&window={window}"

            signing_string = f"instruction={instruction_type}&{query_string}"

            signature = self._sign_message_b64(signing_string)
            return signature
        except Exception as e:
            self.logger.error(f"Error in signature generation: {e}", exc_info=True)
            raise

    async def _query(
            self,
            instruction_type: Literal[
                'balanceQuery',
                'depositAddressQuery',
                'depositQueryAll',
                'fillHistoryQueryAll',
                'positionQuery',
                'orderCancel',
                'orderCancelAll',
                'orderExecute',
                'orderHistoryQueryAll',
                'orderQuery',
                'orderQueryAll',
                'withdraw',
                'withdrawalQueryAll'
            ],
            method: Literal['post', 'get'],
            url_path: str,
            query_data: Optional[Union[Dict[str, Any], List[str], Any]] = None,
            request_body: Optional[Dict[str, Any]] = None,
            window: int = 60000,
    ) -> Dict[str, Any]:
        url = f"{self.backpack_api_url}{url_path}"
        timestamp = int(time.time() * 1000)

        signature = self._sign_query(instruction_type, timestamp, query_data, window)
        headers = self._generate_headers(timestamp, signature, window)

        try:
            if method.lower() == 'post':
                response, status = await self.make_request(
                    method="POST",
                    url=url,
                    headers=headers,
                    json=request_body
                )
            elif method.lower() == 'get':
                response, status = await self.make_request(
                    method="GET",
                    url=url,
                    headers=headers
                )
            else:
                raise ValueError(f"Invalid request method: {method}")

            if status != 200:
                raise ValueError(f"API request failed with status {status}: {response}")

            if response is None:
                self.logger.error(f"Empty response from: {url_path}")
                raise ValueError(f"Empty response despite status {status}")
            return response
        except Exception as ex:
            self.logger.error(f"Error executing query: {ex}")
            raise

    @overload
    async def get_balances(self) -> T_Balances:
        ...

    @overload
    async def get_balances(self, symbol: Literal['ALL']) -> T_Balances:
        ...

    @overload
    async def get_balances(self, symbol: str) -> float:
        ...

    async def get_balances(self, symbol: str = 'ALL') -> Union[T_Balances, float]:
        url_path = 'api/v1/capital'
        try:
            balances = await self._query('balanceQuery', 'get', url_path)

            if not balances or len(balances) == 0:
                self.logger.debug("Empty response with authentication, trying direct request")

                url = f"{self.backpack_api_url}{url_path}"
                basic_headers = {"Content-Type": "application/json"}

                direct_response, direct_status = await self.make_request(
                    method="GET",
                    url=url,
                    headers=basic_headers
                )

                if direct_status == 200 and direct_response and len(direct_response) > 0:
                    balances = direct_response
                    self.logger.info("Successfully retrieved balances with direct request")
                else:
                    self.logger.info(f"No balances found - account may be empty or not properly authenticated")
                    if symbol == 'ALL':
                        return {}
                    else:
                        return 0.0

            if symbol == 'ALL':
                return cast(T_Balances, balances)
            else:
                try:
                    if symbol in balances:
                        self.logger.info(f'Available balance for {symbol} is {balances[symbol]["available"]}')
                        return float(balances[symbol]['available'])
                    else:
                        self.logger.info(f"No balance for {symbol} found. Available tokens: {list(balances.keys())}")
                        return 0.0
                except (KeyError, ValueError) as e:
                    self.logger.error(f"Error retrieving balance for {symbol}: {e}")
                    raise ValueError(f"Could not get balance for {symbol}")

        except Exception as e:
            self.logger.error(f"Error getting balances: {e}")
            if symbol == 'ALL':
                return {}
            else:
                return 0.0

    async def _get_limit_data(self, symbol: str, amount_usd: float, side: Literal['Ask', 'Bid']) -> Tuple[str, str]:
        depth = await self.get_order_book_depth(symbol)

        if side == 'Bid':
            book_side = 'asks'
            price = depth[book_side][0][0]
        else:
            book_side = 'bids'
            price = depth[book_side][-1][0]

        token_decimals = await self.get_token_decimals(symbol)
        if token_decimals is None:
            token_decimals = 8

        amount = amount_usd / float(price)
        amount = str(round(amount * (10 ** token_decimals)) / (10 ** token_decimals))

        if float(amount) == 0 and side == 'Bid':
            raise ValueError('Buy amount is smaller than the minimal amount')

        return price, amount

    async def post_limit_order(
            self,
            symbol: str,
            side: Literal['Bid', 'Ask'],
            amount_usd: float = 0,
            amount_token: float = 0,
            time_in_force: Literal['IOC', 'FOK', 'GTC'] = 'IOC'
    ) -> Dict[str, Any]:
        price, quantity = await self._get_limit_data(symbol, amount_usd, side)

        url_path = 'api/v1/order'

        payload = {
            'orderType': 'Limit',
            'price': price,
            'quantity': quantity if amount_token == 0 else str(amount_token),
            'side': side,
            'symbol': symbol,
            'timeInForce': time_in_force
        }

        order = await self._query('orderExecute', 'post', url_path, payload, payload)
        return order

    async def open_futures_pos(
            self,
            symbol: str,
            side: Literal['Bid', 'Ask'],
            amount_usd: float = 0,
            amount_token: float = 0,
            time_in_force: Literal['IOC', 'FOK', 'GTC'] = 'GTC'
    ) -> int:
        price, quantity = await self._get_limit_data(symbol, amount_usd, side)

        url_path = 'api/v1/order'

        payload = {
            'orderType': 'Market',
            'quantity': quantity if amount_token == 0 else str(amount_token),
            'side': side,
            'symbol': symbol,
            'timeInForce': time_in_force,
            'reduceOnly': False,
        }

        order = await self._query('orderExecute', 'post', url_path, payload, payload)

        if order['status'] == 'Filled':
            self.logger.success(f'{self.public_key_b64}: order filled')
            return 1
        else:
            self.logger.warning(f'{self.public_key_b64}: order failed to fill - order details: {order}')
            return 0

    async def close_futures_pos(
            self,
            symbol: str,
            side_of_opened_pos: Literal['Bid', 'Ask'],
            size_of_opened_pos: float,
            time_in_force: Literal['IOC', 'FOK', 'GTC'] = 'GTC'
    ) -> int:
        self.logger.info(f'{self.public_key_b64}: closing position on {symbol}')
        side = 'Bid' if side_of_opened_pos == 'Ask' else 'Ask'

        url_path = 'api/v1/order'
        payload = {
            'orderType': 'Market',
            'quantity': str(abs(size_of_opened_pos)),
            'side': side,
            'symbol': symbol,
            'timeInForce': time_in_force,
            'reduceOnly': True,
        }
        order = await self._query('orderExecute', 'post', url_path, payload, payload)
        if order['status'] == 'Filled':
            self.logger.success(f'{self.public_key_b64}: order filled')
            return 1
        else:
            self.logger.warning(f'{self.public_key_b64}: order failed to fill - order details: {order}')
            return 0

    async def backpack_withdraw(
            self,
            amount_to_deposit: float,
            blockchain: Literal['Solana', 'Ethereum', 'Polygon', 'Bitcoin'] = 'Solana',
            symbol: str = 'USDC',
            address: Optional[str] = None
    ) -> Dict[str, Any]:
        if address is None:
            raise ValueError("Withdrawal address must be provided")

        url_path = 'wapi/v1/capital/withdrawals'
        amount_str = str(Decimal(amount_to_deposit).quantize(Decimal(f'1e-{2}'), rounding=ROUND_DOWN))
        payload = {
            "address": address,
            "blockchain": blockchain,
            "quantity": amount_str,
            "symbol": symbol
        }

        timestamp = int(time.time() * 1000)
        window = 60000

        signing_string = f"instruction=withdraw&timestamp={timestamp}&window={window}"
        signature = self._sign_message_b64(signing_string)

        headers = {
            'X-API-KEY': self.public_key_b64,
            'X-SIGNATURE': signature,
            'X-TIMESTAMP': str(timestamp),
            'X-WINDOW': str(window),
            "Content-Type": "application/json; charset=utf-8"
        }

        full_url = f"{self.backpack_api_url}{url_path}"

        self.logger.info(f"Withdrawing {amount_to_deposit} {symbol} to {address} on {blockchain} blockchain")

        print(f"\nWithdrawal Request:")
        print(f"URL: {full_url}")
        print(f"Payload: {payload}")
        print(f"Headers: {headers}\n")

        async with self.session.request(
                method="POST",
                url=full_url,
                headers=headers,
                json=payload
        ) as response:
            print(f"\nWithdrawal Response:")
            print(f"Status: {response.status}")
            print(f"Headers: {response.headers}")

            try:
                response_json = await response.json()
                print(f"Response JSON: {response_json}\n")

                if response.status == 200:
                    self.logger.success(f"Successfully withdrawn {amount_to_deposit} {symbol} to {address}")
                    return response_json
                else:
                    error_msg = f"Failed to withdraw {symbol}: Status {response.status}, Response: {response_json}"
                    self.logger.error(error_msg)
                    raise ValueError(error_msg)
            except Exception as ex:
                response_text = await response.text()
                print(f"Response Text: {response_text}\n")

                error_msg = f"Failed to withdraw {symbol}: Status {response.status}, Response: {response_text}"
                self.logger.error(error_msg)
                raise ValueError(error_msg)

    async def get_open_positions(self) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        url_path = f'api/v1/position'
        positions = await self._query('positionQuery', 'get', url_path)
        return positions

    async def close_all_positions(self) -> int:
        positions = await self.get_open_positions()

        if isinstance(positions, dict):
            position_list = positions.get('positions', [])
        else:
            position_list = positions

        if len(position_list) < 1:
            self.logger.info(f'{self.public_key_b64}: No positions to close')
            return 0

        for position in position_list:
            pos_size = float(position['netQuantity'])
            side = cast(Literal['Bid', 'Ask'], 'Bid' if pos_size > 0 else 'Ask')
            res = await self.close_futures_pos(position['symbol'], side, pos_size)
            if res and position != position_list[-1]:
                await asyncio.sleep(1)
        return 1

    async def check_all_positions(self) -> None:
        positions = await self.get_open_positions()

        if len(positions) < 1:
            self.logger.info(f'{self.public_key_b64}: No open positions')

        for position in positions:
            pos_size = float(position['netQuantity'])
            side = 'Bid' if pos_size > 0 else 'Ask'
            self.logger.info(
                f'{self.public_key_b64}: {position["symbol"]} {"LONG" if side == "Bid" else "SHORT"}'
                f' position - size: {abs(pos_size)}'
            )

    async def withdraw(
            self,
            percent_to_withdraw: Union[List[float], int] = 100,
            blockchain: Literal['Solana', 'Ethereum', 'Polygon', 'Bitcoin'] = 'Solana',
            symbol: str = 'USDC',
            address: Optional[str] = None
    ) -> Dict[str, Any]:
        if address is None:
            raise ValueError("Withdrawal address must be provided")

        balance = await self.get_balances(symbol)

        if isinstance(percent_to_withdraw, list) and len(percent_to_withdraw) == 2:
            percent = random.uniform(percent_to_withdraw[0], percent_to_withdraw[1]) / 100
            quantity = round(balance * percent, 4)
        else:
            percent = percent_to_withdraw / 100
            quantity = round(balance * percent, 4)

        if quantity <= 0:
            raise ValueError(f"Calculated withdrawal amount is too small: {quantity} {symbol}")

        url_path = 'wapi/v1/capital/withdrawals'

        payload = {
            "address": address,
            "blockchain": blockchain,
            "quantity": str(quantity),
            "symbol": symbol,
            "twoFactorToken": "",
            "autoNorrow": False,
            "autoLendRedeem": False
        }

        self.logger.info(f"Withdrawing {quantity} {symbol} to {address} on {blockchain} blockchain")

        try:
            withdrawal = await self._query('withdraw', 'post', url_path, payload, payload)
            self.logger.success(f"Withdrawal request submitted successfully")
            return withdrawal
        except Exception as ex:
            self.logger.error(f"Withdrawal failed: {ex}")

            if "403" in str(ex):
                self.logger.error(
                    "Access forbidden. This could be due to insufficient permissions or 2FA requirements.")

            raise

    async def get_overall_balance(self) -> float:
        balances = await self.get_balances()
        total_balance = 0.0

        for token in balances.keys():
            if token == 'USDC':
                total_balance += float(balances['USDC']['available'])
                continue

            decimals = await self.get_token_decimals(f'{token}_USDC')
            balance = float(balances[token]['available'])

            if balance != 0:
                price = await self.get_token_price(f'{token}_USDC')
                await asyncio.sleep(1)
                total_balance = total_balance + balance * float(price)

        return round(total_balance, 2)

    async def get_token_balances(self) -> None:
        balances = await self.get_balances()
        total_balance = 0.0
        positions = []

        for token in balances.keys():
            if token == 'USDC':
                total_balance += float(balances['USDC']['available'])
                continue

            decimals = await self.get_token_decimals(f'{token}_USDC')
            balance = float(balances[token]['available'])

            if balance != 0:
                price = await self.get_token_price(f'{token}_USDC')
                await asyncio.sleep(1)
                total_balance = total_balance + balance * float(price)

                positions.append([token, balances[token]['available'], round(balance * float(price), 2)])

        if len(positions) < 1:
            self.logger.info(f'{self.public_key_b64}: No token positions')

        for position in positions:
            self.logger.info(f'{self.public_key_b64}: {position[2]} USD in {position[1]} {position[0]}')

        self.logger.info(f'{self.public_key_b64}: Total balance: {total_balance} USD')

    async def post_limit_sell_order(self, symbol: str, amount_token: float,
                                    time_in_force: Literal['IOC', 'FOK', 'GTC'] = 'GTC') -> Dict[str, Any]:
        token_decimals = await self.get_token_decimals(symbol) or 6
        amount_token_formatted = round(amount_token, token_decimals)

        url_path = 'api/v1/order'
        current_price = await self.get_token_price(symbol)
        price, _ = await self._get_limit_data(symbol, float(current_price) * amount_token_formatted, 'Ask')

        payload = {
            'orderType': 'Limit',
            'price': price,
            'quantity': str(amount_token_formatted),
            'side': 'Ask',
            'symbol': symbol,
            'timeInForce': time_in_force
        }

        return await self._query('orderExecute', 'post', url_path, payload, payload)

    async def get_deposit_address(self, chain: Literal['Solana', 'Bitcoin', 'Ethereum', 'Polygon'] = 'Solana') -> str:
        url_path = 'wapi/v1/capital/deposit/address'
        timestamp = int(time.time() * 1000)
        window = 60000
        query_string = f"blockchain={chain}&timestamp={timestamp}&window={window}"
        signing_string = f"instruction=depositAddressQuery&{query_string}"
        signature = self._sign_message_b64(signing_string)
        headers = self._generate_headers(timestamp, signature, window)

        full_url = f"{self.backpack_api_url}{url_path}?blockchain={chain}"
        response, status = await self.make_request(
            method="GET",
            url=full_url,
            headers=headers
        )

        if status == 200 and response:
            self.logger.success(f"Successfully retrieved deposit address for {chain}")
            return response['address']
        else:
            self.logger.error(f"Failed to get deposit address")
            raise ValueError(f"Failed to get deposit address, see logs for details")
