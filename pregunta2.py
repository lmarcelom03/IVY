"""Pregunta 2: Análisis de una acción con modelos de series de tiempo.

Este script descarga (o lee desde un CSV) los últimos cinco años de datos
diarios para un ticker seleccionado y desarrolla los análisis solicitados en
las partes 1 y 2 del enunciado. Los resultados (gráficos y tablas) se guardan
en la carpeta ``resultados_pregunta2`` y también se muestran por consola los
resúmenes solicitados.

Requisitos (instalación recomendada):
    python -m pip install yfinance pandas numpy matplotlib seaborn statsmodels

Ejecución típica en línea:
    python pregunta2.py --ticker AAPL

Modo sin conexión (cargando un CSV con datos históricos):
    python pregunta2.py --input datos.csv --ticker AAPL

El archivo CSV debe tener la fecha en la primera columna y contener al menos
una columna "Adj Close" o "Close".
"""
from __future__ import annotations

import argparse
import importlib
import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import statsmodels.api as sm
from statsmodels.tsa.holtwinters import ExponentialSmoothing
# Carga opcional de yfinance, permitiendo ejecutar el script con archivos
# locales cuando el paquete no esté instalado.
if importlib.util.find_spec("yfinance") is not None:  # pragma: no cover - depende del entorno
    yf = importlib.import_module("yfinance")  # type: ignore
else:  # pragma: no cover
    yf = None

try:  # pragma: no cover - estilo depende del entorno
    import seaborn as sns
except ImportError:  # pragma: no cover - disponibilidad opcional
    sns = None


try:  # pragma: no cover - estilo depende de la versión de matplotlib
    plt.style.use("seaborn-v0_8")
except OSError:  # pragma: no cover
    plt.style.use("ggplot")


@dataclass
class ModelResult:
    name: str
    fitted: object
    predictions: pd.Series
    rmse: float


def download_data(ticker: str, start: Optional[str], end: Optional[str]) -> pd.DataFrame:
    """Descarga datos diarios mediante yfinance."""
    if yf is None:
        raise RuntimeError(
            "El paquete yfinance no está disponible. Use la opción --input para cargar un CSV."
        )

    kwargs = {"interval": "1d", "auto_adjust": False}
    if start or end:
        if start:
            kwargs["start"] = start
        if end:
            kwargs["end"] = end
    else:
        kwargs["period"] = "5y"

    df = yf.download(ticker, **kwargs)
    if df.empty:
        raise RuntimeError(
            "No se obtuvieron datos para el ticker especificado. Verifique el código o utilice --input."
        )
    df.index.name = "Date"
    return df


def load_from_csv(path: str) -> pd.DataFrame:
    """Carga un archivo CSV con columna de fecha y precios."""
    df = pd.read_csv(path, parse_dates=[0])
    df = df.set_index(df.columns[0])
    df.index.name = "Date"
    return df


def acquire_data(
    ticker: str,
    csv_path: Optional[str],
    start: Optional[str],
    end: Optional[str],
) -> pd.DataFrame:
    """Obtiene los datos ya sea desde CSV o mediante descarga remota."""
    if csv_path:
        print(f"Cargando datos locales desde: {csv_path}")
        df = load_from_csv(csv_path)
    else:
        print("Descargando datos con yfinance...")
        df = download_data(ticker, start, end)

    if "Adj Close" not in df.columns:
        if "AdjClose" in df.columns:
            df = df.rename(columns={"AdjClose": "Adj Close"})
        elif "Close" in df.columns:
            df = df.rename(columns={"Close": "Adj Close"})
        else:
            raise KeyError(
                "El dataset debe contener una columna 'Adj Close' o 'Close' para continuar."
            )
    df = df.sort_index()
    return df


