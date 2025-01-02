# Standard library imports
from pathlib import Path
import os
import warnings
import logging
import argparse

# Third party imports
import torch
import whisper
from whisper.utils import get_writer
import boto3

# Local application imports
from utils import wait_for_file

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
warnings.filterwarnings("ignore")

# Initialize AWS S3 client
s3_client = boto3.client("s3")


def download_from_s3(bucket, key, local_path):
    """Download a file from S3 to a local path."""
    logging.info(f"Downloading file from S3: s3://{bucket}/{key} to {local_path}")
    s3_client.download_file(bucket, key, local_path)
    logging.info(f"Download complete: {local_path}")
    return local_path


def transcribe_file(model, srt, plain, file):
    input_file_path = Path(file)
    logging.info(f"Transcribing file: {input_file_path}\n")

    # Ensure the output directory exists
    output_dir = Path("whisper_output")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Run Whisper
    result = model.transcribe(str(input_file_path), fp16=False, verbose=False, language="en")

    output_file_name = input_file_path.stem

    if plain:
        txt_path = output_dir / f"{output_file_name}.txt"
        logging.info(f"Creating text file: {txt_path}")

        with open(txt_path, "w", encoding="utf-8") as txt:
            txt.write(result["text"])

        transcript = result["text"]

    if srt:
        logging.info(f"Creating SRT file")
        srt_writer = get_writer("srt", str(output_dir))
        srt_writer(result, output_file_name)

        # Construct the SRT file path manually
        srt_path = output_dir / f"{output_file_name}.srt"

        # Read the SRT subtitles from the generated file
        with open(srt_path, "r", encoding="utf-8") as srt_file:
            subtitles = srt_file.read()

    return result, transcript, subtitles


def transcribe_main(bucket_name, s3_key):
    # Specify the type of file outputs you need from Whisper
    plain = True
    srt = True

    # Whisper configuration
    # Use CUDA, if available
    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

    # Load the desired model
    model = whisper.load_model("medium.en").to(DEVICE)

    # Download file from S3
    local_file_path = f"downloads/{Path(s3_key).name}"
    os.makedirs("downloads", exist_ok=True)
    download_from_s3(bucket_name, s3_key, local_file_path)

    # Transcribe the downloaded file
    result, transcript, subtitles = transcribe_file(model, srt, plain, local_file_path)

    return transcript, subtitles


def process_s3_files(bucket_name, s3_prefix, crew_output_folder, transcribe_flag=True):
    """Process all files in an S3 bucket prefix."""
    paginator = s3_client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket_name, Prefix=s3_prefix):
        for obj in page.get("Contents", []):
            s3_key = obj["Key"]
            if s3_key.endswith(".mp4"):
                logging.info(f"Processing S3 object: {s3_key}")

                if transcribe_flag:
                    full_transcript, full_subtitles = transcribe_main(bucket_name, s3_key)
                    output_srt_path = os.path.join(crew_output_folder, f"{Path(s3_key).stem}_subtitles.srt")
                    with open(output_srt_path, "w") as srt_file:
                        srt_file.write(full_subtitles)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transcribe MP4 files from S3 bucket using Whisper")
    parser.add_argument("bucket_name", type=str, help="The name of the S3 bucket")
    parser.add_argument("s3_prefix", type=str, help="The S3 prefix (folder path) containing the MP4 files")
    parser.add_argument("--output_folder", type=str, default="crew_output", help="Local folder to store output files")

    args = parser.parse_args()

    bucket_name = args.bucket_name
    s3_prefix = args.s3_prefix
    crew_output_folder = args.output_folder

    os.makedirs(crew_output_folder, exist_ok=True)
    process_s3_files(bucket_name, s3_prefix, crew_output_folder)