#!/usr/bin/python3
import pprint
import os
import fnmatch
import re
import datetime
import sys
import logging
import configparser
import telepot
from subprocess import check_output
from subprocess import call
from urllib.request import urlopen
import time
import pytz
import datetime
from shutil import copy2
# from LED import *
import requests
from PIL import Image
from PIL.ExifTags import TAGS
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive



def perform_backup(file_dicts,client_id,backup_folder_location,telegram_ids):
    #This function backups up files from SD if space allows. If not it
    # starts deleting backed up files, old to new, untill space is available.
    # If no space is available still, the files are not backed up.

    #initiation
    total_file_size = 0 #Used to determine total file size of all images combined
    output = ''
    scan_ids = list(set(f['scan_id'] for f in file_dicts))

    #    backup_folder_base = backup_folder_location+scan_id+'/'
    updated_file_dicts = []

    #Create required folders
    if not os.path.exists(backup_folder_location):
        os.makedirs(backup_folder_location)

    #Create the required backup folder for each scan_id. Add (x) for copies
    backup_folder_dict = {}
    for scan_id in scan_ids:
        duplicate_counter = 1
        backup_folder_base = backup_folder_location+scan_id+'/'
        backup_folder = backup_folder_base
        while os.path.exists(backup_folder):
            backup_folder = backup_folder_base[0:-1]+'({})/'.format(duplicate_counter)
            duplicate_counter +=1
        os.makedirs(backup_folder)
        backup_folder_dict.update({scan_id: backup_folder})

    existing_scans = os.listdir(backup_folder_location)
    existing_scans.sort()

    #Determine available space
    target_stats = os.statvfs(backup_folder_location)
    avail_space = target_stats.f_frsize * target_stats.f_bavail

    #Determine required size
    total_file_size_dict = {}
    for f in file_dicts:
        image_size = os.path.getsize(f['filepath'])
        scan_id = f['scan_id']
        if scan_id in total_file_size_dict.keys():
            total_file_size_dict[scan_id] += image_size
        else:
            total_file_size_dict[scan_id] = image_size
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
            warning_msg = "removed folder {} to make space".format(existing_scans[0])
            logging.warning(warning_msg)
            send_telegram('{}: '.format(client_id)+warning_msg,telegram_ids)
            target_stats = os.statvfs(backup_folder_location)
            avail_space = target_stats.f_frsize * target_stats.f_bavail
            existing_scans = os.listdir(backup_folder_location)
            existing_scans.sort()

        #If size is available, copy files. Otherwise don't backup, but let us know via telegram
        if total_file_size < avail_space:
            logging.warning('Enough available space to fit add images to backup drive')
            counter = 1
            for filedict in file_dicts:
                original_filepath = filedict['filepath']
                filename = filedict['filename']
                scan_id = filedict['scan_id']
                extension = os.path.splitext(filename)
                backup_name = filedict['base_title']
                backup_folder = backup_folder_dict[scan_id]
                copy2(original_filepath,backup_folder+backup_name)
                counter+=1
                logging.warning('Copied image {} of {}.'.format(counter-1,len(file_dicts)))
                filedict['backup_filename'] = backup_name
                filedict['backup_filepath'] = backup_folder_dict[scan_id]+backup_name
                updated_file_dicts.append(filedict)
        else:
            #This ELSE should be redundant, because of the main IF (before the WHILE)
            logging.warning('Disk full, no backup performed.')
            send_telegram('client {}: Disk full - no backup performed.'.format(client_ID),telegram_ids)

    else:
        logging.warning('Disk full, no backup performed.')
        send_telegram('client {}: Disk full - no backup performed.'.format(client_ID),telegram_ids)

    return total_file_size_dict, updated_file_dicts

def get_device_name(mountpoint):
    df = str(check_output("df"))
    first_occ = df.find("n/dev/sd")
    mountpoint = "/media/usb0"
    mountpoint_char = df.find(mountpoint)
    inv_mountpoint_char = len(df) - mountpoint_char
    inv_df = df[::-1]
    name_linestart_inv = inv_df.find("\\",inv_mountpoint_char)
    name_linestart = len(df) - name_linestart_inv
    line = df[name_linestart:mountpoint_char+len(mountpoint)]
    devname_end = line.find(" ")
    devname_start = line.find("n")
    devname = line[devname_start+1:devname_end]
    return devname

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

def create_drive_obj(credentials_file = "/usr/bin/photup/gdrive_creds.txt"):
    gauth = GoogleAuth()
    # Try to load saved client credentials
    gauth.LoadCredentialsFile(credentials_file)
    if gauth.credentials is None:
        # Authenticate if they're not there
        gauth.LocalWebserverAuth()
    elif gauth.access_token_expired:
        gauth.Refresh()
    else:
        # Initialize the saved creds
        gauth.Authorize()
    # Save the current credentials to a file
    gauth.SaveCredentialsFile(credentials_file)

    drive = GoogleDrive(gauth)
    return drive

