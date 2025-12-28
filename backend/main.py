from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
import logging
import time
from datetime import datetime
from pathlib import Path
import io

import torch
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    AutoModelForSeq2SeqLM,
)
from peft import PeftModel
import uvicorn

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class Config:
    MODEL_DIR = Path("../ml/models")
    CLASSIFIER_PATH = MODEL_DIR / "classifier" / "final"
    REASONING_PATH = MODEL_DIR / "reasoning" / "final"

    BASE_CLASSIFIER = "microsoft/deberta-v3-base"
    BASE_REASONING = "google/flan-t5-base"

    MAX_LENGTH = 256
    WINDOW_SIZE = 8
    STRIDE = 8
    CONFIDENCE_THRESHOLD = 0.65

    MAX_FILE_SIZE = 50 * 1024 * 1024

    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


config = Config()


class AnomalyResult(BaseModel):
    sequence_id: int
    confidence: float = Field(..., ge=0, le=1)
    severity: str = Field(..., description="high/medium/low")
    explanation: str
    log_snippet: str = Field(..., max_length=200)
    timestamp: Optional[str] = None


class AnalysisResponse(BaseModel):
    status: str
    total_sequences: int
    anomalies_detected: int
    anomaly_rate: float = Field(..., ge=0, le=1)
    processing_time: float
    results: List[AnomalyResult]
    summary: str


class HealthResponse(BaseModel):
    status: str
    models_loaded: bool
    device: str
    timestamp: str


class ModelManager:

    def __init__(self):
        self.classifier = None
        self.classifier_tokenizer = None
        self.reasoning = None
        self.reasoning_tokenizer = None
        self.device = torch.device(config.DEVICE)

        logger.info(f"Initializing ModelManager on device: {self.device}")

    def load_models(self):
        try:
            logger.info("Loading classifier model...")

            self.classifier_tokenizer = AutoTokenizer.from_pretrained(
                str(config.CLASSIFIER_PATH)
            )

            base_classifier = AutoModelForSequenceClassification.from_pretrained(
                config.BASE_CLASSIFIER, num_labels=2
            )

            self.classifier = PeftModel.from_pretrained(
                base_classifier, str(config.CLASSIFIER_PATH)
            )
            self.classifier.to(self.device)
            self.classifier.eval()

            logger.info("Classifier loaded successfully")

            logger.info("Loading reasoning model...")

            self.reasoning_tokenizer = AutoTokenizer.from_pretrained(
                str(config.REASONING_PATH)
            )

            base_reasoning = AutoModelForSeq2SeqLM.from_pretrained(
                config.BASE_REASONING
            )

            self.reasoning = PeftModel.from_pretrained(
                base_reasoning, str(config.REASONING_PATH)
            )
            self.reasoning.to(self.device)
            self.reasoning.eval()

            logger.info("Reasoning model loaded successfully")

            return True

        except Exception as e:
            logger.error(f"Error loading models: {e}")
            raise

    def predict(self, sequences: List[str]) -> List[Dict]:
        if self.classifier is None:
            raise RuntimeError("Models not loaded")

        results = []

        with torch.no_grad():
            encodings = self.classifier_tokenizer(
                sequences,
                truncation=True,
                padding=True,
                max_length=config.MAX_LENGTH,
                return_tensors="pt",
            )

            encodings = {k: v.to(self.device) for k, v in encodings.items()}

            outputs = self.classifier(**encodings)
            logits = outputs.logits
            probs = torch.softmax(logits, dim=1)

            for idx, (seq, prob) in enumerate(zip(sequences, probs)):
                anomaly_prob = prob[1].item()

                if anomaly_prob > config.CONFIDENCE_THRESHOLD:
                    explanation = self.generate_explanation(seq)

                    if anomaly_prob > 0.9:
                        severity = "high"
                    elif anomaly_prob > 0.7:
                        severity = "medium"
                    else:
                        severity = "low"

                    results.append(
                        {
                            "sequence_id": idx,
                            "confidence": anomaly_prob,
                            "severity": severity,
                            "explanation": explanation,
                            "log_snippet": seq[:200],
                        }
                    )

        return results

    def generate_explanation(self, sequence: str) -> str:
        try:
            prompt = (
                f"Analyze this log sequence and explain why it's anomalous:\n{sequence}"
            )

            inputs = self.reasoning_tokenizer(
                prompt,
                max_length=config.MAX_LENGTH,
                truncation=True,
                return_tensors="pt",
            )

            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            with torch.no_grad():
                outputs = self.reasoning.generate(
                    **inputs, max_new_tokens=64, num_beams=4, early_stopping=True
                )

            explanation = self.reasoning_tokenizer.decode(
                outputs[0], skip_special_tokens=True
            )

            return explanation

        except Exception as e:
            logger.error(f"Error generating explanation: {e}")
            return "Unable to generate explanation"


