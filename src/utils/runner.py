import random
from typing import Optional, Literal, List, Dict
from asyncio import sleep
from decimal import Decimal, ROUND_DOWN

from loguru import logger

from config import *
from src.database.base_models.pydantic_manager import DataBaseManagerConfig
from src.database.models import Forks
from src.database.utils.db_manager import DataBaseUtils
from src.models.cex import OKXConfig, WithdrawSettings, CEXConfig, DepositSettings
from src.models.route import Route
from src.modules.backpack.backpack_account import BackpackAccount
from src.modules.cex.okx.okx import OKX
from src.utils.proxy_manager import Proxy


async def process_backpack_spot(route: Route) -> Optional[bool]:
    side = BackpackSpotSettings.side
    symbol = random.choice(BackpackSpotSettings.symbol) + '_USDC'
    time_in_force: Literal['IOC', 'FOK', 'GTC'] = 'FOK'

    token = symbol.split('_')[0]

    backpack = BackpackAccount(
        proxy=route.wallet.proxy,
        api_key=route.wallet.private_key
    )

    try:
        if side == 'Bid':  # BUY (side == 'Bid')
            usdc_balance = await backpack.get_balances("USDC")
            logger.info(f"USDC balance: {usdc_balance}")

            if BackpackSpotSettings.use_percentage_usdc:
                percentage = random.uniform(BackpackSpotSettings.trade_percentage_usdc[0],
                                            BackpackSpotSettings.trade_percentage_usdc[1])
                amount_usdc = usdc_balance * percentage
                logger.info(f"Using {percentage * 100:.2f}% of balance ({amount_usdc} USDC) for purchase")
            else:
                amount_usdc = random.uniform(BackpackSpotSettings.amount_usdc[0],
                                             BackpackSpotSettings.amount_usdc[1])
                if amount_usdc > usdc_balance:
                    logger.warning(f"Insufficient USDC balance: {usdc_balance}, needed: {amount_usdc}")
                    return False
                logger.info(f"Using fixed amount: {amount_usdc} USDC for purchase")

            result = await backpack.post_limit_order(
                symbol=symbol,
                side='Bid',
                amount_usd=amount_usdc,
                time_in_force=time_in_force
            )

        else:  # SELL (side == 'Ask')
            token_balance = await backpack.get_balances(token)
            logger.info(f"{token} balance: {token_balance}")

            token_decimals = await backpack.get_token_decimals(symbol) or 6
            logger.info(f"{token} decimal precision: {token_decimals}")

            if BackpackSpotSettings.use_percentage_token:
                percentage = random.uniform(BackpackSpotSettings.trade_percentage_token[0],
                                            BackpackSpotSettings.trade_percentage_token[1])

                raw_amount = token_balance * percentage

                precise_amount = Decimal(str(raw_amount)).quantize(
                    Decimal('0.' + '0' * token_decimals),
                    rounding=ROUND_DOWN
                )

                amount_token = float(precise_amount)

                logger.info(
                    f"Selling {percentage * 100:.2f}% of balance ({raw_amount} →"
                    f" {amount_token} {token}, rounded to {token_decimals} decimals)")
            else:
                amount_token = random.uniform(BackpackSpotSettings.amount_token[0],
                                              BackpackSpotSettings.amount_token[1])
                if amount_token > token_balance:
                    logger.warning(f"Insufficient {token} balance: {token_balance}, needed: {amount_token}")
                    return False

                precise_amount = Decimal(str(amount_token)).quantize(
                    Decimal('0.' + '0' * token_decimals),
                    rounding=ROUND_DOWN
                )

                amount_token = float(precise_amount)

                logger.info(f"Selling fixed amount: {amount_token} {token} (rounded to {token_decimals} decimals)")

            if amount_token <= 0:
                logger.warning(f"After rounding, amount became zero. Skipping trade.")
                return False

            result = await backpack.post_limit_sell_order(
                symbol=symbol,
                amount_token=amount_token,
                time_in_force=time_in_force
            )

        if result:
            if isinstance(result, dict) and 'status' in result:
                if result['status'] == 'Filled':
                    logger.success(f"Order filled successfully!")
                elif result['status'] == 'New':
                    logger.info(f"Order placed successfully and is now active")
                else:
                    logger.info(f"Order status: {result['status']}")
            else:
                logger.info(f"Order placed, response: {result}")

        return True
    except Exception as ex:
        logger.error(f"Failed to place spot order: {ex}")
        return False


