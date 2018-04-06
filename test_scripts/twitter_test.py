# =* coding: utf-8 *=

import platform
import sys
import queue
import threading

import time
#print(platform.system())

packages_path = ""
cache_dir_path = ""

if platform.system() == "Darwin":
    packages_path = "/Users/Shared/TD-Python/lib/python3.5/site-packages"
    cache_dir_path = "/Users/Shared/TouchDesigner-Twitter-Cache"
else:
    packages_path = "C:\\TD-Python\\Lib\\site-packages"
    cache_dir_path = "C:\\Users\\Public\\Documents\\TouchDesigner-Twitter-Cache"

if packages_path not in sys.path:
    sys.path.append(packages_path)

#print(sys.path)

import os
import requests
from pprint import pprint

from twython import Twython
APP_KEY = 'hGnpvU4F3zE6jFJC6bbYtlm3z'
APP_SECRET = 'hUYfBmmHZPlLXwZpyhIBCEEigbRoK9NQxSDquqa7VT0EiQqbHh'




#cache_dir_path = os.path.join(curr_dir_path, 'cache/')
if not os.path.exists(cache_dir_path):
    os.makedirs(cache_dir_path)


twitter = Twython(APP_KEY, APP_SECRET)


def get_media(s):
    entities = None
    if 'extended_entities' in s:
        #print('has extended_entities')
        entities = s['extended_entities']
    elif 'entities' in s:
        #print('has entities')
        entities = s['entities']

    media = None
    if 'media' in entities:
        #print('has media')
        media = entities['media']
    return media


def get_photo(s):
    media = get_media(s)

    if media:
        for m in media:
            if m['type'] == 'photo':
                #print('has photo')
                return m['media_url']

    return None

def get_profile_picture(s):
    media = get_media(s)

    if media:
        for m in media:
            if m['type'] == 'photo':
                #print('has photo')
                return m['media_url']

    return None

def get_video(s):
    media = get_media(s)

    if media:
        for m in media:
            if m['type'] == 'video':
                #print('has video')
                video_thumbnail_url = m['media_url']
                video_variants = [x for x in m['video_info']['variants'] if x['content_type'] == 'video/mp4']
                if len(video_variants) > 0:
                    mp4_url = video_variants[-1]['url']
                    return video_thumbnail_url, mp4_url
                #print("%i video variants" % len(video_variants))

    return None

def maybe_download_photo(s):
    photo_url = get_photo(s)
    if not photo_url:
        return

    #print('download photo %s' % photo_url)
    tid = s['id']
    ext = photo_url.split('.')[-1]    
    photo_path = os.path.join(cache_dir_path, "%i_photo.%s" % (tid, ext))

    if os.path.exists(photo_path):
        return photo_path

    #print('downloading photo to %s...' % photo_path)
    r = requests.get(photo_url)
    open(photo_path, 'wb').write(r.content)
    #print('downloaded photo to %s' % photo_path)

    return photo_path


def maybe_download_video(s):
    video = get_video(s)
    if not video:
        return



    video_thumbnail_url, video_url = video

    #print('download video %s' % video_url)

    tid = s['id']

    # thumbnail
    thumb_ext = video_thumbnail_url.split('.')[-1]    
    thumb_path = os.path.join(cache_dir_path, "%i_video_thumb.%s" % (tid, thumb_ext))

    if not os.path.exists(thumb_path):        
        #print('downloading thumbnail to %s...' % thumb_path)
        r = requests.get(video_thumbnail_url)
        open(thumb_path, 'wb').write(r.content)
        #print('downloaded thumbnail to %s' % thumb_path)

    # video
    video_ext = video_url.split('.')[-1]    
    video_path = os.path.join(cache_dir_path, "%i_video.%s" % (tid, video_ext))

    if not os.path.exists(video_path):        
        #print('downloading video to %s...' % video_path)
        r = requests.get(video_url)
        open(video_path, 'wb').write(r.content)
        #print('downloaded video to %s' % video_path)

    return thumb_path, video_path


