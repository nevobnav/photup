
#!/usr/bin/python3
import sys
import syslog
from scripts_test import *
from shutil import copy2
from LED import *
import datetime
import time
import logging
import configparser
import pytz

#### DEBUG SETTINGS
backup= False
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
led_thread = start_blink()
led_blink = True
led_error = False
total_file_size = 0 #Used to determine total file size of all images combined

#Basic settings#syslog.syslog('config parser start')
minimum_expiration_time = 1800                       #minimum expiration time in seconds for Gdrive (expires in 3600 secs), refresh when reached.
settings=configparser.ConfigParser()
settings.read('/usr/bin/photup/photup_conf')
client_id = settings.get('basic_settings','client_id')
telegram_ids = settings.get('basic_settings','telegram_id').splitlines()
telegram_ids = list(map(int,telegram_ids))
extensions = settings.get('basic_settings','extensions').splitlines()	#Only these files are transfered (case SENSITIVE)
version= '0.1'
backup_folder_location = '/usr/bin/photup/image_backup/'
logging.warning('Version: {}'.format(version))
logging.warning('client_id: {0}'.format(client_id))
logging.warning('Loaded all settings')


#Get dictionary with filenames and dates from SD card
#Dict keys: ['root' ,'filepath', 'filename','scan_id']
file_dicts = get_filedicts(sdcard,extensions, client_id)        #change this
total_file_size = sum([os.path.getsize(f['filepath']) for f in file_dicts])
imgs_available = len(file_dicts)>0
scan_ids = list(set(f['scan_id'] for f in file_dicts))

#Call an early stop if there are no images on the drive.
if not imgs_available:
    try:
        logging.warning('No imgs found')
        send_telegram('client {}: no images found. Exiting'.format(client_id),telegram_ids)
        cleanexit(imgs_available,devname,led_thread, formatting = False, succes=True)
    #Include this except to make sure we exit if connectivity fails and we error on the telegram messaging.
    except:
        logging.warning('reached except loop in early-stop call')
        cleanexit(imgs_available,devname,led_thread,formatting = False, succes = False)
    sys.exit()


if backup:
    try:
        if test_internet():
            send_telegram('{}: starting backup.'.format(client_id),telegram_ids)
        total_file_size_dict, updated_file_dicts = perform_backup(file_dicts,client_id,backup_folder_location,telegram_ids)
        #Overwrite variable 'files' to start uploading from backup, not from SD
        file_dicts = updated_file_dicts
    except Exception as e:
        backup = False
        send_telegram('client {}: perform_backup failed. Please check: {}'.format(client_id,e),telegram_ids)

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



# ##### DEBUGGING FIX FILE NAMES WIHTOUT BACKUPING ALL IMAGES:
# xxbase = '/usr/bin/photup/image_backup/20190324/20190324_c04_verdegaal_img000001.JPG'
# backup_files = []
# for x in range(1,2532):
#     xxfilename = '/usr/bin/photup/image_backup/20190324/20190324_c04_verdegaal_img'+str(x).zfill(6)+'.JPG'
#     backup_files.append(xxfilename)
# files = backup_files
# ########################


logging.warning('Starting uploads...')

#Check or wait for connection to establish
conn_tests = 0

logging.warning('No. of images found on disc:{}'.format(str(len(file_dicts))))