async def process_backpack_futures(route: Route) -> Optional[bool]:
    amount = random.uniform(BackpackFuturesSettings.amount[0], BackpackFuturesSettings.amount[1])
    side = BackpackFuturesSettings.side
    use_percentage = BackpackFuturesSettings.use_percentage
    percentage = random.uniform(BackpackFuturesSettings.trade_percentage[0],
                                BackpackFuturesSettings.trade_percentage[1])
    leverage = BackpackFuturesSettings.leverage
    symbol = random.choice(BackpackFuturesSettings.symbol) + '_USDC_PERP'

    backpack = BackpackAccount(
        proxy=route.wallet.proxy,
        api_key=route.wallet.private_key
    )

    usdc_balance = await backpack.get_balances("USDC")
    amount_usd = amount * leverage
    if use_percentage:
        amount_usd = usdc_balance * percentage * leverage
        logger.info(
            f"Using {percentage * 100}% of balance ({usdc_balance * percentage} USDC) with {leverage}x leverage")
    else:
        if amount > usdc_balance:
            logger.warning(f"Insufficient USDC balance: {usdc_balance}, needed: {amount}")
            return False

    try:
        await backpack.open_futures_pos(
            symbol=symbol,
            side=side,
            amount_usd=amount_usd
        )
        logger.info(
            f"Opened {side} position on {BackpackFuturesSettings.symbol} "
            f"with {amount_usd} USDC (leverage: {leverage}x)"
        )
        return True
    except Exception as ex:
        logger.error(f"Failed to open position: {ex}")
        return False


async def process_random_swaps(route: Route) -> Optional[bool]:
    backpack = BackpackAccount(
        proxy=route.wallet.proxy,
        api_key=route.wallet.private_key
    )

    num_swaps = random.randint(
        RandomSpotSwapsSettings.num_of_swaps[0],
        RandomSpotSwapsSettings.num_of_swaps[1]
    )

    logger.info(f"Starting {num_swaps} random token purchases")

    successful_swaps = 0
    time_in_force: Literal['IOC', 'FOK', 'GTC'] = 'GTC'

    try:
        for i in range(num_swaps):
            try:
                usdc_balance = await backpack.get_balances("USDC")
                if usdc_balance <= 0.2:
                    logger.warning("Insufficient USDC balance for further purchases")
                    break

                symbol = random.choice(RandomSpotSwapsSettings.symbols) + '_USDC'

                percentage = random.uniform(
                    RandomSpotSwapsSettings.swap_percentage[0],
                    RandomSpotSwapsSettings.swap_percentage[1]
                )

                amount_usdc = usdc_balance * percentage

                logger.info(
                    f"Purchase {i + 1}/{num_swaps}: {symbol} for {amount_usdc:.4f}"
                    f" USDC ({percentage * 100:.2f}% of current USDC balance)")

                try:
                    result = await backpack.post_limit_order(
                        symbol=symbol,
                        side='Bid',
                        amount_usd=amount_usdc,
                        time_in_force=time_in_force
                    )

                    if 'status' in result and (result['status'] == 'Filled' or result['status'] == 'New'):
                        logger.success(f"Buy order for {symbol} successfully placed: {result['status']}")
                        successful_swaps += 1
                    else:
                        logger.warning(f"Unexpected response when placing buy order: {result}")
                except Exception as ex:
                    logger.error(f"Failed to place buy order for {symbol}: {ex}")

            except Exception as ex:
                logger.error(f"Error during purchase {i + 1}: {ex}")

            time_to_sleep = random.randint(PAUSE_BETWEEN_MODULES[0], PAUSE_BETWEEN_MODULES[1])
            logger.info(f'Sleeping {time_to_sleep} seconds...')
            await sleep(time_to_sleep)

        logger.info(f"Completed {successful_swaps} successful purchases out of {num_swaps} attempts")
        return successful_swaps > 0

    except Exception as ex:
        logger.error(f"Error in process_random_swaps: {ex}")
        return False