app = FastAPI(
    title="LogAnomaly API",
    description="ML-powered log anomaly detection with explainable AI",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

model_manager = ModelManager()


@app.on_event("startup")
async def startup_event():
    logger.info("Starting LogAnomaly API...")
    try:
        model_manager.load_models()
        logger.info("All models loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load models: {e}")
        raise


def parse_log_file(content: bytes) -> List[str]:
    try:
        text = content.decode("utf-8", errors="ignore")
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        return lines
    except Exception as e:
        logger.error(f"Error parsing log file: {e}")
        raise HTTPException(status_code=400, detail="Invalid log file format")


def create_sequences(logs: List[str], window_size: int, stride: int) -> List[str]:
    sequences = []

    for i in range(0, len(logs) - window_size + 1, stride):
        sequence = " ".join(logs[i : i + window_size])
        sequences.append(sequence)

    return sequences


@app.get("/", response_model=Dict)
async def root():
    return {
        "service": "LogAnomaly API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {"health": "/health", "analyze": "/analyze", "docs": "/docs"},
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="healthy",
        models_loaded=model_manager.classifier is not None,
        device=str(config.DEVICE),
        timestamp=datetime.now().isoformat(),
    )


@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_logs(file: UploadFile = File(...)):
    start_time = time.time()

    try:
        if not file.filename.endswith((".log", ".txt")):
            raise HTTPException(
                status_code=400, detail="Only .log and .txt files are supported"
            )

        content = await file.read()

        if len(content) > config.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Max size: {config.MAX_FILE_SIZE / 1024 / 1024}MB",
            )

        logger.info(f"Processing file: {file.filename} ({len(content)} bytes)")

        logs = parse_log_file(content)
        logger.info(f"Parsed {len(logs)} log lines")

        if len(logs) < config.WINDOW_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File must contain at least {config.WINDOW_SIZE} log lines",
            )

        sequences = create_sequences(logs, config.WINDOW_SIZE, config.STRIDE)
        logger.info(f"Created {len(sequences)} sequences")

        anomalies = model_manager.predict(sequences)

        processing_time = time.time() - start_time
        anomaly_rate = len(anomalies) / len(sequences) if sequences else 0

        if len(anomalies) == 0:
            summary = "No anomalies detected. All logs appear normal."
        elif anomaly_rate < 0.05:
            summary = f"{len(anomalies)} anomalies detected ({anomaly_rate*100:.1f}%). System appears mostly healthy."
        else:
            summary = f"{len(anomalies)} anomalies detected ({anomaly_rate*100:.1f}%). Immediate attention recommended."

        logger.info(
            f"Analysis complete: {len(anomalies)} anomalies in {processing_time:.2f}s"
        )

        return AnalysisResponse(
            status="success",
            total_sequences=len(sequences),
            anomalies_detected=len(anomalies),
            anomaly_rate=anomaly_rate,
            processing_time=processing_time,
            results=anomalies,
            summary=summary,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats")
async def get_stats():
    return {
        "model_info": {
            "classifier": {
                "name": "DeBERTa-v3-base",
                "precision": 0.999,
                "recall": 0.669,
                "f1_score": 0.801,
            },
            "reasoning": {"name": "FLAN-T5-base", "loss": 0.06},
        },
        "config": {
            "window_size": config.WINDOW_SIZE,
            "stride": config.STRIDE,
            "max_file_size_mb": config.MAX_FILE_SIZE / 1024 / 1024,
            "device": str(config.DEVICE),
        },
    }


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "Internal server error",
            "detail": str(exc),
        },
    )


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False, log_level="info")
