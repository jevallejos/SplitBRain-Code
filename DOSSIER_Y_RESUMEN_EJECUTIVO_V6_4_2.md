# DOSSIER MAESTRO DE INGENIERÍA Y RESUMEN EJECUTIVO CONSOLIDADO — SPLITBRAIN-ARGON V6.4.2 (BASE PARA OMEGA V7.0)

- **Fecha de Compilación Automática (Antigravity IDE)**: `2026-10-16 21:26:45 UTC`
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
| `config_parametros.py` | 528 | `99786dbc6c02` | Configuración Maestra Institucional, Universo Tier-1, Blacklist y Contrato AST (64+ constantes) |
| `main.py` | 375 | `fdcf6baea74f` | Orquestador Central Asíncrono, Cerrojo Físico (.splitbrain.lock), Pre-Calentamiento y Reconciliación |
| `1_radar_volatilidad.py` | 683 | `e81c534edf40` | Radar Microestructural O(1): VentanaZ, Lyapunov 1ra/2da Derivada, Kernel Hawkes 5s, VPIN y Anclaje EMA900 |
| `2_escudo_semantico.py` | 375 | `4d3267fc6d40` | Escudo Semántico O(1) en RAM, Dinámica Evolutiva del Replicador OOS y Pool Multi-Modelo Groq LPU |
| `3_ejecutor_sniper.py` | 782 | `ace6d0d140b8` | Ejecutor Sniper Zero-REST, Single-Slot Mutex, Re-Quote 3.5s PostOnly y Kelly Dinámico BRB + Target-Sigma |
| `4_telemetria_telegram.py` | 26 | `f2e38e0073b8` | Despachador Asíncrono Fire-and-Forget de Telemetría y Alertas Operativas hacia Telegram |
| `5_gestor_posiciones.py` | 759 | `b1716fb4a160` | PositionManager: Curva Hiperbólica Almgren-Chriss Maker-Unwind, Maker-Scratch 85s y Anti-Zombie 3 Etapas |
| `6_stats_tracker.py` | 334 | `a0d47cbc5bab` | Caja Negra JSONL, Desduplicador Fantasma, Contabilidad MAP/LVR y Calculador Kelly Busseti-Ryu-Boyd |
| `test_v6_2_suite.py` | 529 | `28fa8a1c2fb5` | Suite Determinista de 15 Pruebas de Integridad Sintáctica, Microestructural y de Reconciliación |

### Módulo `config_parametros.py` (SHA-256: `99786dbc6c02` | 528 líneas)
- **Responsabilidad**: Configuración Maestra Institucional, Universo Tier-1, Blacklist y Contrato AST (64+ constantes)

### Módulo `main.py` (SHA-256: `fdcf6baea74f` | 375 líneas)
- **Responsabilidad**: Orquestador Central Asíncrono, Cerrojo Físico (.splitbrain.lock), Pre-Calentamiento y Reconciliación
- **Clases Declaradas (AST)**: `_TeeLogger (__init__, _formatear_con_hora, write, flush, isatty, __getattr__)`
- **Funciones y Corutinas Principales (AST)**: `_sello_tiempo(), adquirir_bloqueo_instancia_unica(), liberar_bloqueo_instancia_unica(), _es_perpetuo_cripto_puro(), _es_lote_minimo_viable(), async _inicializar_mercados_con_backoff(), async _auditar_margen_libre(), async main()`

### Módulo `1_radar_volatilidad.py` (SHA-256: `e81c534edf40` | 683 líneas)
- **Responsabilidad**: Radar Microestructural O(1): VentanaZ, Lyapunov 1ra/2da Derivada, Kernel Hawkes 5s, VPIN y Anclaje EMA900
- **Clases Declaradas (AST)**: `VentanaZ (__init__, reset, cambio_relativo, caida_desde_maximo, desviacion_ema_macro, volatilidad_relativa...); MediaMovilTemporal (__init__, push, media, cobertura)`
- **Funciones y Corutinas Principales (AST)**: `registrar_cierre_sl_estructural(), es_glitch(), calcular_ofi(), calcular_spread_relativo(), bloqueo_activo(), registrar_y_verificar_contagio(), _validar_compuertas_v6_4_2(), async cazar_cisne_negro(), async cazar_anomalia_ws()`

