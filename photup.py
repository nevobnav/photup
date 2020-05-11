
#!/usr/bin/python3
import sys
import syslog
from scripts import *
from shutil import copy2
from LED import *
import datetime
import time
import logging, traceback
import configparser

#### DEBUG SETTINGS
backup= True
format= True
upload = True
####################


#Setup logs:
logging.root.handlers = []
logging.basicConfig(format='%(asctime)s : %(levelname)s : %(message)s', level=logging.WARNING , filename='/usr/bin/photup/logdetails.log')
# set up logging to console
console = logging.StreamHandler()
console.setLevel(logging.ERROR)
# set a format which is simpler for console use
formatter = logging.Formatter('%(asctime)s : %(levelname)s : %(message)s')
console.setFormatter(formatter)
logging.getLogger("").addHandler(console)


# Wait until network is established #
conn = test_internet()
while not(conn):
    logging.warning('Photup: cannot establish network - trying again in 5s')
    time.sleep(5)
    conn = test_internet()

#Getting values from USBMOUNT
mountpoint = "/media/usb0"
devname = get_device_name(mountpoint)

#initiate
utc = pytz.utc
no_of_imgs = {}
successful_uploads = {}
files_per_scan = {}
sdcard = mountpoint +"/"
led = LED()
led.blink()
total_file_size = 0 #Used to determine total file size of all images combined
minimum_expiration_time = 1800                       #minimum expiration time in seconds for Gdrive (expires in 3600 secs), refresh when reached.
settings=configparser.ConfigParser()
logging.warning('Loading user settings: ')
settings.read('/usr/bin/photup/photup_conf')
client_id = settings.get('basic_settings','client_id')
client_name = settings.get('basic_settings','client_name')
slack_token = settings.get('basic_settings','slack_api_token')
# telegram_ids = settings.get('basic_settings','telegram_id').splitlines()
# telegram_ids = list(map(int,telegram_ids))
extensions = settings.get('basic_settings','extensions').splitlines()	#Only these files are transfered (case SENSITIVE)

#Initiate slack integration
slackchat = SlackChat(slack_token)
version= '0.2'
backup_folder_location = '/usr/bin/photup/image_backup/'
logging.warning('Version: {}'.format(version))
logging.warning('client_id: {0}'.format(client_id))
logging.warning('extensions: {}'.format(extensions))
logging.warning('Loaded all settings')

#Get dictionary with filenames and dates from SD card
#Dict keys:
    #'root': gives image curent root folder (e.g. '/usr/bin/photup/backup/')
    #'filepath': gives current full file filepath (e.g. '/usr/bin/photup/backup/img1.jpg')
    #'filename': gives full filename, without path (e.g. img1.jpg)
    #'scan_id': gives scan_id string (e.g. '20200101')
    #'base_title': target filename for saving on gdrive

file_dicts = get_filedicts(sdcard,extensions, client_id)

total_file_size = sum([os.path.getsize(f['filepath']) for f in file_dicts])
imgs_available = len(file_dicts)>0
scan_ids = list(set(f['scan_id'] for f in file_dicts))

#Call an early stop if there are no images on the drive.
if not imgs_available:
    try:
        logging.warning('No imgs found')
        slack_resp = slackchat.create_msg('Client *{}*: no images found. Exiting'.format(client_name))
        slack_sent = slack_response['ok']
    #Include this except to make sure we exit if connectivity fails and we error on the slack messaging.
    except:
        logging.warning('reached except loop when sending initial slack msg') #Add exception to warning
        slack_sent = False
    if slack_sent is True:
        cleanexit(imgs_available,devname,led, formatting = False, succes=True)
    else:
        cleanexit(imgs_available,devname,led, formatting = False, succes = False)
    sys.exit()
else:
    slack_resp = slackchat.create_msg('*Incoming from {}*: {} images found ({} mb)'.format(
        client_name, len(file_dicts), round(total_file_size/1e6)))


if backup:
    try:
        if test_internet():
            slackchat.follow_up_msg('Starting backup...')
        total_file_size_dict, updated_file_dicts = perform_backup(file_dicts,client_id,backup_folder_location,slackchat)
        #Overwrite variable 'files' to start uploading from backup, not from SD
        file_dicts = updated_file_dicts
    except Exception as e:
        backup = False
        slackchat.follow_up_msg('Perform_backup failed. Please check: {}'.format(e))

logging.warning('finished backup procedure')

#Determine image-file-locations per scan, use backup if available
for scan_id in scan_ids:
    no_of_imgs[scan_id] = 0
    successful_uploads[scan_id] = 0
    files = []
    for file_dict in file_dicts:
        if file_dict['scan_id'] == scan_id:
            if 'backup_filename' in file_dict.keys():
                files.append(file_dict['backup_filepath'])
            else:
                files.append(file_dict['filepath'])
    files_per_scan[scan_id] = files


logging.warning('Starting uploads...')

#Check or wait for connection to establish
conn_tests = 0

logging.warning('No. of images found on disc:{}'.format(str(len(file_dicts))))

