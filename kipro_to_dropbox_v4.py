"""
Copy Right Abram Murphy
Customized For: Vineyard Columbus

AJA Ki Pro to Dropbox Automation Script
Transfers specific .mov files from Ki Pro to Dropbox weekly and wipes the media of all three Ki Pros
"""

import requests
import dropbox
import os
import json
import time
import logging
from datetime import datetime
from pathlib import Path
import schedule

# Configuration
KIPRO_IP = "10.3.10.13"  # Only retrives files from Ki Pro 3
KIPRO_2_IP = ""  # For formatting only
KIPRO_3_IP = ""  # For formatting only
DROPBOX_ACCESS_TOKEN = "sl.u.AFwIKLFkTyHoolcjuyM3MrBRqLglhz5UnB15o78CkGeS1Y6AfHaho8TuZh7R-GX7Un9UUVQTdEEuxT8gv-sTIZj0ZY1cWtOJThd2c-qW8cpbtdhwrvgKik2GW8ZQkfVYFwDJCi126-1F9oFCXODoyjfn6yDQSXlgQnuvrUliOajVy3m4dmpTYbrpH5eqC6NMvf2hkVAl5IQHW4-ArxuZinHVMHAMIu8Ne2iKyyrcVC5RGnqpke8esnBUQPBhtK3K-9q2bS92xD1pB_n83Wr6U1DoJeUft8mBMtzmp9suL_x4V3OhbE-PUxncFByYzmiwIozje83iFu-qbdNgba01UGkx9HgCheQMoZrSO62YwMWWJe8uufegh64QR4H14385I59FX3hik1-64aJ7u6S0IULQt_sQhjkpVD2FRDKP46dNXvOSzCt2wi2jFcZrFZyIphSug86K0Nvjqyp2uxWJu7-gFO-RrLZrMmHAAbNnCge19oEdWTL_130GkuDIB1dzrF2GaE_D8w7h7Ud_FxFxDR_c54JPEl8WZZZcfTDZT7KPtqmlXhrejsMYI4KYF_65UHSUlPstUbdIHqUDxHpes0aK6CZixQKn5Mz8_4xOY7mKxHsDSnv1yG7cg2Oko1EtRod9g6w1jw9lLQ5qfffACU2xNbFYJGY80ZGHDWWRIPz7JHA7Gk3FxwVWT_MqAHhlJyLAe5u6Vz8UtUSBgrm6Uux3g9PpuN_7opHoGzctDud6gi8xMWAh8emNUYsjzXYGBFSwJ5ftJEku3QUfsBgmVpF6iMnoTpkm4lZMHw16eFzDCr8q8eiYeK0dWKDXMQUIBeN_Ww-U2n8mkjFVecqM0sbLf6aVevmihVoB8yt-eDQ1wndIqd4AvLzEfTcJRSSzkVrc_9R75pKrgYqFwb1xf785gJAWa76HdaCSkLsrJmHGAjN3wtOyeTDwXwEDcuyMNhV5YO9eV5b_Kw2BPSxHwz63GWJcu10_dnBLW_32KnmUt9vPT1KkbnfrdcqZB0hHJSoF70UAXJwTkQU7TFuUt3xlLrE0XQj3EkXqK-0qRJ39CkRw35eUP9yTdyDTs_ubOndC3B7Ww2iXXswkOxpNTWofS3yEdgscyO4NqAVe8Bdr1j1kInJd29BjtaaKWXlZzvNpfdT5z5_e5Kk5ATuRFP9EBQSSNTuLyllbBfZdL9ObuAUgKz7BfxttFAMPvgckpXBcoKJhNzLYZMTdahfHHx25oXS-wBOhcHvFeKF-5LLKVVApb2o7R3qaLQRnthfesMgd-2wmueUQYJg66EMIiAgayC3F7QLwsW-RlNGMV6gAyENvYJKL3bGwRMU2Cxl56FU"  # Get from Dropbox API
DROPBOX_FOLDER = "/AUTO TEST"  # Dropbox destination folder
LOCAL_TEMP_DIR = "./temp_downloads"  # Local temporary storage
LOG_FILE = "kipro_automation.log"

# Files to backup - Add your specific file names here
FILES_TO_UPLOAD = [
    "test_file.txt"
    # Add more specific filenames as needed
]

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

