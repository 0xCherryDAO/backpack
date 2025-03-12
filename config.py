MOBILE_PROXY = False  # True - мобильные proxy/False - обычные proxy
ROTATE_IP = False  # Настройка только для мобильных proxy

TG_BOT_TOKEN = ''  # str ('2282282282:AAZYB35L2PoziKsri6RFPOASdkal-z1Wi_s')
TG_USER_ID = None  # int (22822822) or None

SHUFFLE_WALLETS = False
PAUSE_BETWEEN_WALLETS = [1, 5]
PAUSE_BETWEEN_MODULES = [15, 20]
RETRIES = 3  # Сколько раз повторять 'зафейленное' действие
PAUSE_BETWEEN_RETRIES = 15  # Пауза между повторами

# -------------------------------------------------------------------------

# --- CEXs --- #
OKX_WITHDRAW = False  # Вывод с ОКХ на кошельки
OKX_DEPOSIT = False  # Вывод с кошельков на ОКХ

# ====== BackPack ====== #
# ====== AUTOMATIC TRADING OPTIONS ======
RANDOM_SWAPS = False  # Свапы USDC в токены из списка в RandomSpotSwapsSettings

CLOSE_ALL = False  # Закрытие всех фьюче-позиций
SWAP_ALL_TO_USDC = False  # Свап всех токенов в USDC

# ====== MANUAL TRADING OPTIONS ======
# Опциональные режимы для единоразовых торговых операций (выполняются только один раз для каждого кошелька)
BACKPACK_SPOT = False  # Одиночная операция (покупка/продажа) конкретного токена по настройкам из BackpackSpotSettings
BACKPACK_FUTURES = False  # Одиночное открытие фьючерсной позиции по настройкам из BackpackFuturesSettings


# --- Backpack settings --- #
class RandomSpotSwapsSettings:
    symbols = ['SOL', 'ETH', 'PYTH', 'JTO', 'LINK', 'USDT', 'UNI']
    num_of_swaps = [3, 4]
    swap_percentage = [0.1, 0.2]  # 0.1 - 10% | 0.23 - 23%


class BackpackSpotSettings:
    symbol = ['SOL']  # Тикер для спот-торговли, формат: "ТИКЕР_USDC"
    side = 'Ask'  # 'Bid' - покупка / 'Ask' - продажа

    # Для покупки (Bid) - указываем сумму в USDC
    amount_usdc = [10, 15]  # Используется когда side = 'Bid' (диапазон USDC для покупки)
    use_percentage_usdc = True  # Использовать процент от баланса USDC вместо фиксированной суммы
    trade_percentage_usdc = [0.1, 0.15]  # Процент от баланса для торговли, если use_percentage_usdc=True

    # Для продажи (Ask) - указываем количество токенов
    amount_token = [0.1, 0.2]  # Используется когда side = 'Ask' (диапазон количества токенов для продажи)
    use_percentage_token = True  # Использовать процент от баланса токена
    trade_percentage_token = [0.8, 0.8]  # Процент от баланса токена для продажи


class BackpackFuturesSettings:
    symbol = ['SOL']  # Тикер, который торгуем, указывать первым -> "ТИКЕР_USDC_PERP",
    amount = [5, 10]  # Количество USDC, которые будут умножены на leverage
    side = 'Ask'  # side 'Ask' - шорт / 'Bid' - лонг
    leverage = 2  # Плечо
    use_percentage = False  # Использовать процент от баланса USDC вместо фиксированной суммы
    trade_percentage = [0.1, 0.2]  # Проценты от баланса USDC, которые будут умножены на leverage


# --- CEXs --- #
class OKXWithdrawSettings:  # Вывод с ОКХ на кошельки
    chain = ['Solana']  # 'Base' / 'Optimism' / 'Arbitrum One'
    token = 'USDC'
    amount = [5, 10]  # (учитывайте минималку 1.01 USDC)

    min_usdc_balance = 25  # Если в chain уже есть больше min_usdc_balance, то вывода не будет.


class OKXDepositSettings:  # Вывод с кошельков на ОКХ. Выводит весь баланс с учетом keep_balance
    chain = 'Solana'  # 'Base' / 'Optimism' / 'Arbitrum One'
    token = 'USDC'

    keep_balance = [30, 30]  # Какой баланс оставить на кошельках


class OKXSettings:
    API_KEY = ''
    API_SECRET = ''
    API_PASSWORD = ''

    PROXY = None  # 'http://login:pass@ip:port' (если нужно)


GET_TICKERS = False  # Получить все существующие тикеры в терминал

SPOT_MARKETS = [
    'SOL_USDC', 'PYTH_USDC', 'JTO_USDC', 'HNT_USDC', 'MOBILE_USDC', 'BONK_USDC', 'WIF_USDC', 'USDT_USDC',
    'JUP_USDC', 'RENDER_USDC', 'WEN_USDC', 'BTC_USDC', 'W_USDC', 'TNSR_USDC', 'PRCL_USDC', 'MEW_USDC',
    'BOME_USDC', 'RAY_USDC', 'HONEY_USDC', 'KMNO_USDC', 'ETH_USDC', 'DRIFT_USDC', 'SHFL_USDC', 'NYAN_USDC',
    'PEPE_USDC', 'SHIB_USDC', 'LINK_USDC', 'UNI_USDC', 'ONDO_USDC', 'MATIC_USDC', 'STRK_USDC', 'BLUR_USDC',
    'WLD_USDC', 'GALA_USDC', 'HLG_USDC', 'MON_USDC', 'MANEKI_USDC', 'BODEN_USDC', 'ZKJ_USDC', 'HABIBI_USDC',
    'IO_USDC', 'UNA_USDC', 'ZRO_USDC', 'ZEX_USDC', 'MOTHER_USDC', 'LDO_USDC', 'AAVE_USDC', 'ME_USDC', 'MAX_USDC',
    'POL_USDC', 'TRUMPWIN_USDC', 'HARRISWIN_USDC', 'MOODENG_USDC', 'DBR_USDC', 'ACT_USDC', 'GOAT_USDC', 'APE_USDC',
    'ENA_USDC', 'ME_USDC', 'PENGU_USDC', 'CHILLGUY_USDC',
]

PERP_MARKETS = [
    'SOL_USDC_PERP', 'BTC_USDC_PERP', 'ETH_USDC_PERP', 'XRP_USDC_PERP', 'SUI_USDC_PERP', 'DOGE_USDC_PERP',
    'JUP_USDC_PERP', 'TRUMP_USDC_PERP', 'WIF_USDC_PERP', 'BERA_USDC_PERP', 'LTC_USDC_PERP', 'ADA_USDC_PERP',
    'LINK_USDC_PERP', 'IP_USDC_PERP', 'HYPE_USDC_PERP', 'BNB_USDC_PERP', 'AVAX_USDC_PERP', 'S_USDC_PERP'
]
