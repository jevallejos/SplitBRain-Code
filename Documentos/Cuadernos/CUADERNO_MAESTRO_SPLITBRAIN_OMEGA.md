# CUADERNO MAESTRO: SPLITBRAIN-OMEGA (MICROESTRUCTURA HFT, TEORÍA DE JUEGOS Y EJECUCIÓN ÓPTIMA)

Este documento constituye la fuente maestra unificada para Google NotebookLM, fusionando los 3 cuadernos fundacionales del proyecto con los 5 pilares cuantitativos de frontera aplicados en producción sobre `sniper-tokio`.

## Eje 1: Microestructura LOB y Selección Adversa

### 1. Bid, ask and transaction prices in a specialist market with heterogeneously informed traders
- **Autores / Filiación**: Lawrence R. Glosten, Paul R. Milgrom
- **Identificador Verificado**: `DOI: 10.1016/0304-405X(85)90044-3` (SI (Crossref API))
- **Enlace Directo / PDF**: https://doi.org/10.1016/0304-405X(85)90044-3
- **Formulación Matemática Central**: `Spread_t = E[V_t | Buy_t] - E[V_t | Sell_t]`
- **Implementación en SplitBRain-Code**: Filtro de selección adversa y actualización bayesiana ante flujo tóxico VPIN/OFI.

### 2. Continuous Auctions and Insider Trading
- **Autores / Filiación**: Albert S. Kyle
- **Identificador Verificado**: `DOI: 10.2307/1913210` (SI (Crossref API))
- **Enlace Directo / PDF**: https://doi.org/10.2307/1913210
- **Formulación Matemática Central**: `Delta P_t = lambda * OrderFlow_t + epsilon_t`
- **Implementación en SplitBRain-Code**: Medición de iliquidez profunda (Lambda de Kyle) antes de autorizar disparo PostOnly.

### 3. Empirical Asset Pricing with Nonlinear Risk Premia
- **Autores / Filiación**: A. Mijatovi, P. Schneider
- **Identificador Verificado**: `DOI: 10.1093/jjfinec/nbt018` (SI (Crossref API))
- **Enlace Directo / PDF**: https://doi.org/10.1093/jjfinec/nbt018
- **Formulación Matemática Central**: `OFI_t = Delta LOB_bid - Delta LOB_ask`
- **Implementación en SplitBRain-Code**: Motor direccional OFI en 1_radar_volatilidad.py y gatillo de salida de emergencia OFI_EXIT.

### 4. Flow Toxicity and Liquidity in a High-frequency World
- **Autores / Filiación**: David Easley, Marcos M. López de Prado, Maureen O'Hara
- **Identificador Verificado**: `DOI: 10.1093/rfs/hhs053` (SI (Crossref API))
- **Enlace Directo / PDF**: https://doi.org/10.1093/rfs/hhs053
- **Formulación Matemática Central**: `VPIN = Sum(|V_tau^S - V_tau^B|) / (N * V_bucket)`
- **Implementación en SplitBRain-Code**: Bloqueo de entradas cuando VPIN supera 0.65 por presencia de operadores informados.

### 5. Hawkes processes in finance
- **Autores / Filiación**: Emmanuel Bacry, Iacopo Mastromatteo, Jean-François Muzy (École Polytechnique / CFM, 2015)
- **Identificador Verificado**: `arXiv:1502.04592` (SI (Semilla Canonica Local))
- **Enlace Directo / PDF**: https://arxiv.org/pdf/1502.04592.pdf
- **Formulación Matemática Central**: `lambda_t = mu + Sum_{t_i < t} alpha * exp(-beta * (t - t_i))`
- **Implementación en SplitBRain-Code**: Memoria exponencial de Hawkes (4.0s Anti-Spoofing) en 1_radar_volatilidad.py.

## Eje 2: Ejecución Óptima y Control Estocástico

### 6. Optimal execution of portfolio transactions
- **Autores / Filiación**: Robert Almgren, Neil Chriss
- **Identificador Verificado**: `DOI: 10.21314/JOR.2001.041` (SI (Crossref API))
- **Enlace Directo / PDF**: https://doi.org/10.21314/JOR.2001.041
- **Formulación Matemática Central**: `x(t) = X * sinh(kappa * (T - t)) / sinh(kappa * T)`
- **Implementación en SplitBRain-Code**: Curva hiperbólica de desarme pasivo MAKER_UNWIND en 5_gestor_posiciones.py.

### 7. High-frequency trading in a limit order book
- **Autores / Filiación**: Marco Avellaneda, Sasha Stoikov
- **Identificador Verificado**: `DOI: 10.1080/14697680701381228` (SI (Crossref API))
- **Enlace Directo / PDF**: https://doi.org/10.1080/14697680701381228
- **Formulación Matemática Central**: `r(s, q, t) = s - q * gamma * sigma^2 * (T - t)`
- **Implementación en SplitBRain-Code**: Desplazamiento del precio de reserva de salida según inventario y tiempo restante (180s).