async def process_swap_all_to_usdc(route: Route) -> Optional[bool]:
    backpack = BackpackAccount(
        proxy=route.wallet.proxy,
        api_key=route.wallet.private_key
    )

    logger.info("Starting conversion of all tokens to USDC")
    time_in_force: Literal['IOC', 'FOK', 'GTC'] = 'GTC'

    try:
        all_balances = await backpack.get_balances()

        if not all_balances:
            logger.info("No balances found or failed to get balance information")
            return False

        any_success = False

        for token, balance_info in all_balances.items():
            if token in ["USDC"]:
                continue

            token_balance = float(balance_info['available'])
            if token_balance <= 0:
                continue

            trading_pair = f"{token}_USDC"

            try:
                token_price = await backpack.get_token_price(trading_pair)
                token_decimals = await backpack.get_token_decimals(trading_pair) or 6
                usdc_value = token_balance * float(token_price)

                logger.info(
                    f"Balance {token}: {token_balance}, Value in USDC: ~{usdc_value:.4f}, Precision: {token_decimals}")

                precise_balance = Decimal(str(token_balance)).quantize(
                    Decimal('0.' + '0' * token_decimals),
                    rounding=ROUND_DOWN
                )

                amount_to_swap = float(precise_balance)

                if amount_to_swap <= 0:
                    logger.warning(
                        f"After rounding to {token_decimals} decimals, {token} balance became zero, skipping")
                    continue

                logger.info(
                    f"Attempting to convert {amount_to_swap} {token} (rounded according to precision {token_decimals})")

                try:
                    result = await backpack.post_limit_sell_order(
                        symbol=trading_pair,
                        amount_token=amount_to_swap,
                        time_in_force=time_in_force
                    )

                    if 'status' in result and (result['status'] == 'Filled' or result['status'] == 'New'):
                        logger.success(f"Order for {token} successfully placed: {result['status']}")
                        any_success = True
                    else:
                        logger.warning(f"Unexpected response when placing order for {token}: {result}")
                except Exception as ex:
                    logger.warning(f"Failed to place order for {token}: {ex}")

            except Exception as ex:
                logger.error(f"Error processing {token}: {ex}")

            time_to_sleep = random.randint(PAUSE_BETWEEN_MODULES[0], PAUSE_BETWEEN_MODULES[1])
            logger.info(f'Sleeping {time_to_sleep} seconds...')
            await sleep(time_to_sleep)

        return any_success

    except Exception as ex:
        logger.error(f"Error in process_swap_all_to_usdc: {ex}")
        return False


async def process_close_all_positions(route: Route) -> Optional[bool]:
    backpack = BackpackAccount(
        proxy=route.wallet.proxy,
        api_key=route.wallet.private_key
    )

    logger.info(f"Closing all positions for account")

    await backpack.check_all_positions()

    result = await backpack.close_all_positions()

    if result == 1:
        logger.success(f"Successfully closed all positions")
        return True
    else:
        logger.info(f"No positions to close or closing failed")
        return False


async def process_get_usdc_symbols(route: Route) -> Optional[bool]:
    backpack = BackpackAccount(
        proxy=route.wallet.proxy,
        api_key=route.wallet.private_key
    )
    spot, futures = await backpack.get_usdc_symbols()
    print(spot)
    print('\n', futures)
    if spot:
        return True


