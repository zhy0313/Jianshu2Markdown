import os, re, threading
from queue import Queue

import requests
import html2text
from bs4 import BeautifulSoup


BASE = "http://www.jianshu.com/"
BASE_PROFILE = BASE + 'users/'
BASE_NOTEBOOK = BASE + 'notebooks/'
PATTERN = re.compile(r'href="(.*?)"')
PAGINATION = 'latest_articles?page={}'
THREAD_NUM = 5
TIMEOUT = 3


class BasicSpider(object):
    def __init__(self, html_dir, md_dir):
        self.html_dir = html_dir
        self.md_dir = md_dir
        self.post_queue = Queue()  # put post's url


class ProfileSpider(BasicSpider):

    def __init__(self, user_id, html_dir, md_dir):
        super().__init__(html_dir, md_dir)
        self.url = BASE_PROFILE + str(user_id) + '/'
        self.profile_queue = Queue()  # put user's profile

    def get_profile_end(self):
        """Get pagination end number"""
        text = _get_text(self.url)
        if text is None:
            return

        bsobj = BeautifulSoup(text, 'html.parser')
        last_link = bsobj.find('li', class_='last')
        pattern = re.compile(r'href=".*?page=(\d+)')
        end = re.search(pattern, str(last_link))
        return 1 if end is None else int(end.group(1))

    def start(self):
        end = self.get_profile_end()
        if not isinstance(end, int):
            return

        for _ in range(THREAD_NUM // 3):
            t = ThreadProfile(self.profile_queue, self.post_queue)
            t.setDaemon(True)
            t.start()

        for i in range(1, end+1):
            self.profile_queue.put(self.url + PAGINATION.format(i))

        for _ in range(THREAD_NUM):
            t = ThreadPost(self.post_queue, self.html_dir, self.md_dir)
            t.setDaemon(True)
            t.start()

        self.profile_queue.join()
        self.post_queue.join()


class NotebookSpider(BasicSpider):

    def __init__(self, nb_id, html_dir, md_dir):
        super().__init__(html_dir, md_dir)
        self.url = BASE_NOTEBOOK + str(nb_id) + '/latest'

    def start(self):
        self._get_posts_url(self.url)
        for _ in range(THREAD_NUM):
            t = ThreadPost(self.post_queue, self.html_dir, self.md_dir)
            t.setDaemon(True)
            t.start()

        self.post_queue.join()

    def _get_posts_url(self, url):
        text = _get_text(url)
        if text is None:
            return

        bsobj = BeautifulSoup(text, "html.parser")
        items = bsobj.find_all('h4', class_='title')
        for item in items:
            print(BASE + re.search(PATTERN, str(item)).group(1))
            self.post_queue.put(BASE + re.search(PATTERN, str(item)).group(1))


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
        text = _get_text(url)
        if text is None:
            return

        bsobj = BeautifulSoup(text, "html.parser")
        items = bsobj.find_all('h4', class_='title')
        for item in items:
            print(BASE + re.search(PATTERN, str(item)).group(1))
            self.post_queue.put(BASE + re.search(PATTERN, str(item)).group(1))


class ThreadPost(threading.Thread):

    def __init__(self, queue, html_dir, md_dir):
        super(ThreadPost, self).__init__()
        self.queue = queue
        self.html_dir = html_dir
        self.md_dir = md_dir
        self.convertor = html2text.HTML2Text()
        self.convertor.body_width = 0

    def run(self):
        while True:
            url = self.queue.get()
            self.get_post(url)
            self.queue.task_done()

    def get_post(self, url):
        text = _get_text(url)
        if text is None:
            return
        bsobj = BeautifulSoup(text, 'html.parser').find('div', class_="container")
        title = bsobj.find('h1', class_="title").text
        result = bsobj.find('div', class_='show-content')
        # print(result)
        text = result.prettify()
        self._download(text, title + '.html', self.html_dir)
        self._download(self._convert2md(text), title + '.md', self.md_dir)

    def _convert2md(self, text):
        return self.convertor.handle(text)

    def _download(self, content, name, directory):
        if not os.path.exists(directory):
            os.mkdir(directory)
        with open(os.path.join(directory, name), 'w', encoding='utf-8') as f:
            f.write(content)


def _get_text(url):
    try:
        res = requests.get(url, timeout=TIMEOUT)
    except requests.Timeout:
        print("access to {} timeout".format(url))
        return
    else:
        if res.status_code == 200:
            return res.text
        else:
            return


def main():
    import argparse
    os.environ["PYTHONIOENCODING"] = 'utf-8'
    parser = argparse.ArgumentParser()
    parser.add_argument("-u", "--user", help="user id")
    parser.add_argument("-n", "--notebook", help="notebook id")
    parser.add_argument("-hd", '--htmldir', help="html dir")
    parser.add_argument("-md", '--mddir', help="md dir")
    args = parser.parse_args()
    html_dir = args.htmldir if args.htmldir else 'html'
    md_dir = args.mddir if args.mddir else 'md'
    if not os.path.exists(html_dir):
        os.mkdir(html_dir)
    if not os.path.exists(md_dir):
        os.mkdir(md_dir)
    client = None
    if args.user:
        client = ProfileSpider(args.user, html_dir, md_dir)
    elif args.notebook:
        client = NotebookSpider(args.notebook, html_dir, md_dir)
    if client:
        client.start()


if __name__ == '__main__':
    main()