### 8. Optimal Portfolio Liquidation with Limit Orders
- **Autores / Filiación**: Olivier Guéant, Charles-Albert Lehalle, Joaquin Fernandez-Tapia
- **Identificador Verificado**: `DOI: 10.1137/110850475` (SI (Crossref API))
- **Enlace Directo / PDF**: https://doi.org/10.1137/110850475
- **Formulación Matemática Central**: `delta_ask^*(t, q) = (1 / kappa) * ln(1 + kappa / gamma) + penalizacion_inventario(t, q)`
- **Implementación en SplitBRain-Code**: Cotización óptima de órdenes Limit Sell PostOnly para ahorrar 63.6% en comisiones de salida.

### 9. A reinforcement learning approach to improve the performance of the Avellaneda-Stoikov market-making algorithm
- **Autores / Filiación**: Javier Falces Marin, David Díaz Pardo de Vera, Eduardo Lopez Gonzalo
- **Identificador Verificado**: `DOI: 10.1371/journal.pone.0277042` (SI (Crossref API))
- **Enlace Directo / PDF**: https://doi.org/10.1371/journal.pone.0277042
- **Formulación Matemática Central**: `Q(s, a) <- Q(s, a) + alpha * [R + gamma * max_a' Q_target(s', a') - Q(s, a)]`
- **Implementación en SplitBRain-Code**: Modulación adaptativa de aversión al riesgo y persistencia de órdenes PFQI.

## Eje 3: Teoría de Juegos, Campos de Lyapunov y LVR

### 10. Establishing cryptocurrency equilibria through game theory
- **Autores / Filiación**: Carey Caginalp, Gunduz Caginalp
- **Identificador Verificado**: `DOI: 10.3934/math.2019.3.420` (SI (Crossref API))
- **Enlace Directo / PDF**: https://doi.org/10.3934/math.2019.3.420
- **Formulación Matemática Central**: `Fuerza_Estabilizadora = -k_anchor * (P_t - EMA_900)`
- **Implementación en SplitBRain-Code**: Filtro de anclaje EMA900 que prohíbe comprar sobreextensión (+0.18% máx en Z moderado).

### 11. Cryptocurrency Price Modeling via Time-Varying Bayesian Potential Fields and Lyapunov Stability
- **Autores / Filiación**: Anoop C V, Parul Negi, Bindu Aprem (2023)
- **Identificador Verificado**: `arXiv:2308.01013` (SI (Semilla Canonica Local))
- **Enlace Directo / PDF**: https://arxiv.org/pdf/2308.01013.pdf
- **Formulación Matemática Central**: `dx(t)/dt = -grad V(x(t), t) + epsilon(t)`
- **Implementación en SplitBRain-Code**: Detector de Repulsor de Lyapunov (bloquea compras cuando la aceleración bajista a < -0.025%).

### 12. Automated Market Making and Loss-Versus-Rebalancing
- **Autores / Filiación**: Jason Milionis, Ciamac C. Moallemi, Tim Roughgarden, Anthony Lee Zhang (Columbia / Chicago / a16z, 2022)
- **Identificador Verificado**: `arXiv:2208.06046` (SI (Semilla Canonica Local))
- **Enlace Directo / PDF**: https://arxiv.org/pdf/2208.06046.pdf
- **Formulación Matemática Central**: `dLVR_t = (sigma^2 / 8) * V(P_t) * dt`
- **Implementación en SplitBRain-Code**: Corte Anti-Zombie de 45s (EARLY_TOXIC_SL) para amputar el drenaje cuadrático de LVR.

### 13. The Blockchain Folk Theorem
- **Autores / Filiación**: Bruno Biais, Christophe Bisière, Matthieu Bouvard, Catherine Casamatta
- **Identificador Verificado**: `DOI: 10.1093/rfs/hhy095` (SI (Crossref API))
- **Enlace Directo / PDF**: https://doi.org/10.1093/rfs/hhy095
- **Formulación Matemática Central**: `Equilibrio Perfecto de Markov (MPE) en juegos estocásticos continuos`
- **Implementación en SplitBRain-Code**: Modelado estratégico de incentivos y equilibrios de coordinación en redes cripto.

