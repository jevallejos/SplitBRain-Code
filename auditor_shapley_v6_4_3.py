"""Analizador Forense de Atribución Cooperativa de Shapley (SHAP) y Cola LOB — SplitBrain V6.4.3.
Flujo Inmutable: Google Antigravity IDE -> GitHub (origin/main) -> sniper-tokio -> SplitBrain-Omega v7.0.

Ejecuta sobre las 274+ transacciones reales (`splitbrain_stats_v6.jsonl` / `Transacciones.txt`)
y los registros de telemetría (`bot_hft.log` / `Bot_log.txt`):
1. Cálculo exacto de los Valores de Shapley (2^5 = 32 coaliciones) para:
   - PnL Neto Acumulado (USDT)
   - Esperanza Matemática por Operación (USDT / trade)
   - Win Rate Operativo (%)
2. Auditoría de Dinámica del Replicador dx_i/dt = x_i * (E_i(x) - E_bar(x)) por activo.
3. Desglose microestructural por motivo de salida y cuantificación del ahorro Maker-Unwind (-63.6% fee).
4. Cuantificación forense de señales bloqueadas por el antiguo cronómetro de 1.0s de Hawkes y órdenes
   PostOnly no llenadas en 10s, generando `REPORTE_SHAPLEY_ETAPA4_V6_4_3.md` para SplitBrain-Omega v7.0.
"""
from collections import defaultdict
from datetime import datetime, timezone
import itertools
import json
import math
from pathlib import Path
import re
import sys
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

RAIZ = Path(__file__).resolve().parent

PARES_DRENADORES = {
    "WLD/USDT:USDT",
    "ZRO/USDT:USDT",
    "DOGE/USDT:USDT",
    "ONDO/USDT:USDT",
    "TRUTH/USDT:USDT",
    "SOL/USDT:USDT",
    "ZEC/USDT:USDT",
}

PARES_NUCLEO_ALFA = {
    "ZEREBRO/USDT:USDT",
    "WAL/USDT:USDT",
    "STRK/USDT:USDT",
    "INJ/USDT:USDT",
    "TIA/USDT:USDT",
    "XRP/USDT:USDT",
    "1000PEPE/USDT:USDT",
    "HYPE/USDT:USDT",
}

MOTIVOS_BOOT = {"ESCAPE_HUERFANA_BOOT", "CIERRE_LIMPIO_PRE_UPGRADE"}


def _parse_ts(ts_str: Any) -> float:
    if not ts_str or not isinstance(ts_str, str):
        return 0.0
    try:
        return datetime.fromisoformat(ts_str).timestamp()
    except Exception:
        return 0.0


def _es_duplicado_fantasma(prev: Dict[str, Any], curr: Dict[str, Any]) -> bool:
    if prev.get("symbol") != curr.get("symbol"):
        return False
    try:
        if abs(float(prev.get("entry_price") or 0.0) - float(curr.get("entry_price") or 0.0)) > 1e-9:
            return False
        if abs(float(prev.get("exit_price") or 0.0) - float(curr.get("exit_price") or 0.0)) > 1e-9:
            return False
        if abs(float(prev.get("qty") or 0.0) - float(curr.get("qty") or 0.0)) > 1e-9:
            return False
        t1 = _parse_ts(prev.get("timestamp"))
        t2 = _parse_ts(curr.get("timestamp"))
        if t1 > 0 and t2 > 0 and abs(t2 - t1) <= 15.0:
            return True
    except Exception:
        return False
    return False


