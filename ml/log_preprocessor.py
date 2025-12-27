import re
import pandas as pd
from pathlib import Path
from typing import List, Dict, Optional
import logging
from tqdm import tqdm
import gc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HDFSLogParser:

    def __init__(self):
        self.log_pattern = re.compile(
            r"^(?P<Date>\d{4}-\d{2}-\d{2})\s+"
            r"(?P<Time>\d{2}:\d{2}:\d{2},\d{3})\s+"
            r"(?P<Level>\w+)\s+"
            r"(?P<Component>[\w\.$]+):\s+"
            r"(?P<Content>.*)",
            re.MULTILINE,
        )

        self.anomaly_keywords = [
            "exception",
            "error",
            "fail",
            "timeout",
            "corrupt",
            "lost",
            "unable",
            "denied",
            "abort",
            "fatal",
            "crash",
            "eof",
            "refused",
            "rejected",
            "invalid",
        ]

        self.line_count = 0

    def is_anomaly(self, content: str, level: str) -> int:
        """Determine if log is anomaly"""
        content_lower = content.lower()
        level_lower = level.lower()

        if level_lower in ["error", "fatal"]:
            return 1

        if level_lower == "warn":
            if any(k in content_lower for k in ["exception", "error", "fail", "eof"]):
                return 1

        if any(keyword in content_lower for keyword in self.anomaly_keywords):
            return 1

        return 0

    def parse_log_line(self, line: str, source_file: str) -> Optional[Dict]:
        if not line.strip():
            return None

        match = self.log_pattern.match(line.strip())

        if not match:
            return None

        log_dict = match.groupdict()

        log_dict["Content"] = " ".join(log_dict["Content"].split())

        log_dict["EventTemplate"] = log_dict["Content"][:100]
        log_dict["EventId"] = "E1"

        log_dict["Label"] = self.is_anomaly(log_dict["Content"], log_dict["Level"])

        self.line_count += 1
        log_dict["LineId"] = self.line_count
        log_dict["SourceFile"] = source_file

        return log_dict

    def process_file_to_csv(
        self, filepath: Path, output_csv: Path, chunk_size: int = 100000
    ):
        logger.info(f"Processing {filepath.name}...")

        chunk_data = []
        total_logs = 0
        total_anomalies = 0

        write_header = not output_csv.exists()

        try:
            with open(filepath, "r", errors="ignore", encoding="utf-8") as f:
                for line in f:
                    parsed = self.parse_log_line(line, filepath.name)
                    if parsed:
                        chunk_data.append(parsed)
                        total_logs += 1
                        if parsed["Label"] == 1:
                            total_anomalies += 1

                        if len(chunk_data) >= chunk_size:
                            df = pd.DataFrame(chunk_data)
                            df.to_csv(
                                output_csv, mode="a", header=write_header, index=False
                            )
                            write_header = False
                            chunk_data = []
                            gc.collect()

                if chunk_data:
                    df = pd.DataFrame(chunk_data)
                    df.to_csv(output_csv, mode="a", header=write_header, index=False)
                    chunk_data = []
                    gc.collect()

        except Exception as e:
            logger.error(f"Error processing {filepath}: {e}")
            return 0, 0

        logger.info(
            f"  {total_logs:,} logs ({total_anomalies:,} anomalies, {total_anomalies/max(total_logs,1)*100:.1f}%)"
        )
        return total_logs, total_anomalies

    def process_directory_streaming(
        self, data_dir: Path, output_file: Path, max_files: int = None
    ) -> tuple:

        log_files = sorted(data_dir.glob("hadoop-*.log"))

        if not log_files:
            logger.error(f"No HDFS log files found in {data_dir}")
            return 0, 0

        if max_files:
            log_files = log_files[:max_files]

        logger.info(f"Found {len(log_files)} HDFS log files")
        logger.info(
            f"Total size: {sum(f.stat().st_size for f in log_files) / (1024**2):.1f} MB"
        )

        if output_file.exists():
            output_file.unlink()

        total_logs = 0
        total_anomalies = 0

        for log_file in tqdm(log_files, desc="Processing files"):
            logs, anomalies = self.process_file_to_csv(log_file, output_file)
            total_logs += logs
            total_anomalies += anomalies

        logger.info(f"\n{'='*60}")
        logger.info(f"Total logs: {total_logs:,}")
        logger.info(
            f"Total anomalies: {total_anomalies:,} ({total_anomalies/max(total_logs,1)*100:.2f}%)"
        )
        logger.info(f"{'='*60}")

        return total_logs, total_anomalies