async def process_multiple_deposit_addresses(api_keys: List[str], proxies: Optional[List[str]] = None) -> Dict[
    str, str]:
    with open('deposit_addresses.txt', 'w') as file:
        file.write("# API Key : Deposit Address\n")

    logger.info(f"Processing {len(api_keys)} API keys to get deposit addresses")

    results = {}

    proxy_index = 0
    for i, api_key in enumerate(api_keys):
        try:
            with open('wallets.txt', 'r') as file:
                file_private_keys = [line.strip() for line in file]

            key_index = file_private_keys.index(api_key)

            proxy = proxies[key_index]
            proxy_index = (proxy_index + 1) % len(proxies)

            change_link = ''

            if proxy:
                if MOBILE_PROXY:
                    proxy_url, change_link = proxy.split('|')
                else:
                    proxy_url = proxy

                proxy = Proxy(proxy_url=proxy_url, change_link=change_link)

            backpack = BackpackAccount(
                proxy=proxy,
                api_key=api_key
            )

            address = await backpack.get_deposit_address(chain='Solana')
            shortened_key = api_key[:6] + '...' + api_key[-4:]
            logger.success(f"[{i + 1}/{len(api_keys)}] Retrieved Solana deposit address for {shortened_key}: {address}")

            results[api_key] = address

            with open('deposit_addresses.txt', 'a') as file:
                file.write(f"{api_key}:{address}\n")

            if i < len(api_keys) - 1:
                time_to_pause = random.randint(PAUSE_BETWEEN_MODULES[0], PAUSE_BETWEEN_MODULES[1])
                logger.info(f'Sleeping {time_to_pause} seconds before next wallet...')
                await sleep(time_to_pause)

        except Exception as ex:
            logger.error(f"[{i + 1}/{len(api_keys)}] Failed to get deposit address for key {api_key[:6]}...: {ex}")

    logger.info(f"Successfully retrieved {len(results)} deposit addresses out of {len(api_keys)}")
    return results


async def process_cex_withdraw(route: Route) -> Optional[bool]:
    backpack = BackpackAccount(
        proxy=route.wallet.proxy,
        api_key=route.wallet.private_key
    )

    address = await backpack.get_deposit_address(chain='Solana')

    chain = OKXWithdrawSettings.chain
    token = OKXWithdrawSettings.token
    amount = OKXWithdrawSettings.amount

    okx_config = OKXConfig(
        deposit_settings=None,
        withdraw_settings=WithdrawSettings(
            token=token,
            chain=chain,
            to_address=str(address),
            amount=amount
        ),
        API_KEY=OKXSettings.API_KEY,
        API_SECRET=OKXSettings.API_SECRET,
        PASSPHRASE=OKXSettings.API_PASSWORD,
        PROXY=OKXSettings.PROXY
    )

    config = CEXConfig(
        okx_config=okx_config,
    )
    cex = OKX(
        config=config,
        private_key=route.wallet.private_key,
        proxy=OKXSettings.PROXY
    )

    logger.debug(cex)
    withdrawn = await cex.okx_withdraw()

    if withdrawn is True:
        return True


async def process_cex_deposit(route: Route) -> Optional[bool]:
    keep_balance = OKXDepositSettings.keep_balance
    token = OKXDepositSettings.token
    chain = OKXDepositSettings.chain
    okx_config = OKXConfig(
        deposit_settings=DepositSettings(
            token=token,
            chain=chain,
            to_address=route.wallet.recipient,
            keep_balance=keep_balance
        ),
        withdraw_settings=None,
        API_KEY=OKXSettings.API_KEY,
        API_SECRET=OKXSettings.API_SECRET,
        PASSPHRASE=OKXSettings.API_PASSWORD,
        PROXY=OKXSettings.PROXY
    )

    config = CEXConfig(
        okx_config=okx_config
    )
    cex = OKX(
        config=config,
        private_key=route.wallet.private_key,
        proxy=route.wallet.proxy
    )

    logger.debug(cex)
    deposited = await cex.deposit()

    if deposited:
        return True