def part1_analysis(df: pd.DataFrame, ticker: str, out_dir: Path) -> pd.Series:
    """Realiza las tareas de la parte 1 y retorna la serie de retornos diarios."""
    print("\n=== Parte 1: Exploración de datos ===")
    print("Primeras filas:")
    print(df.head())

    print("\nValores faltantes por columna:")
    print(df.isna().sum())

    print("\nTipos de datos:")
    print(df.dtypes)

    price = df["Adj Close"].rename("AdjClose")
    ma30 = price.rolling(window=30).mean()
    ma60 = price.rolling(window=60).mean()

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(price.index, price, label="Precio ajustado")
    ax.plot(ma30.index, ma30, label="Media móvil 30d")
    ax.plot(ma60.index, ma60, label="Media móvil 60d")
    ax.set_title(f"{ticker}: Precio ajustado y medias móviles")
    ax.set_xlabel("Fecha")
    ax.set_ylabel("USD")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig_path = out_dir / f"{ticker}_precio_ma.png"
    fig.savefig(fig_path, dpi=150)
    plt.close(fig)
    print(f"Gráfico de precio y medias móviles guardado en: {fig_path}")

    returns = price.pct_change().dropna()
    stats = {
        "media": returns.mean(),
        "volatilidad": returns.std(),
        "asimetria": returns.skew(),
        "curtosis": returns.kurt(),
        "min": returns.min(),
        "max": returns.max(),
        "percentil_25": returns.quantile(0.25),
        "mediana": returns.median(),
        "percentil_75": returns.quantile(0.75),
    }
    stats_df = pd.DataFrame(stats, index=[ticker])
    stats_path = out_dir / f"{ticker}_estadisticos_retornos.csv"
    stats_df.to_csv(stats_path)
    print("\nEstadísticos descriptivos de los retornos diarios:")
    print(stats_df.T)
    print(f"Estadísticos guardados en: {stats_path}")

    last_1y = returns.last("365D")
    last_2y = returns.last("730D")

    fig, axes = plt.subplots(nrows=1, ncols=3, figsize=(15, 4), sharey=True)
    datasets = [last_1y, last_2y, returns]
    titles = ["Retornos último año", "Retornos últimos 2 años", "Retornos 5 años"]
    for ax, data, title in zip(axes, datasets, titles):
        if sns is not None:
            sns.histplot(data, bins=40, kde=True, ax=ax)
        else:
            ax.hist(data, bins=40, alpha=0.8, color="C0")
        ax.set_title(title)
        ax.set_xlabel("Retorno diario")
    for ax in axes:
        ax.grid(alpha=0.3)
    fig.tight_layout()
    hist_path = out_dir / f"{ticker}_hist_retornos.png"
    fig.savefig(hist_path, dpi=150)
    plt.close(fig)
    print(f"Histogramas de retornos guardados en: {hist_path}")

    return returns


def split_series(price: pd.Series) -> Tuple[pd.Series, pd.Series]:
    """Divide la serie de precios en conjuntos de entrenamiento y prueba."""
    if len(price) < 20:
        raise ValueError(
            "Se requieren al menos 20 observaciones para ajustar y evaluar los modelos."
        )
    test_size = min(60, max(10, int(len(price) * 0.1)))
    train = price.iloc[:-test_size]
    test = price.iloc[-test_size:]
    return train, test


def fit_models(train: pd.Series, test: pd.Series) -> Dict[str, ModelResult]:
    """Ajusta dos modelos de series de tiempo sobre los precios."""

    models: Dict[str, ModelResult] = {}

    # Modelo 1: ARIMA(1,1,1)
    arima_model = sm.tsa.statespace.SARIMAX(
        train,
        order=(1, 1, 1),
        enforce_stationarity=False,
        enforce_invertibility=False,
    )
    arima_res = arima_model.fit(disp=False)
    arima_forecast = arima_res.get_forecast(steps=len(test))
    arima_pred = pd.Series(
        arima_forecast.predicted_mean.to_numpy(),
        index=test.index,
        name="forecast",
    )
    arima_rmse = float(np.sqrt(np.mean((arima_pred.to_numpy() - test.to_numpy()) ** 2)))
    models["ARIMA(1,1,1)"] = ModelResult(
        name="ARIMA(1,1,1)",
        fitted=arima_res,
        predictions=arima_pred,
        rmse=arima_rmse,
    )

    # Modelo 2: Holt-Winters sin componente estacional
    hw_model = ExponentialSmoothing(train, trend="add", seasonal=None)
    hw_res = hw_model.fit(optimized=True)
    hw_pred_values = hw_res.forecast(len(test))
    hw_pred = pd.Series(np.asarray(hw_pred_values), index=test.index, name="forecast")
    hw_rmse = float(np.sqrt(np.mean((hw_pred.to_numpy() - test.to_numpy()) ** 2)))
    models["Holt-Winters (trend additivo)"] = ModelResult(
        name="Holt-Winters (trend additivo)",
        fitted=hw_res,
        predictions=hw_pred,
        rmse=hw_rmse,
    )

    return models


def evaluate_models(models: Dict[str, ModelResult]) -> Tuple[str, ModelResult]:
    print("\n=== Parte 2: Modelos de series de tiempo ===")
    for name, result in models.items():
        print(f"Modelo: {name}")
        print(f"  RMSE en el conjunto de prueba: {result.rmse:.4f}")
    best_name, best_result = min(models.items(), key=lambda kv: kv[1].rmse)
    print(f"\nEl modelo con mejor desempeño (menor RMSE) es: {best_name}")
    return best_name, best_result


