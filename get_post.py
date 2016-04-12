import os, re, threading
from queue import Queue

import requests
from bs4 import BeautifulSoup


BASE = "http://www.jianshu.com/"
BASE_PROFILE = BASE + 'users/'
PATTERN = re.compile(r'href="(.*?)"')
pagination = 'latest_articles?page={}'
THREAD_NUM = 5


class GetPost(object):

    def __init__(self, user_id, html_dir):
        self.url = BASE_PROFILE + str(user_id) + '/'
        self.html_dir = html_dir
        self.md_url = None  # TODO
        self.post_queue = Queue()     # put post's url
        self.profile_queue = Queue()  # get user's profile, pagination

    def get_profile_end(self):
        res = requests.get(self.url)
        bsobj = BeautifulSoup(res.text, 'html.parser')
        last_link = bsobj.find('li', class_='last')
        pattern = re.compile(r'href=".*?page=(\d+)')
        end = re.search(pattern, str(last_link))
        return int(end.group(1))

    def start(self):
        end = self.get_profile_end()

        for i in range(1, int(end)+1):
            self.profile_queue.put(self.url + pagination.format(i))

        for _ in range(3):
            t = ThreadProfile(self.profile_queue, self.post_queue)
            t.setDaemon(True)
            t.start()

        for _ in range(5):
            t = ThreadPost(self.post_queue, self.html_dir)
            t.setDaemon(True)
            t.start()

        self.profile_queue.join()
        self.post_queue.join()


class ThreadProfile(threading.Thread):
    """Get post's url from user's profile and put them in post queue
    """

    def __init__(self, profile_queue, post_queue):
        super(ThreadProfile, self).__init__()
        self.profile_queue = profile_queue
        self.post_queue = post_queue

    def run(self):
        while True:
            url = self.profile_queue.get()
            self._get_posts_url(url)
            self.profile_queue.task_done()

    def _get_posts_url(self, url):
        res = requests.get(url+pagination)
        bsobj = BeautifulSoup(res.text, "html.parser")
        items = bsobj.find_all('h4', class_='title')

        for item in items:
            print(BASE + re.search(PATTERN, str(item)).group(1))
            self.post_queue.put(BASE + re.search(PATTERN, str(item)).group(1))


class ThreadPost(threading.Thread):

    def __init__(self, queue, html_dir):
        super(ThreadPost, self).__init__()
        self.queue = queue
        self.html_dir = html_dir

    def run(self):
        while True:
            url = self.queue.get()
            self.get_post(url)
            self.queue.task_done()

    def get_post(self, url):
        res = requests.get(url)
        bsobj = BeautifulSoup(res.text, 'html.parser').\
                                find('div', class_="container")
        title = bsobj.find('h1', class_="title").text
        result = bsobj.find('div', class_='show-content')
        # print(result)
        self._download(result.prettify(), title + '.html')

    def _download(self, content, name):
        with open(os.path.join(self.html_dir, name), 'w', encoding='utf-8') as f:
            f.write(content)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-u", "--user", help="user id here")
    parser.add_argument("-hd", '--htmldir', help="html dir here")
    args = parser.parse_args()
    if not args.user:
        print("please put userid")
        return
    if not args.htmldir:
        args.htmldir = "html"
    os.environ["PYTHONIOENCODING"] = 'utf-8'
    if not os.path.exists(args.htmldir):
        os.mkdir(args.htmldir)
    client = GetPost(args.user, args.htmldir)
    client.start()


if __name__ == '__main__':
    main()
