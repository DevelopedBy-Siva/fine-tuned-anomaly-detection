# LogAnomaly

An intelligent log analysis system that uses fine-tuned Large Language Models (LLMs) to detect anomalies in system logs and generate human-readable explanations for detected issues.

## Overview

LogAnomaly leverages fine-tuned TinyLlama models with LoRA (Low-Rank Adaptation) to analyze log sequences from the BlueGene/L supercomputer system. The system employs two specialized models: a classification model for anomaly detection and a reasoning model for generating explanations. Using Drain3 for log parsing and sliding window sequence generation, the application provides real-time analysis through an intuitive desktop interface built with CustomTkinter.

## Features

- **Dual-Model Architecture** – Classification model for anomaly detection and reasoning model for explanation generation
- **Fine-Tuned LLM Classification** – TinyLlama model fine-tuned with LoRA for binary log sequence classification (Normal/Anomalous)
- **Intelligent Log Parsing** – Drain3 template mining for preprocessing raw logs and extracting patterns
- **Sliding Window Analysis** – Sequences logs using configurable window size and stride for context-aware detection
- **Explainable AI** – Generates natural language explanations for detected anomalies using causal language modeling
- **Desktop GUI Application** – CustomTkinter interface for importing log files and viewing analysis results
- **High Accuracy** – Achieves F1 score of 0.97+ with 94% precision and 100% recall on test data
- **Optimized Threshold Tuning** – Dynamic threshold adjustment based on precision-recall curves
- **Visual Analytics** – Color-coded anomaly highlighting with detailed reasoning display
- **Real-Time Processing** – Analyzes log files on-demand with progress indicators

## Tech Stack

- **Backend:** Python
- **Machine Learning:** PyTorch, Transformers, PEFT (LoRA)
- **Models:** TinyLlama-1.1B-Chat (fine-tuned)
- **NLP:** Drain3 (log parsing), Tokenization
- **Data Processing:** Pandas, NumPy
- **Evaluation:** Scikit-learn, Seaborn, Matplotlib
- **GUI:** CustomTkinter
- **Dataset:** BlueGene/L Supercomputer Logs

## Installation
```bash
# Clone the repository
git clone https://github.com/yourusername/log-anomaly.git
cd log-anomaly

# Install dependencies
pip install torch transformers peft datasets pandas numpy scikit-learn \
            drain3 customtkinter seaborn matplotlib

# Run the application
python main.py
```

## Project Structure
```
log-anomaly/
├── app/
│   ├── anomaly_detector.py     # Core anomaly detection logic
│   ├── ui.py                   # CustomTkinter GUI implementation
│   └── utils.py                # UI constants and utilities
├── notebook/
│   ├── model/
│   │   ├── classifier/         # Fine-tuned classification model
│   │   └── reasoning/          # Fine-tuned reasoning model
│   └── training_notebook.ipynb # Model training workflow
├── data/
│   ├── BGL_train.csv          # Training dataset
│   ├── test.log               # Test log file
│   └── anomaly_explanation.csv # Synthetic reasoning dataset
├── main.py                     # Application entry point
└── README.md
```

## How It Works

1. **Log Preprocessing** – Drain3 parses raw logs to extract templates and normalize dynamic fields
2. **Sequence Generation** – Sliding window (size=10, stride=3) creates overlapping log sequences
3. **Tokenization** – TinyLlama tokenizer converts sequences to model-ready input tensors
4. **Anomaly Classification** – Fine-tuned LoRA model predicts anomaly probability with optimized threshold
5. **Reasoning Generation** – Causal LM generates natural language explanations for detected anomalies
6. **Visualization** – GUI displays results with color-coded highlighting and detailed reasoning

## Model Architecture

### Classification Model
- **Base Model:** TinyLlama-1.1B-Chat-v1.0
- **Task:** Sequence Classification (Binary)
- **Fine-Tuning:** LoRA (r=32, alpha=64, dropout=0.1)
- **Target Modules:** q_proj, v_proj, k_proj
- **Training:** 10 epochs, AdamW optimizer, weighted cross-entropy loss
- **Performance:** F1=0.97, Precision=0.94, Recall=1.0

### Reasoning Model
- **Base Model:** TinyLlama-1.1B-Chat-v1.0
- **Task:** Causal Language Modeling
- **Fine-Tuning:** LoRA (r=32, alpha=64, dropout=0.1)
- **Training:** 10 epochs on synthetic reasoning dataset
- **Output:** 20-50 token explanations for anomalies

## Dataset

- **Source:** BlueGene/L Supercomputer System Logs
- **Training:** 2000 log entries (18.46% anomalous)
- **Preprocessing:** Drain3 template extraction, sequence windowing
- **Features:** Timestamp, Node ID, Log Level, Event Template, Content

## Usage

1. Launch the application with `python main.py`
2. Click "Import File" to select a `.log` file
3. Wait for analysis to complete (progress shown in UI)
4. View results:
   - **Header:** Total sequences, anomaly count, model confidence
   - **Log Entries:** Normal logs in gray, anomalies highlighted in yellow
   - **Reasoning:** Detailed explanations for each detected anomaly
5. Click "Reset" to clear results and analyze a new file

## Key Features in Detail

- **Drain3 Template Mining** – Automatically identifies log patterns and normalizes variable fields
- **Sliding Window Sequences** – Captures temporal context across 10 consecutive log entries
- **LoRA Fine-Tuning** – Parameter-efficient training with only 0.59% trainable parameters
- **Threshold Optimization** – Precision-recall curve analysis for optimal classification threshold
- **Explainable Predictions** – Human-readable reasoning for every detected anomaly
- **Confidence Metrics** – Model confidence scores displayed for transparency

## Performance Metrics

- **Classification F1 Score:** 0.9697
- **Precision:** 0.9412
- **Recall:** 1.0000
- **Trainable Parameters:** 0.59% of total model (6.1M / 1.04B)
- **Inference Speed:** Real-time analysis with batch processing

## Future Enhancements

- Multi-class anomaly classification (error types)
- Real-time log streaming and continuous monitoring
- Integration with system monitoring tools
- Anomaly severity scoring
- Historical trend analysis and reporting
- Support for additional log formats
- TinyLlama team for the base model
- BlueGene/L dataset contributors
- Hugging Face Transformers and PEFT libraries
