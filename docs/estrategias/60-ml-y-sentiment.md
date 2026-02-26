# Estrategias ML y Sentiment

## Estrategias cubiertas (SSRN 3247865)

- `18.2 Artificial neural network (ANN)`
- `18.3 Sentiment analysis - naive Bayes Bernoulli`
- `3.17 Machine learning - single-stock KNN` (adaptable a crypto)

## Validacion externa (resumen)

- ML en trading sirve mas como capa de probabilidad que como "boton magico".
- Sentiment puede aportar, pero es vulnerable a ruido, spam y prompt/data poisoning.
- En crypto conviene combinar features de precio/volatilidad/flujo con reglas de riesgo deterministas.

Ver fuentes:

- `fuentes-validadas-2026-02-19.md` (ML/Sentiment y seguridad operacional)

## Cuando aplicar

### Scalping

- Solo modelos simples y muy bien monitorizados.
- No recomendado arrancar con deep models pesados.

### Intraday

- Mejor equilibrio para features de mercado + sentiment.

### Swing

- Util para ranking de setups, no como trigger unico.

## Spot vs Futures

- Spot: menor riesgo de error modelado.
- Futures: usar ML solo con limites de riesgo mas estrictos y hard-gates.

## Reglas operativas recomendadas

1. Nunca ejecutar por score ML sin pasar risk middleware.
2. Evitar leakage temporal (split train/val/test por fecha).
3. Definir umbrales de confianza calibrados, no arbitrarios.
4. Reentrenar en ventanas rodantes y monitorear drift.

## Snippet Python (clasificador probabilistico simple)

```python
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

def train_prob_model(df: pd.DataFrame, feature_cols, target_col="y_up"):
    train = df.dropna(subset=feature_cols + [target_col]).copy()
    X = train[feature_cols]
    y = train[target_col].astype(int)

    model = RandomForestClassifier(
        n_estimators=300,
        max_depth=6,
        min_samples_leaf=50,
        random_state=42,
    )
    model.fit(X, y)
    return model

def signal_from_prob(prob_up, buy_thr=0.62, sell_thr=0.38):
    if prob_up >= buy_thr:
        return "buy"
    if prob_up <= sell_thr:
        return "sell"
    return "hold"
```

## Riesgos tipicos

- Sobreajuste y degradacion en vivo.
- Datos alternativos de baja calidad.
- Dependencia de features no reproducibles.

## Recomendacion para este repo

- Prioridad media: ML como meta-filtro sobre estrategias deterministicas.
- Prioridad baja inicial: sentiment en tiempo real sin pipeline anti-spam robusto.
