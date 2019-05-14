#python3

import _thread
import requests
import time

counter = 0

proxies = {
    'http': 'taojy123.cn:1087',
}

def fuck():
    global counter
    counter += 1
    print(counter)
    try:
        # url = 'http://myip.ipip.net/'
        url = 'http://47.90.13.47/messages/'
        r = requests.get(url, proxies=proxies, timeout=30)
        # print(r.text)
    except Exception as e:
        print(e)
    counter -= 1
    

for i in range(10):
    _thread.start_new_thread(fuck, ())
    time.sleep(10)


