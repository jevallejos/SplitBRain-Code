# REPORTE FORENSE DE ATRIBUCIÓN COOPERATIVA DE SHAPLEY (SHAP) Y TELEMETRÍA — ETAPA 4 (`SPLITBRAIN-OMEGA V7.0`)

- **Fecha de Auditoría**: `2026-10-16 20:41:53 UTC`
- **Fuentes Transaccionales Procesadas**: `Semilla Verificada sniper-tokio (Transacciones.txt #275)` (`45` registros analizados | Producción `sniper-tokio`: `275 trades, 155W / 120L, 56.4% Win Rate, Balance 10.7425 USDT`)
- **Baseline Sin Filtros $v(\emptyset)$**: `45 trades` | Win Rate: `64.44%` | PnL Muestra: `+0.8428 USDT` | Esperanza: `+0.0187 USDT/trade`
- **Gran Coalición Activa $v(N)$ (`V6.4.3`)**: `31 trades` | Win Rate: **`77.42%`** | PnL Muestra: **`+1.8176 USDT`** | Esperanza: **`+0.0586 USDT/trade`**
- **Ganancia Marginal Total de la Arquitectura ($v(N) - v(\emptyset)$)**: **`+0.9747 USDT`** (`+12.97%` en Win Rate)

---

## 1. MATRIZ EXACTA DE VALORES DE SHAPLEY ($\phi_i$) SOBRE LAS $2^5 = 32$ COALICIONES

| Compuerta / Mecanismo Cooperativo ($i \in N$) | $\phi_i(\text{PnL Total})$ [USDT] | $\phi_i(\text{Win Rate})$ [%] | $\phi_i(\text{Esperanza})$ [USDT/trade] | Veredicto Cuantitativo |
| :--- | :---: | :---: | :---: | :--- |
| **G5: Jerarquía SL (-1.15%/-1.65%) + Anti-Knife 900s** | **`+0.8203 USDT`** | **`+1.16%`** | `+0.02404` | Impulsor Primario de Alfa |
| **G1: Purga Drenadores OOS (Replicator Dynamics)** | **`+0.3115 USDT`** | **`+7.44%`** | `+0.01228` | Impulsor Primario de Alfa |
| **G4: Motor Maker-Unwind PostOnly (Almgren-Chriss)** | **`+0.2497 USDT`** | **`+0.00%`** | `+0.00615` | Impulsor Primario de Alfa |
| **G3: Absorción OFI >= +0.08 (Glosten-Milgrom)** | **`-0.5054 USDT`** | **`-1.53%`** | `-0.01132` | Filtro Protector de Cola |
| **G2: Tiering Z-Score (Campbell-Thompson OOS)** | **`+0.0986 USDT`** | **`+5.90%`** | `+0.00876` | Filtro Protector de Cola |
| **SUMA AXIOMÁTICA DE EFICIENCIA ($\sum \phi_i = v(N) - v(\emptyset)$)** | **`+0.9747 USDT`** | **`+12.97%`** | **`+0.03990`** | **100% Verificado (Pareto)** |

---

## 2. MATRIZ DE DINÁMICA DEL REPLICADOR POR ACTIVO ($\dot{x}_i = x_i(E_i(\mathbf{x}) - \bar{E}(\mathbf{x}))$)

