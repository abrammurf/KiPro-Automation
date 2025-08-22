"""
Copy Right Abram Murphy
Customized For: Vineyard Columbus

AJA Ki Pro to Dropbox Automation Script
Transfers specific .mov files from Ki Pro to Dropbox weekly and wipes the media of all three Ki Pros
Enhanced with automatic recording functionality and improved Dropbox authentication
"""

import requests
import dropbox
from dropbox import DropboxOAuth2FlowNoRedirect
import os
import json
import time
import logging
from datetime import datetime
from pathlib import Path
import schedule
from urllib.parse import quote

# Configuration
KIPRO_3_IP = ""  # Only retrieves files from Ki Pro 3
KIPRO_2_IP = ""  # For formatting/recording only
KIPRO_1_IP = ""  # For formatting/recording only
DROPBOX_FOLDER = "/AUTO TEST"  # Dropbox destination folder
LOCAL_TEMP_DIR = "./temp_downloads"  # Local temporary storage
LOG_FILE = "kipro_automation.log"
TOKEN_FILE = "dropbox_token.json"  # File to store Dropbox tokens

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

def save_tokens(access_token, refresh_token=None):
    """Save Dropbox tokens to file"""
    tokens = {
        'access_token': access_token,
        'refresh_token': refresh_token,
        'created_at': datetime.now().isoformat()
    }
    
    try:
        with open(TOKEN_FILE, 'w') as f:
            json.dump(tokens, f, indent=2)
        logging.info("Dropbox tokens saved successfully")
    except Exception as e:
        logging.error(f"Failed to save tokens: {e}")

def load_tokens():
    """Load Dropbox tokens from file"""
    try:
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, 'r') as f:
                tokens = json.load(f)
            logging.info("Dropbox tokens loaded from file")
            return tokens.get('access_token'), tokens.get('refresh_token')
    except Exception as e:
        logging.error(f"Failed to load tokens: {e}")
    
    return None, None

def get_dropbox_access_token():
    """Get Dropbox access token through OAuth flow or from saved file"""
    # First try to load existing tokens
    access_token, refresh_token = load_tokens()
    
    if access_token:
        # Test if the token still works
        try:
            dbx = dropbox.Dropbox(access_token)
            dbx.users_get_current_account()
            logging.info("Using existing Dropbox access token")
            return access_token
        except Exception as e:
            logging.warning(f"Existing token invalid: {e}")
            # Token is invalid, need to get a new one
    
    # Your app's credentials
    APP_KEY = '4rfvzrcbfo8jx9z'
    APP_SECRET = 'ay4y7k5ozlhihwv'

    print("\n" + "="*50)
    print("DROPBOX AUTHENTICATION REQUIRED")
    print("="*50)
    print("This is a one-time setup. The token will be saved for future use.")
    
    # OAuth flow
    auth_flow = DropboxOAuth2FlowNoRedirect(APP_KEY, APP_SECRET, token_access_type='offline')

    authorize_url = auth_flow.start()
    print(f"\n1. Open this URL in your browser:")
    print(f"   {authorize_url}")
    print("\n2. Click 'Allow' (you might have to log in first)")
    print("3. Copy the authorization code from the success page")

    auth_code = input("\nEnter the authorization code here: ").strip()

    try:
        oauth_result = auth_flow.finish(auth_code)
        access_token = oauth_result.access_token
        refresh_token = getattr(oauth_result, 'refresh_token', None)
        
        # Save tokens for future use
        save_tokens(access_token, refresh_token)
        
        print("\n✓ Authentication successful! Token saved for future use.")
        print("="*50)
        
        return access_token

    except Exception as e:
        logging.error(f"Authentication failed: {e}")
        print(f"\n✗ Authentication failed: {e}")
        return None

def test_dropbox_connection(access_token):
    """Test Dropbox connection"""
    try:
        dbx = dropbox.Dropbox(access_token)
        account = dbx.users_get_current_account()
        logging.info(f"Connected to Dropbox as: {account.name.display_name}")
        return True
    except Exception as e:
        logging.error(f"Dropbox connection test failed: {e}")
        return False