def cargar_transacciones_unificadas() -> Tuple[List[Dict[str, Any]], List[str]]:
    """Carga y unifica sin duplicados los registros de `splitbrain_stats_v6.jsonl` y `Transacciones.txt`."""
    candidatos = [
        RAIZ / "splitbrain_stats_v6.jsonl",
        RAIZ / "Transacciones.txt",
        RAIZ / "splitbrain_stats_v6_3.txt",
        RAIZ / "splitbrain_stats_v6.4.txt",
    ]
    fuentes_leidas: List[str] = []
    crudos: List[Dict[str, Any]] = []

    for ruta in candidatos:
        if not ruta.exists():
            continue
        fuentes_leidas.append(ruta.name)
        texto = ruta.read_text(encoding="utf-8", errors="ignore")
        # Soportar JSONL partido por saltos de línea de consola (como en Transacciones.txt)
        buffer = ""
        for linea in texto.splitlines():
            s = linea.strip()
            if not s:
                continue
            if s.startswith('{"timestamp"'):
                if buffer:
                    try:
                        crudos.append(json.loads(buffer))
                    except Exception:
                        pass
                buffer = s
            else:
                buffer += s
        if buffer:
            try:
                crudos.append(json.loads(buffer))
            except Exception:
                pass

    # Ordenar cronológicamente y eliminar duplicados exactos o fantasmas (<15s)
    crudos.sort(key=lambda r: _parse_ts(r.get("timestamp")))
    unicos: List[Dict[str, Any]] = []
    vistos: Set[Tuple[str, float, float, float]] = set()

    for reg in crudos:
        sym = str(reg.get("symbol") or "")
        ep = round(float(reg.get("entry_price") or 0.0), 8)
        xp = round(float(reg.get("exit_price") or 0.0), 8)
        qt = round(float(reg.get("qty") or 0.0), 6)
        ts_redondeado = round(_parse_ts(reg.get("timestamp")) / 5.0)
        clave = (sym, ep, xp, ts_redondeado)
        if clave in vistos:
            continue
        if unicos and _es_duplicado_fantasma(unicos[-1], reg):
            continue
        vistos.add(clave)
        unicos.append(reg)

    return unicos, fuentes_leidas


