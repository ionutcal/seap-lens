"""The three model variants the spec compares, behind one fit and predict interface."""

import lightgbm
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.model_features import CATEGORICAL_FEATURES, FEATURES, NUMERIC_FEATURES

SEED = 0


class MeanRateModel:
    """The share of single offers by CPV group and procedure type, with fallbacks for rare pairs."""

    keys = ["cpv_group", "procedure_type"]
    min_rows = 30

    def __init__(self, **_):
        pass

    def fit(self, frame: pd.DataFrame, labels: pd.Series) -> "MeanRateModel":
        data = frame[self.keys].assign(label=labels.astype(float).to_numpy())
        pairs = data.groupby(self.keys).label.agg(["mean", "size"])
        self.rates = pairs[pairs["size"] >= self.min_rows]["mean"]
        self.group_rates = data.groupby("cpv_group").label.mean()
        self.overall = data.label.mean()
        return self

    def predict(self, frame: pd.DataFrame):
        pairs = pd.MultiIndex.from_frame(frame[self.keys])
        fallback = frame.cpv_group.map(self.group_rates).fillna(self.overall).to_numpy()
        specific = self.rates.reindex(pairs).to_numpy()
        return pd.Series(specific).where(pd.notna(specific), fallback).to_numpy()


class LogisticModel:
    def __init__(self, C: float = 1.0):
        self.C = C

    def fit(self, frame: pd.DataFrame, labels: pd.Series) -> "LogisticModel":
        columns = ColumnTransformer([
            ("categories", OneHotEncoder(handle_unknown="ignore", min_frequency=20), CATEGORICAL_FEATURES),
            ("numbers", make_pipeline(SimpleImputer(strategy="median", add_indicator=True), StandardScaler()), NUMERIC_FEATURES),
        ])
        self.pipeline = make_pipeline(columns, LogisticRegression(C=self.C, max_iter=1000))
        self.pipeline.fit(frame[FEATURES], labels.astype(int))
        return self

    def predict(self, frame: pd.DataFrame):
        return self.pipeline.predict_proba(frame[FEATURES])[:, 1]


class LightGBMModel:
    def __init__(self, num_leaves: int = 31, min_child_samples: int = 200):
        self.parameters = dict(
            num_leaves=num_leaves, min_child_samples=min_child_samples, n_estimators=300, learning_rate=0.05,
            subsample=0.8, subsample_freq=1, colsample_bytree=0.8, random_state=SEED, verbose=-1, n_jobs=4,
        )

    def _prepared(self, frame: pd.DataFrame) -> pd.DataFrame:
        prepared = frame[FEATURES].copy()
        for column in CATEGORICAL_FEATURES:
            known = prepared[column].where(prepared[column].isin(self.categories[column]))
            prepared[column] = pd.Categorical(known, categories=self.categories[column])
        return prepared

    def fit(self, frame: pd.DataFrame, labels: pd.Series) -> "LightGBMModel":
        self.categories = {column: sorted(frame[column].unique()) for column in CATEGORICAL_FEATURES}
        self.model = lightgbm.LGBMClassifier(**self.parameters)
        self.model.fit(self._prepared(frame), labels.astype(int))
        return self

    def predict(self, frame: pd.DataFrame):
        return self.model.predict_proba(self._prepared(frame))[:, 1]


VARIANTS = {"mean_rate": MeanRateModel, "logistic": LogisticModel, "lightgbm": LightGBMModel}
VARIANT_ORDER = ["mean_rate", "logistic", "lightgbm"]
SEARCH_SPACE = {
    "mean_rate": [{}],
    "logistic": [{"C": 0.1}, {"C": 1.0}],
    "lightgbm": [
        {"num_leaves": 15, "min_child_samples": 200},
        {"num_leaves": 31, "min_child_samples": 200},
        {"num_leaves": 31, "min_child_samples": 1000},
    ],
}