def plot_model_diagnostics(
    best_name: str, best_result: ModelResult, price: pd.Series, out_dir: Path
) -> None:
    """Genera gráficos diagnósticos para el mejor modelo."""
    if best_name.startswith("ARIMA"):
        resid = best_result.fitted.resid
        fitted_values = best_result.fitted.fittedvalues
        resid_index = resid.index
        fitted_index = fitted_values.index
    else:
        fitted_values = best_result.fitted.fittedvalues
        resid = price.loc[fitted_values.index] - fitted_values
        resid_index = fitted_values.index
        fitted_index = fitted_values.index

    fig, axes = plt.subplots(nrows=3, ncols=1, figsize=(10, 10))

    axes[0].plot(resid_index, resid)
    axes[0].axhline(0, color="black", linewidth=1)
    axes[0].set_title(f"{best_name}: Residuales en el tiempo")
    axes[0].set_xlabel("Fecha")
    axes[0].set_ylabel("Error")
    axes[0].grid(alpha=0.3)

    if sns is not None:
        sns.histplot(resid, bins=40, kde=True, ax=axes[1])
    else:
        axes[1].hist(resid, bins=40, alpha=0.8, color="C0")
    axes[1].set_title(f"{best_name}: Histograma de residuales")
    axes[1].set_xlabel("Error")

    axes[2].scatter(price.loc[fitted_index], fitted_values, alpha=0.6)
    axes[2].plot(price.loc[fitted_index], price.loc[fitted_index], color="red", linestyle="--")
    axes[2].set_title(f"{best_name}: Real vs Ajustado")
    axes[2].set_xlabel("Precio real")
    axes[2].set_ylabel("Precio estimado")
    axes[2].grid(alpha=0.3)

    fig.tight_layout()
    diag_path = out_dir / f"{best_name.replace(' ', '_')}_diagnosticos.png"
    fig.savefig(diag_path, dpi=150)
    plt.close(fig)
    print(f"Gráficos diagnósticos guardados en: {diag_path}")


def forecast_future(
    best_name: str,
    best_result: ModelResult,
    price: pd.Series,
    out_dir: Path,
    steps: int = 5,
) -> pd.DataFrame:
    """Genera pronóstico y devuelve DataFrame con intervalos de confianza."""
    if best_name.startswith("ARIMA"):
        model_full = sm.tsa.statespace.SARIMAX(
            price,
            order=(1, 1, 1),
            enforce_stationarity=False,
            enforce_invertibility=False,
        )
        res_full = model_full.fit(disp=False)
        forecast_res = res_full.get_forecast(steps=steps)
        forecast_df = forecast_res.summary_frame(alpha=0.05)
        forecast_df.rename(
            columns={"mean": "forecast", "mean_ci_lower": "lower", "mean_ci_upper": "upper"},
            inplace=True,
        )
    else:
        model_full = ExponentialSmoothing(price, trend="add", seasonal=None)
        res_full = model_full.fit(optimized=True)
        forecast_values = res_full.forecast(steps)
        resid = price.loc[res_full.fittedvalues.index] - res_full.fittedvalues
        resid_std = resid.std(ddof=1)
        index = forecast_values.index
        lower = forecast_values - 1.96 * resid_std
        upper = forecast_values + 1.96 * resid_std
        forecast_df = pd.DataFrame({
            "forecast": forecast_values,
            "lower": lower,
            "upper": upper,
        }, index=index)

    if isinstance(forecast_df.index, pd.PeriodIndex):
        forecast_df.index = forecast_df.index.to_timestamp()

    forecast_path = out_dir / f"{best_name.replace(' ', '_')}_pronostico.csv"
    forecast_df.to_csv(forecast_path)
    print(f"Pronóstico a {steps} días guardado en: {forecast_path}")
    print(forecast_df)

    fig, ax = plt.subplots(figsize=(10, 5))
    last_obs = price.iloc[-20:]
    ax.plot(last_obs.index, last_obs, label="Observado", marker="o")
    ax.plot(forecast_df.index, forecast_df["forecast"], label="Pronóstico", marker="o")
    ax.fill_between(
        forecast_df.index,
        forecast_df["lower"],
        forecast_df["upper"],
        color="C1",
        alpha=0.2,
        label="Intervalo 95%",
    )
    ax.set_title(f"{best_name}: Pronóstico 5 días")
    ax.set_xlabel("Fecha")
    ax.set_ylabel("Precio")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    forecast_fig_path = out_dir / f"{best_name.replace(' ', '_')}_pronostico_plot.png"
    fig.savefig(forecast_fig_path, dpi=150)
    plt.close(fig)
    print(f"Gráfico de pronóstico guardado en: {forecast_fig_path}")

    return forecast_df


def ensure_output_dir(path: Optional[str]) -> Path:
    out_dir = Path(path) if path else Path("resultados_pregunta2")
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pregunta 2 - Análisis de acción")
    parser.add_argument(
        "--ticker",
        type=str,
        default="AAPL",
        help="Ticker de la acción a analizar (por defecto: AAPL)",
    )
    parser.add_argument(
        "--input",
        type=str,
        help="Ruta a un CSV local con datos históricos (opcional).",
    )
    parser.add_argument(
        "--start",
        type=str,
        help="Fecha de inicio (YYYY-MM-DD) para la descarga opcional.",
    )
    parser.add_argument(
        "--end",
        type=str,
        help="Fecha de término (YYYY-MM-DD) para la descarga opcional.",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Directorio donde se guardarán los resultados (por defecto: resultados_pregunta2)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ticker = args.ticker.upper()
    out_dir = ensure_output_dir(args.output)

    df = acquire_data(ticker, args.input, args.start, args.end)
    part1_analysis(df, ticker, out_dir)

    price = df["Adj Close"].dropna()
    train, test = split_series(price)
    models = fit_models(train, test)
    best_name, best_result = evaluate_models(models)

    plot_model_diagnostics(best_name, best_result, price, out_dir)
    forecast_future(best_name, best_result, price, out_dir, steps=5)


if __name__ == "__main__":
    main()