def create_train_test_split_streaming(
    input_file: Path, data_dir: Path, test_size: float = 0.2, sample_size: int = 1000000
):
    logger.info(f"\nCreating train/test split (sampling {sample_size:,} logs)...")

    total_lines = sum(1 for _ in open(input_file))
    logger.info(f"Total logs in file: {total_lines:,}")

    if total_lines > sample_size:
        skip_prob = 1 - (sample_size / total_lines)
        logger.info(
            f"Sampling ~{sample_size:,} logs (skip probability: {skip_prob:.3f})"
        )
    else:
        skip_prob = 0
        logger.info(f"Using all {total_lines:,} logs")

    import random

    random.seed(42)

    sampled_data = []
    chunk_size = 100000

    logger.info("Reading and sampling data...")
    for chunk in tqdm(
        pd.read_csv(input_file, chunksize=chunk_size), total=total_lines // chunk_size
    ):
        if skip_prob > 0:
            mask = [random.random() > skip_prob for _ in range(len(chunk))]
            sampled_chunk = chunk[mask]
        else:
            sampled_chunk = chunk

        sampled_data.append(sampled_chunk)

        if sum(len(d) for d in sampled_data) >= sample_size:
            break

    df = pd.concat(sampled_data, ignore_index=True)
    logger.info(f"Sampled {len(df):,} logs")

    from sklearn.model_selection import train_test_split

    train_df, test_df = train_test_split(
        df, test_size=test_size, random_state=42, stratify=df["Label"]
    )

    train_file = data_dir / "HDFS_train.csv"
    test_file = data_dir / "HDFS_test.csv"

    train_df.to_csv(train_file, index=False)
    test_df.to_csv(test_file, index=False)

    logger.info(
        f"\nTrain set: {len(train_df):,} logs ({train_df['Label'].mean()*100:.2f}% anomaly)"
    )
    logger.info(
        f"Test set:  {len(test_df):,} logs ({test_df['Label'].mean()*100:.2f}% anomaly)"
    )
    logger.info(f"\nFiles saved:")
    logger.info(f"  {train_file}")
    logger.info(f"  {test_file}")

    return train_file, test_file


def show_sample_logs(csv_file: Path, n_samples: int = 5):
    logger.info("\n" + "=" * 80)
    logger.info("📊 Sample Logs")
    logger.info("=" * 80)

    df = pd.read_csv(csv_file, nrows=10000)

    normal_df = df[df["Label"] == 0].head(n_samples)
    if len(normal_df) > 0:
        print("\nSample NORMAL logs:")
        for idx, row in normal_df.iterrows():
            print(f"[{row['Level']}] {row['Component']}: {row['Content'][:80]}...")

    anomaly_df = df[df["Label"] == 1].head(n_samples)
    if len(anomaly_df) > 0:
        print("\nSample ANOMALY logs:")
        for idx, row in anomaly_df.iterrows():
            print(f"[{row['Level']}] {row['Component']}: {row['Content'][:80]}...")

    logger.info("=" * 80)


def main():

    print("=" * 80)
    print("HDFS Log Preprocessor - Memory Efficient")
    print("=" * 80)

    data_dir = Path("./data")
    output_file = data_dir / "HDFS_structured.csv"

    log_files = list(data_dir.glob("hadoop-*.log"))
    if not log_files:
        print(f"\nNo HDFS log files found in {data_dir}")
        return

    print(f"\nFound {len(log_files)} HDFS log files")

    print("\nOptions:")
    print("1. Process first 5 files")
    print("2. Process first 10 files")
    print("3. Process ALL files")

    choice = input("\nEnter choice (1/2/3): ").strip() or "3"

    max_files = None
    if choice == "1":
        max_files = 5
    elif choice == "2":
        max_files = 10

    print("\n" + "=" * 80)
    print("Step 1: Parsing logs (streaming to CSV)...")
    print("=" * 80)

    parser = HDFSLogParser()
    total_logs, total_anomalies = parser.process_directory_streaming(
        data_dir, output_file, max_files=max_files
    )

    if total_logs == 0:
        print("\nFailed to process logs")
        return

    show_sample_logs(output_file)

    print("\n" + "=" * 80)
    print("Step 2: Creating train/test split...")
    print("=" * 80)

    train_file, test_file = create_train_test_split_streaming(
        output_file, data_dir, sample_size=1000000
    )

    print("Preprocessing Complete!")

    print(f"\nDataset Statistics:")
    print(f"  Full dataset:   {total_logs:,} logs")
    print(f"  Anomaly rate:   {total_anomalies/max(total_logs,1)*100:.2f}%")
    print(f"  Training set:   {pd.read_csv(train_file).shape[0]:,} logs")
    print(f"  Test set:       {pd.read_csv(test_file).shape[0]:,} logs")

    print(f"\nFiles created:")
    print(f"  Full dataset:   {output_file}")
    print(f"  Training set:   {train_file}")
    print(f"  Test set:       {test_file}")

    gc.collect()


if __name__ == "__main__":
    main()
