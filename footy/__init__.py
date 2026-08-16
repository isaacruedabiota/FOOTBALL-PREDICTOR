"""Modelo predictivo de fútbol con registro y evaluación de predicciones."""

__version__ = "0.1.0"
MODEL_VERSION = "dc-v1"      # modelo principal (Dixon-Coles)
BASELINE_VERSION = "elo-v1"  # baseline de referencia (Elo) para comparar

# Etiquetas legibles para los informes.
MODEL_LABELS = {
    MODEL_VERSION: "Dixon-Coles",
    BASELINE_VERSION: "Elo (baseline)",
}
