
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


#### DEBUG SETTINGS
backup= True
format= False
upload = True
####################

# Wait until network is established #
conn = test_internet()
while not(conn):
    syslog.syslog('Photup: cannot establish network - trying again in 5s')
    time.sleep(5)
    conn = test_internet()

syslog.syslog('Python scrip started')
logging.basicConfig(filename = '/usr/bin/photup/logdetails.log', level=logging.INFO, format='%(asctime)s %(message)s')
log_msg = 'New image processing order: \n'
f = open('log_msg',"a+")

#Getting values from USBMOUNT
mountpoint = "/media/usb0"
devname = get_device_name(mountpoint)

#initiate
log = []
no_of_imgs = {}
successful_uploads = {}
files_per_scan = {}
sdcard = mountpoint +"/"
led_thread = start_blink()
led_blink = True
led_error = False
total_file_size = 0 #Used to determine total file size of all images combined

#Basic settings#syslog.syslog('config parser start')
settings=configparser.ConfigParser()
settings.read('/usr/bin/photup/photup_conf')
client_id = settings.get('basic_settings','client_id')
telegram_ids = settings.get('basic_settings','telegram_id').splitlines()
telegram_ids = list(map(int,telegram_ids))
extensions = settings.get('basic_settings','extensions').splitlines()	#Only these files are transfered (case SENSITIVE)
version= '0.1'
backup_folder_location = '/usr/bin/photup/image_backup/'
syslog.syslog('loaded all settings')

##
#initiate log file
now = get_now()
log_msg += 'Time: ' +now+'\n'
log_msg += 'Version: '+version+'\n'
log_msg += 'client_id: {0}'.format(client_id) +'\n'
f.write(log_msg)

#Get dictionary with filenames and dates from SD card
#Dict keys: ['root' ,'filepath', 'filename','scan_id']
file_dicts = get_filedicts(sdcard,extensions, client_id)        #change this
imgs_available = len(file_dicts)>0
scan_ids = list(set(f['scan_id'] for f in file_dicts))

#Call an early stop if there are no images on the drive.
if not imgs_available:
    try:
        print('no images found')
        send_telegram('client {}: no images found. Exiting'.format(client_id),telegram_ids)
        log_msg += 'No images found. Quiting.' +'\n'
        f.close()
        cleanexit(imgs_available,devname,led_thread, formatting = False, succes=True)
    #Include this except to make sure we exit if connectivity fails and we error on the telegram messaging.
    except:
        print('reached except loop in early-stop call')
        syslog.syslog('No imgs found, failed to send telegram and/or exit')
        cleanexit(imgs_available,devname,led_thread,formatting = False, succes = False)
    sys.exit()


if backup:
    try:
        output, total_file_size_dict, updated_file_dicts = perform_backup(file_dicts,client_id,backup_folder_location)
        #Overwrite variable 'files' to start uploading from backup, not from SD
        file_dicts = updated_file_dicts
    except Exception as e:
        output = "perform_backup failed: {}".format(str(e))
        send_telegram('client {}: perform_backup failed. Please check'.format(client_id),telegram_ids)
    log_msg += output +'\n'
    f.write(output + '\n')

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


print(file_dicts)
print('Checking internet and starting to upload')

#Check or wait for connection to establish
conn_tests = 0

logstring = 'No. of images found on disc: ' + str(len(file_dicts))
log_msg +=logstring + '\n'
syslog.syslog(logstring)

