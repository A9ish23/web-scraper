"""Train and evaluate a text classifier from user-corrected page labels."""

from pathlib import Path
from functools import lru_cache

MODEL_PATH = Path(__file__).resolve().parents[2] / "data" / "page_classifier.joblib"


def _pipeline():
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    return make_pipeline(TfidfVectorizer(ngram_range=(1, 2), min_df=1, max_features=30000),
                         LogisticRegression(max_iter=1000, class_weight="balanced"))


def train_classifier(records: list[dict], evaluation_records: list[dict] | None = None) -> dict:
    from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
    labels = [record["label"] for record in records]
    texts = [record["text"] for record in records]
    classes = sorted(set(labels))
    if len(records) < 6 or len(classes) < 2:
        return {"trained": False, "sample_count": len(records), "classes": classes,
                "message": "Add at least 6 labeled pages across at least 2 categories before training."}

    counts = {label: labels.count(label) for label in classes}
    evaluation_records = evaluation_records or []
    metrics = None
    if evaluation_records:
        evaluation_texts = [record["text"] for record in evaluation_records]
        expected = [record["label"] for record in evaluation_records]
        evaluation_model = _pipeline().fit(texts, labels)
        predicted = evaluation_model.predict(evaluation_texts)
        report_labels = sorted(set(expected) | set(predicted))
        metrics = {
            "accuracy": round(float(accuracy_score(expected, predicted)), 3),
            "macro_f1": round(float(f1_score(expected, predicted, average="macro", zero_division=0)), 3),
            "report": classification_report(expected, predicted, labels=report_labels, output_dict=True, zero_division=0),
            "confusion_matrix": confusion_matrix(expected, predicted, labels=report_labels).tolist(),
            "labels": report_labels,
            "evaluation_size": len(evaluation_records),
        }

    model = _pipeline().fit(texts, labels)
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    import joblib
    joblib.dump(model, MODEL_PATH)
    _load_model.cache_clear()
    return {"trained": True, "sample_count": len(records), "classes": classes,
            "label_counts": counts, "evaluation": metrics,
            "message": "Model trained only on training examples. Metrics use the separately labeled evaluation set." if metrics else
                       "Model trained. Add separately marked evaluation examples to measure generalization."}


@lru_cache(maxsize=1)
def _load_model():
    import joblib
    return joblib.load(MODEL_PATH)


def predict_page(text: str) -> dict | None:
    if not MODEL_PATH.exists():
        return None
    model = _load_model()
    probabilities = model.predict_proba([text])[0]
    best = int(probabilities.argmax())
    return {"label": str(model.classes_[best]), "confidence": round(float(probabilities[best]), 3),
            "method": "trained text model", "evidence": []}


def model_status() -> dict:
    return {"trained": MODEL_PATH.exists()}
