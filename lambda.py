import json
import logging
from pathlib import Path
import os
from send2trash import send2trash

# Configure logging for Lambda
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def clean_whisper_output(whisper_output_folder):
    # Use /tmp directory in Lambda for temporary files
    whisper_output_folder = f"/tmp/{whisper_output_folder}"
    for filename in os.listdir(whisper_output_folder):
        file_path = os.path.join(whisper_output_folder, filename)
        try:
            if os.path.isfile(file_path):
                send2trash(file_path)
                logger.info(f"Moved {file_path} to trash")
        except Exception as e:
            logger.error(f"Error while moving {file_path} to trash: {e}")

def lambda_handler(event, context):
    # Use /tmp directory in Lambda for all folders
    input_folder = '/tmp/input_files'
    output_video_folder = '/tmp/clipper_output' 
    crew_output_folder = '/tmp/crew_output'
    whisper_output_folder = '/tmp/whisper_output'
    subtitler_output_folder = '/tmp/subtitler_output'

    # Ensure directories exist in /tmp
    for folder in [input_folder, output_video_folder, crew_output_folder, 
                  whisper_output_folder, subtitler_output_folder]:
        os.makedirs(folder, exist_ok=True)

    try:
        # Get input from event payload
        youtube_url = event.get('youtube_url')
        choice = event.get('choice', '1')

        if choice == '1' and youtube_url:
            logger.info(f"Processing YouTube URL: {youtube_url}")
            # Call YouTube processing function
            ytdl_main(youtube_url, input_folder, whisper_output_folder, whisper_output_folder)
        elif choice == '2':
            logger.info("Using existing video file")
            # Process existing file from /tmp directory
            if not os.listdir(input_folder):
                return {
                    'statusCode': 400,
                    'body': json.dumps('No video files found in input folder')
                }
            clean_whisper_output(whisper_output_folder)
            local_whisper_process(input_folder, whisper_output_folder)

        return {
            'statusCode': 200,
            'body': json.dumps('Processing completed successfully')
        }

    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error: {str(e)}')
        }