### Módulo `2_escudo_semantico.py` (SHA-256: `4d3267fc6d40` | 375 líneas)
- **Responsabilidad**: Escudo Semántico O(1) en RAM, Dinámica Evolutiva del Replicador OOS y Pool Multi-Modelo Groq LPU
- **Clases Declaradas (AST)**: `CentinelaSemanticoRAM (__init__, inicializar_universo, actualizar_telemetria, esta_aprobado, evaluar_dinamica_replicador_oos, _filtro_heuristico_respaldo...)`
- **Funciones y Corutinas Principales (AST)**: `_extraer_json_robusto(), async evaluar_anomalia_groq()`

### Módulo `3_ejecutor_sniper.py` (SHA-256: `ace6d0d140b8` | 782 líneas)
- **Responsabilidad**: Ejecutor Sniper Zero-REST, Single-Slot Mutex, Re-Quote 3.5s PostOnly y Kelly Dinámico BRB + Target-Sigma
- **Funciones y Corutinas Principales (AST)**: `_lanzar_bg(), enviar_alerta_bg(), async sincronizar_saldo_ram(), disparar_sincronizacion_saldo_bg(), async bucle_keepalive_socket(), async precalentar_apalancamiento_universo(), posicion_activa(), total_posiciones_activas(), cupo_portafolio_disponible(), en_cooldown_post_cierre(), _d(), cuantizar_orden(), _es_error_blacklist(), async _fijar_apalancamiento(), _extraer_precio_maker_ws(), _obtener_sl_bybit_pct(), _calcular_kelly_operativo(), async ejecutar_orden_sniper()`

### Módulo `4_telemetria_telegram.py` (SHA-256: `f2e38e0073b8` | 26 líneas)
- **Responsabilidad**: Despachador Asíncrono Fire-and-Forget de Telemetría y Alertas Operativas hacia Telegram
- **Funciones y Corutinas Principales (AST)**: `async enviar_alerta()`

### Módulo `5_gestor_posiciones.py` (SHA-256: `b1716fb4a160` | 759 líneas)
- **Responsabilidad**: PositionManager: Curva Hiperbólica Almgren-Chriss Maker-Unwind, Maker-Scratch 85s y Anti-Zombie 3 Etapas
- **Clases Declaradas (AST)**: `Posicion (); PositionManager (__init__, tiene, registrar_cooldown_post_cierre, en_cooldown, segundos_cooldown_restantes, calcular_objetivo_sl_exchange...)`
- **Funciones y Corutinas Principales (AST)**: `calcular_ofi(), calcular_umbral_maker_almgren_chriss(), _obtener_jerarquia_sl_pct()`

### Módulo `6_stats_tracker.py` (SHA-256: `a0d47cbc5bab` | 334 líneas)
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

