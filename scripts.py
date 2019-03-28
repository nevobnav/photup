#!/usr/bin/python3
import flickrapi
import pprint
import os
import fnmatch
import re
import datetime
import sys
import configparser
import telepot
from subprocess import check_output
from subprocess import call
from urllib.request import urlopen
import time
import datetime
from shutil import copy2
from LED import *
import requests
from PIL import Image
from PIL.ExifTags import TAGS
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive


def perform_backup(files,client_id,scan_id):
    #This function backups up files from SD if space allows. If not it
    # starts deleting backed up files, old to new, untill space is available.
    # If no space is available still, the files are not backed up.
    total_file_size = 0 #Used to determine total file size of all images combined
    output = ''
    backup_folder_location = '/usr/bin/photup/image_backup/'
    backup_folder_base = backup_folder_location+scan_id+'/'
    backup_filelist = []
    duplicate_counter = 0

    #Create required folders
    if not os.path.exists(backup_folder_location):
        os.makedirs(backup_folder_location)

    backup_folder = backup_folder_base
    while os.path.exists(backup_folder):
        backup_folder = backup_folder_base[0:-1]+'({})/'.format(duplicate_counter)
        duplicate_counter +=1

    os.makedirs(backup_folder)
    existing_scans = os.listdir(backup_folder_location)
    existing_scans.sort()

    #Determine available space
    target_stats = os.statvfs(backup_folder_location)
    avail_space = target_stats.f_frsize * target_stats.f_bavail

    #Determine required size
    for img in files:
        image_size = os.path.getsize(img)
        total_file_size += image_size

    #Determine total backup size
    total_backup_size = sum( os.path.getsize(os.path.join(dirpath,filename)) for\
        dirpath, dirnames, filenames in os.walk( backup_folder_location ) for filename in filenames )

    if (avail_space + total_backup_size) > total_file_size:
        #Onlny start working if the total file size is workable

        #Delete old folders until required size is available or no old folders are left
        while (total_file_size > avail_space) and (len(existing_scans)>1) :
            oldest_dir = backup_folder_location+existing_scans[0]+'/'

            for file in os.listdir(oldest_dir):
                os.remove(os.path.join(oldest_dir,file))

            os.rmdir(oldest_dir)
            output += "Removed folder {} to make space".format(existing_scans[0])+'\n'
            target_stats = os.statvfs(backup_folder_location)
            avail_space = target_stats.f_frsize * target_stats.f_bavail
            existing_scans = os.listdir(backup_folder_location)
            existing_scans.sort()

        #If size is available, copy files. Otherwise don't backup, but let us know via telegram
        if total_file_size < avail_space:
            output += 'Enough avialable space to fit add images to backup drive'+'\n'
            counter = 1
            for img in files:
                extension = os.path.splitext(img)
                img_name = scan_id +'_'+client_id+'_img'+str(counter).zfill(6)+extension[-1]
                copy2(img,backup_folder+img_name)
                counter+=1
                print('Copied image {} of {}.'.format(counter-1,len(files)))
                img_path = backup_folder+img_name
                backup_filelist.append(img_path)
        else:
            #This ELSE should be redundant, because of the main IF (before the WHILE)
            output += 'Disk full - No images copied!'+'\n'
            send_telegram('client {}: Disk full - no backup performed.'.format(client_ID),telegram_IDs)

    else:
        output += 'Disk full - No images copied!'+'\n'
        send_telegram('client {}: Disk full - no backup performed.'.format(client_ID),telegram_IDs)

    return output,total_file_size, backup_filelist

def get_device_name():
    df = str(check_output("df"))
    first_occ = df.find("n/dev/sd")
    name = df[first_occ+1:first_occ+10]
    return name

def test_internet(timeout = 5):
    try:
        requests.head('http://www.google.com', timeout = timeout)
        return True
    except:
        return False

def send_telegram(message_text,telegramlist):
    for ID in telegramlist:
        #Our bot's username is 'VluchtBot', with ID 799284289
        bot = telepot.Bot('799284289:AAGQyamXQLC4fPrtePnciwnJc-m8G91YWPk')
        bot.sendMessage(ID, message_text)

def get_now():
    timestamp_string = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
    return timestamp_string

def create_drive_obj():
    gauth = GoogleAuth()
    # Try to load saved client credentials
    gauth.LoadCredentialsFile("/usr/bin/photup/gdrive_creds.txt")
    if gauth.credentials is None:
        # Authenticate if they're not there
        gauth.LocalWebserverAuth()
    elif gauth.access_token_expired:
        # Refresh them if expired
        gauth.Refresh()
    else:
        # Initialize the saved creds
        gauth.Authorize()
    # Save the current credentials to a file
    gauth.SaveCredentialsFile("/usr/bin/photup/gdrive_creds.txt")

    drive = GoogleDrive(gauth)
    return drive

def refresh_drive_obj():
    gauth = GoogleAuth()
    gauth.LoadCredentialsFile("/usr/bin/photup/gdrive_creds.txt")
    gauth.Refresh()
    gauth.SaveCredentialsFile("/usr/bin/photup/gdrive_creds.txt")
    drive = GoogleDrive(gauth)
    return drive


def get_filelist(drive, id):
    query = "'" + id + "' in parents and trashed=false"
    file_list = drive.ListFile({'q': query}).GetList()
    return file_list

