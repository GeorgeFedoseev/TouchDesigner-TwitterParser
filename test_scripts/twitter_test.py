# =* coding: utf-8 *=
import sys
import os
import requests
from pprint import pprint

import threading

from twython import Twython
APP_KEY = 'hGnpvU4F3zE6jFJC6bbYtlm3z'
APP_SECRET = 'hUYfBmmHZPlLXwZpyhIBCEEigbRoK9NQxSDquqa7VT0EiQqbHh'


curr_dir_path = os.path.dirname(os.path.realpath(__file__))
cache_dir_path = os.path.join(curr_dir_path, 'cache/')
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


def dictlist_to_2d_array(dictlist, header):
    res = [[item.get(key, '') for key in header] for item in dictlist]
    res.insert(0, header)
    return res




#print(requests.get("http://google.com").text)



def process_query(query, max_id=0, min_posts=20):
    results = []

    statuses = twitter.search(q=query, result_type='recent', count=100, include_entities=True, max_id=max_id)
    
    #pprint(statuses)

    photos_count = 0
    videos_count = 0
    total_count = 0
    

    
    current_min_id = 9223372036854775807

    for s in statuses["statuses"]:
        total_count += 1

        tweet_id = s['id']

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


    if len(results) < min_posts:
        #print("Not enough posts (%i), get more, current_min_id = %i" % (len(results), current_min_id))
        results += process_query(query, max_id=current_min_id, min_posts=(min_posts - len(results)))
    
    return results
    

def get_table_for_query(query, min_posts=50):
    posts = process_query(query, min_posts=min_posts)

    table = dictlist_to_2d_array(posts, [
        'id',
        'is_retweet',
        'text',
        'likes',
        'has_photo', 'photo_url', "photo_path",
        'has_video', 'video_thumbnail_url', 'mp4_url', "video_thumbnail_path", "mp4_path",
        'created_at'
    ])

    pprint(posts)
    print("%i posts" % len(posts))

    return table


callback_queue = Queue.Queue()

def from_main_thread_nonblocking():
    while True:
        try:
            callback = callback_queue.get(False) #doesn't block
        except Queue.Empty: #raised when queue is empty
            break
        callback()         



if __name__ == "__main__":
    t = threading.Thread(target=get_table_for_query, args=["#asd"])
    t.daemon = True
    t.start()
    t.join()
    #get_table_for_query("#asd")

    