try:
    while conn_tests<100 and len(file_dicts)>0 and upload:
        if led_error:
            stop_led(led_thread)
            led_error = False
            led_thread = start_blink()
            led_bink = True

        conn = test_internet()
        print(conn)
        log_addition = 'Connection before uploading starts: '+str(conn) +'\n'
        log_msg += log_addition
        syslog.syslog(log_addition)
        if conn:
            start_time = time.time()
            message_text = "{0}: pictures incoming!".format(client_id)
            send_telegram(message_text,telegram_ids)
            #Create flickr opject
            #flickr = create_flickr_obj()
            #if not flickr.token_valid(perms='write'):
            #    flickr = authorize_flickr(flickr)
            #create drive object
            drive = create_drive_obj()
            #Refresh just in case current token has a very short lifespan
            drive = refresh_drive_obj()

            gdrive_files = {}

            #Create init and exit txt files with the full list of images (basename only)
            #Upload initiation file
            for scan_id in scan_ids:
                drive_filenames, drive_folder_scan_id = prepare_new_scan(drive,client_id,scan_id)
                init_file_name = create_init_file(files_per_scan[scan_id],scan_id,client_id,drive_filenames)
                resp = upload_to_gdrive(drive, os.path.basename(init_file_name),init_file_name, client_id, drive_folder_scan_id)
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
                    title = title[:-len(extension)]+ '({})'.format(duplicate_counter) + extension
                    duplicate_counter += 1
                try:
                    if (sum(successful_uploads.values())+1)%75 == 0:
                        print('Renewing drive object')
                        log_msg += 'Renewing drive object \n'
                        #Refreshing every 100 images ensures token is refreshed before running out (after 3600 seconds)
                        drive = refresh_drive_obj()
                    stop_led(led_thread)
                    led_error = False
                    led_thread = start_blink()
                    led_bink = True

                    print('Uploading file: ',file_dict['base_title'])
                    log_msg +='Uploading file: '+str(file_dict['base_title']) +'\n'
                    f.write("Uploading file: "+str(file_dict['base_title']) +'\n')
                    syslog.syslog(log_msg[0:-3])
                    conn_intermediate = test_internet()
                    if conn_intermediate:

                        if resp is True:
                            log_msg +='Upload succeeded'+'\n'
                            successful_uploads[scan_id] += 1
                            conn_tests = 9999
                        else:
                            stop_led(led_thread)
                            led_blink = False
                            start_error()
                            led_error = True
                            log_msg += 'gdrive upload script failed, resetting counter and trying again'+'\n'
                            f.write('gdrive upload script failed, resetting counter and trying again'+'\n')
                            conn_tests += 1
                            break
                    else:
                        print('Uploading loop failed, resetting counter and trying again')
                        stop_led(led_thread)
                        led_blink = False
                        start_error()
                        led_error = True

                        log_msg += 'Uploading loop failed, resetting counter and trying again'+'\n'
                        f.write('Uploading loop failed, resetting counter and trying again'+'\n')
                        conn_tests += 1
                        break
                except Exception as e:
                    print('Failed unkown at file: ',str(title))
                    print('Except', str(e))
                    stop_led(led_thread)
                    led_blink = False
                    start_error()
                    led_error = True
                    log_msg += 'Script failed unknown at file: ' + str(title) +'\n'
                    f.write('Script failed unknown at file: ' + str(title) +'\n')
            #Upload exit file here.
            end_time = time.time()
            duration = (end_time-start_time)

            for scan_id in scan_ids:
                if total_file_size_dict:
                    total_file_size = total_file_size_dict[scan_id]
                exit_file_name, exit_msg = create_exit_file(no_of_imgs[scan_id],total_file_size, successful_uploads[scan_id],duration,log_msg,scan_id,client_id,no_of_scans = len(scan_ids))
                resp = upload_to_gdrive(drive, os.path.basename(exit_file_name),exit_file_name, client_id, gdrive_files[scan_id]['drive_folder_scan_id'])

        else:
            stop_led(led_thread)
            led_blink = False
            led_thread = start_error()
            led_error = True

            syslog.syslog('No connection found. Upload has not started. Going to sleep for 60s and try again')
            log_msg += 'No connection found. Upload has not started. Going to sleep for 60s and try again' +'\n'
            f.write('No connection found. Upload has not started. Going to sleep for 60s and try again' +'\n')
            print(log_msg)
            time.sleep(60)
            conn_tests +=1
            logging_conn_issue = "Retry connection - attempt no " + str(conn_tests)
            syslog.syslog(logging_conn_issue)
            print(logging_conn_issue)
            log_msg += logging_conn_issue +'\n'

    #Close down session
    cleanexit(imgs_available,devname,led_thread,formatting = format, succes = True)

    #Send alert:
    conn = False
    conn_tests = 0
    log_msg += 'Finalized after {} successful uploads of {} image-files'.format(successful_uploads,len(files))
    f.write('Finalized after {} successful uploads of {} image-files'.format(successful_uploads,len(files)))
    while conn is False and conn_tests<100:
        conn = test_internet()
        if conn:
            line1= '{}: finished uploading. \n'.format(client_id)
            send_telegram(line1+exit_msg,telegram_ids)
        else:
            time.sleep(60)
            conn_tests += 1

except:
    log_msg += 'Error occured. Broke out of Try-Except around main loop'
    f.write('Error occured. Broke out of Try-Except around main loop')
    conn = False
    conn_tests = 0
    while conn is False and conn_tests<100:
        conn = test_internet()
        if conn:
            send_telegram(log_msg,telegram_ids)
        else:
            print('Cannot send final Telegram - No interwebs')
            time.sleep(60)
            conn_tests += 1
    led_thread = cleanexit(imgs_available,devname,led_thread,formatting = False, succes=False)
    led_blink = False
    led_error = True
f.close()
sys.exit()