try:
    while conn_tests<100 and len(file_dicts)>0 and upload:

        if led_error:
            stop_led(led_thread)
            led_error = False
            led_thread = start_blink()
            led_bink = True

        conn = test_internet()
        logging.warning('Connection before upload: {}'.format(str(conn)))
        if conn:
            start_time = time.time()
            message_text = "{0}: pictures incoming!".format(client_id)
            send_telegram(message_text,telegram_ids)
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
                resp = upload_to_gdrive(drive, os.path.basename(init_file_name),init_file_name_base, client_id, drive_folder_scan_id)
                gdrive_files[scan_id] = {'drive_folder_scan_id':drive_folder_scan_id, 'drive_filenames': drive_filenames, 'init_file_name':init_file_name}


            #Upload files onto Gdrive
            for file_dict in file_dicts:
                #use backed up image if available:
                if 'backup_filepath' in file_dict:
                    file_location = file_dict['backup_filepath']
                else:
                    file_location = file_dict['filepath']

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
                try:
                    utc = pytz.utc
                    gauth_exp = drive.auth.credentials.token_expiry
                    gauth_exp_utc = utc.localize(gauth_exp)
                    gauth_exp_ts = datetime.datetime.timestamp(gauth_exp_utc)
                    now_ts = datetime.datetime.timestamp(datetime.datetime.now())
                    exp_remain = int(gauth_exp_ts - now_ts)
                    logging.warning('Drive object expires in {} minutes'.format(int(exp_remain/60)))
                    if exp_remain < minimum_expiration_time:
                        logging.warning('Refreshing drive object now')
                        drive = refresh_drive_obj()
                        gauth_exp = drive.auth.credentials.token_expiry
                        gauth_exp_utc = utc.localize(gauth_exp)
                        gauth_exp_ts = datetime.datetime.timestamp(gauth_exp_utc)
                        now_ts = datetime.datetime.timestamp(datetime.datetime.now())
                        exp_remain = int(gauth_exp_ts - now_ts)
                        logging.warning('New drive objected OK for {} minutes'.format(int(exp_remain/60)))
                    # if (sum(successful_uploads.values())+1)%75 == 0:
                        # print('Renewing drive object')
                        # logging.warning('Renewing gdrive object')
                        #Refreshing every 100 images ensures token is refreshed before running out (after 3600 seconds)
                        # drive,gauth = refresh_drive_obj()
                    stop_led(led_thread)
                    led_error = False
                    led_thread = start_blink()
                    led_bink = True

                    logging.warning('Uploading file: {}'.format(file_dict['base_title']))
                    conn_intermediate = test_internet()
                    if conn_intermediate:
                        logging.warning('Connection live')
                        resp = upload_to_gdrive(drive,title,file_location, client_id, gdrive_files[scan_id]['drive_folder_scan_id'])

                        if resp is True:
                            logging.warning('Upload successful')
                            successful_uploads[scan_id] += 1
                            conn_tests = 9999
                        else:
                            stop_led(led_thread)
                            led_blink = False
                            start_error()
                            led_error = True
                            logging.warning('Upload failed, resetting counter and trying again')
                            conn_tests += 1
                            break
                    else:
                        logging.warning('Uploading loop failed, resetting counter and trying again')
                        stop_led(led_thread)
                        led_blink = False
                        start_error()
                        led_error = True
                        conn_tests += 1
                        break
                except Exception as e:
                    logging.warning('Failed unkown at file:{}'.format(title))
                    logging.warning('Exception: {}'.format(str(e)))
                    stop_led(led_thread)
                    led_blink = False
                    start_error()
                    led_error = True
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
                resp = upload_to_gdrive(drive, os.path.basename(exit_file_name),exit_file_name_base, client_id, gdrive_files[scan_id]['drive_folder_scan_id'])
                send_telegram('{}: finished uploading \n'.format(client_id)+exit_msg,telegram_ids)

        else:
            stop_led(led_thread)
            led_blink = False
            led_thread = start_error()
            led_error = True
            logging.warning('No connection found. Upload has not started. Going to sleep for 60s and try again')
            time.sleep(60)
            conn_tests +=1
            logging_conn_issue = "Retry connection - attempt no " + str(conn_tests)
            logging.warning('Retry connection - attempt no {}'.format(str(conn_tests)))

    #Close down session
    cleanexit(imgs_available,devname,led_thread,formatting = format, succes = True)

    logging.warning('Finalized after {} successful uploads of {} image-files'.format(sum(successful_uploads.values()),len(file_dicts)))


except Exception as e:
    logging.warning('Error occured. Broke out of Try-Except around main loop')
    conn = False
    conn_tests = 0
    while conn is False and conn_tests<100:
        conn = test_internet()
        if conn:
            send_telegram(str(e),telegram_ids)
        else:
            logging.warning('Cannot send final Telegram - No interwebs')
            time.sleep(60)
            conn_tests += 1
    led_thread = cleanexit(imgs_available,devname,led_thread,formatting = False, succes=False)
    led_blink = False
    led_error = True
sys.exit()
