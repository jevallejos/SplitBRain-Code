# DOSSIER MAESTRO DE INGENIERÍA Y RESUMEN EJECUTIVO CONSOLIDADO — SPLITBRAIN-ARGON V6.4.2 (BASE PARA OMEGA V7.0)

- **Fecha de Compilación Automática (Antigravity IDE)**: `2026-10-16 18:17:32 UTC`
- **Repositorio Oficial**: `https://github.com/jevallejos/SplitBRain-Code.git`
- **Nodo de Producción**: `sniper-tokio` (`asia-northeast1`, GCP) — Bybit V5 Perpetuals USDT (UTA)
- **Pipeline de Despliegue Inmutable**: `Google Antigravity IDE (D:\dev\SplitBRain-Code) -> GitHub (origin/main) -> sniper-tokio`
- **Estado de Validación**: `15/15 Pruebas Superadas (test_v6_2_suite.py)` | `100% Nativo (Cero Monkey-Patching)`

---

## 1. RESUMEN EJECUTIVO Y TELEMETRÍA DE PRODUCCIÓN (270 OPERACIONES AUDITADAS)

**SplitBrain-Argon v6.4.2** constituye la versión puente 100% nativa previa a **SplitBrain-Omega v7.0**. Opera bajo una arquitectura asíncrona *Zero-REST* en la ruta crítica y filtrado semántico en memoria RAM de complejidad $O(1)$ (< 90 microsegundos), diseñada para capturar reversiones a la media de alta convicción tras cascadas de liquidación forzada en futuros perpetuos USDT de Bybit.

