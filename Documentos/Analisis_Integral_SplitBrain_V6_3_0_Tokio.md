# DOSSIER MAESTRO DE INGENIERÍA CUANTITATIVA: PROYECTO SplitBRain-Code (V6.3.0 ANTI-CONTAGIO — TOKIO HFT)

**Proyecto:** `SplitBRain-Code` (`Split-Brain-Argon` HFT Engine)  
**Versión Consolidada:** `V6.3.0 Anti-Contagio` (`tag: v6.3.0-anti-contagio`)  
**Infraestructura de Producción:** Google Cloud Platform (GCP) · Región `asia-northeast1` (Tokio) · Instancia `e2-micro` (`ubuntu-minimal-2604-resolute-amd64`, Kernel HFT `TCP BBR` + `ZRAM zstd` + `uvloop 0.22.1`)  
**Mercado Objetivo:** Contratos Perpetuos Lineales (`USDT:USDT`) en Cuentas Unificadas (UTA) de Bybit v5  
**Estado de Verificación:** 10/10 Pruebas AST y de Integración Superadas · Validado en Fuego Real (Trades #1 a #83)

---

## 1. Definición Arquitectónica y Resolución Dialéctica TRIZ

**SplitBRain-Code** es un motor autónomo de arbitraje cuantitativo de microestructura y captura de reversión a la media en alta frecuencia (HFT), diseñado para operar sobre el libro de órdenes límite ($LOB$) de futuros perpetuos lineales en Bybit UTA. Su propósito es detectar vacíos abruptos de liquidez provocados por cascadas de pánico intradiario, discriminar en sub-milisegundos si el flujo entrante corresponde a liquidaciones forzadas no informadas o a flujo tóxico informado, y proveer liquidez pasiva (`Limit PostOnly`) capturando la prima de reversión neta de comisiones institucionales Maker ($0.02\%$).

### Principio de Separación de TRIZ (En el Tiempo, Espacio y Condición)
El sistema erradica la contradicción física entre la alta latencia de inferencia contextual de los Grandes Modelos de Lenguaje ($\sim 600\text{–}1,300\text{ ms}$) y la velocidad sub-milisegundo exigida por el cálculo microestructural y despacho de órdenes ($\sim 0.65\ \mu\text{s}$ en RAM y $< 100\text{ ms}$ de RTT de red en Tokio) mediante tres motores asíncronos desacoplados sobre `uvloop`:

1. **Motor Cuantitativo de Detección y Contagio — Motor A (`1_radar_volatilidad.py`):**
   Escanea en tiempo real los flujos WebSocket (`ccxt.pro`) de las $N = 15$ presas cripto-nativas con mayor volumen y viabilidad de lote mínimo. Calcula en complejidad $\mathcal{O}(1)$ el $Z$-Score rodante de $60\text{ s}$ (`VentanaZ`) con piso de volatilidad relativa (`STD_REL_FLOOR = 0.0005`), la caída porcentual desde el máximo rodante (`CAIDA_MIN_PCT = -0.0045`), el desequilibrio instantáneo en la punta del libro (`calcular_ofi`) y gobierna dos cortafuegos sistémicos con evacuación activa: el **Circuit Breaker de BTC** ($Z_{\text{BTC}} \le -4.0$) y el **Detector de Contagio Simultáneo Cross-Asset** (*Breadth Contagion Breaker*, $\ge 3$ pares en pánico en una ventana móvil de $10\text{ s}$).

2. **Motor Cualitativo/Cuantitativo LPU con Rotación Multi-Modelo — Motor B (`2_escudo_semantico.py`):**
   Opera como un demonio asíncrono en segundo plano (`CentinelaGroqRAM`) que empaqueta cada $180\text{ s}$ el vector de telemetría (`z`, `ofi`, `price`, `chg_pct`) de los 15 activos y consulta la red Groq LPU mediante rotación automática libre de bloqueo ante errores HTTP 429 (`openai/gpt-oss-20b` $\to$ `llama-3.3-70b-versatile` $\to$ `llama-3.1-8b-instant`). El resultado actualiza mediante intercambio atómico de punteros un conjunto inmutable `frozenset` en memoria RAM (`_whitelist_ram`), logrando verificaciones en la ruta crítica en **$\sim 0.65\ \mu\text{s}$ ($\mathcal{O}(1)$ Lock-Free)**, respaldado por un filtro determinista local Anti-LUNA.

3. **Motor Determinista de Ejecución Zero-REST y Gestión de Inventario — Motor C (`3_ejecutor_sniper.py` y `5_gestor_posiciones.py`):**
   El Sniper ejecuta en régimen **Zero-REST** leyendo el margen libre cacheado en RAM (`_saldo_libre_ram`), manteniendo caliente el socket TLS privado hacia Bybit cada $45\text{ s}$ (`bucle_keepalive_socket`), aplicando cotización óptima en rejilla discreta de Bertrand (*Penny-Jump*: `best_bid + 1 tick` cuando el spread es $\ge 2\text{ ticks}$ y $\text{OFI} \ge +0.25$) y cancelando órdenes no llenadas a los $10\text{ s}$ (`ESPERA_LLENADO_SEG = 10`). Una vez ejecutada la compra, el `PositionManager` administra la posición bajo el esquema de **Triple Barrera Recalibrado**: Micro-Break-Even a **$+0.48\%$** ($+0.12\%$ asegurado), Trailing Stop a **$+0.80\%$** (distancia $0.35\%$), salida de emergencia por toxicidad (`OFI_EXIT` cuando $\text{OFI}_{10\text{s}} < -0.80$), liquidación anti-zombie a los $300\text{ s}$ (`ESCAPE_TEMPORAL`), evacuación inmediata ante colapso macro (`evacuar_por_emergencia_macro`) y **Cuarentena Post-Cierre de $300\text{ s}$** (`COOLDOWN_POST_CIERRE_SEG = 300`) para erradicar el *Serial Knife-Catching*.

---

## 2. Fundamentación Matemática y Teórico-Juegos (Síntesis de los 3 Cuadernos Canónicos)

### 2.1. Teoría de Juegos Algorítmica: Stackelberg, Bertrand Discreto y Estrategia *Grim Trigger*
1. **Liderazgo de Stackelberg en Escalas de Tiempo Separadas y Juegos Globales (Morris & Shin; Caginalp & Caginalp, 2019):**
   Durante choques sistémicos, Bitcoin y el factor de mercado cross-asset actúan como el *Líder de Stackelberg* y señal pública de coordinación (*sunspot* $r_\tau$). Mantener inventario largo $q > 0$ tras observar el colapso del líder constituye una estrategia estrictamente dominada bajo Eliminación Iterativa ($EIE$) y criterio Minimax ($\max_{\mathbf{x}} \min_{\mathbf{y}} \mathbf{x}^T A \mathbf{y}$), lo que fundamenta la ejecución inmediata de `evacuar_por_emergencia_macro()`.
2. **Competencia de Precios en Rejilla Discreta de Bertrand (*Penny-Jump*):**
   Dado un paso mínimo de precio $p_m = \text{tick\_size}$, un `best_bid` $B_t$ y un `best_ask` $A_t$ con spread en ticks $K_t = \text{round}((A_t - B_t)/p_m)$, la cotización óptima pasiva que maximiza la probabilidad de captura en reversiones rápidas sin perder la tarifa Maker ($0.02\%$) es:
   $$P_{\text{quote}}^*(t) = \begin{cases} B_t + p_m & \text{si } K_t \ge 2 \;\land\; \text{OFI}_t \ge +0.25 \quad \text{(Prioridad 100\% en cola, PostOnly seguro)} \\ B_t & \text{si } K_t = 1 \;\lor\; \text{OFI}_t \in [-0.35, +0.25) \quad \text{(Paridad en } B_t\text{)} \\ \text{ABORT} & \text{si } \text{OFI}_t < -0.35 \quad \text{(Veto por Selección Adversa)} \end{cases}$$
3. **Equilibrio Bayesiano Perfecto ($PBE$) y *Grim Trigger* en Procesos Auto-Excitados de Hawkes:**
   La llegada de ventas agresivas en el libro de órdenes obedece a un proceso punto auto-excitado de Hawkes con intensidad condicional:
   $$\lambda_m(t \mid \mathcal{F}_t) = \mu_m + \sum_{n=1}^{M} \int_{0}^{t} \alpha_{mn} e^{-\beta_{mn}(t - s)}\, dN_n(s)$$
   Cuando una posición cierra a los $300\text{ s}$ o toca Stop-Loss, el kernel de excitación $\alpha e^{-\beta(t - \tau_{\text{close}})}$ permanece elevado. Imponer `COOLDOWN_POST_CIERRE_SEG = 300` contados desde el instante exacto de cierre $\tau_{\text{close}}$ aplica una estrategia de disparador (*Grim Trigger*) que permite la relajación exponencial de la cascada ($\lambda_m(t) \to \mu_m$) antes de volver a cotizar en ese activo.

### 2.2. Descomposición Beta vs. Alfa, *Loss-Versus-Rebalancing* ($LVR$) y Control HJB de Avellaneda-Stoikov
1. **Teorema de Descomposición de Milionis, Moallemi, Roughgarden & Zhang (`arXiv:2208.06046`):**
   Aplicando el Lema de Itô a la función de valor $V(P_t)$ de una posición pasiva frente a una estrategia de rebalanceo $R_t$, el PnL se descompone en exposición direccional de mercado (**Beta**, que explica el $99.991\%$ de la varianza) y un componente microestructural (**Alfa**) drenado continuamente por el costo de selección adversa (*Loss-Versus-Rebalancing*):
   $$V(P_t) = R_t - \text{LVR}_t, \qquad \text{LVR}_t = \int_{0}^{t} \frac{\sigma_s^2 P_s^2}{2}\big\vert{}x^{*\prime}(P_s)\big\vert{}\, ds \approx \int_{0}^{t} \frac{\sigma_s^2}{8} V(P_s)\, ds$$
   Retener inventario pasivo durante $300\text{ s}$ esperando un $+1.00\%$ estático cuando el rebote medio de microestructura es de $+0.45\%$ a $+0.85\%$ permite que el drenaje cuadrático de $\text{LVR}_t \propto \sigma_t^2$ y la comisión Taker de salida ($0.055\%$) conviertan operaciones ganadoras en pérdidas. La recalibración de la Triple Barrera a $+0.48\%$ (Micro-Break-Even) y $+0.80\%$ (Trailing Stop) trunca la exposición temporal y asegura el Alfa antes de que actúe el decaimiento por $LVR$.
2. **Precio de Reserva HJB de Avellaneda-Stoikov (2008):**
   Para un creador de mercado con utilidad CARA $U(x, q, t) = -\exp(-\gamma(x + q S_t))$, el precio subjetivo de indiferencia para evacuar el inventario normalizado $q \in (0, 1]$ en el tiempo remanente $T - t$ es:
   $$r(S_t, q, t) = S_t - q\gamma\sigma_t^2(T - t), \qquad \delta^a(S_t, q, t) = r(S_t, q, t) - S_t + \frac{1}{\gamma}\ln\left(1 + \frac{\gamma}{k}\right)$$

### 2.3. Econometría del Contagio Cripto-Nativo ($\Delta\rho_{\text{DCCA}}$, TVP-FAVAR y BEKK Asimétrico)
Los estudios de Ferreira & Pereira (2019), Antonakakis et al. (2019) y Lucey et al. (2019) demuestran que durante eventos de estrés la conectividad total dinámica TVP-FAVAR salta del $25\%$ al $75\%$ y el diferencial de correlación cruzada sin tendencia $\Delta\rho_{\text{DCCA}}(n) > 0$ converge hacia la unidad en todas las altcoins. El detector `registrar_y_verificar_contagio()` mide en $\mathcal{O}(1)$ esta transición de fase:
$$\mathcal{C}_{\text{panic}}(t) = \sum_{i=1}^{N} \mathbb{I}\left(\sup_{s \in [t-10,\, t]} \big(-Z_i(s)\big) \ge \vert{}Z_{\text{pánico}}\vert{} \;\land\; \Delta P_{i, 60\text{s}}(s) \le -0.45\%\right) \ge 3$$
activando instantáneamente el bloqueo global y la evacuación de posiciones sin esperar a que `BTC/USDT:USDT` perfore $Z \le -4.0$.

---

## 3. Genealogía Evolutiva Completa del Sistema (V1.0 a V6.3.0)

| Versión | Hito Arquitectónico | Innovaciones y Remediaciones Implementadas |
| :--- | :--- | :--- |
| **V1.0 – V2.0** | Fase de Laboratorio | Prototipo en *Paper Trading* local; identificación del cuello de botella por inferencia LLM local en GPU. |
| **V3.0 – V4.0** | Telemetría LPU y Cloud | Delegación a Groq LPU (`openai/gpt-oss-20b`), escaneo multipar WebSocket, sincronización `chrony` y órdenes `Limit PostOnly`. |
| **V5.0** | Arquitectura Cuántica OFI | Creación del repositorio limpio `SplitBRain-Code`; clase `VentanaZ` en $\mathcal{O}(1)$ ($60\text{ s}$) y filtro $OFI_{L_1}$. |
| **V6.0** | Salidas Dinámicas y UTA | Soporte Bybit UTA (`acknowledged: True`, `reduceOnly: True`), lista blanca `🟩` en Telegram y primer motor de salida temporal. |
| **V6.1** | Adaptive Quantum Predator | `cuantizar_orden` con `Decimal`, Auto-Blacklist (`110126`, `10024`, `10029`), filtro `es_glitch` ($\vert{}Z\vert{}>50$), `PositionManager` y Caja Negra JSONL. |
| **V6.2 – V6.2.3** | Groq RAM Lock-Free & Boot | Hilo demonio `CentinelaGroqRAM` con `frozenset` ($\sim 0.65\ \mu\text{s}$), piso `STD_REL_FLOOR = 0.0005`, `.splitbrain.lock`, `ESCAPE_TEMPORAL` ($300\text{ s}$), `reconciliar_posiciones_exchange()` y auditoría AST en `test_v6_2_suite.py`. |
| **V6.2.4** | Base Estable Zero-REST | Caché `_saldo_libre_ram`, inyección directa de ticker WebSocket, pre-calentamiento de apalancamiento, alertas *fire-and-forget* (`enviar_alerta_bg`), `UMBRAL_OFI_TOXICO = -0.35` y logger con sellado de tiempo dual `[CL | UTC]`. |
| **V6.3.0** | **Anti-Contagio & Tokio HFT** | **1.** Migración a GCP Tokio (`asia-northeast1`) + Kernel HFT (`TCP BBR`, `tcp_slow_start_after_idle=0`, `ZRAM zstd`) + bucle en C `uvloop==0.22.1` + `bucle_keepalive_socket` ($45\text{ s}$).<br>**2.** Evacuación activa de posiciones en crash macro (`evacuar_por_emergencia_macro`).<br>**3.** Detector de contagio simultáneo cross-asset ($\ge 3$ pares en $10\text{ s}$).<br>**4.** Cooldown Post-Cierre de $300\text{ s}$ por símbolo (`COOLDOWN_POST_CIERRE_SEG = 300`).<br>**5.** Fin del "Valle de la Muerte": Micro-Break-Even a $+0.48\%$ ($+0.12\%$ asegurado) y Trailing a $+0.80\%$ (dist. $0.35\%$).<br>**6.** Rotación multi-modelo en Groq ante Error 429 (`gpt-oss-20b` $\to$ `llama-3.3-70b` $\to$ `llama-3.1-8b`).<br>**7.** Filtro de lote mínimo en `main.py` (expulsión automática de `SOL`, `ZEC`, `BTW`), cotización *Penny-Jump* (`best_bid + 1 tick`), espera reducida a $10\text{ s}$, blindaje de propiedad de `.splitbrain.lock` y métricas $\text{MAP}/\text{LVR}$. |

---

## 4. Auditoría Forense de Producción: De los Vectores de Pérdida V6.2.4 a la Validación en Vivo de V6.3.0 (Trades #1 a #83)

### 4.1. Diagnóstico de los 79 Trades Pre-Upgrade (`splitbrain_stats_v6.jsonl` y `transacciones Bybit.txt`)
El análisis exhaustivo de las primeras 79 operaciones cerradas en producción demostró que:
1. **Eficacia de los Motores de Captura y Defensa:** Los cierres por `TRAILING` tuvieron un **100% de Win Rate** (`+0.8119 USDT` en 4 trades explosivos), `BREAK_EVEN` tuvo un **100% de Win Rate**, y `OFI_EXIT` actuó como un cortafuegos quirúrgico cerrando 8 desplomes tóxicos con una pérdida media de apenas `-0.20%` (`-0.0165 USDT`) en lugar de `-2.50%`.
2. **Aislamiento Determinista del Drawdown:** El $100\%$ de la erosión de capital se concentró en cuatro fenómenos mecánicos que quedaron erradicados en V6.3.0:
   - **Tramo 3 (*Serial Knife-Catching* en `WAL`):** Tres recompras sucesivas durante la misma cascada (`-2.76%`, `-1.51%`, `-1.03%`; `-$0.3652 USDT`) porque el cooldown antiguo de $60\text{ s}$ se medía desde la apertura ($t=0$) y ya había expirado cuando la posición cerraba a los $300\text{ s}$.
   - **Tramo 5 ("Valle de la Muerte" y Error 429 en Groq):** Quince posiciones que subieron entre $+0.40\%$ y $+0.85\%$ no alcanzaron el umbral de $+1.00\%$ de Break-Even y expiraron a los $300\text{ s}$ en leve pérdida tras pagar comisión Taker ($0.055\%$), mientras `openai/gpt-oss-20b` arrojaba error HTTP 429 por agotar la cuota de $200,000\text{ TPD}$.
   - **Tramo 6 y Olas de Contagio (`02:18`, `02:58` y `03:43 UTC`):** Las caídas simultáneas de $\ge 3$ altcoins y el colapso de BTC encontraron posiciones largas abiertas sin mecanismo de evacuación activa.
   - **Inanición por Lote Mínimo (`ZEC` y `BTW`) y Bug de `.splitbrain.lock`:** `BTW` abortó más de 18 veces por requerir $\sim \$23.6\text{ USDT}$, mientras que un intento de doble arranque a las `03:55:30 UTC` ejecutó `sys.exit(1)` y eliminó accidentalmente el archivo `.splitbrain.lock` en el bloque `finally`.

### 4.2. Certificación Empírica en Fuego Real de la Versión V6.3.0 en Tokio (Trades #80 a #83)
Tras aplicar el acondicionamiento de kernel en `sniper-tokio` (`asia-northeast1`), superar las **10/10 pruebas** de `test_v6_2_suite.py` y arrancar con `PID 1875 (Loop: Loop)`, los primeros 17 minutos de operación real (`06:36:54` a `06:53:53 UTC`) validaron en vivo cada mejora:

| Componente V6.3.0 | Evidencia Empírica Registrada en `bot_hft.log` (`06:36 – 06:53 UTC`) | Impacto Cuantitativo Verificado |
| :--- | :--- | :--- |
| **Filtro de Lote Mínimo (`main.py`)** | `[MAIN] Filtro de lote mínimo V6.3.0 excluyó pares indivisibles: SOL/USDT:USDT, ZEC/USDT:USDT, BTW/USDT:USDT` | **0 abortos por munición insuficiente de lote**; inclusión automática de `ZEREBRO`, `UNI` y `LINK`. |
| **Latencia RTT en Tokio + `uvloop` + `Keep-Alive`** | Disparos en `ZEREBRO` (`114.0 ms`), `ENA` (`109.0 ms`), `PUMPFUN` (`101.3 ms`), `WAL` (`97.0 ms`) y sync SL (`98.0 ms`). | **Reducción del 64%–77% en latencia máxima de disparo** (de `298–417 ms` a `97–114 ms`). |
| **Liberación Rápida de Órdenes No Llenadas (`10s`)** | `[06:40:24 UTC] Compra en PUMPFUN/USDT:USDT no llenada en 10s: margen liberado.` | Reducción del tiempo de bloqueo de capital de `30.8 s` a **`10.9 s`**. |
| **Cooldown Post-Cierre (`300s`) Anti-Knife-Catching** | Tras cerrar `ZEREBRO` (Trade #80) a las `06:44:06 UTC`, el radar interceptó y bloqueó **11 intentos de recompra tóxica** entre `06:45:23` y `06:48:53 UTC`. | Evitó recomprar `ZEREBRO` en plena cascada bajista y reservó el margen para el Trade ganador #83 en `WAL`. |
| **Micro-Break-Even (`+0.48%`) y Trailing (`+0.80%`)** | **Trade #82 (`PUMPFUN`):** Armó Micro-BE a `+0.49%` y cerró en **`+0.35%` (`+0.0252 USDT`)**.<br>**Trade #83 (`WAL`):** Armó Micro-BE en $9\text{ s}$ (`+0.49%`), activó Trailing a **`+0.82%`**, subió el SL en Bybit 7 veces y cerró en **`+0.90%` (`+0.1054 USDT`)**. | **Validación directa del fin del "Valle de la Muerte":** un rebote de `+0.82%` que bajo V6.2.4 jamás habría activado el Trailing (`+1.50%`) fue capturado limpiamente en `116s`. |

---

## 5. Ingeniería de Infraestructura de Baja Latencia en `sniper-tokio` (`asia-northeast1`)

La instancia de producción opera sobre `ubuntu-minimal-2604-resolute-amd64` (`e2-micro`, 1 GB RAM, 20 GB SSD) en la región **`asia-northeast1` (Tokio)** con las siguientes optimizaciones de sistema aplicadas mediante `optimizar_vm_hft.sh`:

1. **Pila TCP de Baja Latencia (`/etc/sysctl.d/99-splitbrain-hft.conf`):**
   - `net.core.default_qdisc = fq` y `net.ipv4.tcp_congestion_control = bbr` (control de congestión Google BBR).
   - `net.ipv4.tcp_slow_start_after_idle = 0` (**Crítico HFT**: impide que el kernel Linux colapse la ventana de congestión TCP tras periodos sin enviar órdenes REST).
   - `net.ipv4.tcp_fastopen = 3`, `net.ipv4.tcp_tw_reuse = 1` y `tcp_keepalive_time = 30`.
2. **Subsistema de Memoria y Tiempo Atómico:**
   - `zram-tools` activo con algoritmo `zstd` (`476 MiB` de swap comprimida en RAM con prioridad 100 y `vm.swappiness = 10`), manteniendo `> 600 MiB` de memoria disponible libre de paginación a disco.
   - `chrony` sincronizado con `chronyc makestep` (`200 OK`) + `recvWindow: 15000 ms` y `adjustForTimeDifference: True` en `ccxt`.
3. **Runtime CPython Acelerado:**
   - Bucle de eventos `uvloop==0.22.1` (compatible al $100\%$ con `ccxt 4.5.87` verificado vía `pip check`) inyectado automáticamente al inicio de `main.py`.

---

## 6. Hoja de Ruta Técnica hacia V6.4.0 / Fase 3 Cuantitativa

Con la base operativa **V6.3.0 Anti-Contagio** estabilizada y rentabilizando rebotes en Tokio, los siguientes pasos evolutivos de frontera son:

1. **Estacionariedad $I(0)$ mediante Retornos Logarítmicos y Filtrado de Kalman en $\mathcal{O}(1)$ (`1_radar_volatilidad.py`):**
   Sustituir el $Z$-Score sobre niveles de precios $P_t \sim I(1)$ por retornos logarítmicos $r_t = \ln(P_t/P_{t-1})$ procesados mediante un filtro de estado latente de Kalman recursivo en $\mathcal{O}(1)$ que separe el precio eficiente verdadero del rebote microestructural bid-ask.
2. **Diferencial Dinámico Cont OFI (Cont, Kukanov & Stoikov, 2014) y Toxicidad VPIN (`1_radar_volatilidad.py`):**
   Reemplazar el desequilibrio instantáneo de colas $L_1$ por la acumulación vectorial de eventos de libro $\Delta LOB_{\text{bid}} - \Delta LOB_{\text{ask}}$ y la Probabilidad de Trading Informado Sincronizada por Volumen ($VPIN$) sobre cubos de volumen constante $V_{\text{bucket}}$, ponderada junto con el ratio de iliquidez de Amihud ($\vert{}R_t\vert{}/\text{Vol}_t$) para discriminar vacíos de liquidez puros frente a cascadas informadas.
3. **Calibración Evolutiva Offline (*Gen-AS* — `calibrador_gen_as.py`):**
   Ejecutar periódicamente un algoritmo genético sobre los registros acumulados en `splitbrain_stats_v6.jsonl` para optimizar el cromosoma de hiperparámetros $(\text{BE\_ACTIVACION\_PCT}, \text{TRAIL\_ACTIVACION\_PCT}, \text{TRAIL\_DISTANCIA\_PCT}, \gamma_{\text{AS}}, k_{\text{AS}})$ maximizando el ratio de Sharpe y la métrica institucional $\text{PnL-to-MAP}$.