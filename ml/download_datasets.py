import os
import urllib.request
import zipfile
from pathlib import Path
import pandas as pd


def download_file(url: str, destination: str):
    print(f"Downloading {url}...")

    def reporthook(count, block_size, total_size):
        percent = int(count * block_size * 100 / total_size)
        print(f"\rProgress: {percent}%", end="")

    urllib.request.urlretrieve(url, destination, reporthook)
    print("\nDownload complete!")


def download_hdfs_dataset():

    data_dir = Path("./data")
    data_dir.mkdir(exist_ok=True)

    url = "https://zenodo.org/record/3227177/files/HDFS_2.tar.gz"
    tar_file = data_dir / "HDFS.tar.gz"

    print("Downloading HDFS Dataset")

    if not tar_file.exists():
        download_file(url, str(tar_file))
    else:
        print(f"File already exists: {tar_file}")

    print("\nExtracting...")
    import tarfile

    with tarfile.open(tar_file, "r:gz") as tar:
        tar.extractall(data_dir)

    print(f"Dataset extracted to: {data_dir}")

    csv_files = list(data_dir.glob("**/*structured.csv"))
    if csv_files:
        print(f"\nFound structured file: {csv_files[0]}")
        return csv_files[0]

    return None


def download_bgl_dataset():

    data_dir = Path("./data")
    data_dir.mkdir(exist_ok=True)

    url = "https://zenodo.org/record/3227177/files/BGL.tar.gz"
    tar_file = data_dir / "BGL.tar.gz"

    print("Downloading BGL Dataset")
    if not tar_file.exists():
        download_file(url, str(tar_file))
    else:
        print(f"File already exists: {tar_file}")

    print("\nExtracting...")
    import tarfile

    with tarfile.open(tar_file, "r:gz") as tar:
        tar.extractall(data_dir)

    print(f"Dataset extracted to: {data_dir}")

    csv_files = list(data_dir.glob("**/*structured.csv"))
    if csv_files:
        print(f"\nFound structured file: {csv_files[0]}")
        return csv_files[0]

    return None


def prepare_sample_dataset():

    data_dir = Path("./data")
    data_dir.mkdir(exist_ok=True)

    sample_data = {
        "LineId": range(1, 2001),
        "Label": ["Normal"] * 1800 + ["Anomaly"] * 200,
        "Timestamp": [1117838570 + i for i in range(2000)],
        "Level": ["INFO"] * 1500 + ["ERROR"] * 300 + ["FATAL"] * 200,
        "Component": ["KERNEL"] * 1000 + ["APP"] * 1000,
        "Content": [
            (
                f"Normal log entry {i}"
                if i < 1800
                else (
                    f"Error: Connection timeout {i}"
                    if i < 1900
                    else f"FATAL: System crash {i}"
                )
            )
            for i in range(2000)
        ],
        "EventTemplate": [
            (
                "Normal log entry"
                if i < 1800
                else "Error Connection timeout" if i < 1900 else "FATAL System crash"
            )
            for i in range(2000)
        ],
    }

    df = pd.DataFrame(sample_data)

    output_file = data_dir / "sample_train.csv"
    df.to_csv(output_file, index=False)

    print(f"Created sample dataset: {output_file}")
    print(f"Total logs: {len(df)}")
    print(
        f"Anomalies: {(df['Label'] == 'Anomaly').sum()} ({(df['Label'] == 'Anomaly').sum() / len(df) * 100:.1f}%)"
    )

    return output_file


def main():

    print("LogAnomaly Dataset Downloader")
    print("\nSelect dataset to download:")
    print("1. HDFS - 11M logs")
    print("2. BGL - 4.7M logs")
    print("3. Sample - 2K logs")
    print("4. All datasets")

    choice = input("\nEnter choice (1-4): ").strip()

    if choice == "1":
        download_hdfs_dataset()
    elif choice == "2":
        download_bgl_dataset()
    elif choice == "3":
        prepare_sample_dataset()
    elif choice == "4":
        download_hdfs_dataset()
        download_bgl_dataset()
        prepare_sample_dataset()
    else:
        print("Invalid choice!")
        return

    print("Download complete...")


if __name__ == "__main__":
    main()