def create_delta_neutral_strategy(balances):
    accounts = list(balances.keys())
    all_positions = []
    used_accounts = set()
    MAX_LEVERAGE = 5.0

    total_accounts = len(accounts)
    min_accounts_per_pair = 3
    max_accounts_per_pair = 6
    avg_accounts_per_pair = 5
    num_pairs = total_accounts // avg_accounts_per_pair
    if total_accounts >= min_accounts_per_pair and num_pairs == 0:
        num_pairs = 1

    for _ in range(num_pairs):
        symbol = f"{random.choice(BackpackFuturesSettings.symbol)}_USDC_PERP"
        remaining_accounts = [acc for acc in accounts if acc not in used_accounts]
        if len(remaining_accounts) < min_accounts_per_pair:
            break

        long_account = random.choice(remaining_accounts)
        used_accounts.add(long_account)

        long_base_size = round(balances[long_account] * random.uniform(0.65, 0.75))
        if long_base_size > balances[long_account] * 0.75:
            long_base_size = round(balances[long_account] * 0.75)
        long_leverage = random.randint(2, 5)
        long_position_size = round(long_base_size * long_leverage, 2)

        remaining_after_long = [acc for acc in remaining_accounts if acc != long_account]
        max_short_accounts = min(5, len(remaining_after_long))
        min_short_accounts = 2
        num_short_accounts = random.randint(min_short_accounts, min(max_short_accounts, max_accounts_per_pair - 1))

        short_accounts = random.sample(remaining_after_long, num_short_accounts)
        used_accounts.update(short_accounts)

        total_available_short = sum(balances[acc] for acc in short_accounts)
        short_positions = []

        for acc in short_accounts:
            proportion = balances[acc] / total_available_short
            target_total_size = round(long_position_size * proportion, 2)

            leverage = min(MAX_LEVERAGE, max(2, random.uniform(2, 3)))
            base_size = round(target_total_size / leverage, 2)

            if base_size > balances[acc]:
                base_size = round(balances[acc], 2)
                target_total_size = round(base_size * leverage, 2)

            short_positions.append({
                "symbol": symbol,
                "account": acc,
                "direction": "short",
                "base_size": base_size,
                "leverage": round(leverage, 2),
                "total_size": target_total_size
            })

        total_short_size = sum(pos["total_size"] for pos in short_positions)
        correction_factor = long_position_size / total_short_size if total_short_size > 0 else 1

        used_total_sizes = set()
        for pos in short_positions:
            pos["total_size"] = round(pos["total_size"] * correction_factor, 2)
            pos["base_size"] = round(pos["total_size"] / pos["leverage"], 2)

            if pos["base_size"] > balances[pos["account"]]:
                pos["base_size"] = round(balances[pos["account"]], 2)
                pos["leverage"] = round(pos["total_size"] / pos["base_size"], 2)
                if pos["leverage"] > MAX_LEVERAGE:
                    pos["leverage"] = MAX_LEVERAGE
                pos["total_size"] = round(pos["base_size"] * pos["leverage"], 2)

            while pos["total_size"] in used_total_sizes:
                deviation = random.uniform(-0.5, 0.5)
                pos["total_size"] = round(pos["total_size"] + deviation, 2)
                pos["base_size"] = round(pos["total_size"] / pos["leverage"], 2)
                if pos["base_size"] > balances[pos["account"]]:
                    pos["base_size"] = round(balances[pos["account"]], 2)
                    pos["total_size"] = round(pos["base_size"] * pos["leverage"], 2)
            used_total_sizes.add(pos["total_size"])

        all_positions.append({
            "symbol": symbol,
            "account": long_account,
            "direction": "long",
            "base_size": long_base_size,
            "leverage": long_leverage,
            "total_size": long_position_size
        })
        all_positions.extend(short_positions)

    return all_positions


