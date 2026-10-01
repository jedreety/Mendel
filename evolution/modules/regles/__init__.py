"""Les regles du moteur (modules/rules/), portees en modules de signal du bot.

Un module par fichier, du nom de la regle. Le signal d'une regle est le sens de son vote fois son intensite, 0 quand
elle s'abstient ; ses parametres sont des genes. Les regles qui votent toujours 0 (doji, toupie, barre interieure)
donnent la presence de leur motif, et celles qui votent un sens fixe (heure, jour) donnent 1 quand elles votent :
le reseau en apprend le poids et le signe. Inverted, qui ne fait qu'inverser un vote, n'a pas lieu d'etre ici.

L'ordre est celui des familles de input/catalog.py, et fixe la place des genes dans le genome.
"""
from evolution.modules.regles import (
    adx, aroon, autocorrelation, balance_of_power, bollinger_bands, candle_color, candle_streak, cci,
    chaikin_money_flow, dark_cloud_cover, day_of_month, day_of_week, directional_movement, doji, donchian_breakout,
    dragonfly_doji, ease_of_movement, efficiency_ratio, engulfing, evening_star, exponential_moving_average,
    exponential_moving_average_cross, force_index, fractal_breakout, gravestone_doji, hammer, hanging_man, harami,
    heikin_ashi, hour_of_day, ichimoku_cloud, inside_bar, internal_bar_strength, inverted_hammer, keltner_channel,
    linear_regression_slope, macd, market_structure, marubozu, momentum, money_flow_index, morning_star,
    moving_average, moving_average_cross, narrow_range, on_balance_volume, opening_range_breakout, outside_bar,
    parabolic_sar, piercing_line, pivot_point, previous_day_range, rsi, session_move, session_open, shooting_star,
    spinning_top, squeeze, stochastic, stochastic_rsi, supertrend, three_black_crows, three_inside, three_methods,
    three_outside, three_white_soldiers, tweezer, ultimate_oscillator, volatility_breakout, volume_surge, vortex, vwap,
)

BOUGIES = (candle_color, candle_streak, doji, dragonfly_doji, gravestone_doji, hammer, hanging_man, inverted_hammer,
           shooting_star, marubozu, spinning_top, engulfing, harami, piercing_line, dark_cloud_cover, tweezer,
           inside_bar, outside_bar, morning_star, evening_star, three_white_soldiers, three_black_crows, three_inside,
           three_outside, three_methods, heikin_ashi)
SEANCES = (session_open, session_move, opening_range_breakout, previous_day_range, pivot_point, hour_of_day,
           day_of_week, day_of_month)
TENDANCE = (momentum, moving_average, moving_average_cross, exponential_moving_average,
            exponential_moving_average_cross, macd, linear_regression_slope, directional_movement, adx, vortex, aroon,
            cci, ichimoku_cloud, supertrend, parabolic_sar, efficiency_ratio, autocorrelation, market_structure,
            donchian_breakout, fractal_breakout, narrow_range, squeeze, volatility_breakout)
RETOUR = (rsi, stochastic_rsi, stochastic, ultimate_oscillator, internal_bar_strength, bollinger_bands,
          keltner_channel)
VOLUME = (volume_surge, on_balance_volume, force_index, money_flow_index, chaikin_money_flow, ease_of_movement,
          balance_of_power, vwap)
REGLES = (*BOUGIES, *SEANCES, *TENDANCE, *RETOUR, *VOLUME)