try:
    while conn_tests<100 and imgs_available and upload:

        led.blink()
        conn = test_internet()
        logging.warning('Connection before upload: {}'.format(str(conn)))
        if conn:
            start_time = time.time()
            slackchat.follow_up_msg("Upload started...")
            slackchat.follow_up_random_img(file_dicts)

            drive = create_drive_obj()
            #Refresh just in case current token has a very short lifespan
            drive = refresh_drive_obj()

            gdrive_files = {}
            #Create init and exit txt files with the full list of images (basename only)
            #Upload initiation file
            for scan_id in scan_ids:
                init_doubles = 1
                drive_filenames, drive_folder_scan_id = prepare_new_scan(drive,client_id,scan_id)
                init_file_name_base = create_init_file(files_per_scan[scan_id],scan_id,client_id,drive_filenames)
                init_file_name = init_file_name_base
                while os.path.basename(init_file_name) in drive_filenames:
                    init_file_name = init_file_name_base[:-4]+'({})'.format(init_doubles) + '.txt'
                    init_doubles += 1
                gdrive_files[scan_id] = {'drive_folder_scan_id':drive_folder_scan_id, 'drive_filenames': drive_filenames, 'init_file_name':init_file_name}
                resp = upload_to_gdrive(drive, os.path.basename(init_file_name),init_file_name_base, client_id, gdrive_files[scan_id])


            #Upload files onto Gdrive
            for file_dict in file_dicts:
                try:
                    #use backed up image if available:
                    if 'backup_filepath' in file_dict:
                        file_location = file_dict['backup_filepath']
                    else:
                        file_location = file_dict['filepath']

                    #Check file integrity:
                    filesize = os.path.getsize(file_location)
                    if filesize == 0:
                        logging.warning ("Corrupted file found: {}".format(file_location))
                        slackchat.follow_up_msg("Corrupted file found: {}".format(file_location))
                        continue

                    extension = os.path.splitext(file_dict['filename'])[-1]
                    scan_id = file_dict['scan_id']
                    no_of_imgs[scan_id] += 1

                    #Determine file title, add (1) or (2) etc. for duplicate files
                    duplicate_counter = 1
                    base_title = file_dict['base_title']
                    title = base_title
                    while title in gdrive_files[scan_id]['drive_filenames']:
                        title = base_title[:-len(extension)]+ '({})'.format(duplicate_counter) + extension
                        duplicate_counter += 1

                    #Check if Gdrive token needs refreshment
                    token_expiry_remaining = gdrive_get_expiration_ts(drive)
                    logging.warning('Drive object expires in {} minutes'.format(int(token_expiry_remaining/60)))
                    if token_expiry_remaining < minimum_expiration_time:
                        logging.warning('Refreshing drive object now')
                        drive = refresh_drive_obj()
                        new_token_expiry_remaining = gdrive_get_expiration_ts(drive)
                        logging.warning('New drive objected OK for {} minutes'.format(int(new_token_expiry_remaining/60)))

                    #Start actual upload
                    logging.warning('Uploading file: {}'.format(file_dict['base_title']))
                    conn_intermediate = test_internet()
                    if conn_intermediate:
                        logging.warning('Connection live')
                        resp = False
                        while not(resp):
                            resp = upload_to_gdrive(drive,title,file_location, client_id, gdrive_files[scan_id])
                            if resp is True:
                                logging.warning('Upload successful')
                                successful_uploads[scan_id] += 1
                                conn_tests = 9999
                            else:
                                logging.warning('Issue uploading title {}, skipping file'.format(title))
                                try:
                                    slackchat.follow_up_msg('Issue uploading title {}, skipping it...'.format(title))
                                except:
                                    logging.warning('Unable to send slack')
                                conn_tests += 1
                                time.sleep(30)
                    else:
                        logging.warning('Uploading loop failed, resetting counter and trying again')
                        led.error()
                        conn_tests += 1
                        continue
                except Exception as e:
                    logging.warning('Failed unkown at file:{}'.format(title))
                    logging.warning('Exception: {}'.format(str(e)))
                    led.error()
                    conn_tests = 9999

            #Upload exit file here.
            end_time = time.time()
            duration = (end_time-start_time)

            for scan_id in scan_ids:
                if backup:
                    total_file_size = total_file_size_dict[scan_id]
                exit_doubles = 1
                exit_file_name_base, exit_msg = create_exit_file(no_of_imgs[scan_id],total_file_size, successful_uploads[scan_id],duration,scan_id,client_id,no_of_scans = len(scan_ids))
                exit_file_name = exit_file_name_base
                while os.path.basename(exit_file_name) in gdrive_files[scan_id]['drive_filenames']:
                    exit_file_name = exit_file_name_base[:-4]+'({})'.format(init_doubles) + '.txt'
                    exit_doubles += 1
                resp = upload_to_gdrive(drive, os.path.basename(exit_file_name),exit_file_name_base, client_id, gdrive_files[scan_id])
                slackchat.follow_up_msg('Finished uploading \n'+exit_msg)

        else:
            led.error()
            logging.warning('No connection found. Upload has not started. Going to sleep for 60s and try again')
            time.sleep(60)
            conn_tests +=1
            logging.warning('Retry connection - attempt no {}'.format(str(conn_tests)))

    #Close down session
    logging.warning('reached cleanexit after succes')
    cleanexit(imgs_available,devname,led,formatting = format, succes = True)
    logging.warning('Finalized after {} successful uploads of {} image-files'.format(sum(successful_uploads.values()),len(file_dicts)))


except Exception as e:
    logging.warning('Error occured. Broke out of Try-Except around main loop')
    logging.warning(traceback.format_exc())
    conn = False
    conn_tests = 0
    while conn is False and conn_tests<100:
        conn = test_internet()
        if conn:
            slackchat.follow_up_msg('Error: {}'.format(traceback.format_exc()))
        else:
            logging.warning('Cannot send final Slack - No interwebs')
            time.sleep(60)
            conn_tests += 1
    cleanexit(imgs_available,devname,led,formatting = False, succes=False)
    led.error()
    sys.exit()


logging.warning('Hit EOF')
