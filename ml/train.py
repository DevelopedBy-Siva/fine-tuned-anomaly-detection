import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from dataclasses import dataclass

import pandas as pd
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    AutoModelForSeq2SeqLM,
    Trainer,
    TrainingArguments,
    EarlyStoppingCallback,
)
from peft import LoraConfig, get_peft_model, TaskType
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.metrics import (
    f1_score,
    precision_score,
    recall_score,
    confusion_matrix,
    precision_recall_curve,
    classification_report,
    roc_auc_score,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("training.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """Configuration for model training"""

    CLASSIFIER_MODEL: str = "microsoft/deberta-v3-base"
    REASONING_MODEL: str = "google/flan-t5-base"

    DATA_DIR: Path = Path("./data")
    MODEL_DIR: Path = Path("./models")
    LOGS_DIR: Path = Path("./logs")

    MAX_LENGTH: int = 512
    BATCH_SIZE: int = 32
    CLASSIFIER_EPOCHS: int = 10
    REASONING_EPOCHS: int = 8
    LEARNING_RATE: float = 2e-5
    WEIGHT_DECAY: float = 0.01
    WARMUP_RATIO: float = 0.1

    PATIENCE: int = 3

    WINDOW_SIZE: int = 10
    STRIDE: int = 5

    MAX_SEQUENCES: int = 100000

    LORA_R: int = 16
    LORA_ALPHA: int = 32
    LORA_DROPOUT: float = 0.1

    MLFLOW_TRACKING_URI: str = "mlruns"
    EXPERIMENT_NAME: str = "LogAnomaly_v2"

    DEVICE: str = "cuda" if torch.cuda.is_available() else "cpu"

    def __post_init__(self):
        self.DATA_DIR.mkdir(exist_ok=True)
        self.MODEL_DIR.mkdir(exist_ok=True)
        self.LOGS_DIR.mkdir(exist_ok=True)

        logger.info(f"Using device: {self.DEVICE}")
        logger.info(f"Classifier: {self.CLASSIFIER_MODEL}")
        logger.info(f"Reasoning: {self.REASONING_MODEL}")


class LogDataset(Dataset):

    def __init__(self, encodings: dict, labels: List[int]):
        self.encodings = encodings
        self.labels = labels

    def __len__(self) -> int:
        return len(self.labels)

    def __getitem__(self, idx: int) -> dict:
        item = {key: val[idx] for key, val in self.encodings.items()}
        item["labels"] = torch.tensor(self.labels[idx], dtype=torch.long)
        return item


class ReasoningDataset(Dataset):

    def __init__(
        self,
        sequences: List[str],
        reasons: List[str],
        tokenizer,
        max_input_length: int = 512,
        max_target_length: int = 128,
    ):
        self.sequences = sequences
        self.reasons = reasons
        self.tokenizer = tokenizer
        self.max_input_length = max_input_length
        self.max_target_length = max_target_length

    def __len__(self) -> int:
        return len(self.sequences)

    def __getitem__(self, idx: int) -> dict:
        sequence = self.sequences[idx]
        reason = self.reasons[idx]

        input_text = (
            f"Analyze this log sequence and explain why it's anomalous:\n{sequence}"
        )

        model_inputs = self.tokenizer(
            input_text,
            max_length=self.max_input_length,
            truncation=True,
            padding="max_length",
            return_tensors="pt",
        )

        labels = self.tokenizer(
            reason,
            max_length=self.max_target_length,
            truncation=True,
            padding="max_length",
            return_tensors="pt",
        )

        model_inputs["labels"] = labels["input_ids"].squeeze()

        return {
            "input_ids": model_inputs["input_ids"].squeeze(),
            "attention_mask": model_inputs["attention_mask"].squeeze(),
            "labels": model_inputs["labels"],
        }


class DataPreprocessor:

    def __init__(self, config: ModelConfig):
        self.config = config

    def load_hdfs_data(self, filepath: str, max_samples: int = None) -> pd.DataFrame:
        logger.info(f"Loading HDFS data from {filepath}")

        if max_samples:
            df_sample = pd.read_csv(filepath, nrows=1000)

            import os

            file_size = os.path.getsize(filepath)
            avg_row_size = file_size / 1000
            total_rows = int(file_size / avg_row_size)

            if total_rows > max_samples:
                skip_prob = 1 - (max_samples / total_rows)
                logger.info(
                    f"Sampling {max_samples:,} from ~{total_rows:,} rows (skip={skip_prob:.3f})"
                )

                import random

                random.seed(42)

                chunks = []
                for chunk in pd.read_csv(filepath, chunksize=50000):
                    mask = [random.random() > skip_prob for _ in range(len(chunk))]
                    sampled = chunk[mask]
                    chunks.append(sampled)

                    if sum(len(c) for c in chunks) >= max_samples:
                        break

                df = pd.concat(chunks, ignore_index=True)[:max_samples]
            else:
                df = pd.read_csv(filepath)
        else:
            df = pd.read_csv(filepath)

        if "Label" not in df.columns:
            raise ValueError("Dataset must have 'Label' column")

        df["Label"] = df["Label"].astype(int)

        if "Content" in df.columns:
            if "Level" in df.columns:
                df["Description"] = (
                    "[" + df["Level"].astype(str) + "] " + df["Content"].astype(str)
                )
            else:
                df["Description"] = df["Content"].astype(str)
        elif "EventTemplate" in df.columns:
            if "Level" in df.columns:
                df["Description"] = (
                    "["
                    + df["Level"].astype(str)
                    + "] "
                    + df["EventTemplate"].astype(str)
                )
            else:
                df["Description"] = df["EventTemplate"].astype(str)
        else:
            raise ValueError(
                "Dataset must have either 'Content' or 'EventTemplate' column"
            )

        logger.info(f"Loaded {len(df):,} logs")
        logger.info(f"Anomaly ratio: {df['Label'].mean():.2%}")

        return df

    def load_bgl_data(self, filepath: str) -> pd.DataFrame:
        """Load and preprocess BGL dataset"""
        logger.info(f"Loading BGL data from {filepath}")

        df = pd.read_csv(filepath)

        df["Label"] = df["Label"].apply(lambda x: 0 if x == "-" else 1)

        df["Description"] = (
            "[" + df["Level"].astype(str) + "] " + df["EventTemplate"].astype(str)
        )

        logger.info(f"Loaded {len(df)} logs")
        logger.info(f"Anomaly ratio: {df['Label'].mean():.2%}")

        return df

    def create_sequences(
        self,
        df: pd.DataFrame,
        window_size: int = None,
        stride: int = None,
        max_sequences: int = 100000,
    ) -> Tuple[List[str], List[int]]:

        window_size = window_size or self.config.WINDOW_SIZE
        stride = stride or self.config.STRIDE

        logger.info(f"Creating sequences (window={window_size}, stride={stride})")

        descriptions = df["Description"].tolist()
        label_list = df["Label"].tolist()

        logger.info(f"Converted to lists (len={len(descriptions):,})")

        sequences = []
        labels = []

        total_possible = (len(descriptions) - window_size + 1) // stride
        logger.info(f"Total possible sequences: {total_possible:,}")

        if total_possible > max_sequences:
            actual_stride = stride * (total_possible // max_sequences)
            logger.info(
                f"Using stride={actual_stride} to limit to {max_sequences:,} sequences"
            )
        else:
            actual_stride = stride

        count = 0
        for i in range(0, len(descriptions) - window_size + 1, actual_stride):
            sequence = " ".join(descriptions[i : i + window_size])

            seq_label = max(label_list[i : i + window_size])

            sequences.append(sequence)
            labels.append(seq_label)

            count += 1
            if count >= max_sequences:
                break

            if count % 10000 == 0:
                logger.info(f"  Created {count:,} sequences...")

        logger.info(f"Created {len(sequences):,} sequences")
        logger.info(
            f"Anomalous sequences: {sum(labels):,} ({sum(labels)/max(len(labels),1):.2%})"
        )

        return sequences, labels

    def generate_explanations(
        self, anomaly_sequences: List[str], method: str = "template"
    ) -> List[str]:

        logger.info(f"Generating explanations for {len(anomaly_sequences)} anomalies")

        explanations = []

        for seq in anomaly_sequences:
            if "FATAL" in seq:
                reason = "Critical system failure detected with FATAL level errors"
            elif "ERROR" in seq and seq.count("ERROR") > 3:
                reason = "Multiple ERROR messages indicate recurring system issues"
            elif "timeout" in seq.lower():
                reason = "Connection or operation timeout suggests network or resource problems"
            elif "failed" in seq.lower():
                reason = "Operation failures indicate system instability"
            elif "crash" in seq.lower() or "abort" in seq.lower():
                reason = "System crash or abort detected, requires immediate attention"
            elif "memory" in seq.lower() or "oom" in seq.lower():
                reason = "Memory-related issues detected, possible resource exhaustion"
            else:
                reason = "Unusual log pattern detected that deviates from normal system behavior"

            explanations.append(reason)

        return explanations


class ClassifierTrainer:

    def __init__(self, config: ModelConfig):
        self.config = config
        self.device = torch.device(config.DEVICE)

        self.tokenizer = AutoTokenizer.from_pretrained(config.CLASSIFIER_MODEL)
        self.model = None

    def tokenize_sequences(self, sequences: List[str]) -> dict:
        return self.tokenizer(
            sequences,
            truncation=True,
            padding=True,
            max_length=self.config.MAX_LENGTH,
            return_tensors="pt",
        )

    def setup_model(self):
        logger.info("Setting up classification model")

        self.model = AutoModelForSequenceClassification.from_pretrained(
            self.config.CLASSIFIER_MODEL,
            num_labels=2,
            problem_type="single_label_classification",
        )

        lora_config = LoraConfig(
            task_type=TaskType.SEQ_CLS,
            r=self.config.LORA_R,
            lora_alpha=self.config.LORA_ALPHA,
            lora_dropout=self.config.LORA_DROPOUT,
            target_modules=["query_proj", "value_proj"],
        )

        self.model = get_peft_model(self.model, lora_config)
        self.model.print_trainable_parameters()

        return self.model

    def compute_metrics(self, eval_pred):
        predictions, labels = eval_pred
        predictions = np.argmax(predictions, axis=1)

        return {
            "f1": f1_score(labels, predictions, zero_division=0),
            "precision": precision_score(labels, predictions, zero_division=0),
            "recall": recall_score(labels, predictions, zero_division=0),
        }

    def train(
        self,
        train_sequences: List[str],
        train_labels: List[int],
        val_sequences: List[str],
        val_labels: List[int],
    ) -> Dict:

        logger.info("Starting classifier training")

        train_encodings = self.tokenize_sequences(train_sequences)
        val_encodings = self.tokenize_sequences(val_sequences)

        train_dataset = LogDataset(train_encodings, train_labels)
        val_dataset = LogDataset(val_encodings, val_labels)

        self.setup_model()

        training_args = TrainingArguments(
            output_dir=str(self.config.MODEL_DIR / "classifier" / "checkpoints"),
            num_train_epochs=self.config.CLASSIFIER_EPOCHS,
            per_device_train_batch_size=self.config.BATCH_SIZE,
            per_device_eval_batch_size=self.config.BATCH_SIZE,
            learning_rate=self.config.LEARNING_RATE,
            weight_decay=self.config.WEIGHT_DECAY,
            warmup_ratio=self.config.WARMUP_RATIO,
            eval_strategy="epoch",
            save_strategy="epoch",
            load_best_model_at_end=True,
            metric_for_best_model="f1",
            greater_is_better=True,
            logging_dir=str(self.config.LOGS_DIR / "classifier"),
            logging_steps=10,
            save_total_limit=2,
            report_to="none",
        )

        trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=val_dataset,
            compute_metrics=self.compute_metrics,
            callbacks=[
                EarlyStoppingCallback(early_stopping_patience=self.config.PATIENCE)
            ],
        )

        train_result = trainer.train()
        metrics = trainer.evaluate()

        save_path = self.config.MODEL_DIR / "classifier" / "final"
        trainer.save_model(str(save_path))
        self.tokenizer.save_pretrained(str(save_path))

        logger.info(f"Classifier training complete. Metrics: {metrics}")

        return metrics


class ReasoningTrainer:

    def __init__(self, config: ModelConfig):
        self.config = config
        self.device = torch.device(config.DEVICE)

        self.tokenizer = AutoTokenizer.from_pretrained(config.REASONING_MODEL)
        self.model = None

    def setup_model(self):
        """Initialize FLAN-T5 model with LoRA"""
        logger.info("Setting up reasoning model")

        self.model = AutoModelForSeq2SeqLM.from_pretrained(self.config.REASONING_MODEL)

        lora_config = LoraConfig(
            task_type=TaskType.SEQ_2_SEQ_LM,
            r=self.config.LORA_R,
            lora_alpha=self.config.LORA_ALPHA,
            lora_dropout=self.config.LORA_DROPOUT,
            target_modules=["q", "v"],  # T5 modules
        )

        self.model = get_peft_model(self.model, lora_config)
        self.model.print_trainable_parameters()

        return self.model

    def train(
        self,
        train_sequences: List[str],
        train_reasons: List[str],
        val_sequences: List[str],
        val_reasons: List[str],
    ) -> Dict:

        logger.info("Starting reasoning model training")

        train_dataset = ReasoningDataset(train_sequences, train_reasons, self.tokenizer)
        val_dataset = ReasoningDataset(val_sequences, val_reasons, self.tokenizer)

        self.setup_model()

        training_args = TrainingArguments(
            output_dir=str(self.config.MODEL_DIR / "reasoning" / "checkpoints"),
            num_train_epochs=self.config.REASONING_EPOCHS,
            per_device_train_batch_size=self.config.BATCH_SIZE,
            per_device_eval_batch_size=self.config.BATCH_SIZE,
            learning_rate=self.config.LEARNING_RATE,
            weight_decay=self.config.WEIGHT_DECAY,
            warmup_ratio=self.config.WARMUP_RATIO,
            eval_strategy="epoch",
            save_strategy="epoch",
            load_best_model_at_end=True,
            metric_for_best_model="eval_loss",
            greater_is_better=False,
            logging_dir=str(self.config.LOGS_DIR / "reasoning"),
            logging_steps=10,
            save_total_limit=2,
            report_to="none",
        )

        trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=val_dataset,
            callbacks=[
                EarlyStoppingCallback(early_stopping_patience=self.config.PATIENCE)
            ],
        )

        train_result = trainer.train()
        metrics = trainer.evaluate()

        save_path = self.config.MODEL_DIR / "reasoning" / "final"
        trainer.save_model(str(save_path))
        self.tokenizer.save_pretrained(str(save_path))

        logger.info(f"Reasoning training complete. Metrics: {metrics}")

        return metrics


def main():

    config = ModelConfig()

    preprocessor = DataPreprocessor(config)

    logger.info("=" * 80)
    logger.info("STEP 1: Loading and preprocessing data")
    logger.info("=" * 80)

    hdfs_file = config.DATA_DIR / "HDFS_train.csv"
    bgl_file = config.DATA_DIR / "BGL_train.csv"

    if hdfs_file.exists():
        logger.info(f"Using HDFS dataset: {hdfs_file}")
        df = preprocessor.load_hdfs_data(str(hdfs_file), max_samples=100000)
    elif bgl_file.exists():
        logger.info(f"Using BGL dataset: {bgl_file}")
        df = preprocessor.load_bgl_data(str(bgl_file))
    else:
        logger.error("No dataset found!")
        logger.error("Please run: python preprocess_hdfs.py")
        logger.error("Or ensure HDFS_train.csv or BGL_train.csv exists in data/")
        return

    logger.info(f"Dataset loaded: {len(df):,} logs, {df['Label'].sum():,} anomalies")

    logger.info("Converting to sequences...")
    sequences, labels = preprocessor.create_sequences(df, max_sequences=50000)

    logger.info(f"Sequences created: {len(sequences):,}")

    del df
    import gc

    gc.collect()
    logger.info("Memory cleaned")

    train_seqs, val_seqs, train_labels, val_labels = train_test_split(
        sequences, labels, test_size=0.2, random_state=42, stratify=labels
    )

    del sequences, labels
    gc.collect()

    logger.info(f"Train: {len(train_seqs):,} | Val: {len(val_seqs):,}")

    logger.info("=" * 80)
    logger.info("STEP 2: Training classification model")
    logger.info("=" * 80)

    classifier_trainer = ClassifierTrainer(config)
    classifier_metrics = classifier_trainer.train(
        train_seqs, train_labels, val_seqs, val_labels
    )

    logger.info("=" * 80)
    logger.info("STEP 3: Preparing reasoning data")
    logger.info("=" * 80)

    anomaly_seqs = [seq for seq, label in zip(train_seqs, train_labels) if label == 1]
    anomaly_reasons = preprocessor.generate_explanations(anomaly_seqs)

    reason_train_seqs, reason_val_seqs, reason_train_reasons, reason_val_reasons = (
        train_test_split(anomaly_seqs, anomaly_reasons, test_size=0.2, random_state=42)
    )

    logger.info("=" * 80)
    logger.info("STEP 4: Training reasoning model")
    logger.info("=" * 80)

    reasoning_trainer = ReasoningTrainer(config)
    reasoning_metrics = reasoning_trainer.train(
        reason_train_seqs, reason_train_reasons, reason_val_seqs, reason_val_reasons
    )

    logger.info("=" * 80)
    logger.info("TRAINING COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Classifier metrics: {classifier_metrics}")
    logger.info(f"Reasoning metrics: {reasoning_metrics}")
    logger.info(f"Models saved to: {config.MODEL_DIR}")


if __name__ == "__main__":
    main()
