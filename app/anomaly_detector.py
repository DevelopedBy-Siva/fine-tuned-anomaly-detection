import os
import numpy as np
from drain3.template_miner_config import TemplateMinerConfig
from drain3.template_miner import TemplateMiner
import torch
from torch.utils.data import Dataset, DataLoader
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    AutoModelForCausalLM,
)
from peft import PeftModel, PeftConfig


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REASONING_MODEL_LOCATION = os.path.abspath(
    os.path.join(BASE_DIR, "../notebook/model/reasoning/anomaly_reasoning")
)
CLASSIFICATION_MODEL_LOCATION = os.path.abspath(
    os.path.join(BASE_DIR, "../notebook/model/classifier/anomaly_classifier")
)


class LogDataset(Dataset):
    def __init__(self, encodings, labels):
        self.encodings = encodings
        self.labels = labels

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        item = {key: val[idx] for key, val in self.encodings.items()}
        item["labels"] = torch.tensor(self.labels[idx], dtype=torch.long)
        return item


class AnomalyDetector:
    def __init__(self, logs):
        self.logs = logs
        self.log_sequences = self.__pre_process()

    def __pre_process(self):
        config = TemplateMinerConfig()
        template_miner = TemplateMiner(config=config)

        test_logs = []
        for line in self.logs:
            result = template_miner.add_log_message(line)
            if result is not None:
                test_logs.append({"raw": line, "processed": result["template_mined"]})

        # window slicing: form sequences
        window_size = 10
        stride = 3

        # Generate sequences
        sequences = []
        for i in range(0, len(test_logs) - window_size + 1, stride):
            raw_sequence = " ".join(
                [log["raw"] for log in test_logs[i : i + window_size]]
            )
            processed_sequence = " ".join(
                [log["processed"] for log in test_logs[i : i + window_size]]
            )
            sequences.append(
                {"raw_sequence": raw_sequence, "processed_sequence": processed_sequence}
            )
        return sequences

    def __tokenize_sequences(self, sequences, tokenizer, max_length=512):
        return tokenizer(
            sequences,
            truncation=True,
            padding=True,
            max_length=max_length,
            return_tensors="pt",
        )

    def detect(self):
        """
        Returns:
            int: log sequence count,
            int: anomaly count,
            int: model confidence,
            list: all logs sequences
        """
        self.raw_sequences = [seq["raw_sequence"] for seq in self.log_sequences]
        self.processed_sequences = [
            seq["processed_sequence"] for seq in self.log_sequences
        ]

        # define tokenizer
        tokenizer = AutoTokenizer.from_pretrained(CLASSIFICATION_MODEL_LOCATION)
        encodings = self.__tokenize_sequences(self.processed_sequences, tokenizer)
        # create dataset
        dataset = LogDataset(encodings, [0] * len(self.processed_sequences))
        loader = DataLoader(dataset, batch_size=8, shuffle=False)

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # classification model
        peft_config = PeftConfig.from_pretrained(CLASSIFICATION_MODEL_LOCATION)
        base_model = AutoModelForSequenceClassification.from_pretrained(
            peft_config.base_model_name_or_path,
            num_labels=2,
            pad_token_id=tokenizer.pad_token_id,
        )
        classification_model = PeftModel.from_pretrained(
            base_model, CLASSIFICATION_MODEL_LOCATION
        )
        classification_model.to(device)
        classification_model.eval()

        # reasoning model
        peft_config = PeftConfig.from_pretrained(REASONING_MODEL_LOCATION)
        reasoning_model = AutoModelForCausalLM.from_pretrained(
            peft_config.base_model_name_or_path
        )
        reasoning_model = PeftModel.from_pretrained(
            reasoning_model, REASONING_MODEL_LOCATION
        )
        reasoning_model.to(device)
        reasoning_model.eval()

        # predict anomaly or normal
        predictions = []
        all_confidences = []
        with torch.no_grad():
            for batch in loader:
                input_ids = batch["input_ids"].to(device)
                attention_mask = batch["attention_mask"].to(device)
                outputs = classification_model(input_ids, attention_mask=attention_mask)
                probs = torch.nn.functional.softmax(outputs.logits, dim=1)
                preds = (probs[:, 1] > 0.1039).cpu().numpy().astype(int)
                confidences = probs[:, 1].cpu().numpy()
                predictions.extend(preds)
                all_confidences.extend(confidences)

        # generate anomaly reason
        max_new_tokens = 20
        anomalous_sequences = []
        output = []

        for i, (seq, pred) in enumerate(zip(self.processed_sequences, predictions)):
            explanation = None
            if pred == 1:
                prompt = f"Sequence: {seq} Reason:"
                inputs = tokenizer(prompt, return_tensors="pt").to(device)
                with torch.no_grad():
                    outputs = reasoning_model.generate(
                        **inputs,
                        max_new_tokens=max_new_tokens,
                        pad_token_id=tokenizer.pad_token_id,
                    )
                explanation = tokenizer.decode(outputs[0], skip_special_tokens=True)[
                    len(prompt) :
                ].strip()
                anomalous_sequences.append(
                    (seq, explanation, self.raw_sequences[i])
                )  # store anomalies
            output.append(
                (seq, self.raw_sequences[i], explanation, pred)
            )  # normal and anomaly data
        avg_confidence = float(np.mean(all_confidences))
        avg_confidence = f"{avg_confidence * 100:.2f}%"
        return len(output), len(anomalous_sequences), avg_confidence, output