class KiProAutomation:
    def __init__(self):
        self.kipro_base_url = f"http://{KIPRO_3_IP}"
        
        # Get Dropbox access token
        access_token = get_dropbox_access_token()
        if not access_token:
            raise ValueError("Failed to obtain Dropbox access token")
        
        # Test connection
        if not test_dropbox_connection(access_token):
            raise ValueError("Dropbox connection test failed")
        
        # Initialize Dropbox client
        self.dbx = dropbox.Dropbox(access_token)
        self.temp_dir = Path(LOCAL_TEMP_DIR)
        self.temp_dir.mkdir(exist_ok=True)
        
        logging.info("KiProAutomation initialized successfully")
    
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
    
    def get_kipro_status(self, kipro_ip):
        """Get current status of a Ki Pro device"""
        def _get_json(paramid, timeout=5):
            url = f"http://{kipro_ip}/config"
            try:
                r = requests.get(url, params={"action":"get","paramid":paramid}, timeout=timeout)
                r.raise_for_status()
                # Ki Pro returns JSON like: {"paramid":"...","name":"...","value":"...","value_name":""}
                return r.json().get("value", "").strip()
            except Exception:
                return "unknown"

        try:
            transport_state = _get_json("eParamID_TransportState")
            media_state     = _get_json("eParamID_MediaState")
            clip_name       = _get_json("eParamID_ClipName")
            return {
                "transport_state": transport_state,
                "media_state": media_state,
                "clip_name": clip_name
            }
        except Exception as e:
            logging.error(f"Failed to get status from Ki Pro {kipro_ip}: {e}")
            return None

    def start_recording(self, kipro_ip, filename=None):
        """Start recording on a specific Ki Pro with enhanced error checking"""
        try:
            logging.info(f"=== Starting recording on Ki Pro {kipro_ip} ===")

            # Ensure Record-Play (0), not Data-LAN (1)
            logging.info("Setting Ki Pro to Record-Play mode...")
            mode_resp = requests.get(
                f"http://{kipro_ip}/config",
                params={"action":"set","paramid":"eParamID_MediaState","value":"0"},
                timeout=10
            )
            mode_resp.raise_for_status()

            time.sleep(2)

            # OPTIONAL: set clip name BEFORE recording
            if filename:
                safe_name = quote(filename, safe="._-")  # URL-encode; allow common safe chars
                logging.info(f"Setting recording filename to: {filename}")
                name_resp = requests.get(
                    f"http://{kipro_ip}/config",
                    params={"action":"set","paramid":"eParamID_ClipName","value":safe_name},
                    timeout=10
                )
                name_resp.raise_for_status()
                time.sleep(0.5)

            # Stop any current transport activity -> Send STOP (4) twice to ensure idle
            logging.info("Ensuring transport is idle (Stop x2)...")
            for _ in range(2):
                stop_resp = requests.get(
                    f"http://{kipro_ip}/config",
                    params={"action":"set","paramid":"eParamID_TransportCommand","value":"4"},
                    timeout=10
                )
                stop_resp.raise_for_status()
                time.sleep(0.5)

            # START RECORDING: Record command = 3  (not 2)
            logging.info("Sending record command (3)...")
            rec_resp = requests.get(
                f"http://{kipro_ip}/config",
                params={"action":"set","paramid":"eParamID_TransportCommand","value":"3"},
                timeout=10
            )
            rec_resp.raise_for_status()

            # Give the unit a moment and verify
            time.sleep(2)
            status = self.get_kipro_status(kipro_ip)
            if status:
                logging.info(f"Final status - Transport: {status['transport_state']}, Media: {status['media_state']}")
                # Some firmware reports numeric or text; accept both
                if status['transport_state'] in ('3', 'Recording', 'Record'):
                    logging.info(f"✓ Recording successfully started on Ki Pro {kipro_ip}")
                    return True
                # Some units briefly report Play(1) then switch to Record; retry one probe
                time.sleep(1.5)
                status = self.get_kipro_status(kipro_ip)
                if status and status['transport_state'] in ('3', 'Recording', 'Record'):
                    logging.info(f"✓ Recording successfully started on Ki Pro {kipro_ip}")
                    return True

            logging.warning(f"Recording may not have started. Transport state: {status and status['transport_state']}")
            return False

        except requests.exceptions.Timeout as e:
            logging.error(f"Timeout while starting recording on Ki Pro {kipro_ip}: {e}")
            return False
        except requests.exceptions.ConnectionError as e:
            logging.error(f"Connection error while starting recording on Ki Pro {kipro_ip}: {e}")
            return False
        except requests.exceptions.RequestException as e:
            logging.error(f"Request failed while starting recording on Ki Pro {kipro_ip}: {e}")
            return False
        except Exception as e:
            logging.error(f"Unexpected error while starting recording on Ki Pro {kipro_ip}: {e}")
            return False
    
    def stop_recording(self, kipro_ip):
        """Stop recording on a specific Ki Pro (Stop=4, send twice to exit pause)"""
        try:
            logging.info(f"=== Stopping recording on Ki Pro {kipro_ip} ===")

            # Send STOP (4) twice to ensure we get to idle from pause
            for i in range(2):
                stop_resp = requests.get(
                    f"http://{kipro_ip}/config",
                    params={"action":"set","paramid":"eParamID_TransportCommand","value":"4"},
                    timeout=10
                )
                stop_resp.raise_for_status()
                time.sleep(0.6)

            # Verify
            time.sleep(1.0)
            status = self.get_kipro_status(kipro_ip)
            if status:
                logging.info(f"Final status - Transport: {status['transport_state']}")
                if status['transport_state'] in ('4', '0', 'Stop', 'Stopped', 'Idle', 'Paused'):
                    logging.info(f"✓ Recording stopped (or paused) on Ki Pro {kipro_ip}")
                    return True

            logging.warning(f"Stop may not have completed. Transport state: {status and status['transport_state']}")
            return False

        except requests.exceptions.Timeout as e:
            logging.error(f"Timeout while stopping recording on Ki Pro {kipro_ip}: {e}")
            return False
        except requests.exceptions.ConnectionError as e:
            logging.error(f"Connection error while stopping recording on Ki Pro {kipro_ip}: {e}")
            return False
        except requests.exceptions.RequestException as e:
            logging.error(f"Request failed while stopping recording on Ki Pro {kipro_ip}: {e}")
            return False
        except Exception as e:
            logging.error(f"Unexpected error while stopping recording on Ki Pro {kipro_ip}: {e}")
            return False
    
    def test_kipro_connection(self, kipro_ip):
        """Test connection to a Ki Pro device"""
        try:
            test_url = f"http://{kipro_ip}/config?action=get&paramid=eParamID_TransportState"
            response = requests.get(test_url, timeout=5)
            if response.status_code == 200:
                logging.info(f"✓ Ki Pro {kipro_ip} is reachable")
                return True
            else:
                logging.error(f"✗ Ki Pro {kipro_ip} returned status code: {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            logging.error(f"✗ Cannot reach Ki Pro {kipro_ip}: {e}")
            return False

    def start_all_recordings(self, time_slot):
        """Start recording on all Ki Pro devices with appropriate filenames"""
        logging.info(f"=== Starting {time_slot} recordings on all Ki Pros ===")
        
        today = datetime.today()
        filename = today.strftime("%Y%m%d") + f"_{time_slot}"
        
        kipro_ips = [KIPRO_1_IP, KIPRO_2_IP, KIPRO_3_IP]
        successful_starts = 0
        
        # First test all connections
        logging.info("Testing connections to all Ki Pro devices...")
        for i, ip in enumerate(kipro_ips, 1):
            if not self.test_kipro_connection(ip):
                logging.error(f"Cannot connect to Ki Pro {i} ({ip}) - skipping")
                continue
        
        # Start recordings
        for i, ip in enumerate(kipro_ips, 1):
            kipro_filename = f"{filename}_KiPro{i}"
            logging.info(f"Starting recording on Ki Pro {i} ({ip}) with filename: {kipro_filename}")
            
            if self.start_recording(ip, kipro_filename):
                successful_starts += 1
                logging.info(f"✓ Ki Pro {i} ({ip}) recording started successfully")
            else:
                logging.error(f"✗ Failed to start recording on Ki Pro {i} ({ip})")
                
                # Try alternative approach - start without filename first
                logging.info(f"Attempting fallback approach for Ki Pro {i}...")
                if self.start_recording(ip, None):
                    logging.info(f"✓ Ki Pro {i} started recording without custom filename")
                    successful_starts += 1
        
        logging.info(f"Recording start summary: {successful_starts}/{len(kipro_ips)} successful")
        
        if successful_starts == 0:
            logging.error("No recordings started successfully!")
        elif successful_starts < len(kipro_ips):
            logging.warning(f"Only {successful_starts} out of {len(kipro_ips)} recordings started")
        else:
            logging.info("All recordings started successfully!")
            
        return successful_starts > 0  # Return True if at least one recording started
    
    def stop_all_recordings(self):
        """Stop recording on all Ki Pro devices"""
        logging.info("=== Stopping recordings on all Ki Pros ===")
        
        kipro_ips = [KIPRO_1_IP, KIPRO_2_IP, KIPRO_3_IP]
        successful_stops = 0
        
        # First test all connections
        logging.info("Testing connections to all Ki Pro devices...")
        for i, ip in enumerate(kipro_ips, 1):
            if not self.test_kipro_connection(ip):
                logging.error(f"Cannot connect to Ki Pro {i} ({ip}) - skipping")
                continue
        
        # Stop recordings
        for i, ip in enumerate(kipro_ips, 1):
            logging.info(f"Stopping recording on Ki Pro {i} ({ip})")
            
            if self.stop_recording(ip):
                successful_stops += 1
                logging.info(f"✓ Ki Pro {i} ({ip}) recording stopped successfully")
            else:
                logging.error(f"✗ Failed to stop recording on Ki Pro {i} ({ip})")
        
        logging.info(f"Recording stop summary: {successful_stops}/{len(kipro_ips)} successful")
        
        if successful_stops == 0:
            logging.error("No recordings stopped successfully!")
        elif successful_stops < len(kipro_ips):
            logging.warning(f"Only {successful_stops} out of {len(kipro_ips)} recordings stopped")
        else:
            logging.info("All recordings stopped successfully!")
            
        return successful_stops > 0  # Return True if at least one recording stopped
    
    def check_file_exists(self, filename):
        """Check if a specific file exists on the Ki Pro"""
        # Try both with and without .mov extension
        filenames_to_check = [filename, f"{filename}.mov"]
        
        for fname in filenames_to_check:
            check_url = f"{self.kipro_base_url}/media/{fname}"
            try:
                response = requests.head(check_url, timeout=10)
                if response.status_code == 200:
                    logging.info(f"File {fname} exists on Ki Pro")
                    return fname  # Return the actual filename that exists
            except requests.exceptions.RequestException as e:
                continue
        
        logging.info(f"File {filename} (with or without .mov) not found on Ki Pro")
        return None
    
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
                    if chunk:  # Filter out keep-alive chunks
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
        """Upload file to Dropbox with retry logic"""
        max_retries = 3
        retry_delay = 5
        
        for attempt in range(max_retries):
            try:
                with open(local_file_path, 'rb') as f:
                    file_size = os.path.getsize(local_file_path)
                    logging.info(f"Uploading {local_file_path.name} ({file_size / (1024*1024):.1f} MB) to Dropbox... (Attempt {attempt + 1})")
                    
                    if file_size <= 150 * 1024 * 1024:  # Files smaller than 150MB
                        self.dbx.files_upload(f.read(), dropbox_path, mode=dropbox.files.WriteMode.overwrite)
                    else:
                        # Use upload session for large files
                        f.seek(0)  # Reset file pointer
                        self._upload_large_file(f, dropbox_path, file_size)
                    
                    logging.info(f"✓ Uploaded {local_file_path.name} to Dropbox: {dropbox_path}")
                    return True
                    
            except Exception as e:
                logging.error(f"Upload attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    logging.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    logging.error(f"All upload attempts failed for {local_file_path.name}")
                    return False
        
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
            for file_path in self.temp_dir.iterdir():
                if file_path.is_file():
                    file_path.unlink()
                    logging.info(f"Deleted local file: {file_path}")
        except Exception as e:
            logging.error(f"Error cleaning up local files: {e}")
    
    def format_kipro_media(self):
        """Format/wipe the Ki Pro media"""
        kipro_ips = [KIPRO_1_IP, KIPRO_2_IP, KIPRO_3_IP]
        
        logging.info("=== Starting media format on all Ki Pros ===")
        
        for i, ip in enumerate(kipro_ips, 1):
            try:
                # First set format type to HSF+ (you can change to ExFat by using value=1)
                format_url = f"http://{ip}/config?action=set&paramid=eParamID_FileSystemFormat&value=0"
                response = requests.get(format_url, timeout=10)
                response.raise_for_status()
                
                # Wait a moment
                time.sleep(2)
                
                # Execute the format command
                erase_url = f"http://{ip}/config?action=set&paramid=eParamID_StorageCommand&value=4"
                response = requests.get(erase_url, timeout=10)
                response.raise_for_status()
                
                logging.info(f"✓ Ki Pro {i} ({ip}) media format initiated")
                
            except requests.exceptions.RequestException as e:
                logging.error(f"Failed to format Ki Pro {i} media at {ip}: {e}")
                continue
        
        logging.info("=== Media format completed on all Ki Pros ===")
        return True
    
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
            today = datetime.today()
            files_to_check = [
                today.strftime("%Y%m%d") + "_9AM",
                today.strftime("%Y%m%d") + "_11AM"
            ]
            
            existing_files = []
            for filename in files_to_check:
                actual_filename = self.check_file_exists(filename)
                if actual_filename:
                    existing_files.append(actual_filename)
            
            if not existing_files:
                logging.info("No specified files found to upload")
                # Still return to Record-Play mode
                self.set_kipro_data_mode(False)
                return True
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
            if successful_uploads == len(existing_files):
                logging.info("All files uploaded successfully, formatting Ki Pro media...")
                self.format_kipro_media()
                time.sleep(10)  # Wait for format to complete
            else:
                logging.warning("Some uploads failed, skipping format")
            
            # Step 7: Return Ki Pro to Record-Play mode
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
    try:
        automation = KiProAutomation()
    except Exception as e:
        logging.error(f"Failed to initialize automation: {e}")
        return
    
    # Schedule weekly backup (every Sunday at 2 AM)
    schedule.every().sunday.at("02:00").do(automation.run_weekly_upload)
    
    # Schedule automatic recordings on Sundays
    schedule.every().sunday.at("08:55").do(lambda: automation.start_all_recordings("9AM"))
    schedule.every().sunday.at("10:55").do(lambda: automation.start_all_recordings("11AM"))
    
    # Optional: Schedule automatic recording stops (adjust timing as needed)
    # Assuming 1-hour recordings, stop at 9:55 AM and 11:55 AM
    schedule.every().sunday.at("09:55").do(automation.stop_all_recordings)
    schedule.every().sunday.at("11:55").do(automation.stop_all_recordings)

    # Alternative scheduling options:
    # schedule.every().monday.at("02:00").do(automation.run_weekly_upload)  # Every Monday
    # schedule.every(7).days.at("02:00").do(automation.run_weekly_upload)   # Every 7 days
    
    logging.info("Ki Pro automation scheduler started")
    logging.info("Weekly upload scheduled for Sundays at 2:00 AM")
    logging.info("Automatic recordings scheduled for Sundays at 8:55 AM and 10:55 AM")
    logging.info("Automatic recording stops scheduled for Sundays at 9:55 AM and 11:55 AM")
    
    # Keep the script running
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

if __name__ == "__main__":
    # For testing individual functions:
    print("Ki Pro Automation Script")
    print("=" * 50)
    
    try:
        automation = KiProAutomation()
        
        # Test connections to all Ki Pro devices
        print("\nTesting Ki Pro connections...")
        kipro_ips = [KIPRO_1_IP, KIPRO_2_IP, KIPRO_3_IP]
        for i, ip in enumerate(kipro_ips, 1):
            automation.test_kipro_connection(ip)
        
        # Uncomment the functions you want to test:
        
        # Test recording start
        print("\nTesting recording start...")
        automation.start_all_recordings("TEST")
        
        # Test recording stop
        print("\nTesting recording stop...")
        automation.stop_all_recordings()
        
        # Test individual Ki Pro status
        # print("\nTesting Ki Pro status...")
        # for i, ip in enumerate(kipro_ips, 1):
        #     status = automation.get_kipro_status(ip)
        #     print(f"Ki Pro {i} ({ip}): {status}")
        
        # Test upload
        # print("\nTesting upload...")
        # automation.run_weekly_upload()
        
        print("\nTest completed. Check the log file for detailed results.")
        print("To run the scheduler, uncomment the main() call below.")
        
    except Exception as e:
        print(f"Error during testing: {e}")
        logging.error(f"Error during testing: {e}")
    
    # For production, uncomment this line to run the scheduler:
    # main()