def find_or_create_folder(drive, title, id):
    filelist = get_filelist(drive, id)
    new_folder = (next((folder for folder in filelist if folder["title"] == title), False))
    if not(new_folder):
        print('Creating new folder "{}"'.format(title))
        folder_metadata = {'title' : title, 'mimeType' : 'application/vnd.google-apps.folder'}
        folder_location_metadata = {"parents": [{"kind": "drive#fileLink", "id": id}]}
        folder = drive.CreateFile({**folder_metadata, **folder_location_metadata})
        folder.Upload()
    filelist = get_filelist(drive, id)
    new_folder = (next((folder for folder in filelist if folder["title"] == title), False))
    new_id = new_folder['id']
    return new_id

def prepare_new_scan(drive,client_id,scan_id):
    folder_Opnames_id = '1DTK46R2aG0cWnN698OGSxGY2dIlJ-LEN'
    folder_customer_id = find_or_create_folder(drive,client_id,folder_Opnames_id)
    folder_scan_id = find_or_create_folder(drive,scan_id, folder_customer_id)
    scanfolder_files = get_filelist(drive,folder_scan_id)
    filenames = [file['title'] for file in scanfolder_files]
    return filenames, folder_scan_id

def upload_to_gdrive(drive, title, fname, client_id, drive_folder_scan_id,):
    img_title =  title
    no_tries = 0
    drive_filenames = []
    while not(img_title in drive_filenames) and no_tries <10:
        print("{} not in current fileset".format(img_title))
        newimg = drive.CreateFile({
            'title':img_title,
            "parents": [{
                "kind": "drive#childList",
                "id": drive_folder_scan_id
                }]
            })
        newimg.SetContentFile(fname)
        try:
            newimg.Upload()
        except:
            pass
        scanfolder_files = get_filelist(drive,drive_folder_scan_id)
        drive_filenames = [file['title'] for file in scanfolder_files]
        no_tries += 1
    if img_title in drive_filenames:
        if no_tries == 0:
            print("{} already in drive".format(img_title))
        return True
    else:
        return False

def create_init_file(files,scan_id,client_id,drive_filenames):
    init_file_name = "/usr/bin/photup/init_exit_files/" + client_id + "_" + str(scan_id) + "_init.txt"
    basenames = []
    for file in files:
        duplicate_counter = 1
        basename = os.path.basename(file)
        extension = os.path.splitext(file)[-1]
        name = basename
        while name in drive_filenames:
            name = basename[0:-len_ext]+'({})'.format(duplicate_counter)+basename[-len_ext:]
            duplicate_counter += 1
        basenames.extend([name])\


    with open(init_file_name,'w') as f:
        f.write( ','.join(basenames))
    return init_file_name

def create_exit_file(no_of_imgs,total_file_size, successful_uploads,duration,log_msg,scan_id,client_id):
    if no_of_imgs == 0:
        no_of_imgs = 1
    exit_file_name = "/usr/bin/photup/init_exit_files/" + client_id + "_" + scan_id + "_exit.txt"
    duration_min = round(duration/60)
    avg_duration = round(duration/no_of_imgs)
    total_file_size = round(total_file_size/1e6)
    avg_file_size = round(total_file_size/no_of_imgs)
    with open(exit_file_name,'w') as f:
        f.write('Succesfull uploads: {} of {}.'.format(successful_uploads,no_of_imgs))
        f.write('Finished in {} minutes at an average of {}s per image.'.format(duration_min,avg_duration))
        f.write('Total uploaded file size equals {}MB at an average of {} per image.'.format(total_file_size, avg_file_size))
        f.write('Error log:')
        f.write(log_msg)

    return exit_file_name



def create_flickr_obj():
    config_file = "/etc/flickr.conf"
    config = configparser.ConfigParser()
    try:
        config.read(config_file)
        api_key = config.get("main","api_key")
        api_secret = config.get("main","api_secret")
        api_token = config.get("main","api_token")
    except:
        print("Missing "+config_file)
        sys.exit(0)

    flickr = flickrapi.FlickrAPI(api_key, api_secret, api_token)

        # Only do this if we don't have a valid token already
    if not flickr.token_valid(perms='write'):
        print("Authentication required")
        # Get a request token
        flickr.get_request_token(oauth_callback='oob')

        # Open a browser at the authentication URL. Do this however
        # you want, as long as the user visits that URL.
        authorize_url = flickr.auth_url(perms='write')
        print("Open the following URL on your web browser and copy the code to " + config_file)
        print(authorize_url)

        # Get the verifier code from the user. Do this however you
        # want, as long as the user gives the application the code.
        verifier = input('Verifier code: ')

        # Trade the request token for an access token
        flickr.get_access_token(verifier)
    return flickr


def cleanexit(imgs,devname,led_thread, formatting = True, succes=True):
    call(["sudo","umount",devname])
    #Check if there are any images. If not, it may be the wrong usb stick used
    #for dev work. Dont' wanna format that one.
    if imgs:
        print("Images found")
        #Format memory sdcard
        if formatting:
            print("Formatting SD...")
            call(["sudo","mkfs.exfat","-n","DJI_IMGS",devname])
    if succes:
        stop_led(led_thread)
        led_succes()
    else:
        stop_led(led_thread)
        led_thread = start_error()
        time.sleep(200)
        stop_led(led_thread)
        return led_thread


def get_filenames(sdcard,extensions):
    filelist = []
    for root, dirs, files in os.walk(sdcard, topdown=False):
        for file in files:
            if file.endswith(tuple(extensions)) and not file.startswith("._") and root.find('Trash') == -1:
                filelist.extend([root+"/"+file])
    return filelist

def get_img_date(filename):
    image = Image.open(filename)
    exif = image._getexif()
    #Exif key for DateTime equals 306
    dt_str = exif[306]
    dt_object = datetime.datetime.strptime(dt_str, '%Y:%m:%d %H:%M:%S')
    image_date = dt_object.strftime('%Y%m%d')
    return(image_date)
