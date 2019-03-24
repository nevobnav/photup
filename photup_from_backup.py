
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
backup_folder = "/usr/bin/photup/image_backup/20190322"
scan_id = "20190322"

successful_uploads = 0  #Used to count number of succesfull uploads

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
files = get_filenames(backup_folder,extensions)
successful_uploads = 0
#Create init and exit txt files with the full list of images (basename only)
init_file_name = create_init_file(files,scan_id,client_id)
print(files)

#Check or wait for connection to establish
drive = create_drive_obj()
drive_filenames, drive_folder_scan_id = prepare_new_scan(drive,client_id,scan_id)
start_time = time.time()

#Upload initiation file
resp = upload_to_gdrive(drive, os.path.basename(init_file_name),init_file_name, client_id, drive_folder_scan_id)

for fname in files:
    extension = os.path.splitext(fname)
    datestirng =  datetime.datetime.now().strftime("%Y%m%d")
    title = datestring+'_'+client_id+'_img'+str(successful_uploads+1)+extension[-1]
    resp = upload_to_gdrive(drive, title,fname, client_id, drive_folder_scan_id)
    successful_uploads += 1
    if ((successful_uploads)%50) == 0:
       print('Renewing drive object')
       log_msg += 'Renewing drive object \n'
       drive = create_drive_obj()

end_time = time.time()
duration = (end_time-start_time)
exit_file_name = create_exit_file(no_of_imgs,total_file_size, successful_uploads,duration,log_msg,scan_id,client_id)
resp = upload_to_gdrive(drive, os.path.basename(exit_file_name),exit_file_name, client_id, drive_folder_scan_id)
