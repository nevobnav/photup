
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
format= True
####################

syslog.syslog('Python scrip started')
logging.basicConfig(filename = '/usr/bin/photup/logdetails.log', level=logging.DEBUG)
log_msg = 'New image processing order: \n'
f = open('log_msg',"a+")

#Getting values from USBMOUNT
devname = get_device_name()
mountpoint = "/media/usb0"

#initiate
log = []
sdcard = mountpoint +"/"
led_thread = start_blink()
led_blink = True
led_error = False
total_file_size = 0 #Used to determine total file size of all images combined
successful_uploads = 0  #Used to count number of succesfull uploads


#Basic settings#syslog.syslog('config parser start')
settings=configparser.ConfigParser()
settings.read('/usr/bin/photup/photup_conf')
client_id = settings.get('basic_settings','client_id')
scan_id = datetime.datetime.now().strftime("%Y%m%d")
telegram_ids = settings.get('basic_settings','telegram_id').splitlines()
telegram_ids = list(map(int,telegram_ids))
extensions = settings.get('basic_settings','extensions').splitlines()	#Only these files are transfered (case SENSITIVE)
version= '0.1'
syslog.syslog('loaded all settings')

##
#initiate log file
now = get_now()
log_msg += 'Time: ' +now+'\n'
log_msg += 'Version: '+version+'\n'
log_msg += 'client_id: {0}'.format(client_id) +'\n'
f.write(log_msg)

#Get files from disc
files = get_filenames(sdcard,extensions)
imgs = len(files)>0
no_of_imgs = len(files)


#Create init and exit txt files with the full list of images (basename only)
init_file_name = create_init_file(files,scan_id,client_id)


if imgs and backup:
    try:
        output, total_file_size = perform_backup(files)
    except:
        output, total_file_size = "perform_backup failed. Please check!"
        send_telegram('client {}: perform_backup failed. Please check'.format(client_id),telegram_ids)
    log_msg += output +'\n'
    f.write(output + '\n')

print(files)
print('Checking internet and starting to upload')

#Check or wait for connection to establish
conn_tests = 0

logstring = 'No. of images found on disc: ' + str(len(files))
log_msg +=logstring + '\n'
syslog.syslog(logstring)

try:
    while conn_tests<100 and len(files)>0:
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
            drive_filenames, drive_folder_scan_id = prepare_new_scan(drive,client_id,scan_id)
            #Upload initiation file
            resp = upload_to_gdrive(drive, os.path.basename(init_file_name),init_file_name, client_id, drive_folder_scan_id)
            log_msg += "Currently in drive folder: " + str(drive_filenames) +'\n'
            f.write("Currently in drive folder: " +str(drive_filenames) +'\n')
            #Upload files onto Gdrive
            for fname in files:
                extension = os.path.splitext(fname)
                datestirng =  datetime.datetime.now().strftime("%Y%m%d")
                title = datestring+'_'+client_id+'_img'+str(successful_uploads+1)+extension[-1]
                try:
                    if ((successful_uploads+1)%100) == 0:
                        print('Renewing drive object')
                        log_msg += 'Renewing drive object \n'
                        drive = create_drive_obj()
                    stop_led(led_thread)
                    led_error = False
                    led_thread = start_blink()
                    led_bink = True

                    print('Uploading file: ',fname)
                    log_msg +='Uploading file: '+str(fname) +'\n'
                    f.write("Uploading file: "+str(fname) +'\n')
                    syslog.syslog(log_msg[0:-3])
                    conn_intermediate = test_internet()
                    if conn_intermediate:
                        print('Connection live')
                        log_msg +='Connection live' +'\n'
                        f.write("Connection live \n")
                        resp = upload_to_gdrive(drive, title,fname, client_id, drive_folder_scan_id)
                        if resp is True:
                            log_msg +='Upload succeeded'+'\n'
                            successful_uploads += 1
                            conn_tests = 9999
                        else:
                            stop_led()
                            led_blink = False
                            start_error(led_thread)
                            led_error = True
                            log_msg += 'gdrive upload script failed, resetting counter and trying again'+'\n'
                            f.write('gdrive upload script failed, resetting counter and trying again'+'\n')
                            conn_tests += 1
                            break
                    else:
                        print('Uploading loop failed, resetting counter and trying again')
                        stop_led()
                        led_blink = False
                        start_error(led_thread)
                        led_error = True

                        log_msg += 'Uploading loop failed, resetting counter and trying again'+'\n'
                        f.write('Uploading loop failed, resetting counter and trying again'+'\n')
                        conn_tests += 1
                        break
                except:
                    print('Failed unkown at file: ',fname)
                    stop_led(led_thread)
                    led_blink = False
                    start_error(led_thread)
                    led_error = True
                    log_msg += 'Script failed unknown at file: ' + str(fname) +'\n'
                    f.write('Script failed unknown at file: ' + str(fname) +'\n')
            #Upload exit file here.
            end_time = time.time()
            duration = (end_time-start_time)
            exit_file_name = create_exit_file(no_of_imgs,total_file_size, successful_uploads,duration,log_msg,scan_id,client_id)
            resp = upload_to_gdrive(drive, os.path.basename(exit_file_name),exit_file_name, client_id, drive_folder_scan_id)
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
    cleanexit(imgs,devname,led_thread,formatting = format, succes = True)

    #Send alert:
    conn = False
    conn_tests = 0
    log_msg += 'Finalized after {} successful uploads of {} image-files'.format(successful_uploads,len(files))
    f.write('Finalized after {} successful uploads of {} image-files'.format(successful_uploads,len(files)))
    while conn is False and conn_tests<100:
        conn = test_internet()
        if conn:
            try:
                send_telegram(log_msg,telegram_ids)
            except:
                shorter_msg = 'Finalized after {} successful uploads of {} image-files. Too long for regular message.'.format(successful_uploads,len(files))
                send_telegram(shorter_msg,telegram_ids)
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
    led_thread = cleanexit(imgs,devname,led_thread,formatting = False, succes=False)
    led_blink = False
    led_error = True
f.close()
sys.exit()
