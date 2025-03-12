from src.utils.runner import *

module_handlers = {
    'OKX_WITHDRAW': process_cex_withdraw,
    'OKX_DEPOSIT': process_cex_deposit,
    'BACKPACK_FUTURES': process_backpack_futures,
    'BACKPACK_SPOT': process_backpack_spot,
    'CLOSE_ALL': process_close_all_positions,
    'SWAP_ALL_TO_USDC': process_swap_all_to_usdc,
    'GET_TICKERS': process_get_usdc_symbols,
    'RANDOM_SWAPS': process_random_swaps,
}