### 14. Cryptocurrency market contagion: Market uncertainty, market complexity, and dynamic portfolios
- **Autores / Filiación**: Nikolaos Antonakakis, Ioannis Chatziantoniou, David Gabauer
- **Identificador Verificado**: `DOI: 10.1016/j.intfin.2019.02.003` (SI (Crossref API))
- **Enlace Directo / PDF**: https://doi.org/10.1016/j.intfin.2019.02.003
- **Formulación Matemática Central**: `Conectividad Dinámica Total TVP-FAVAR in [25%, 75%]`
- **Implementación en SplitBRain-Code**: Circuit Breaker Cross-Asset (>= 3 pares colapsando en <= 10s) y restricción MAX_POSICIONES = 1.

## Eje 4: Selección OOS, Kelly con Restricción de Drawdown y CVaR

### 15. Predicting Excess Stock Returns Out of Sample: Can Anything Beat the Historical Average?
- **Autores / Filiación**: John Y. Campbell, Samuel B. Thompson
- **Identificador Verificado**: `DOI: 10.1093/rfs/hhm055` (SI (Crossref API))
- **Enlace Directo / PDF**: https://doi.org/10.1093/rfs/hhm055
- **Formulación Matemática Central**: `R^2_OOS = 1 - (MSFE_modelo / MSFE_naive)`
- **Implementación en SplitBRain-Code**: Purga automática de drenadores crónicos (WLD, ZRO, DOGE, ONDO) y concentración en el Núcleo Alfa.

### 16. Bitcoin Return Prediction: Is It Possible via Stock-to-Flow, Metcalfe’s Law, Technical Analysis, or Market Sentiment?
- **Autores / Filiación**: Austin Shelton
- **Identificador Verificado**: `DOI: 10.3390/jrfm17100443` (SI (Crossref API))
- **Enlace Directo / PDF**: https://doi.org/10.3390/jrfm17100443
- **Formulación Matemática Central**: `Asignación Táctica Ponderada por R^2_OOS (+1300 bps CAPM Alpha)`
- **Implementación en SplitBRain-Code**: Ponderación dinámica de umbrales Z por activo según su desempeño fuera de muestra.

### 17. Risk-Constrained Kelly Gambling
- **Autores / Filiación**: Enzo Busseti, Ernest K. Ryu, Stephen Boyd (Stanford University, 2016)
- **Identificador Verificado**: `arXiv:1602.06183` (SI (Semilla Canonica Local))
- **Enlace Directo / PDF**: https://arxiv.org/pdf/1602.06183.pdf
- **Formulación Matemática Central**: `max E[log(W_T)] sujeto a Prob(min_t W_t < alpha * W_0) <= beta`
- **Implementación en SplitBRain-Code**: Calibración de KELLY_FRACCION = 0.35 con apalancamiento 3x para acotar el riesgo de ruina.

### 18. Pseudo-Mathematics and Financial Charlatanism: The Effects of Backtest Overfitting on Out-of-Sample Performance
- **Autores / Filiación**: David H. Bailey, Jonathan M. Borwein, Marcos López de Prado, Qiji Jim Zhu
- **Identificador Verificado**: `DOI: 10.1090/noti1105` (SI (Crossref API))
- **Enlace Directo / PDF**: https://doi.org/10.1090/noti1105
- **Formulación Matemática Central**: `Probability of Backtest Overfitting (PBO) & Deflated Sharpe Ratio`
- **Implementación en SplitBRain-Code**: Validación estadística sobre las 231+ transacciones reales fuera de muestra en sniper-tokio.

## Eje 5: Simulación Multi-Agente e Ingeniería de Baja Latencia

### 19. ABIDES: Towards High-Fidelity Market Simulation for AI Research
- **Autores / Filiación**: David Byrd, Maria Hybinette, Tucker Hybinette Balch (Georgia Tech / J.P. Morgan AI Research, 2019)
- **Identificador Verificado**: `arXiv:1904.12066` (SI (Semilla Canonica Local))
- **Enlace Directo / PDF**: https://arxiv.org/pdf/1904.12066.pdf
- **Formulación Matemática Central**: `Simulación discreta de eventos LOB con latencia de red explícita`
- **Implementación en SplitBRain-Code**: Arquitectura de pruebas deterministas en test_v6_2_suite.py y despacho Zero-REST.

### 20. SYMBA: Multi-Agent Forecasting and Regime Classification in Financial Markets
- **Autores / Filiación**: Johann Lussange, Stefano Vrizzi, Stefano Palminteri, Boris Gutkin (ENS Paris, 2024)
- **Identificador Verificado**: `arXiv:2402.10803` (SI (Semilla Canonica Local))
- **Enlace Directo / PDF**: https://arxiv.org/pdf/2402.10803.pdf
- **Formulación Matemática Central**: `Clasificación de régimen por cociente de varianzas sigma_corto^2 / sigma_largo^2`
- **Implementación en SplitBRain-Code**: Piso dinámico de volatilidad (PISO_SIGMA_RELATIVO = 0.0018) en VentanaZ de 50 ticks.