def dictlist_to_2d_array(dictlist, header, include_header=False):
    res = [[item.get(key, '') for key in header] for item in dictlist]
    if include_header:
        res.insert(0, header)
    return res




#print(requests.get("http://google.com").text)

currentQuery = ""

def process_query(query, max_id=0, since_id=0, min_posts=20):
    global isBusy
    global currentQuery

    # check if we still need this data
    if currentQuery != query:
        exitProcessingThread()
        
    print("Process query %s with max_id=%i, since_id=%i, min_posts=%i" % (query, max_id, since_id, min_posts))

    results = []

    print('request query: %s' % query)
    statuses = twitter.search(q=query, result_type='recent', count=100, include_entities=True, max_id=max_id, since_id=since_id)
    
    print('got %i statuses' % len(statuses["statuses"]))
    pprint(statuses)

    photos_count = 0
    videos_count = 0
    total_count = 0
    

    
    current_min_id = 9223372036854775807

    for s in statuses["statuses"]:
        # check if we still need this data
        if currentQuery != query:
            exitProcessingThread()

        total_count += 1

        tweet_id = s['id']

        if is_in_current_table(tweet_id):
            continue

        if tweet_id < current_min_id:
            current_min_id = tweet_id

        is_retweet = 'retweeted_status' in s
        if is_retweet:
            continue           




        text = s['text']
        likes = s['favorite_count']

        created_at = s['created_at']
        

        # parse photo
        photo = get_photo(s) 

        photo_url = ''
        photo_path = ''
        if photo:
            photos_count += 1
            photo_url = photo
            photo_path = maybe_download_photo(s)

        # parse video
        video = get_video(s)

        video_thumbnail_url = ''        
        mp4_url = ''      
        video_thumbnail_path = ''
        mp4_path = ''
        if video:
            videos_count += 1
            video_thumbnail_url, mp4_url = video
            video_thumbnail_path, mp4_path = maybe_download_video(s)




        # generate tweet dict
        res = {
            "id": tweet_id,
            "is_retweet": is_retweet,
            "text": text,
            "likes": likes,
            "has_photo": bool(photo),
            "photo_url": photo_url,
            "photo_path": photo_path,
            "has_video": bool(video),
            "video_thumbnail_url": video_thumbnail_url,
            "mp4_url": mp4_url,
            "video_thumbnail_path": video_thumbnail_path,
            "mp4_path": mp4_path,
            "created_at": created_at
        }

        results.append(res)  


    if len(results) > 0:
        if len(results) < min_posts:
            #print("Not enough posts (%i), get more, current_min_id = %i" % (len(results), current_min_id))
            results += process_query(query, max_id=(current_min_id-1), min_posts=(min_posts - len(results)))
    else:
        print("No more results for query %s" % query)
    
    results = sorted(results, key=lambda x: x["id"])
    return results
    

def get_table_for_posts(posts, include_header=False):
    table = dictlist_to_2d_array(posts, [
        'id',
        'is_retweet',
        'text',
        'likes',
        'has_photo', 'photo_url', "photo_path",
        'has_video', 'video_thumbnail_url', 'mp4_url', "video_thumbnail_path", "mp4_path",
        'created_at'
    ], include_header)

    #pprint(posts)
    #print("%i posts" % len(posts))

    return table

def is_in_current_table(id):
    global currentTableData
    for row in currentTableData:
        if row[0] == id:
            return True
    return False

def exitProcessingThread():
    global isBusy
    print("Terminating processing, query has changed to %s" % currentQuery)
    isBusy = False
    sys.exit()

# TOUCH DESIGNER FUNCTIONS

_scriptOp = None
callback_queue = queue.Queue()


isBusy = False

isQueryInUpdateMode = False
currentMaxId = 0

currentTableData = []

DEFAULT_PROCESS_EVERY_SEC = 5

last_time_processed_query = 0


if __name__ == "__main__":

    currentQuery = "#check"
    t = threading.Thread(target=process_query, args=[currentQuery])
    t.daemon = True
    t.start()
    t.join()
    #get_table_for_query("#asd")

    
