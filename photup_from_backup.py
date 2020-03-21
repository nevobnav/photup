
#!/usr/bin/python3
import sys
import syslog
from scripts import *
from shutil import copy2
from LED import *
import datetime
import time
import logging
import configparser


#Getting values from USBMOUNT
backup_folder = "/usr/bin/photup/image_backup/20200321(1)"
scan_id = "20200321"
starting_point = 511 #Skips images until this point. Use 0 to upload all.


successful_uploads = 0  #Used to count number of succesfull uploads
utc = pytz.utc
no_of_imgs = {}
successful_uploads = {}
files_per_scan = {}
minimum_expiration_time = 1800                       #minimum expiration time in seconds for Gdrive (expires in 3600 secs), refresh when reached.



#Basic settings#syslog.syslog('config parser start')
settings=configparser.ConfigParser()
settings.read('/usr/bin/photup/photup_conf')
client_id = settings.get('basic_settings','client_id')
telegram_ids = settings.get('basic_settings','telegram_id').splitlines()
telegram_ids = list(map(int,telegram_ids))
extensions = settings.get('basic_settings','extensions').splitlines()	#Only these files are transfered (case SENSITIVE)
version= '0.1'
syslog.syslog('loaded all settings')


#Get files from disc
file_dicts = get_filedicts(backup_folder,extensions,client_id)
if starting_point > 0:
    file_dicts= [x for x in file_dicts if int(x['base_title'].split('.')[0][-5:])>starting_point]


total_file_size = sum([os.path.getsize(f['filepath']) for f in file_dicts])
imgs_available = len(file_dicts)>0
scan_ids = list(set(f['scan_id'] for f in file_dicts))

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


#Check or wait for connection to establish
drive = create_drive_obj()
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


for file_dict in file_dicts:
    file_location = file_dict['filepath']
    extension = os.path.splitext(file_dict['filename'])[-1]
    scan_id = file_dict['scan_id']
    no_of_imgs[scan_id] += 1

    #Check file integrity:
    filesize = os.path.getsize(file_location)
    if filesize == 0:
        logging.warning (f'Corrupted file found: {file_location}')
        send_telegram(f'Corrupted file found: {file_location}',telegram_ids)
        continue

    #Determine file title, add (1) or (2) etc. for duplicate files
    duplicate_counter = 1
    base_title = file_dict['base_title']
    title = base_title
    while title in gdrive_files[scan_id]['drive_filenames']:
        title = base_title[:-len(extension)]+ '({})'.format(duplicate_counter) + extension
        duplicate_counter += 1

    token_expiry_remaining = gdrive_get_expiration_ts(drive)
    if token_expiry_remaining < minimum_expiration_time:
        drive = refresh_drive_obj()
        new_token_expiry_remaining = gdrive_get_expiration_ts(drive)

    resp = upload_to_gdrive(drive,title,file_location, client_id, gdrive_files[scan_id])

for scan_id in scan_ids:
    exit_doubles = 1
    duration = 0
    exit_file_name_base, exit_msg = create_exit_file(no_of_imgs[scan_id],total_file_size, successful_uploads[scan_id],duration,scan_id,client_id,no_of_scans = len(scan_ids))
    exit_file_name = exit_file_name_base
    while os.path.basename(exit_file_name) in gdrive_files[scan_id]['drive_filenames']:
        exit_file_name = exit_file_name_base[:-4]+'({})'.format(init_doubles) + '.txt'
        exit_doubles += 1
    resp = upload_to_gdrive(drive, os.path.basename(exit_file_name),exit_file_name_base, client_id, gdrive_files[scan_id])
    send_telegram('{}: finished uploading \n'.format(client_id)+exit_msg,telegram_ids)