def refresh_drive_obj(credentials_file="/usr/bin/photup/gdrive_creds.txt"):
    gauth = GoogleAuth()
    gauth.LoadCredentialsFile(credentials_file)
    gauth.Refresh()
    gauth.SaveCredentialsFile(credentials_file)
    gauth.Authorize()
    drive = GoogleDrive(gauth)
    return drive

def gdrive_get_expiration_ts(drive):
    utc = pytz.utc
    gauth_exp = drive.auth.credentials.token_expiry
    gauth_exp_utc = utc.localize(gauth_exp)
    gauth_exp_ts = datetime.datetime.timestamp(gauth_exp_utc)
    now_ts = datetime.datetime.timestamp(datetime.datetime.now())
    exp_remain = int(gauth_exp_ts - now_ts)
    return exp_remain


def get_filelist(drive, id):
    query = "'" + id + "' in parents and trashed=false"
    before = datetime.datetime.now() #DEBUG
    file_list = drive.ListFile({'q': query}).GetList()
    after = datetime.datetime.now() #DEBUG
    time = round((after - before).total_seconds())
    logging.warning('Getting filelist in {} seconds'.format(time))
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

def upload_to_gdrive(drive, title, fname, client_id, gdrive_files):
    drive_folder_scan_id = gdrive_files['drive_folder_scan_id']
    scanfolder_files = gdrive_files['drive_filenames']
    img_title =  title
    no_tries = 0
    succes = False
    while no_tries <10 and not(succes):
        line = "New file: {}, try {}".format(img_title,no_tries)
        print(line)
        logging.warning(line)

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
            succes = True
        except Exception as e:
            logging.warning('Exception in upload_to_gdrive')
            logging.warning(e)
            pass
        no_tries += 1
    if succes is True:
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
        len_ext = len(extension)
        name = basename
        while name in drive_filenames:
            name = basename[0:-len_ext]+'({})'.format(duplicate_counter)+basename[-len_ext:]
            duplicate_counter += 1
        basenames.extend([name])\


    with open(init_file_name,'w') as f:
        f.write( ','.join(basenames))
    return init_file_name

def create_exit_file(no_of_imgs,total_file_size, successful_uploads,duration,scan_id,client_id,no_of_scans):
    if no_of_imgs == 0:
        no_of_imgs = 1
    exit_file_name = "/usr/bin/photup/init_exit_files/" + client_id + "_" + scan_id + "_exit.txt"
    duration_min = round(duration/60)
    avg_duration = round(duration/no_of_imgs)
    total_file_size = round(total_file_size/1e6)
    avg_file_size = round(total_file_size/no_of_imgs)
    line0 = 'Scan_id: {}\n'.format(scan_id)
    line1 = 'Successful uploads: {} of {}. \n'.format(successful_uploads,no_of_imgs)
    line2 = 'Time: {}\n'.format(get_now())
    line3 = 'Finished in {} minutes at an average of {}s per image. \n'.format(duration_min,avg_duration)
    line4 = 'Total uploaded file size equals {}MB at an average of {}MB per image.\n'.format(total_file_size, avg_file_size)

    exit_msg= line0 + line1 + line2 + line3 + line4

    with open(exit_file_name,'w') as f:
        f.write(line1)
        f.write(line2)
        if no_of_scans == 1:
            f.write(line3)
        f.write(line4)
    return exit_file_name, exit_msg



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


def cleanexit(imgs,devname,led, formatting = True, succes=True):
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
        led.reset()
        logging.warning('Finished with cleanexit and succes')
    else:
        led.error()
        led.reset()
        logging.warning('Finished with cleanexit and error')




def get_filedicts(sdcard,extensions,client_id):
    filedicts = []
    counters = {}
    for root, dirs, files in os.walk(sdcard, topdown=False):
        files.sort()#This is new. Check if it doesn't fuck everything up
        for file in files:
            if file.endswith(tuple(extensions)) and not file.startswith("._") and root.find('Trash') == -1:
                scan_date = get_img_date(root+"/"+file)
                if scan_date in counters:
                    counters[scan_date]+=1
                else:
                    counters[scan_date] = 1
                extension = os.path.splitext(file)
                base_title = scan_date+'_'+client_id+'_img'+str(counters[scan_date]).zfill(6)+extension[-1]
                filedict = {'root':root ,'filepath':root+"/"+file, 'filename':file, 'scan_id':scan_date, 'base_title':base_title}
                filedicts.append(filedict)
    return filedicts

def get_img_date(filename):
    image = Image.open(filename)
    exif = image._getexif()
    #Exif key for DateTime equals 306
    dt_str = exif[306]
    dt_object = datetime.datetime.strptime(dt_str, '%Y:%m:%d %H:%M:%S')
    image_date = dt_object.strftime('%Y%m%d')
    return(image_date)