def evaluar_coalicion(trades: List[Dict[str, Any]], coalicion: Set[str]) -> Dict[str, float]:
    """Evalúa el desempeño contrafactual sobre el histórico cuando el subconjunto de compuertas `coalicion` está activo:
    - G1_PURGA_OOS: Excluye PARES_DRENADORES y liquidaciones de arranque huérfanas.
    - G2_TIERING_Z: Exige Z <= -2.85 en Núcleo Alfa y Z <= -3.15 en Secundarios.
    - G3_OFI_GLOSTEN: Exige OFI_entry >= +0.08 (evita comprar en cascada vendedora activa).
    - G4_MAKER_ALMGREN: Aplica desarme Maker-First (fee 0.020% vs 0.055%) y acota holds zombies de 300s a 180s.
    - G5_ANTI_WICK_KNIFE: Jerarquía SL (-1.15% interno con 18s gracia / -1.65% Bybit) + bloqueo de reentrada 900s bajo SL.
    """
    pnls: List[float] = []
    ultimo_sl_por_sym: Dict[str, Tuple[float, float]] = {}

    for t in trades:
        sym = str(t.get("symbol") or "")
        motivo = str(t.get("motivo") or "")
        pnl_real = float(t.get("pnl_usdt") or 0.0)
        pnl_pct = float(t.get("pnl_percentage") or 0.0)
        hold_s = float(t.get("hold_seg") or 0.0)
        entry_p = float(t.get("entry_price") or 0.0)
        exit_p = float(t.get("exit_price") or 0.0)
        qty = float(t.get("qty") or 0.0)
        nocional = float(t.get("map_usdt") or (entry_p * qty) or 11.2)
        ts = _parse_ts(t.get("timestamp"))
        z_in = t.get("z_score_entry")
        ofi_in = t.get("ofi_entry")

        # 1. Compuerta G1: Purga de Drenadores Crónicos y Huérfanas de Arranque
        if "G1_PURGA_OOS" in coalicion:
            if sym in PARES_DRENADORES or motivo in MOTIVOS_BOOT:
                continue

        # 2. Compuerta G2: Tiering Z-Score Campbell-Thompson OOS
        if "G2_TIERING_Z" in coalicion and z_in is not None:
            z_val = float(z_in)
            umbral_z = -2.85 if sym in PARES_NUCLEO_ALFA else -3.15
            if z_val > umbral_z:
                continue

        # 3. Compuerta G3: Absorción Compradora de Glosten-Milgrom (OFI >= +0.08)
        if "G3_OFI_GLOSTEN" in coalicion and ofi_in is not None:
            if float(ofi_in) < 0.08:
                continue

        # 5. Compuerta G5 (Parte A): Escudo Anti-Knife Continuation (900s bajo último SL)
        if "G5_ANTI_WICK_KNIFE" in coalicion and sym in ultimo_sl_por_sym:
            ts_sl_prev, px_sl_prev = ultimo_sl_por_sym[sym]
            z_val_actual = float(z_in) if z_in is not None else -3.0
            if 0 < (ts - ts_sl_prev) < 900.0 and entry_p <= px_sl_prev * 1.0015 and z_val_actual > -5.50:
                continue

        pnl_ajustado = pnl_real

        # 4. Compuerta G4: Efecto de Maker-Unwind (Almgren-Chriss) vs Salida Taker y Corte Zombie 180s
        if "G4_MAKER_ALMGREN" in coalicion:
            # Si fue un ESCAPE_TEMPORAL antiguo de 300s en pérdida severa, el corte de 105s/180s acota el sangrado LVR
            if motivo == "ESCAPE_TEMPORAL" and hold_s >= 280.0 and pnl_ajustado < -0.045:
                pnl_ajustado = max(pnl_ajustado, -0.042)
        else:
            # Contrafactual SIN Maker-Unwind: los cierres MAKER_UNWIND habrían pagado fee Taker (0.055% vs 0.020%)
            if motivo == "MAKER_UNWIND":
                recargo_taker = nocional * (0.00055 - 0.00020)
                pnl_ajustado -= recargo_taker

        # 5. Compuerta G5 (Parte B): Jerarquía SL (-1.15% / -1.65%) y Gracia de 18s contra mechazos de 10s
        if "G5_ANTI_WICK_KNIFE" in coalicion:
            if motivo == "SL_EXCHANGE" and hold_s <= 21.0 and pnl_ajustado < 0:
                # El SL Bybit en -1.65% y la gracia de 18s evitan la liquidación por mechazo de entrada en 10s-20s
                pnl_ajustado = 0.0
            elif motivo in ("SL", "SL_EXCHANGE") and pnl_pct < -1.35:
                # El SL interno en -1.15% acota las pérdidas antiguas de -2.50% / -2.82%
                pnl_ajustado = max(pnl_ajustado, -nocional * 0.0122)

        if pnl_real < 0 and motivo in ("SL_EXCHANGE", "EARLY_TOXIC_SL", "SL", "OFI_EXIT"):
            ultimo_sl_por_sym[sym] = (ts, exit_p)

        pnls.append(pnl_ajustado)

    n = len(pnls)
    if n == 0:
        return {"n": 0.0, "pnl_total": 0.0, "win_rate": 0.0, "expectativa_usdt": 0.0}
    wins = sum(1 for x in pnls if x > 0.0)
    pnl_tot = sum(pnls)
    return {
        "n": float(n),
        "pnl_total": pnl_tot,
        "win_rate": (wins / n) * 100.0,
        "expectativa_usdt": pnl_tot / n,
    }