async def process_forks_database_creation(keys: list[str], proxies: list[str]):
    balance_mapping = {}

    db_utils = DataBaseUtils(
        manager_config=DataBaseManagerConfig(
            action='forks_mode'
        )
    )

    proxy_index = 0
    for api_key in keys:
        with open('wallets.txt', 'r') as file:
            file_private_keys = [line.strip() for line in file]

        key_index = file_private_keys.index(api_key)

        proxy = proxies[key_index]
        proxy_index = (proxy_index + 1) % len(proxies)

        change_link = ''

        proxy = None
        if proxy:
            if MOBILE_PROXY:
                proxy_url, change_link = proxy.split('|')
            else:
                proxy_url = proxy

            proxy = Proxy(proxy_url=proxy_url, change_link=change_link)

        backpack = BackpackAccount(
            proxy=proxy,
            api_key=api_key
        )

        balance = await backpack.get_balances("USDC")
        balance_mapping.update({api_key: balance})

    result = create_delta_neutral_strategy(balance_mapping)

    symbol_totals = {}

    forks_by_symbol = {}
    for position in result:
        symbol = position['symbol']
        if symbol not in forks_by_symbol:
            forks_by_symbol[symbol] = {'accounts': [], 'long': [], 'short': []}

        if position['account'] not in forks_by_symbol[symbol]['accounts']:
            forks_by_symbol[symbol]['accounts'].append(position['account'])

        pos_data = {
            'account': position['account'],
            'base_size': position['base_size'],
            'leverage': position['leverage'],
            'total_size': position['total_size']
        }
        if position['direction'] == 'long':
            forks_by_symbol[symbol]['long'].append(pos_data)
        else:
            forks_by_symbol[symbol]['short'].append(pos_data)

    await db_utils.fill_forks_table(forks_by_symbol)

    for pos in result:
        if pos['symbol'] not in symbol_totals:
            symbol_totals[pos['symbol']] = {"long": 0, "short": 0}
        if pos['direction'] == "long":
            symbol_totals[pos['symbol']]["long"] += pos['total_size']
        else:
            symbol_totals[pos['symbol']]["short"] += pos['total_size']

    for symbol, totals in symbol_totals.items():
        print(f"\nСимвол: {symbol}")
        print(f"Итоговый размер лонг: ${round(totals['long'], 2)}")
        print(f"Итоговый размер шорт: ${round(totals['short'], 2)}")
        print(f"Дельта: ${round(totals['long'] - totals['short'], 2)}")


async def process_fork(task: Forks, proxies: list[str]) -> bool:
    symbol = task.symbol
    forks = task.forks

    all_positions = []

    for pos in forks['long']:
        pos_with_type = pos.copy()
        pos_with_type['type'] = 'Bid'
        all_positions.append(pos_with_type)

    for pos in forks['short']:
        pos_with_type = pos.copy()
        pos_with_type['type'] = 'Ask'
        all_positions.append(pos_with_type)

    random.shuffle(all_positions)

    proxy_index = 0
    for position in all_positions:
        with open('wallets.txt', 'r') as file:
            file_private_keys = [line.strip() for line in file]

        key_index = file_private_keys.index(position['account'])

        proxy = proxies[key_index]
        proxy_index = (proxy_index + 1) % len(proxies)

        change_link = ''

        if proxy:
            if MOBILE_PROXY:
                proxy_url, change_link = proxy.split('|')
            else:
                proxy_url = proxy

            proxy = Proxy(proxy_url=proxy_url, change_link=change_link)

        try:
            backpack = BackpackAccount(
                proxy=proxy,
                api_key=position['account']
            )

            await backpack.open_futures_pos(
                symbol=symbol,
                side=position['type'],
                amount_usd=position['total_size']
            )
            logger.info(
                f"Opened {position['type']} position on {BackpackFuturesSettings.symbol} "
                f"with {position['total_size']} USDC (leverage: {position['leverage']}x)"
            )
        except Exception as ex:
            logger.error(f"Failed to open position: {ex}")

        time_to_sleep = random.randint(PAUSE_BETWEEN_MODULES[0], PAUSE_BETWEEN_MODULES[1])
        logger.info(f'Sleeping {time_to_sleep} seconds...')
        await sleep(time_to_sleep)

    return True