| Activo (`Symbol`) | Trades | Win Rate (%) | PnL Neto (USDT) | Comisiones (USDT) | Esperanza $E_i$ (USDT) | Ventaja Replicador $E_i - \bar{E}$ | Clasificación `V6.4.3` |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `WAL/USDT:USDT` | 11 | `72.7%` | `+0.8160` | `0.0753` | `+0.0742` | `+0.0540` | 💎 NÚCLEO ALFA (Z <= -2.85) |
| `ZEREBRO/USDT:USDT` | 21 | `66.7%` | `+0.2710` | `0.1367` | `+0.0129` | `-0.0073` | 💎 NÚCLEO ALFA (Z <= -2.85) |
| `INJ/USDT:USDT` | 3 | `100.0%` | `+0.1509` | `0.0171` | `+0.0503` | `+0.0301` | 💎 NÚCLEO ALFA (Z <= -2.85) |
| `STRK/USDT:USDT` | 4 | `75.0%` | `+0.1159` | `0.0262` | `+0.0290` | `+0.0087` | 💎 NÚCLEO ALFA (Z <= -2.85) |
| `TIA/USDT:USDT` | 1 | `100.0%` | `+0.0340` | `0.0084` | `+0.0340` | `+0.0138` | 💎 NÚCLEO ALFA (Z <= -2.85) |
| `ADA/USDT:USDT` | 1 | `0.0%` | `-0.0387` | `0.0057` | `-0.0387` | `-0.0589` | ⚖️ SECUNDARIO OOS (Z <= -3.15) |
| `ENA/USDT:USDT` | 1 | `0.0%` | `-0.0422` | `0.0078` | `-0.0422` | `-0.0625` | ⚖️ SECUNDARIO OOS (Z <= -3.15) |
| `ZRO/USDT:USDT` | 1 | `0.0%` | `-0.0855` | `0.0086` | `-0.0855` | `-0.1057` | 🚫 VETADO (Blacklist OOS) |
| `ONDO/USDT:USDT` | 1 | `0.0%` | `-0.1108` | `0.0052` | `-0.1108` | `-0.1310` | 🚫 VETADO (Blacklist OOS) |
| `DOGE/USDT:USDT` | 1 | `0.0%` | `-0.2002` | `0.0053` | `-0.2002` | `-0.2204` | 🚫 VETADO (Blacklist OOS) |

---

## 3. AUDITORÍA MICROESTRUCTURAL POR MOTIVO DE CIERRE Y AHORRO MAKER-UNWIND

| Motivo de Salida (`motivo`) | Operaciones | Win Rate (%) | PnL Acumulado (USDT) | Hold Medio (s) | Fee Medio (USDT) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `TRAILING` | 9 | `100.0%` | `+1.9602` | `135.2s` | `0.0085` |
| `MAKER_UNWIND` | 17 | `100.0%` | `+0.9901` | `58.8s` | `0.0046` |
| `ESCAPE_HUERFANA_BOOT` | 2 | `0.0%` | `-0.0809` | `19985.8s` | `0.0067` |
| `EARLY_TOXIC_SL` | 2 | `0.0%` | `-0.2953` | `83.4s` | `0.0087` |
| `ESCAPE_TEMPORAL` | 4 | `25.0%` | `-0.4833` | `270.6s` | `0.0077` |
| `SL_EXCHANGE` | 8 | `25.0%` | `-0.5883` | `37.8s` | `0.0081` |
| `SL` | 3 | `0.0%` | `-0.5922` | `194.5s` | `0.0054` |

---

## 4. DIAGNÓSTICO DE CUELLOS DE BOTELLA DE ENTRADA (`BOT_LOG.TXT`) RESUELTOS EN `V6.4.3`

- **Intercepciones Totales `[MEMORIA HAWKES]` Analizadas en Logs**: `21` eventos.
- **Oportunidades de Alta Absorción (`I_Hawkes >= +0.18` o Clímax `Z <= -4.00`) Desbloqueadas en `V6.4.3`**: **`18` disparos directos** (anteriormente retenidos por el cronómetro fijo de `1.0s < 3.2s`).
- **Órdenes `Limit Buy PostOnly` No Llenadas en 10s (Objetivo de `Re-Quote 2.0s`)**: `2` órdenes (`{"ZEREBRO/USDT:USDT": 1, "INJ/USDT:USDT": 1}`).
- **Activaciones del Circuit Breaker de Contagio Cross-Asset**: `8` eventos (`174` anomalías suprimidas durante ventanas de contagio).