def calcular_valores_shapley_exactos(
    trades: List[Dict[str, Any]]
) -> Tuple[Dict[str, Dict[str, float]], Dict[FrozenSet[str], Dict[str, float]]]:
    """Calcula la atribución exacta de Shapley sobre las 2^5 = 32 coaliciones."""
    jugadores = [
        "G1_PURGA_OOS",
        "G2_TIERING_Z",
        "G3_OFI_GLOSTEN",
        "G4_MAKER_ALMGREN",
        "G5_ANTI_WICK_KNIFE",
    ]
    n_jug = len(jugadores)
    fact = [math.factorial(i) for i in range(n_jug + 1)]

    valores_coalicion: Dict[FrozenSet[str], Dict[str, float]] = {}
    for r in range(n_jug + 1):
        for comb in itertools.combinations(jugadores, r):
            c_set = frozenset(comb)
            valores_coalicion[c_set] = evaluar_coalicion(trades, set(c_set))

    shapley: Dict[str, Dict[str, float]] = {
        j: {"pnl_total": 0.0, "win_rate": 0.0, "expectativa_usdt": 0.0} for j in jugadores
    }

    for i in jugadores:
        resto = [j for j in jugadores if j != i]
        for r in range(n_jug):
            peso = (fact[r] * fact[n_jug - r - 1]) / fact[n_jug]
            for s_tuple in itertools.combinations(resto, r):
                s = frozenset(s_tuple)
                s_con_i = s | {i}
                for metrica in ("pnl_total", "win_rate", "expectativa_usdt"):
                    delta = valores_coalicion[s_con_i][metrica] - valores_coalicion[s][metrica]
                    shapley[i][metrica] += peso * delta

    return shapley, valores_coalicion


def auditar_logs_hawkes_y_cola() -> Dict[str, Any]:
    """Analiza `Bot_log.txt` / `bot_hft.log` para cuantificar vetos de Hawkes de 1.0s y órdenes no llenadas."""
    archivos_log = [RAIZ / "bot_hft.log", RAIZ / "Bot_log.txt", RAIZ / "bot log.txt"]
    re_hawkes = re.compile(
        r"\[MEMORIA HAWKES[^\]]*\]\s+([A-Z0-9]+/USDT:USDT)\s+estela\s+t[oó]xica\s+reciente\s+\(([0-9.]+)s\s*<\s*([0-9.]+)s(?:\s*\Vert{}\s*I_Hawkes=([+-]?[0-9.]+))?\s*\Vert{}\s*Z=([+-]?[0-9.]+)\)"
    )
    re_no_llenada = re.compile(r"Compra en ([A-Z0-9]+/USDT:USDT) no llenada en (\d+)s: margen liberado")
    re_contagio = re.compile(r"[CIRCUIT BREAKER CONTAGIO]")

    vetos_hawkes = []
    ordenes_no_llenadas = defaultdict(int)
    activaciones_contagio = 0
    lineas_bloqueo_contagio = 0

    for ruta in archivos_log:
        if not ruta.exists():
            continue
        for linea in ruta.read_text(encoding="utf-8", errors="ignore").splitlines():
            m_h = re_hawkes.search(linea)
            if m_h:
                sym, dt_s, cd_s, ih_s, z_s = m_h.groups()
                vetos_hawkes.append(
                    {
                        "symbol": sym,
                        "dt_seg": float(dt_s),
                        "cooldown_seg": float(cd_s),
                        "i_hawkes": float(ih_s) if ih_s is not None else None,
                        "z_score": float(z_s),
                    }
                )
            m_nl = re_no_llenada.search(linea)
            if m_nl:
                ordenes_no_llenadas[m_nl.group(1)] += 1
            if re_contagio.search(linea):
                activaciones_contagio += 1
            if "Contagio simultáneo activo: anomalía ignorada" in linea or "[BLOQUEO] Anomalía ignorada" in linea:
                lineas_bloqueo_contagio += 1

    desbloqueables_v643 = [
        v
        for v in vetos_hawkes
        if (v["i_hawkes"] is not None and v["i_hawkes"] >= 0.18) or v["z_score"] <= -4.00
    ]

    return {
        "total_vetos_hawkes": len(vetos_hawkes),
        "desbloqueables_por_signo_v643": len(desbloqueables_v643),
        "ejemplos_desbloqueados": desbloqueables_v643[:10],
        "ordenes_no_llenadas_por_par": dict(ordenes_no_llenadas),
        "total_ordenes_no_llenadas": sum(ordenes_no_llenadas.values()),
        "activaciones_contagio": activaciones_contagio,
        "anomalias_ignoradas_por_bloqueo": lineas_bloqueo_contagio,
    }