class KiProAutomation:
    def __init__(self):
        self.kipro_base_url = f"http://{KIPRO_IP}"
        self.dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)
        self.temp_dir = Path(LOCAL_TEMP_DIR)
        self.temp_dir.mkdir(exist_ok=True)
        
    def set_kipro_data_mode(self, enable=True):
        """Set Ki Pro to Data-LAN mode for file transfers"""
        mode = 1 if enable else 0  # 1 = Data-LAN, 0 = Record-Play
        url = f"{self.kipro_base_url}/config?action=set&paramid=eParamID_MediaState&value={mode}"
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            mode_name = "Data-LAN" if enable else "Record-Play"
            logging.info(f"Ki Pro set to {mode_name} mode")
            return True
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to set Ki Pro mode: {e}")
            return False
    
    def check_file_exists(self, filename):
        """Check if a specific file exists on the Ki Pro"""
        check_url = f"{self.kipro_base_url}/media/{filename}"
        
        try:
            response = requests.head(check_url, timeout=10)
            if response.status_code == 200:
                logging.info(f"File {filename} exists on Ki Pro")
                return True
            else:
                logging.info(f"File {filename} not found on Ki Pro (status: {response.status_code})")
                return False
        except requests.exceptions.RequestException as e:
            logging.warning(f"Could not check if {filename} exists: {e}")
            return False
    
    def download_file_from_kipro(self, filename):
        """Download a single file from Ki Pro"""
        local_path = self.temp_dir / filename
        download_url = f"{self.kipro_base_url}/media/{filename}"
        
        try:
            logging.info(f"Downloading {filename} from Ki Pro...")
            response = requests.get(download_url, stream=True, timeout=30)
            response.raise_for_status()
            
            # Get file size from headers if available
            total_size = int(response.headers.get('content-length', 0))
            if total_size > 0:
                logging.info(f"File size: {total_size / (1024*1024):.1f} MB")
            
            with open(local_path, 'wb') as f:
                downloaded = 0
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    # Log progress for large files
                    if total_size > 0 and downloaded % (10*1024*1024) == 0:  # Every 10MB
                        progress = (downloaded / total_size) * 100
                        logging.info(f"Download progress: {progress:.1f}%")
            
            logging.info(f"Downloaded {filename} to {local_path}")
            return local_path
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to download {filename}: {e}")
            return None
    
    def upload_to_dropbox(self, local_file_path, dropbox_path):
        """Upload file to Dropbox"""
        try:
            with open(local_file_path, 'rb') as f:
                file_size = os.path.getsize(local_file_path)
                logging.info(f"Uploading {local_file_path.name} ({file_size / (1024*1024):.1f} MB) to Dropbox...")
                
                if file_size <= 150 * 1024 * 1024:  # Files smaller than 150MB
                    self.dbx.files_upload(f.read(), dropbox_path, mode=dropbox.files.WriteMode.overwrite)
                else:
                    # Use upload session for large files
                    self._upload_large_file(f, dropbox_path, file_size)
                
                logging.info(f"Uploaded {local_file_path.name} to Dropbox: {dropbox_path}")
                return True
                
        except Exception as e:
            logging.error(f"Failed to upload {local_file_path.name} to Dropbox: {e}")
            return False
    
    def _upload_large_file(self, file_obj, dropbox_path, file_size):
        """Upload large files using Dropbox upload session"""
        CHUNK_SIZE = 4 * 1024 * 1024  # 4MB chunks
        
        session_start_result = self.dbx.files_upload_session_start(file_obj.read(CHUNK_SIZE))
        cursor = dropbox.files.UploadSessionCursor(
            session_id=session_start_result.session_id,
            offset=file_obj.tell()
        )
        
        while file_obj.tell() < file_size:
            if (file_size - file_obj.tell()) <= CHUNK_SIZE:
                # Final chunk
                commit = dropbox.files.CommitInfo(path=dropbox_path, mode=dropbox.files.WriteMode.overwrite)
                self.dbx.files_upload_session_finish(file_obj.read(CHUNK_SIZE), cursor, commit)
            else:
                self.dbx.files_upload_session_append_v2(file_obj.read(CHUNK_SIZE), cursor)
                cursor.offset = file_obj.tell()
                
                # Log progress for large files
                progress = (file_obj.tell() / file_size) * 100
                logging.info(f"Upload progress: {progress:.1f}%")
    
    def cleanup_local_files(self):
        """Remove temporary downloaded files"""
        try:
            for file_path in self.temp_dir.glob("*.mov"):
                file_path.unlink()
                logging.info(f"Deleted local file: {file_path}")
        except Exception as e:
            logging.error(f"Error cleaning up local files: {e}")
    
    def format_kipro_media(self):
        """Format/wipe the Ki Pro media"""
        try:
            # First set format type to HSF+ (you can change to ExFat by using value=1)
            format_url = f"{self.kipro_base_url}/config?action=set&paramid=eParamID_FileSystemFormat&value=0"
            # Also format other Ki Pros
            format_url_2 = f"{f"http://{KIPRO_2_IP}"}/config?action=set&paramid=eParamID_FileSystemFormat&value=0"
            format_url_3 = f"{f"http://{KIPRO_3_IP}"}/config?action=set&paramid=eParamID_FileSystemFormat&value=0"
            response = requests.get(format_url, timeout=10)
            response = requests.get(format_url_2, timeout=10)
            response = requests.get(format_url_3, timeout=10)

            response.raise_for_status()
            
            # Wait a moment
            time.sleep(2)
            
            # Execute the format command
            erase_url = f"{self.kipro_base_url}/config?action=set&paramid=eParamID_StorageCommand&value=4"
            response = requests.get(erase_url, timeout=10)
            response.raise_for_status()
            
            logging.info("Ki Pro media format initiated")
            return True
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to format Ki Pro media: {e}")
            return False
    
    def run_weekly_upload(self):
        """Main upload routine - run this weekly"""
        logging.info("=== Starting weekly Ki Pro upload ===")
        
        try:
            # Step 1: Set Ki Pro to Data-LAN mode
            if not self.set_kipro_data_mode(True):
                logging.error("Failed to set Data-LAN mode, aborting upload")
                return False
            
            time.sleep(5)  # Wait for mode change
            
            # Step 2: Check which files exist and prepare backup list
            existing_files = []
            for filename in FILES_TO_UPLOAD:
                if self.check_file_exists(filename):
                    existing_files.append(filename)
            
            if not existing_files:
                logging.info("No specified files found to upload")
            else:
                logging.info(f"Found {len(existing_files)} files to upload: {existing_files}")
            
            # Step 3: Create timestamped folder in Dropbox
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            dropbox_backup_folder = f"{DROPBOX_FOLDER}/upload_{timestamp}"
            
            # Step 4: Download and upload each existing file
            successful_uploads = 0
            for filename in existing_files:
                local_file = self.download_file_from_kipro(filename)
                if local_file:
                    dropbox_path = f"{dropbox_backup_folder}/{filename}"
                    if self.upload_to_dropbox(local_file, dropbox_path):
                        successful_uploads += 1
            
            logging.info(f"Successfully uploaded {successful_uploads}/{len(existing_files)} files")
            
            # Step 5: Clean up local temporary files
            self.cleanup_local_files()
            
            # Step 6: Format Ki Pro media (only if uploads were successful)
            if successful_uploads == len(existing_files) and existing_files:
                logging.info("All files uploaded successfully, formatting Ki Pro media...")
                self.format_kipro_media()
            elif not existing_files:
                logging.info("No files to backup, format aborted...")
            else:
                logging.warning("Some uploads failed, format aborted")
            
            # Step 7: Return Ki Pro to Record-Play mode
            time.sleep(10)  # Wait for format to complete
            self.set_kipro_data_mode(False)
            
            logging.info("=== Weekly upload completed ===")
            return True
            
        except Exception as e:
            logging.error(f"Upload failed with error: {e}")
            # Try to return to Record-Play mode
            self.set_kipro_data_mode(False)
            return False

def main():
    """Main function to setup scheduling"""
    automation = KiProAutomation()
    
    # Schedule weekly backup (every Sunday at 2 AM)
    # schedule.every().sunday.at("02:00").do(automation.run_weekly_upload)

    # Alternative scheduling options:
    # schedule.every().monday.at("02:00").do(automation.run_weekly_upload)  # Every Monday
    # schedule.every(7).days.at("02:00").do(automation.run_weekly_upload)   # Every 7 days
    
    logging.info("Ki Pro automation scheduler started")
    logging.info("Weekly upload scheduled for Sundays at 2:00 AM")
    logging.info(f"Files to upload: {FILES_TO_UPLOAD}")
    
    # Keep the script running
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

if __name__ == "__main__":
    # For testing, you can run the backup immediately:
    automation = KiProAutomation()
    automation.run_weekly_upload()
    
    # For production, run the scheduler:
    # main()