### 1.1. Métricas Empíricas Verificadas en `sniper-tokio`
- **Fuente de Telemetría Auditada**: `Telemetría Producción sniper-tokio (bot log.txt #270)`
- **Operaciones Totales Registradas**: `270 trades (151 Victorias / 119 Derrotas)`
- **Win Rate Histórico Global Acumulado**: **`55.9%`** (evolución sostenida desde `51.7%` -> `55.9%`)
- **Win Rate Operativo Post-Purga de Drenadores (Trades #235 a #270)**: **`69.4%` (`25 Victorias / 11 Derrotas` en 36 operaciones)**
- **Mejor / Peor Operación Unitaria**: `+0.4369 USDT (+3.35%)` / `-0.2194 USDT`
- **Ahorro en Comisiones de Salida vía `MAKER_UNWIND` (`PostOnly` 0.020% vs. `Market` 0.055%)**: **`-63.6%`** en comisión de salida (`~0.0044 USDT` roundtrip Maker-Maker frente a `~0.0084 USDT` Maker-Taker), manteniendo **100% de Win Rate** en cierres `MAKER_UNWIND` y `TRAILING`.
- **Latencia de Inferencia Semántica en Background (Groq LPU)**: **`205 ms – 309 ms`** vía `qwen/qwen3.8-27b` fuera de la ruta crítica cada `180s`.

### 1.2. Descomposición Cuantitativa: Alfa Microestructural vs. Fricciones Adversariales
1. **Generación de Alfa ($\alpha_{\text{micro}}$)**: Concentrada en el **Núcleo Alfa** (`ZEREBRO`, `WAL`, `STRK`, `INJ`, `XRP`, `1000PEPE`, `HYPE`), donde la absorción pasiva en el `best_bid` (o *Penny-Jump* `+1 tick`) captura la sobrerreacción de liquidaciones inelásticas y descarga el inventario sobre la curva hiperbólica de Almgren-Chriss.
2. **Erradicación de las 5 Fugas de V6.4.0/V6.4.1 en V6.4.2**:
   - **Fuga #1 Corregida (Inversión de Jerarquía SL)**: En `v6.4.0`, `SL_INICIAL_PCT` estaba en `2.50%` y `SL_PCT` en `1.10%`, provocando cierres Taker prematuros (`SL_EXCHANGE`) en `10s-20s`. En **`v6.4.2`**, `SL Interno` opera en **`-1.15%`** (con ventana de gracia de `18s` contra mechazos) y `SL Bybit` se fija en **`-1.65%`** como respaldo catastrófico de servidor.
   - **Fuga #2 Corregida (Reentrada en Cuchillo Cayendo)**: Se integró el escudo nativo `Anti-Knife Continuation (900s)` que prohíbe recomprar un activo durante 15 minutos tras un SL si cotiza en o por debajo del precio de estopeo.
   - **Fuga #3 Corregida (Caída Abrupta de Maker-Unwind a los 60s)**: Se reemplazó el escalón plano de `+0.12%` por la curva hiperbólica continua de Almgren-Chriss (`+0.52%` -> `+0.44%..+0.26%` -> `+0.18%`) más el desarme pasivo `Maker-Scratch` (`85s-105s`).
   - **Fuga #4 Corregida (Solapamiento de 2da Posición)**: Se implementó `cupo_portafolio_disponible()` dentro de `_lock_disparo` para garantizar `MAX_POSICIONES_SIMULTANEAS = 1` en todo el portafolio.
   - **Fuga #5 Corregida (Órdenes No Llenadas y Bloqueo de Clímax)**: Se incorporó `Re-Quote 3.5s PostOnly` en `3_ejecutor_sniper.py` y desbloqueo de clímax en `1.2s` para caídas extremas ($Z \le -4.15, \text{OFI} \ge +0.70$).

---

## 2. ARQUITECTURA DE LOS 8 MÓDULOS DE PRODUCCIÓN + SUITE DE PRUEBAS (INTROSPECCIÓN AST EN VIVO)

| Módulo | Líneas | SHA-256 Actual | Rol Arquitectónico en `SplitBrain-Argon v6.4.2` |
| :--- | :---: | :---: | :--- |
| `config_parametros.py` | 440 | `10b4e3a1ff19` | Configuración Maestra Institucional, Universo Tier-1, Blacklist y Contrato AST (64+ constantes) |
| `main.py` | 375 | `fdcf6baea74f` | Orquestador Central Asíncrono, Cerrojo Físico (.splitbrain.lock), Pre-Calentamiento y Reconciliación |
| `1_radar_volatilidad.py` | 599 | `757fc101ec05` | Radar Microestructural O(1): VentanaZ, Lyapunov 1ra/2da Derivada, Kernel Hawkes 5s, VPIN y Anclaje EMA900 |
| `2_escudo_semantico.py` | 375 | `b1665c40c825` | Escudo Semántico O(1) en RAM, Dinámica Evolutiva del Replicador OOS y Pool Multi-Modelo Groq LPU |
| `3_ejecutor_sniper.py` | 782 | `014a726190fc` | Ejecutor Sniper Zero-REST, Single-Slot Mutex, Re-Quote 3.5s PostOnly y Kelly Dinámico BRB + Target-Sigma |
| `4_telemetria_telegram.py` | 26 | `f2e38e0073b8` | Despachador Asíncrono Fire-and-Forget de Telemetría y Alertas Operativas hacia Telegram |
| `5_gestor_posiciones.py` | 759 | `df4a08874f0e` | PositionManager: Curva Hiperbólica Almgren-Chriss Maker-Unwind, Maker-Scratch 85s y Anti-Zombie 3 Etapas |
| `6_stats_tracker.py` | 334 | `d11a1b88f7b1` | Caja Negra JSONL, Desduplicador Fantasma, Contabilidad MAP/LVR y Calculador Kelly Busseti-Ryu-Boyd |
| `test_v6_2_suite.py` | 529 | `28fa8a1c2fb5` | Suite Determinista de 15 Pruebas de Integridad Sintáctica, Microestructural y de Reconciliación |

### Módulo `config_parametros.py` (SHA-256: `10b4e3a1ff19` | 440 líneas)
- **Responsabilidad**: Configuración Maestra Institucional, Universo Tier-1, Blacklist y Contrato AST (64+ constantes)

### Módulo `main.py` (SHA-256: `fdcf6baea74f` | 375 líneas)
- **Responsabilidad**: Orquestador Central Asíncrono, Cerrojo Físico (.splitbrain.lock), Pre-Calentamiento y Reconciliación
- **Clases Declaradas (AST)**: `_TeeLogger (__init__, _formatear_con_hora, write, flush, isatty, __getattr__)`
- **Funciones y Corutinas Principales (AST)**: `_sello_tiempo(), adquirir_bloqueo_instancia_unica(), liberar_bloqueo_instancia_unica(), _es_perpetuo_cripto_puro(), _es_lote_minimo_viable(), async _inicializar_mercados_con_backoff(), async _auditar_margen_libre(), async main()`

### Módulo `1_radar_volatilidad.py` (SHA-256: `757fc101ec05` | 599 líneas)
- **Responsabilidad**: Radar Microestructural O(1): VentanaZ, Lyapunov 1ra/2da Derivada, Kernel Hawkes 5s, VPIN y Anclaje EMA900
- **Clases Declaradas (AST)**: `VentanaZ (__init__, reset, cambio_relativo, caida_desde_maximo, desviacion_ema_macro, volatilidad_relativa...); MediaMovilTemporal (__init__, push, media, cobertura)`
- **Funciones y Corutinas Principales (AST)**: `registrar_cierre_sl_estructural(), es_glitch(), calcular_ofi(), calcular_spread_relativo(), bloqueo_activo(), registrar_y_verificar_contagio(), _validar_compuertas_v6_4_2(), async cazar_cisne_negro(), async cazar_anomalia_ws()`

### Módulo `2_escudo_semantico.py` (SHA-256: `b1665c40c825` | 375 líneas)
- **Responsabilidad**: Escudo Semántico O(1) en RAM, Dinámica Evolutiva del Replicador OOS y Pool Multi-Modelo Groq LPU
- **Clases Declaradas (AST)**: `CentinelaSemanticoRAM (__init__, inicializar_universo, actualizar_telemetria, esta_aprobado, evaluar_dinamica_replicador_oos, _filtro_heuristico_respaldo...)`
- **Funciones y Corutinas Principales (AST)**: `_extraer_json_robusto(), async evaluar_anomalia_groq()`

### Módulo `3_ejecutor_sniper.py` (SHA-256: `014a726190fc` | 782 líneas)
- **Responsabilidad**: Ejecutor Sniper Zero-REST, Single-Slot Mutex, Re-Quote 3.5s PostOnly y Kelly Dinámico BRB + Target-Sigma
- **Funciones y Corutinas Principales (AST)**: `_lanzar_bg(), enviar_alerta_bg(), async sincronizar_saldo_ram(), disparar_sincronizacion_saldo_bg(), async bucle_keepalive_socket(), async precalentar_apalancamiento_universo(), posicion_activa(), total_posiciones_activas(), cupo_portafolio_disponible(), en_cooldown_post_cierre(), _d(), cuantizar_orden(), _es_error_blacklist(), async _fijar_apalancamiento(), _extraer_precio_maker_ws(), _obtener_sl_bybit_pct(), _calcular_kelly_operativo(), async ejecutar_orden_sniper()`

### Módulo `4_telemetria_telegram.py` (SHA-256: `f2e38e0073b8` | 26 líneas)
- **Responsabilidad**: Despachador Asíncrono Fire-and-Forget de Telemetría y Alertas Operativas hacia Telegram
- **Funciones y Corutinas Principales (AST)**: `async enviar_alerta()`

### Módulo `5_gestor_posiciones.py` (SHA-256: `df4a08874f0e` | 759 líneas)
- **Responsabilidad**: PositionManager: Curva Hiperbólica Almgren-Chriss Maker-Unwind, Maker-Scratch 85s y Anti-Zombie 3 Etapas
- **Clases Declaradas (AST)**: `Posicion (); PositionManager (__init__, tiene, registrar_cooldown_post_cierre, en_cooldown, segundos_cooldown_restantes, calcular_objetivo_sl_exchange...)`
- **Funciones y Corutinas Principales (AST)**: `calcular_ofi(), calcular_umbral_maker_almgren_chriss(), _obtener_jerarquia_sl_pct()`

### Módulo `6_stats_tracker.py` (SHA-256: `d11a1b88f7b1` | 334 líneas)
- **Responsabilidad**: Caja Negra JSONL, Desduplicador Fantasma, Contabilidad MAP/LVR y Calculador Kelly Busseti-Ryu-Boyd
- **Clases Declaradas (AST)**: `StatsTracker (__init__, cargar, sincronizar_capital_base_con_real, _append, registrar, calcular_kelly_dinamico...)`
- **Funciones y Corutinas Principales (AST)**: `calcular_pnl(), estimar_lvr_operacion(), _parse_ts_epoch(), _es_duplicado_fantasma(), async leer_balance_real(), async bucle_dashboard()`

### Módulo `test_v6_2_suite.py` (SHA-256: `28fa8a1c2fb5` | 529 líneas)
- **Responsabilidad**: Suite Determinista de 15 Pruebas de Integridad Sintáctica, Microestructural y de Reconciliación
- **Clases Declaradas (AST)**: `_MockExchangeHuerfanas (__init__, fetch_positions, amount_to_precision, price_to_precision, create_order, cancel_order...); _MockExchangeZeroRest (__init__, load_markets, fetch_ticker, set_leverage, fetch_balance, market...)`
- **Funciones y Corutinas Principales (AST)**: `_extraer_atributos_cfg_ast(), async ejecutar_auditoria_v6_4_0()`

---

## 3. FORMULACIÓN MATEMÁTICA NATIVA DE `SPLITBRAIN-ARGON V6.4.2`

### 3.1. Z-Score Rodante O(1), Primera/Segunda Derivada de Lyapunov y VPIN
- **Estadístico Z con Piso Relativo**: $Z_t = \frac{P_t - \mu_{60}}{\max(\sigma_{60}, P_t \cdot \sigma_{\min}, \text{STD\_MIN})}$
- **Velocidad, Aceleración y Jerk en el Campo Potencial de Lyapunov**:
  $$r_t = \ln(P_t / P_{t-1}), \qquad a_t = r_t - r_{t-1}, \qquad \Delta a_t = a_t - a_{t-1}$$
  Se bloquea el disparo si $a_t < -0.00025$ o si $a_t < 0 \wedge \Delta a_t < -0.00015$ (salvo absorción extrema $\text{OFI}_t \ge +0.85$).

### 3.2. Integrador Recursivo del Proceso Puntual de Hawkes (Memoria 5s + Desbloqueo Clímax 1.2s)
- **Kernel Exponencial O(1)**: $I_{\text{Hawkes}}(t) = I_{\text{Hawkes}}(t-1) \cdot e^{-\beta \Delta t} + \text{OFI}_t$ con $\beta = 0.45$.
- **Enfriamiento Adaptativo Post-Pulso Tóxico**: $\tau_{\text{cool}} = 1.2\text{ s}$ si $(Z_t \le -4.15 \wedge \text{OFI}_t \ge +0.70 \wedge \Delta_{\text{EMA900}} \le -0.40\%)$, o $3.2\text{ s}$ en régimen estándar.

### 3.3. Curva Hiperbólica de Almgren-Chriss / Avellaneda-Stoikov y `Maker-Scratch` (85s–105s)
- **Umbral Dinámico de Ganancia Bruta para `MAKER_UNWIND`**:
  $$\Pi_{\text{Maker}}^*(t) = \Pi_{\text{fin}} + (\Pi_{\text{ini}} - \Pi_{\text{fin}}) \frac{\sinh\left(\kappa \frac{180 - t}{120}\right)}{\sinh(\kappa)}, \quad t \in (60, 180]\text{ s}$$
  con $\Pi_{\text{ini}} = +0.52\%$, $\Pi_{\text{fin}} = +0.18\%$ y $\kappa = 2.10$.
- **Ventana `Maker-Scratch` (Guéant, Lehalle & Fernandez-Tapia, 85s a 105s)**: Si la posición no ha activado Break-Even y se encuentra entre $-0.22\% \le \text{PnL} < \Pi_{\text{Maker}}^*(t)$ con $\text{OFI} \le +0.08$, cotiza salida pasiva `PostOnly` en `best_ask` (`0.020%` fee) antes del corte Taker de los `105s`.

### 3.4. Criterio de Kelly con Restricción Convexa de Drawdown (Busseti, Ryu & Boyd) y Target-Sigma
- **Modulación por Drawdown ($DD_t$) y Volatilidad Realizada ($\sigma_{60}$)**:
  $$f_{\text{final}} = \text{clip}\left( f_{\text{BRB}}(DD_t, p_{12}) \cdot \sqrt{\frac{\sigma^*}{\max(\sigma_{60}, 0.0008)}} \cdot \eta_{\text{Tier}}, \; 0.25, \; 0.42 \right)$$
  sujeto a la cota inferior de margen operativo $\text{SaldoLibre} \times f_{\text{final}} \ge 2.25\text{ USDT}$.

---

## 4. CONTRATO SINTÁCTICO AST VERIFICADO EN `config_parametros.py` (238 CONSTANTES ACTIVAS)

| # | Constante AST | Valor Actual en Producción (`v6.4.2`) |
| :---: | :--- | :--- |
| 1 | `ALMGREN_CHRISS_KAPPA` | `2.1` |
| 2 | `ANTI_REENTRADA_BAJO_SL_SEG` | `900.0` |
| 3 | `APALANCAMIENTO` | `3` |
| 4 | `API_KEY` | `BYBIT_API_KEY` |
| 5 | `API_SECRET` | `BYBIT_API_SECRET` |
| 6 | `ARCHIVO_LOCK` | `LOCK_FILE` |
| 7 | `ARCHIVO_LOG` | `LOG_FILE` |
| 8 | `ARCHIVO_STATS` | `STATS_FILE` |
| 9 | `BE_ACTIVACION` | `BREAK_EVEN_ACTIVACION_PCT` |
| 10 | `BE_ACTIVACION_PCT` | `BREAK_EVEN_ACTIVACION_PCT` |
| 11 | `BE_OFFSET` | `BREAK_EVEN_OFFSET_PCT` |
| 12 | `BE_OFFSET_PCT` | `BREAK_EVEN_OFFSET_PCT` |
| 13 | `BE_PISO_EXCHANGE_PCT` | `0.001` |
| 14 | `BLACKLIST_PAIRS` | `{'LUNA/USDT:USDT', 'LUNC/USDT:USDT', 'USTC/USDT:USDT', 'FTT/US...` |
| 15 | `BLACKLIST_TTL_SEG` | `DURACION_BLACKLIST_DINAMICA_SEG` |
| 16 | `BLOQUEO_BTC_SEG` | `300` |
| 17 | `BREAK_EVEN_ACTIVACION_PCT` | `0.0045` |
| 18 | `BREAK_EVEN_OFFSET_PCT` | `0.0016` |
| 19 | `BREAK_EVEN_PLUS_PCT` | `BREAK_EVEN_OFFSET_PCT` |
| 20 | `BREAK_EVEN_TRIGGER_PCT` | `BREAK_EVEN_ACTIVACION_PCT` |
| 21 | `BYBIT_API_KEY` | `os.getenv('BYBIT_API_KEY', '')` |
| 22 | `BYBIT_API_SECRET` | `os.getenv('BYBIT_API_SECRET', '')` |
| 23 | `BYBIT_BE_FLOOR_PCT` | `BYBIT_BE_PISO_MIN_PCT` |
| 24 | `BYBIT_BE_PISO_MIN_PCT` | `0.0012` |
| 25 | `BYBIT_BE_PISO_PCT` | `BYBIT_BE_PISO_MIN_PCT` |
| 26 | `BYBIT_CODIGOS_BLACKLIST` | `CODIGOS_BLACKLIST` |
| 27 | `BYBIT_SL_PCT` | `0.0165` |
| 28 | `CAIDA_MINIMA_RELATIVA` | `RETORNO_MINIMO_CAIDA_PCT` |
| 29 | `CAIDA_MIN_PCT` | `-0.0045` |
| 30 | `CAIDA_MIN_VENTANA_PCT` | `RETORNO_MINIMO_CAIDA_PCT` |
| 31 | `CAPITAL_BASE_USDT` | `11.89` |
| 32 | `CAPITAL_INICIAL_REFERENCIA` | `11.89` |
| 33 | `CAPITAL_INICIAL_USDT` | `11.89` |
| 34 | `CODIGOS_BLACKLIST` | `('110004', '110007', '110012', '110043', '110066', '170131', '...` |
| 35 | `CONTAGIO_COOLDOWN_SEG` | `CONTAGIO_PAUSA_MACRO_SEG` |
| 36 | `CONTAGIO_MIN_PARES` | `CONTAGIO_UMBRAL_PARES` |
| 37 | `CONTAGIO_PAUSA_MACRO_SEG` | `180.0` |
| 38 | `CONTAGIO_UMBRAL_PARES` | `3` |
| 39 | `CONTAGIO_VENTANA_SEG` | `10.0` |
| 40 | `COOLDOWN_DISPARO_SEG` | `COOLDOWN_PAR_SEG` |
| 41 | `COOLDOWN_MISMO_PAR_SEG` | `COOLDOWN_PAR_SEG` |
| 42 | `COOLDOWN_PAR_SEG` | `15.0` |
| 43 | `COOLDOWN_POST_CIERRE_SEG` | `300.0` |
| 44 | `DASHBOARD_INTERVALO_SEG` | `300.0` |
| 45 | `DISTANCIA_MAX_SOBRE_EMA_PCT` | `0.008` |
| 46 | `DURACION_BLACKLIST_DINAMICA_SEG` | `3600.0` |
| 47 | `EARLY_TOXIC_CHECK_SEG` | `45` |
| 48 | `EARLY_TOXIC_CUT_SEG` | `45` |
| 49 | `EARLY_TOXIC_HARD_LOSS_PCT` | `-0.0075` |
| 50 | `EARLY_TOXIC_HOLD_SEG` | `45` |
| 51 | `EARLY_TOXIC_LOSS_PCT` | `-0.0065` |
| 52 | `EARLY_TOXIC_OFI_MAX` | `-0.15` |
| 53 | `EARLY_TOXIC_OFI_UMBRAL` | `EARLY_TOXIC_OFI_MAX` |
| 54 | `EMA_MACRO_TICKS` | `900` |
| 55 | `EMA_MACRO_VENTANA_SEG` | `900` |
| 56 | `EMA_MAX_PREMIUM_ENTRADA_NORMAL_PCT` | `0.0015` |
| 57 | `EMA_MAX_PREMIUM_PCT` | `DISTANCIA_MAX_SOBRE_EMA_PCT` |
| 58 | `EMA_TICKS_PERIODO` | `EMA_MACRO_TICKS` |
| 59 | `ESPERA_LLENADO_SEG` | `10` |
| 60 | `EXCLUIR_ZONA_INNOVATION` | `True` |
| 61 | `FACTOR_SEGURIDAD_LOTE_MIN` | `1.15` |
| 62 | `FACTOR_SEGURIDAD_MARGEN` | `0.95` |
| 63 | `FEE_MAKER` | `0.0002` |
| 64 | `FEE_ROUNDTRIP_ESTIMADO` | `FEE_ROUNDTRIP_MAKER_TAKER` |
| 65 | `FEE_ROUNDTRIP_MAKER_MAKER` | `FEE_MAKER + FEE_MAKER` |
| 66 | `FEE_ROUNDTRIP_MAKER_TAKER` | `FEE_MAKER + FEE_TAKER` |
| 67 | `FEE_TAKER` | `0.00055` |
| 68 | `GAMMA_AS` | `0.05` |
| 69 | `GROQ_API_KEY` | `os.getenv('GROQ_API_KEY', '')` |
| 70 | `GROQ_CICLO_SEG` | `180.0` |
| 71 | `GROQ_INTERVALO_SEG` | `GROQ_CICLO_SEG` |
| 72 | `GROQ_MODEL` | `'qwen/qwen3.8-27b'` |
| 73 | `GROQ_MODELOS` | `('openai/gpt-oss-20b', 'llama-3.3-70b-versatile', 'llama-3.1-8...` |
| 74 | `GROQ_MODEL_POOL` | `('qwen/qwen3.8-27b', 'allam-2-7b', 'openai/gpt-oss-20b', 'open...` |
| 75 | `GROQ_MODEL_PRIMARY` | `GROQ_MODEL` |
| 76 | `GROQ_TIMEOUT_SEG` | `6.0` |
| 77 | `HAWKES_COOLDOWN_CLIMAX_SEG` | `1.2` |
| 78 | `HAWKES_COOLDOWN_TOXICO_SEG` | `3.2` |
| 79 | `HAWKES_OFI_DECAY_BETA` | `0.45` |
| 80 | `HAWKES_TOXIC_FLOOR_5S` | `-0.45` |
| 81 | `HEARTBEAT_INTERVALO_SEG` | `60.0` |
| 82 | `INTERVALO_DASHBOARD_SEG` | `DASHBOARD_INTERVALO_SEG` |
| 83 | `INTERVALO_MONITOREO_POS_SEG` | `0.5` |
| 84 | `KAPPA_AS` | `1.5` |
| 85 | `KEEPALIVE_SOCKET_SEG` | `45.0` |
| 86 | `KELLY_FRACCION` | `0.35` |
| 87 | `KELLY_FRACTION` | `KELLY_FRACCION` |
| 88 | `KELLY_MAX_DINAMICO_PCT` | `0.42` |
| 89 | `KELLY_MAX_PCT` | `0.35` |
| 90 | `KELLY_MIN_DINAMICO_PCT` | `0.25` |
| 91 | `LEVERAGE` | `APALANCAMIENTO` |
| 92 | `LOCK_FILE` | `'.splitbrain.lock'` |
| 93 | `LOG_FILE` | `'bot_hft.log'` |
| 94 | `LOTE_MAX_PCT_NOCIONAL` | `1.15` |
| 95 | `LYAPUNOV_ACCEL_MIN` | `-0.00025` |
| 96 | `LYAPUNOV_ACELERACION_MIN` | `LYAPUNOV_ACELERACION_MIN_PCT` |
| 97 | `LYAPUNOV_ACELERACION_MIN_PCT` | `-0.00025` |
| 98 | `LYAPUNOV_MIN_ACCEL` | `LYAPUNOV_ACELERACION_MIN_PCT` |
| 99 | `MAKER_FEE` | `FEE_MAKER` |
| 100 | `MAKER_PERSISTENCIA_SEG` | `12.0` |
| 101 | `MAKER_UNWIND_ACTIVACION_PCT` | `0.0052` |
| 102 | `MAKER_UNWIND_MADURO_PCT` | `0.0032` |
| 103 | `MAKER_UNWIND_MAX_INTENTOS` | `3` |
| 104 | `MAKER_UNWIND_MIN_PNL_PCT` | `0.0012` |
| 105 | `MAKER_UNWIND_OFI_ABORT` | `-0.18` |
| 106 | `MAKER_UNWIND_OFI_TECHO` | `0.18` |
| 107 | `MAKER_UNWIND_PERSISTENCIA_SEG` | `MAKER_UNWIND_TIMEOUT_SEG` |
| 108 | `MAKER_UNWIND_STALL_SEG` | `65` |
| 109 | `MAKER_UNWIND_TARDIO_PCT` | `0.0018` |
| 110 | `MAKER_UNWIND_TIMEOUT_SEG` | `12.0` |
| 111 | `MAKER_UNWIND_TRAMO2_PCT` | `0.0032` |
| 112 | `MAKER_UNWIND_TRAMO3_PCT` | `0.002` |
| 113 | `MARGEN_MINIMO_OPERATIVO_USDT` | `2.0` |
| 114 | `MAX_CONCURRENT_POSITIONS` | `1` |
| 115 | `MAX_DISTANCIA_EMA_PCT` | `DISTANCIA_MAX_SOBRE_EMA_PCT` |
| 116 | `MAX_MIN_QTY_KELLY_RATIO` | `0.6` |
| 117 | `MAX_POSICIONES` | `1` |
| 118 | `MAX_POSICIONES_ABIERTAS` | `1` |
| 119 | `MAX_POSICIONES_SIMULTANEAS` | `1` |
| 120 | `MAX_SPREAD_PCT` | `SPREAD_MAX_PCT` |
| 121 | `MAX_SPREAD_REL_ENTRADA` | `0.0012` |
| 122 | `MAX_TRADES_SIMULTANEOS` | `1` |
| 123 | `MIN_FREE_MARGIN_USDT` | `MARGEN_MINIMO_OPERATIVO_USDT` |
| 124 | `MIN_INVERSION_USDT` | `2.0` |
| 125 | `MIN_NOTIONAL_USDT` | `NOCIONAL_MINIMO_BYBIT_USDT` |
| 126 | `MIN_TICKS_VENTANA` | `20` |
| 127 | `MIN_VOLUMEN_24H_USDT` | `VOLUMEN_MIN_24H_USDT` |
| 128 | `MODO_PAPER` | `PAPER_TRADING` |
| 129 | `MODO_SALIDA` | `'TRAILING+MAKER_PFQI'` |
| 130 | `MODO_TESTNET` | `os.getenv('MODO_TESTNET', 'False').strip().lower() in ('true',...` |
| 131 | `MOTOR_SALIDA` | `'TRAILING'` |
| 132 | `NOCIONAL_MINIMO_BYBIT_USDT` | `5.0` |
| 133 | `OFI_EXIT_MIN_HOLD_SEG` | `40` |
| 134 | `OFI_EXIT_MIN_LOSS_PCT` | `-0.0035` |
| 135 | `OFI_EXIT_UMBRAL` | `-0.55` |
| 136 | `OFI_MIN` | `OFI_UMBRAL_MINIMO` |
| 137 | `OFI_MIN_ENTRADA` | `0.08` |
| 138 | `OFI_REANUDACION_BTC` | `0.3` |
| 139 | `OFI_REANUDACION_VENTANA_SEG` | `30` |
| 140 | `OFI_SALIDA_EMERGENCIA` | `-0.42` |
| 141 | `OFI_SALIDA_MIN_LOSS_PCT` | `-0.0025` |
| 142 | `OFI_SALIDA_VENTANA_SEG` | `10` |
| 143 | `OFI_UMBRAL_MINIMO` | `0.08` |
| 144 | `PAPER_TRADING` | `os.getenv('PAPER_TRADING', 'False').strip().lower() in ('true'...` |
| 145 | `PARES_CRYPTO` | `PARES_OBJETIVO` |
| 146 | `PARES_DRENADORES_VETADOS` | `('WLD/USDT:USDT', 'ZRO/USDT:USDT', 'DOGE/USDT:USDT', 'ONDO/USD...` |
| 147 | `PARES_NUCLEO_ALFA` | `('ZEREBRO/USDT:USDT', 'WAL/USDT:USDT', 'STRK/USDT:USDT', 'INJ/...` |
| 148 | `PARES_OBJETIVO` | `['NEAR/USDT:USDT', 'XRP/USDT:USDT', 'SOL/USDT:USDT', 'HYPE/USD...` |
| 149 | `PENNY_JUMP_ACTIVO` | `True` |
| 150 | `PENNY_JUMP_OFI_MIN` | `PENNY_JUMP_OFI_UMBRAL` |
| 151 | `PENNY_JUMP_OFI_UMBRAL` | `0.25` |
| 152 | `PENNY_JUMP_SPREAD_MIN_TICKS` | `2` |
| 153 | `PERMITIR_ZONA_INNOVATION` | `False` |
| 154 | `PISO_SIGMA_RELATIVO` | `0.0018` |
| 155 | `PORCENTAJE_CAPITAL_POR_TRADE` | `KELLY_FRACCION` |
| 156 | `PROHIBIDAS` | `{'XAUT/USDT:USDT', 'PAXG/USDT:USDT', 'USDC/USDT:USDT', 'USDE/U...` |
| 157 | `RECONCILIACION_BOOT_ACTIVA` | `True` |
| 158 | `RECONCILIACION_MAX_EDAD_SEG` | `TIEMPO_MAX_HOLD_SEG` |
| 159 | `RECUPERACION_MIN_PCT` | `0.5` |
| 160 | `REPLICADOR_QUARANTINE_SEG` | `3600.0` |
| 161 | `REQUOTE_TRIGGER_SEG` | `3.5` |
| 162 | `RETORNO_MINIMO_CAIDA_PCT` | `-0.0055` |
| 163 | `SIGMA_PISO_MINIMO` | `PISO_SIGMA_RELATIVO` |
| 164 | `SL_BYBIT_PCT` | `0.0165` |
| 165 | `SL_GRACIA_MECHAZO_SEG` | `18.0` |
| 166 | `SL_INICIAL_PCT` | `0.0115` |
| 167 | `SL_INTERNO_PCT` | `0.0115` |
| 168 | `SL_PCT` | `0.0115` |
| 169 | `SL_PORCENTAJE` | `0.0115` |
| 170 | `SPREAD_MAX_ENTRADA_PCT` | `SPREAD_MAX_PCT` |
| 171 | `SPREAD_MAX_PCT` | `0.0012` |
| 172 | `STAGNATION_BAND_MAX_PCT` | `0.0015` |
| 173 | `STAGNATION_BAND_MIN_PCT` | `-0.0035` |
| 174 | `STAGNATION_CHECK_SEG` | `105` |
| 175 | `STAGNATION_CUT_SEG` | `STAGNATION_CHECK_SEG` |
| 176 | `STAGNATION_HOLD_SEG` | `105` |
| 177 | `STAGNATION_LOSS_PCT` | `-0.0022` |
| 178 | `STAGNATION_MAX_PNL_PCT` | `STAGNATION_BAND_MAX_PCT` |
| 179 | `STAGNATION_MIN_PNL_PCT` | `STAGNATION_BAND_MIN_PCT` |
| 180 | `STAGNATION_OFI_MAX` | `0.02` |
| 181 | `STATS_FILE` | `'splitbrain_stats_v6.jsonl'` |
| 182 | `STD_MIN` | `1e-08` |
| 183 | `STD_REL_FLOOR` | `0.0005` |
| 184 | `STOP_LOSS_BYBIT_PCT` | `0.0165` |
| 185 | `STOP_LOSS_PCT` | `0.0115` |
| 186 | `SYNC_SL_EXCHANGE_SEG` | `5` |
| 187 | `TAKER_FEE` | `FEE_TAKER` |
| 188 | `TAKE_PROFIT_PCT` | `0.012` |
| 189 | `TARGET_SIGMA_REL` | `0.0022` |
| 190 | `TECHO_MACRO_EMA_PCT` | `0.008` |
| 191 | `TELEGRAM_ACTIVO` | `bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)` |
| 192 | `TELEGRAM_BOT_TOKEN` | `os.getenv('TELEGRAM_BOT_TOKEN', os.getenv('TELEGRAM_TOKEN', ''))` |
| 193 | `TELEGRAM_CHAT_ID` | `os.getenv('TELEGRAM_CHAT_ID', '')` |
| 194 | `TELEGRAM_TOKEN` | `TELEGRAM_BOT_TOKEN` |
| 195 | `TIEMPO_MAX_HOLD_SEG` | `180` |
| 196 | `TIEMPO_VIDA_ORDEN_SEG` | `TIMEOUT_ORDEN_LIMITE_SEG` |
| 197 | `TIMEOUT_ENTRADA_SEG` | `TIMEOUT_ORDEN_LIMITE_SEG` |
| 198 | `TIMEOUT_ORDEN_LIMITE_SEG` | `10.0` |
| 199 | `TIMEOUT_ORDEN_MAKER_SEG` | `TIMEOUT_ORDEN_LIMITE_SEG` |
| 200 | `TOP_N` | `15` |
| 201 | `TOP_N_PARES` | `15` |
| 202 | `TOP_PARES_VOLUMEN` | `TOP_N_PARES` |
| 203 | `TP_PCT` | `TAKE_PROFIT_PCT` |
| 204 | `TP_PORCENTAJE` | `TAKE_PROFIT_PCT` |
| 205 | `TRAILING_ACTIVACION_PCT` | `TRAIL_ACTIVACION_PCT` |
| 206 | `TRAILING_DISTANCIA_PCT` | `TRAIL_DISTANCIA_PCT` |
| 207 | `TRAIL_ACTIVACION_PCT` | `0.0075` |
| 208 | `TRAIL_DISTANCIA_PCT` | `0.0025` |
| 209 | `UMBRAL_OFI_MINIMO` | `0.08` |
| 210 | `UMBRAL_OFI_TOXICO` | `0.08` |
| 211 | `UMBRAL_PANICO` | `-2.6` |
| 212 | `UMBRAL_SIGMA_DINAMICO` | `PISO_SIGMA_RELATIVO` |
| 213 | `UMBRAL_VPIN_TOXICO` | `VPIN_UMBRAL_MAXIMO` |
| 214 | `UMBRAL_Z` | `-2.9` |
| 215 | `UMBRAL_Z_SCORE` | `-2.9` |
| 216 | `UNIVERSO_PARES` | `PARES_OBJETIVO` |
| 217 | `VENTANA_MAX_EDAD_SEG` | `VENTANA_TIEMPO_MAX_SEG` |
| 218 | `VENTANA_MIN_TICKS` | `MIN_TICKS_VENTANA` |
| 219 | `VENTANA_TICKS` | `50` |
| 220 | `VENTANA_TIEMPO_MAX_SEG` | `25.0` |
| 221 | `VENTANA_Z_TICKS` | `VENTANA_TICKS` |
| 222 | `VOLUMEN_MIN_24H_USDT` | `15000000.0` |
| 223 | `VOL_MAX_P99_ALFA_REL` | `0.0085` |
| 224 | `VOL_MAX_P99_REL` | `0.0065` |
| 225 | `VPIN_MAX` | `VPIN_UMBRAL_MAXIMO` |
| 226 | `VPIN_MAX_ENTRADA` | `VPIN_UMBRAL_MAXIMO` |
| 227 | `VPIN_MAX_TOXICO` | `0.72` |
| 228 | `VPIN_UMBRAL_MAXIMO` | `0.65` |
| 229 | `WS_KEEPALIVE_MS` | `10000` |
| 230 | `WS_MAX_PING_MISSES` | `5.0` |
| 231 | `WS_POSITIONS_STREAM_ACTIVO` | `True` |
| 232 | `ZONAS_EXCLUIDAS` | `{'innovation', 'pre-market', 'premarket'}` |
| 233 | `Z_MAX_ABS` | `50.0` |
| 234 | `Z_MIN_ENTRADA` | `Z_SCORE_UMBRAL` |
| 235 | `Z_SCORE_NUCLEO_ALFA` | `-2.9` |
| 236 | `Z_SCORE_SECUNDARIOS_OOS` | `-3.35` |
| 237 | `Z_SCORE_UMBRAL` | `-2.9` |
| 238 | `Z_UMBRAL` | `-2.9` |

---

## 5. ESPECIFICACIÓN DE FRONTERA PARA `SPLITBRAIN-OMEGA V7.0`

1. **Núcleo Híbrido Event-Driven Python/Rust (`NautilusTrader` + `PyO3` + `uvloop` + `msgspec`)**: Paridad determinista nanosegundo entre *backtest* L2/L3 y ejecución en vivo sobre `sniper-tokio`.
2. **Predictor Conjunto de Signo y Timing `MHP-COE` (Hawkes Multivariado + Continuous-Time Output Error)**: Anticipación de reversión de cola en L1/L2 antes de colocar la orden `PostOnly`.
3. **Salida Fraccionada Parcial 50/50 (`Maker-Unwind + Trailing Stop`)**: Cosecha del 50% del lote en `+0.48%` vía Maker para autofinanciar el riesgo y retención del 50% restante con *Trailing Stop* para capturar colas derechas de `+1.80%` a `+3.35%`.
4. **Control Distribucional de Cola (`QR-DDPG` / `SAC` con `CVaR 95%`) y Deslizamiento Geodésico de Fisher-Rao / Wasserstein-2**.
5. **Atribución Cooperativa en Tiempo Real mediante Valores de Shapley (`SHAP`)** sobre cada compuerta del radar.