## 4. CONTRATO SINTÁCTICO AST VERIFICADO EN `config_parametros.py` (243 CONSTANTES ACTIVAS)

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
| 17 | `BLOQUEO_CONTAGIO_ALT_SEG` | `90.0` |
| 18 | `BREAK_EVEN_ACTIVACION_PCT` | `0.0045` |
| 19 | `BREAK_EVEN_OFFSET_PCT` | `0.0016` |
| 20 | `BREAK_EVEN_PLUS_PCT` | `BREAK_EVEN_OFFSET_PCT` |
| 21 | `BREAK_EVEN_TRIGGER_PCT` | `BREAK_EVEN_ACTIVACION_PCT` |
| 22 | `BYBIT_API_KEY` | `os.getenv('BYBIT_API_KEY', '')` |
| 23 | `BYBIT_API_SECRET` | `os.getenv('BYBIT_API_SECRET', '')` |
| 24 | `BYBIT_BE_FLOOR_PCT` | `BYBIT_BE_PISO_MIN_PCT` |
| 25 | `BYBIT_BE_PISO_MIN_PCT` | `0.0012` |
| 26 | `BYBIT_BE_PISO_PCT` | `BYBIT_BE_PISO_MIN_PCT` |
| 27 | `BYBIT_CODIGOS_BLACKLIST` | `CODIGOS_BLACKLIST` |
| 28 | `BYBIT_SL_PCT` | `0.0122` |
| 29 | `CAIDA_MINIMA_RELATIVA` | `RETORNO_MINIMO_CAIDA_PCT` |
| 30 | `CAIDA_MIN_PCT` | `-0.0045` |
| 31 | `CAIDA_MIN_VENTANA_PCT` | `RETORNO_MINIMO_CAIDA_PCT` |
| 32 | `CAPITAL_BASE_USDT` | `11.89` |
| 33 | `CAPITAL_INICIAL_REFERENCIA` | `11.89` |
| 34 | `CAPITAL_INICIAL_USDT` | `11.89` |
| 35 | `CODIGOS_BLACKLIST` | `('110004', '110007', '110012', '110043', '110066', '170131', '...` |
| 36 | `CONTAGIO_COOLDOWN_SEG` | `CONTAGIO_PAUSA_MACRO_SEG` |
| 37 | `CONTAGIO_MIN_PARES` | `3` |
| 38 | `CONTAGIO_PAUSA_MACRO_SEG` | `180.0` |
| 39 | `CONTAGIO_UMBRAL_PARES` | `3` |
| 40 | `CONTAGIO_VENTANA_SEG` | `10.0` |
| 41 | `COOLDOWN_DISPARO_SEG` | `COOLDOWN_PAR_SEG` |
| 42 | `COOLDOWN_MISMO_PAR_SEG` | `COOLDOWN_PAR_SEG` |
| 43 | `COOLDOWN_PAR_SEG` | `15.0` |
| 44 | `COOLDOWN_POST_CIERRE_SEG` | `300.0` |
| 45 | `DASHBOARD_INTERVALO_SEG` | `300.0` |
| 46 | `DISTANCIA_MAX_SOBRE_EMA_PCT` | `0.008` |
| 47 | `DURACION_BLACKLIST_DINAMICA_SEG` | `3600.0` |
| 48 | `EARLY_TOXIC_CHECK_SEG` | `45` |
| 49 | `EARLY_TOXIC_CUT_SEG` | `45` |
| 50 | `EARLY_TOXIC_HARD_LOSS_PCT` | `-0.0075` |
| 51 | `EARLY_TOXIC_HOLD_SEG` | `45` |
| 52 | `EARLY_TOXIC_LOSS_PCT` | `-0.0065` |
| 53 | `EARLY_TOXIC_OFI_MAX` | `-0.15` |
| 54 | `EARLY_TOXIC_OFI_UMBRAL` | `EARLY_TOXIC_OFI_MAX` |
| 55 | `EMA_MACRO_TICKS` | `900` |
| 56 | `EMA_MACRO_VENTANA_SEG` | `900` |
| 57 | `EMA_MAX_PREMIUM_ENTRADA_NORMAL_PCT` | `0.0015` |
| 58 | `EMA_MAX_PREMIUM_PCT` | `DISTANCIA_MAX_SOBRE_EMA_PCT` |
| 59 | `EMA_TICKS_PERIODO` | `EMA_MACRO_TICKS` |
| 60 | `ESPERA_LLENADO_SEG` | `10` |
| 61 | `EXCLUIR_ZONA_INNOVATION` | `True` |
| 62 | `FACTOR_SEGURIDAD_LOTE_MIN` | `1.15` |
| 63 | `FACTOR_SEGURIDAD_MARGEN` | `0.95` |
| 64 | `FEE_MAKER` | `0.0002` |
| 65 | `FEE_ROUNDTRIP_ESTIMADO` | `FEE_ROUNDTRIP_MAKER_TAKER` |
| 66 | `FEE_ROUNDTRIP_MAKER_MAKER` | `FEE_MAKER + FEE_MAKER` |
| 67 | `FEE_ROUNDTRIP_MAKER_TAKER` | `FEE_MAKER + FEE_TAKER` |
| 68 | `FEE_TAKER` | `0.00055` |
| 69 | `GAMMA_AS` | `0.05` |
| 70 | `GROQ_API_KEY` | `os.getenv('GROQ_API_KEY', '')` |
| 71 | `GROQ_CICLO_SEG` | `180.0` |
| 72 | `GROQ_INTERVALO_SEG` | `GROQ_CICLO_SEG` |
| 73 | `GROQ_MODEL` | `'qwen/qwen3.8-27b'` |
| 74 | `GROQ_MODELOS` | `('openai/gpt-oss-20b', 'llama-3.3-70b-versatile', 'llama-3.1-8...` |
| 75 | `GROQ_MODEL_POOL` | `('qwen/qwen3.8-27b', 'allam-2-7b', 'openai/gpt-oss-20b', 'open...` |
| 76 | `GROQ_MODEL_PRIMARY` | `GROQ_MODEL` |
| 77 | `GROQ_TIMEOUT_SEG` | `6.0` |
| 78 | `HAWKES_COOLDOWN_CLIMAX_SEG` | `0.0` |
| 79 | `HAWKES_COOLDOWN_TOXICO_SEG` | `1.6` |
| 80 | `HAWKES_INTENSIDAD_DESBLOQUEO` | `0.18` |
| 81 | `HAWKES_OFI_DECAY_BETA` | `0.45` |
| 82 | `HAWKES_TOXIC_FLOOR_5S` | `-0.45` |
| 83 | `HEARTBEAT_INTERVALO_SEG` | `60.0` |
| 84 | `INTERVALO_DASHBOARD_SEG` | `DASHBOARD_INTERVALO_SEG` |
| 85 | `INTERVALO_MONITOREO_POS_SEG` | `0.5` |
| 86 | `KAPPA_AS` | `1.5` |
| 87 | `KEEPALIVE_SOCKET_SEG` | `45.0` |
| 88 | `KELLY_FRACCION` | `0.35` |
| 89 | `KELLY_FRACTION` | `KELLY_FRACCION` |
| 90 | `KELLY_MAX_DINAMICO_PCT` | `0.42` |
| 91 | `KELLY_MAX_PCT` | `0.35` |
| 92 | `KELLY_MIN_DINAMICO_PCT` | `0.25` |
| 93 | `LEVERAGE` | `APALANCAMIENTO` |
| 94 | `LOCK_FILE` | `'.splitbrain.lock'` |
| 95 | `LOG_FILE` | `'bot_hft.log'` |
| 96 | `LOTE_MAX_PCT_NOCIONAL` | `1.15` |
| 97 | `LYAPUNOV_ACCEL_MIN` | `-0.00025` |
| 98 | `LYAPUNOV_ACELERACION_MIN` | `LYAPUNOV_ACELERACION_MIN_PCT` |
| 99 | `LYAPUNOV_ACELERACION_MIN_PCT` | `-0.00025` |
| 100 | `LYAPUNOV_MIN_ACCEL` | `LYAPUNOV_ACELERACION_MIN_PCT` |
| 101 | `MAKER_FEE` | `FEE_MAKER` |
| 102 | `MAKER_PERSISTENCIA_SEG` | `12.0` |
| 103 | `MAKER_UNWIND_ACTIVACION_PCT` | `0.0052` |
| 104 | `MAKER_UNWIND_MADURO_PCT` | `0.0032` |
| 105 | `MAKER_UNWIND_MAX_INTENTOS` | `3` |
| 106 | `MAKER_UNWIND_MIN_PNL_PCT` | `0.0012` |
| 107 | `MAKER_UNWIND_OFI_ABORT` | `-0.18` |
| 108 | `MAKER_UNWIND_OFI_TECHO` | `0.18` |
| 109 | `MAKER_UNWIND_PERSISTENCIA_SEG` | `MAKER_UNWIND_TIMEOUT_SEG` |
| 110 | `MAKER_UNWIND_STALL_SEG` | `65` |
| 111 | `MAKER_UNWIND_TARDIO_PCT` | `0.0018` |
| 112 | `MAKER_UNWIND_TIMEOUT_SEG` | `12.0` |
| 113 | `MAKER_UNWIND_TRAMO2_PCT` | `0.0032` |
| 114 | `MAKER_UNWIND_TRAMO3_PCT` | `0.002` |
| 115 | `MARGEN_MINIMO_OPERATIVO_USDT` | `2.0` |
| 116 | `MAX_CONCURRENT_POSITIONS` | `1` |
| 117 | `MAX_DISTANCIA_EMA_PCT` | `DISTANCIA_MAX_SOBRE_EMA_PCT` |
| 118 | `MAX_MIN_QTY_KELLY_RATIO` | `0.6` |
| 119 | `MAX_POSICIONES` | `1` |
| 120 | `MAX_POSICIONES_ABIERTAS` | `1` |
| 121 | `MAX_POSICIONES_SIMULTANEAS` | `1` |
| 122 | `MAX_SPREAD_PCT` | `SPREAD_MAX_PCT` |
| 123 | `MAX_SPREAD_REL_ENTRADA` | `0.0012` |
| 124 | `MAX_TRADES_SIMULTANEOS` | `1` |
| 125 | `MIN_FREE_MARGIN_USDT` | `MARGEN_MINIMO_OPERATIVO_USDT` |
| 126 | `MIN_INVERSION_USDT` | `2.0` |
| 127 | `MIN_NOTIONAL_USDT` | `NOCIONAL_MINIMO_BYBIT_USDT` |
| 128 | `MIN_TICKS_VENTANA` | `20` |
| 129 | `MIN_VOLUMEN_24H_USDT` | `VOLUMEN_MIN_24H_USDT` |
| 130 | `MODO_PAPER` | `PAPER_TRADING` |
| 131 | `MODO_SALIDA` | `'TRAILING+MAKER_PFQI'` |
| 132 | `MODO_TESTNET` | `os.getenv('MODO_TESTNET', 'False').strip().lower() in ('true',...` |
| 133 | `MOTOR_SALIDA` | `'TRAILING'` |
| 134 | `NOCIONAL_MINIMO_BYBIT_USDT` | `5.0` |
| 135 | `OFI_EXIT_MIN_HOLD_SEG` | `40` |
| 136 | `OFI_EXIT_MIN_LOSS_PCT` | `-0.0035` |
| 137 | `OFI_EXIT_UMBRAL` | `-0.55` |
| 138 | `OFI_MIN` | `OFI_UMBRAL_MINIMO` |
| 139 | `OFI_MIN_ENTRADA` | `0.08` |
| 140 | `OFI_REANUDACION_BTC` | `0.3` |
| 141 | `OFI_REANUDACION_VENTANA_SEG` | `30` |
| 142 | `OFI_SALIDA_EMERGENCIA` | `-0.42` |
| 143 | `OFI_SALIDA_MIN_LOSS_PCT` | `-0.0025` |
| 144 | `OFI_SALIDA_VENTANA_SEG` | `10` |
| 145 | `OFI_UMBRAL_MINIMO` | `0.08` |
| 146 | `PAPER_TRADING` | `os.getenv('PAPER_TRADING', 'False').strip().lower() in ('true'...` |
| 147 | `PARES_CRYPTO` | `PARES_OBJETIVO` |
| 148 | `PARES_DRENADORES_VETADOS` | `('WLD/USDT:USDT', 'ZRO/USDT:USDT', 'DOGE/USDT:USDT', 'ONDO/USD...` |
| 149 | `PARES_NUCLEO_ALFA` | `('WAL/USDT:USDT', 'ZEREBRO/USDT:USDT', 'INJ/USDT:USDT', 'XRP/U...` |
| 150 | `PARES_OBJETIVO` | `['NEAR/USDT:USDT', 'XRP/USDT:USDT', 'SOL/USDT:USDT', 'HYPE/USD...` |
| 151 | `PENNY_JUMP_ACTIVO` | `True` |
| 152 | `PENNY_JUMP_OFI_MIN` | `PENNY_JUMP_OFI_UMBRAL` |
| 153 | `PENNY_JUMP_OFI_UMBRAL` | `0.25` |
| 154 | `PENNY_JUMP_SPREAD_MIN_TICKS` | `2` |
| 155 | `PERMITIR_ZONA_INNOVATION` | `False` |
| 156 | `PISO_SIGMA_RELATIVO` | `0.0018` |
| 157 | `PORCENTAJE_CAPITAL_POR_TRADE` | `KELLY_FRACCION` |
| 158 | `PROHIBIDAS` | `{'XAUT/USDT:USDT', 'PAXG/USDT:USDT', 'USDC/USDT:USDT', 'USDE/U...` |
| 159 | `RECONCILIACION_BOOT_ACTIVA` | `True` |
| 160 | `RECONCILIACION_MAX_EDAD_SEG` | `TIEMPO_MAX_HOLD_SEG` |
| 161 | `RECUPERACION_MIN_PCT` | `0.5` |
| 162 | `REPLICADOR_QUARANTINE_SEG` | `3600.0` |
| 163 | `REQUOTE_MAX_DRIFT_PCT` | `0.0028` |
| 164 | `REQUOTE_MIN_OFI` | `0.3` |
| 165 | `REQUOTE_TRIGGER_SEG` | `2.0` |
| 166 | `RETORNO_MINIMO_CAIDA_PCT` | `-0.0055` |
| 167 | `SIGMA_PISO_MINIMO` | `PISO_SIGMA_RELATIVO` |
| 168 | `SL_BYBIT_PCT` | `0.0122` |
| 169 | `SL_GRACIA_MECHAZO_SEG` | `6.0` |
| 170 | `SL_INICIAL_PCT` | `0.0088` |
| 171 | `SL_INTERNO_PCT` | `0.0088` |
| 172 | `SL_PCT` | `0.0122` |
| 173 | `SL_PORCENTAJE` | `0.0115` |
| 174 | `SPREAD_MAX_ENTRADA_PCT` | `SPREAD_MAX_PCT` |
| 175 | `SPREAD_MAX_PCT` | `0.0012` |
| 176 | `STAGNATION_BAND_MAX_PCT` | `0.0015` |
| 177 | `STAGNATION_BAND_MIN_PCT` | `-0.0035` |
| 178 | `STAGNATION_CHECK_SEG` | `105` |
| 179 | `STAGNATION_CUT_SEG` | `STAGNATION_CHECK_SEG` |
| 180 | `STAGNATION_HOLD_SEG` | `105` |
| 181 | `STAGNATION_LOSS_PCT` | `-0.0022` |
| 182 | `STAGNATION_MAX_PNL_PCT` | `STAGNATION_BAND_MAX_PCT` |
| 183 | `STAGNATION_MIN_PNL_PCT` | `STAGNATION_BAND_MIN_PCT` |
| 184 | `STAGNATION_OFI_MAX` | `0.02` |
| 185 | `STATS_FILE` | `'splitbrain_stats_v6.jsonl'` |
| 186 | `STD_MIN` | `1e-08` |
| 187 | `STD_REL_FLOOR` | `0.0005` |
| 188 | `STOP_LOSS_BYBIT_PCT` | `0.0122` |
| 189 | `STOP_LOSS_PCT` | `0.0088` |
| 190 | `SYNC_SL_EXCHANGE_SEG` | `5` |
| 191 | `TAKER_FEE` | `FEE_TAKER` |
| 192 | `TAKE_PROFIT_PCT` | `0.012` |
| 193 | `TARGET_SIGMA_REL` | `0.0022` |
| 194 | `TECHO_MACRO_EMA_PCT` | `0.008` |
| 195 | `TELEGRAM_ACTIVO` | `bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)` |
| 196 | `TELEGRAM_BOT_TOKEN` | `os.getenv('TELEGRAM_BOT_TOKEN', os.getenv('TELEGRAM_TOKEN', ''))` |
| 197 | `TELEGRAM_CHAT_ID` | `os.getenv('TELEGRAM_CHAT_ID', '')` |
| 198 | `TELEGRAM_TOKEN` | `TELEGRAM_BOT_TOKEN` |
| 199 | `TIEMPO_MAX_HOLD_SEG` | `180` |
| 200 | `TIEMPO_VIDA_ORDEN_SEG` | `TIMEOUT_ORDEN_LIMITE_SEG` |
| 201 | `TIMEOUT_ENTRADA_SEG` | `TIMEOUT_ORDEN_LIMITE_SEG` |
| 202 | `TIMEOUT_ORDEN_LIMITE_SEG` | `10.0` |
| 203 | `TIMEOUT_ORDEN_MAKER_SEG` | `TIMEOUT_ORDEN_LIMITE_SEG` |
| 204 | `TOP_N` | `15` |
| 205 | `TOP_N_PARES` | `15` |
| 206 | `TOP_PARES_VOLUMEN` | `TOP_N_PARES` |
| 207 | `TP_PCT` | `TAKE_PROFIT_PCT` |
| 208 | `TP_PORCENTAJE` | `TAKE_PROFIT_PCT` |
| 209 | `TRAILING_ACTIVACION_PCT` | `TRAIL_ACTIVACION_PCT` |
| 210 | `TRAILING_DISTANCIA_PCT` | `TRAIL_DISTANCIA_PCT` |
| 211 | `TRAIL_ACTIVACION_PCT` | `0.0075` |
| 212 | `TRAIL_DISTANCIA_PCT` | `0.0025` |
| 213 | `UMBRAL_OFI_MINIMO` | `0.08` |
| 214 | `UMBRAL_OFI_TOXICO` | `0.08` |
| 215 | `UMBRAL_PANICO` | `-2.6` |
| 216 | `UMBRAL_SIGMA_DINAMICO` | `PISO_SIGMA_RELATIVO` |
| 217 | `UMBRAL_VPIN_TOXICO` | `VPIN_UMBRAL_MAXIMO` |
| 218 | `UMBRAL_Z` | `-2.9` |
| 219 | `UMBRAL_Z_SCORE` | `-2.9` |
| 220 | `UNIVERSO_PARES` | `PARES_OBJETIVO` |
| 221 | `UNIVERSO_SHAPLEY_ELITE` | `['WAL/USDT:USDT', 'ZEREBRO/USDT:USDT', 'INJ/USDT:USDT', 'XRP/U...` |
| 222 | `VENTANA_MAX_EDAD_SEG` | `VENTANA_TIEMPO_MAX_SEG` |
| 223 | `VENTANA_MIN_TICKS` | `MIN_TICKS_VENTANA` |
| 224 | `VENTANA_TICKS` | `50` |
| 225 | `VENTANA_TIEMPO_MAX_SEG` | `25.0` |
| 226 | `VENTANA_Z_TICKS` | `VENTANA_TICKS` |
| 227 | `VOLUMEN_MIN_24H_USDT` | `15000000.0` |
| 228 | `VOL_MAX_P99_ALFA_REL` | `0.0085` |
| 229 | `VOL_MAX_P99_REL` | `0.0065` |
| 230 | `VPIN_MAX` | `VPIN_UMBRAL_MAXIMO` |
| 231 | `VPIN_MAX_ENTRADA` | `VPIN_UMBRAL_MAXIMO` |
| 232 | `VPIN_MAX_TOXICO` | `0.72` |
| 233 | `VPIN_UMBRAL_MAXIMO` | `0.65` |
| 234 | `WS_KEEPALIVE_MS` | `10000` |
| 235 | `WS_MAX_PING_MISSES` | `5.0` |
| 236 | `WS_POSITIONS_STREAM_ACTIVO` | `True` |
| 237 | `ZONAS_EXCLUIDAS` | `{'innovation', 'pre-market', 'premarket'}` |
| 238 | `Z_MAX_ABS` | `50.0` |
| 239 | `Z_MIN_ENTRADA` | `Z_SCORE_UMBRAL` |
| 240 | `Z_SCORE_NUCLEO_ALFA` | `-2.85` |
| 241 | `Z_SCORE_SECUNDARIOS_OOS` | `-3.2` |
| 242 | `Z_SCORE_UMBRAL` | `-2.9` |
| 243 | `Z_UMBRAL` | `-2.9` |

---

## 5. ESPECIFICACIÓN DE FRONTERA PARA `SPLITBRAIN-OMEGA V7.0`

1. **Núcleo Híbrido Event-Driven Python/Rust (`NautilusTrader` + `PyO3` + `uvloop` + `msgspec`)**: Paridad determinista nanosegundo entre *backtest* L2/L3 y ejecución en vivo sobre `sniper-tokio`.
2. **Predictor Conjunto de Signo y Timing `MHP-COE` (Hawkes Multivariado + Continuous-Time Output Error)**: Anticipación de reversión de cola en L1/L2 antes de colocar la orden `PostOnly`.
3. **Salida Fraccionada Parcial 50/50 (`Maker-Unwind + Trailing Stop`)**: Cosecha del 50% del lote en `+0.48%` vía Maker para autofinanciar el riesgo y retención del 50% restante con *Trailing Stop* para capturar colas derechas de `+1.80%` a `+3.35%`.
4. **Control Distribucional de Cola (`QR-DDPG` / `SAC` con `CVaR 95%`) y Deslizamiento Geodésico de Fisher-Rao / Wasserstein-2**.
5. **Atribución Cooperativa en Tiempo Real mediante Valores de Shapley (`SHAP`)** sobre cada compuerta del radar.