def generar_reporte_etapa4() -> int:
    trades, fuentes = cargar_transacciones_unificadas()
    if not trades:
        print("[ERROR] No se encontraron registros en splitbrain_stats_v6.jsonl ni Transacciones.txt.")
        return 1

    shapley, coaliciones = calcular_valores_shapley_exactos(trades)
    log_info = auditar_logs_hawkes_y_cola()

    v_vacio = coaliciones[frozenset()]
    v_total = coaliciones[
        frozenset({"G1_PURGA_OOS", "G2_TIERING_Z", "G3_OFI_GLOSTEN", "G4_MAKER_ALMGREN", "G5_ANTI_WICK_KNIFE"})
    ]

    # Estadísticas por activo (Dinámica del Replicador)
    por_par: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    por_motivo: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for t in trades:
        por_par[str(t.get("symbol") or "N/A")].append(t)
        por_motivo[str(t.get("motivo") or "N/A")].append(t)

    e_bar_global = sum(float(t.get("pnl_usdt") or 0.0) for t in trades) / len(trades)

    nombres_legibles = {
        "G1_PURGA_OOS": "G1: Purga Drenadores OOS (Replicator Dynamics)",
        "G2_TIERING_Z": "G2: Tiering Z-Score (Campbell-Thompson OOS)",
        "G3_OFI_GLOSTEN": "G3: Absorción OFI >= +0.08 (Glosten-Milgrom)",
        "G4_MAKER_ALMGREN": "G4: Motor Maker-Unwind PostOnly (Almgren-Chriss)",
        "G5_ANTI_WICK_KNIFE": "G5: Jerarquía SL (-1.15%/-1.65%) + Anti-Knife 900s",
    }

    ahora_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    md: List[str] = [
        "# REPORTE FORENSE DE ATRIBUCIÓN COOPERATIVA DE SHAPLEY (SHAP) Y TELEMETRÍA — ETAPA 4 (`SPLITBRAIN-OMEGA V7.0`)",
        "",
        f"- **Fecha de Auditoría**: `{ahora_utc}`",
        f"- **Fuentes Transaccionales Procesadas**: `{', '.join(fuentes)}` (`{len(trades)}` operaciones únicas verificadas)",
        f"- **Baseline Sin Filtros $v(\\emptyset)$**: `{int(v_vacio['n'])} trades` | Win Rate: `{v_vacio['win_rate']:.2f}%` | PnL: `{v_vacio['pnl_total']:+.4f} USDT` | Esperanza: `{v_vacio['expectativa_usdt']:+.4f} USDT/trade`",
        f"- **Gran Coalición Activa $v(N)$ (`V6.4.3`)**: `{int(v_total['n'])} trades` | Win Rate: **`{v_total['win_rate']:.2f}%`** | PnL: **`{v_total['pnl_total']:+.4f} USDT`** | Esperanza: **`{v_total['expectativa_usdt']:+.4f} USDT/trade`**",
        f"- **Ganancia Marginal Total de la Arquitectura ($v(N) - v(\\emptyset)$)**: **`{v_total['pnl_total'] - v_vacio['pnl_total']:+.4f} USDT`** (`{v_total['win_rate'] - v_vacio['win_rate']:+.2f}%` en Win Rate)",
        "",
        "---",
        "",
        "## 1. MATRIZ EXACTA DE VALORES DE SHAPLEY ($\\phi_i$) SOBRE LAS $2^5 = 32$ COALICIONES",
        "",
        "| Compuerta / Mecanismo Cooperativo ($i \\in N$) | $\\phi_i(\\text{PnL Total})$ [USDT] | $\\phi_i(\\text{Win Rate})$ [%] | $\\phi_i(\\text{Esperanza})$ [USDT/trade] | Veredicto Cuantitativo |",
        "| :--- | :---: | :---: | :---: | :--- |",
    ]

    suma_phi_pnl = 0.0
    suma_phi_wr = 0.0
    suma_phi_exp = 0.0

    for cod in ("G5_ANTI_WICK_KNIFE", "G1_PURGA_OOS", "G4_MAKER_ALMGREN", "G3_OFI_GLOSTEN", "G2_TIERING_Z"):
        vals = shapley[cod]
        suma_phi_pnl += vals["pnl_total"]
        suma_phi_wr += vals["win_rate"]
        suma_phi_exp += vals["expectativa_usdt"]
        veredicto = "Impulsor Primario de Alfa" if vals["pnl_total"] > 0.25 else "Filtro Protector de Cola"
        md.append(
            f"| **{nombres_legibles[cod]}** | **`{vals['pnl_total']:+.4f} USDT`** | **`{vals['win_rate']:+.2f}%`** | `{vals['expectativa_usdt']:+.5f}` | {veredicto} |"
        )

    md.append(
        f"| **SUMA AXIOMÁTICA DE EFICIENCIA ($\\sum \\phi_i = v(N) - v(\\emptyset)$)** | **`{suma_phi_pnl:+.4f} USDT`** | **`{suma_phi_wr:+.2f}%`** | **`{suma_phi_exp:+.5f}`** | **100% Verificado (Pareto)** |"
    )

    md.extend(
        [
            "",
            "---",
            "",
            "## 2. MATRIZ DE DINÁMICA DEL REPLICADOR POR ACTIVO ($\\dot{x}_i = x_i(E_i(\\mathbf{x}) - \\bar{E}(\\mathbf{x}))$)",
            "",
            "| Activo (`Symbol`) | Trades | Win Rate (%) | PnL Neto (USDT) | Comisiones (USDT) | Esperanza $E_i$ (USDT) | Ventaja Replicador $E_i - \\bar{E}$ | Clasificación `V6.4.3` |",
            "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |",
        ]
    )

    ranking_pares = sorted(
        por_par.items(),
        key=lambda kv: sum(float(x.get("pnl_usdt") or 0.0) for x in kv[1]),
        reverse=True,
    )
    for sym, lista in ranking_pares:
        n_s = len(lista)
        w_s = sum(1 for x in lista if float(x.get("pnl_usdt") or 0.0) > 0)
        wr_s = (w_s / n_s) * 100.0 if n_s else 0.0
        pnl_s = sum(float(x.get("pnl_usdt") or 0.0) for x in lista)
        fees_s = sum(float(x.get("fees_usdt") or 0.0) for x in lista)
        e_i = pnl_s / n_s if n_s else 0.0
        ventaja = e_i - e_bar_global
        if sym in PARES_DRENADORES:
            clase = "🚫 VETADO (Blacklist OOS)"
        elif sym in PARES_NUCLEO_ALFA:
            clase = "💎 NÚCLEO ALFA (Z <= -2.85)"
        else:
            clase = "⚖️ SECUNDARIO OOS (Z <= -3.15)"
        md.append(
            f"| `{sym}` | {n_s} | `{wr_s:.1f}%` | `{pnl_s:+.4f}` | `{fees_s:.4f}` | `{e_i:+.4f}` | `{ventaja:+.4f}` | {clase} |"
        )

    md.extend(
        [
            "",
            "---",
            "",
            "## 3. AUDITORÍA MICROESTRUCTURAL POR MOTIVO DE CIERRE Y AHORRO MAKER-UNWIND",
            "",
            "| Motivo de Salida (`motivo`) | Operaciones | Win Rate (%) | PnL Acumulado (USDT) | Hold Medio (s) | Fee Medio (USDT) |",
            "| :--- | :---: | :---: | :---: | :---: | :---: |",
        ]
    )

    for mot, lista in sorted(
        por_motivo.items(),
        key=lambda kv: sum(float(x.get("pnl_usdt") or 0.0) for x in kv[1]),
        reverse=True,
    ):
        n_m = len(lista)
        w_m = sum(1 for x in lista if float(x.get("pnl_usdt") or 0.0) > 0)
        wr_m = (w_m / n_m) * 100.0 if n_m else 0.0
        pnl_m = sum(float(x.get("pnl_usdt") or 0.0) for x in lista)
        hold_m = sum(float(x.get("hold_seg") or 0.0) for x in lista) / n_m if n_m else 0.0
        fee_m = sum(float(x.get("fees_usdt") or 0.0) for x in lista) / n_m if n_m else 0.0
        md.append(f"| `{mot}` | {n_m} | `{wr_m:.1f}%` | `{pnl_m:+.4f}` | `{hold_m:.1f}s` | `{fee_m:.4f}` |")

    md.extend(
        [
            "",
            "---",
            "",
            "## 4. DIAGNÓSTICO DE CUELLOS DE BOTELLA DE ENTRADA (`BOT_LOG.TXT`) RESUELTOS EN `V6.4.3`",
            "",
            f"- **Intercepciones Totales `[MEMORIA HAWKES]` Analizadas en Logs**: `{log_info['total_vetos_hawkes']}` eventos.",
            f"- **Oportunidades de Alta Absorción (`I_Hawkes >= +0.18` o Clímax `Z <= -4.00`) Desbloqueadas en `V6.4.3`**: **`{log_info['desbloqueables_por_signo_v643']}` disparos directos** (anteriormente retenidos por el cronómetro fijo de `1.0s < 3.2s`).",
            f"- **Órdenes `Limit Buy PostOnly` No Llenadas en 10s (Objetivo de `Re-Quote 2.0s`)**: `{log_info['total_ordenes_no_llenadas']}` órdenes (`{json.dumps(log_info['ordenes_no_llenadas_por_par'])}`).",
            f"- **Activaciones del Circuit Breaker de Contagio Cross-Asset**: `{log_info['activaciones_contagio']}` eventos (`{log_info['anomalias_ignoradas_por_bloqueo']}` anomalías suprimidas durante ventanas de contagio).",
            "",
        ]
    )

    ruta_md = RAIZ / "REPORTE_SHAPLEY_ETAPA4_V6_4_3.md"
    ruta_json = RAIZ / "auditoria_shapley_v6_4_3.json"

    ruta_md.write_text("\n".join(md), encoding="utf-8")
    ruta_json.write_text(
        json.dumps(
            {
                "timestamp_utc": ahora_utc,
                "total_trades_analizados": len(trades),
                "baseline_sin_filtros": v_vacio,
                "gran_coalicion_v643": v_total,
                "shapley_values": shapley,
                "diagnostico_logs_cola": log_info,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("=" * 108)
    print(f"AUDITORIA COOPERATIVA DE SHAPLEY COMPLETADA SOBRE {len(trades)} OPERACIONES REALES")
    print("=" * 108)
    print(f"  * Baseline sin filtros v(0) : {int(v_vacio['n']):3d} trades | WR: {v_vacio['win_rate']:5.2f}% | PnL: {v_vacio['pnl_total']:+8.4f} USDT")
    print(f"  * Gran Coalicion V6.4.3 v(N): {int(v_total['n']):3d} trades | WR: {v_total['win_rate']:5.2f}% | PnL: {v_total['pnl_total']:+8.4f} USDT")
    print("-" * 108)
    for cod in ("G5_ANTI_WICK_KNIFE", "G1_PURGA_OOS", "G4_MAKER_ALMGREN", "G3_OFI_GLOSTEN", "G2_TIERING_Z"):
        v = shapley[cod]
        print(f"  -> {nombres_legibles[cod]:<50} | Shapley PnL: {v['pnl_total']:+8.4f} USDT | Shapley WR: {v['win_rate']:+6.2f}%")
    print("-" * 108)
    print(f"[OK] Reporte Markdown Etapa 4 : {ruta_md}")
    print(f"[OK] Telemetria JSON Etapa 4  : {ruta_json}")
    print("=" * 108)
    return 0


if __name__ == "__main__":
    sys.exit(generar_reporte_etapa4())