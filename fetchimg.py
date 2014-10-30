# -*- coding: utf-8 -*-
#
# Filename: fetchimg.py
# Author:
#       sdkyoku
# Created: 2014-09-08 18:18


__version__ = '1.1.0'


from logger import mylogger as logger
from urllib import unquote
import sys
try:
    from bs4 import BeautifulSoup
except ImportError as ie:
    logger.error('%s', ie)
    sys.stdout.write('Cannot found module \"bs4\", please install \"beautifulsoup4\" with easy_install or pip.\n')
    sys.exit(77)
import ConfigParser
import sqlite3
import threading
import urllib2
import socket


try:
    import socks
except ImportError as ie:
    logger.error('%s', ie)
    sys.stdout.write('Cannot found module \"socks\", please install \"socks\" with easy_install or pip.\n')
    sys.exit(77)


import ssl
import time
import Queue
import os


class CfgReader:
    """
    读取当前目录下的配置文件
    """
    def __init__(self):
        self.cfg_file = r'moeimouto.conf'
        self.reader = ConfigParser.ConfigParser()
        self.reader.read(self.cfg_file)

    def get_cfg(self, section, key):
        """
        使用方法：
        value = get_cfg('base', 'key')
        """
        return self.reader.get(section, key)


# 在系统中注册此模块
cfg_reader = sys.modules['cfg_reader'] = CfgReader()


def get_filename(fname):
    """返回一个绝对路径"""
    return os.path.join(PATH, fname)


def get_file_size(fname):
    """取得文件大小
    如果文件存在则返回文件的大小，单位是字节
    如果不存在则返回0
    """
    return os.path.getsize(fname) if os.path.exists(fname) else 0


def set_socks5_proxy():
    status = cfg_reader.get_cfg('proxy', 'enabled')
    serv = cfg_reader.get_cfg('proxy', 'server')
    pt = int(cfg_reader.get_cfg('proxy', 'port'))
    if status == '1':
        logger.info('Use proxy %s:%s' % (serv, pt))
        socks.setdefaultproxy(socks.PROXY_TYPE_SOCKS5, serv, pt)
        socket.socket = socks.socksocket
    else:
        return


PATH = cfg_reader.get_cfg('base', 'path')
db_file = os.path.join(PATH, cfg_reader.get_cfg('base', 'db_file'))
conn = sqlite3.connect(db_file, check_same_thread=False)
cur = conn.cursor()
UA = cfg_reader.get_cfg('base', 'user-agent')


class DbHandle:
    """Class DbHandle

    This database has a table named \"tbl_hash\":

    | HASH | URL | APTIME(append time) | FLG(flag) |
    |------|-----|---------------------|-----------|
    |  **  | *** |         ***         |    ***    |
    """
    def __init__(self):
        self.create_database()

    def create_database(self):
        cur.execute("CREATE TABLE IF NOT EXISTS tbl_hash"
                    "(hash TEXT PRIMARY KEY, url TEXT, date TEXT, flag BOOLEAN)")

    def record(self, _dict):
        cur.execute("INSERT INTO tbl_hash VALUES (?,?,?,?)",
                    (_dict['HASH'], _dict['URL'], _dict['APTIME'], _dict['FLG']))

    def query(self, _hash):
        """query(hash)

        if hint, return 0,
        if hint none, return 1
        """
        cur.execute("SELECT * FROM tbl_hash WHERE hash = ?", (_hash,))
        result = cur.fetchall()
        return 0 if result else 1

    def disconnect(self):
        try:
            conn.commit()
            cur.close()
            conn.close()
        except sqlite3.DatabaseError, e:
            if isinstance(e.args[0], sqlite3.DatabaseError):
                logger.error('%s', e.args[0])
            else:
                raise

    def backup(self):
        # TODO: 实现备份数据库的功能，不过我一直想不到有什么备份的需要所以就打个标签先放这里好了
        pass


db_handle = sys.modules['db_handle'] = DbHandle()


class Fetcher(threading.Thread):
    def __init__(self, name, queue, thread_list):
        super(Fetcher, self).__init__()
        self.name = name
        self.queue = queue
        self.thread_list = thread_list

    def get_response(self, dic):
        pos = get_file_size(get_filename(dic['FILENAME']))
        logger.debug('Filename: %s', get_filename(dic['FILENAME']))
        logger.debug('Position: %d', pos)
        try:
            req = urllib2.Request(dic['URL'])
            if pos != 0:
                req.headers['Range'] = 'bytes=%s-' % pos
            resp = urllib2.urlopen(req, timeout=30)
            totalsize = resp.info().getheader('Content-Length').strip()
            totalsize = int(totalsize)
            size = totalsize-pos
            return (resp, pos, size, totalsize)
        except (urllib2.HTTPError, ssl.SSLError, socket.timeout):
            # handle timeout, nothing here
            logger.error('%s', 'time out.')
        except urllib2.URLError as e:
            logger.error('%s', e.reason)

    def show_progress(total, processed, fhash, qsize):
        percent = float(processed)/total
        percent = round(percent*100, 2)
        sys.stdout.write('[%s | %d of %d bytes| %.2f %%](%d left)\r'
                         % (fhash, processed, total, percent, qsize))
        sys.stdout.flush()

    def download(self, dic, chunk_size=1024*4, progressBar=show_progress):
        """将取得的内容写入文件"""
        try:
            (resp, pos, size, total) = self.get_response(dic)
        except TypeError as nt:
            logger.error('%s', nt.reason)
        bsf = pos
        logger.debug('bsf: %d', bsf)
        _filename = get_filename(dic['FILENAME'])
        if bsf != 0:
            fh = open(_filename, 'ab')
            total = total+pos
            logger.info('Resume mode: start from %d', pos)
        elif bsf == 0:
            fh = open(_filename, 'wb')
        while True:
            try:
                buf = resp.read(chunk_size)
                if not buf:
                    break
                fh.write(buf)
                bsf+=len(buf)
                progressBar(total, bsf, dic['HASH'], self.queue.qsize())
            except (urllib2.HTTPError, ssl.SSLError):
                logger.error('\nTIMEOUT')
                continue
        fh.flush()
        fh.close()
        try:
            sys.stdout.write('\n')
            db_handle.record(dic)
        except:
            pass

    def run(self):
        try:
            logger.debug('Thread %s started.', self.name)
            while not self.queue.empty():
                dic = self.queue.get()
                self.download(dic)
            else:
                logger.debug('nothing to do, exit.')
                self.thread_list.remove(self)
                logger.debug('Wait 3 seconds.')
                time.sleep(3)
        except:
            pass
        finally:
            # time.sleep(1)
            logger.debug('End thread %s.', self.name)
            logger.debug('Thread list contains: %s', self.thread_list)


class Eater(threading.Thread):
    def __init__(self, queue, lst, size=0):
        super(Eater, self).__init__()
        self.queue = queue
        self.thread_list = lst
        self.max_thread = size

    def handle_link(self, link):
        # 因为有些网址里含有CJK字符，所以在这个里边需要进行一下转码
        link = unicode(link)
        req = urllib2.Request(link, headers={'User-Agent': UA})
        resp = urllib2.urlopen(req)
        cont = resp.read()
        soup = BeautifulSoup(cont)
        try:
            resu = soup.find_all('a', class_='original-file-unchanged')
            url = resu[0].get('href')
        except IndexError as ie:
            logger.error('Lossless version not found, download changed version.')
            resu = soup.find_all('a', class_='original-file-changed')
            url = resu[0].get('href')
        # result = PATTERN.match(cont).group(1)
        # logger.info('Matched: %s', result)
        logger.info('Matched: %s', url)
        return url

    def url_eater(self, queue):
        """
        接受用户输入，将检测结果合法的元素放入队列中
        """
        try:
            while 1:
                sys.stdout.write('Enter url: ')
                tmp_url = sys.stdin.readline().strip('\n')
                tmp_time = time.ctime()
                if tmp_url == 'q':
                    logger.debug('Thread pool size: %d', len(self.thread_list))
                    if len(self.thread_list) == 0:
                        db_handle.disconnect()
                        sys.exit(0)
                    else:
                        logger.error('Thread Fetcher is working! Please retry until it done.')
                        time.sleep(3)
                        continue
                if (tmp_url.find('http', 0) == -1 and tmp_url.find('://', 8) != -1):
                    logger.error('Invalid URL: Are you forget the head of http or enter multiple url here?')
                    break
                if (tmp_url.split('.')[-1] != 'png' and tmp_url.split('.')[-1] != 'jpg'):
                    tmp = self.handle_link(tmp_url)
                    tmp_url = tmp
                    #   logger.error('Invalid file extension: %s.', tmp_url.split(r'/')[-1])
                    #   continue
                    tmp_dict = {
                        'URL': tmp_url,
                        'FILENAME': unquote(tmp_url.split(r'/')[-1]),
                        'HASH': tmp_url.split(r'/')[-2],
                        'APTIME': tmp_time,
                        'FLG': False
                    }
                    logger.debug('\nURL: %s\nFILENAME: %s\nHASH: %s\nAPTIME: %s', tmp_dict['URL'], tmp_dict['FILENAME'], tmp_dict['HASH'], tmp_dict['APTIME'])
                    completed = db_handle.query(tmp_dict['HASH'])
                    if completed == 0:
                        logger.info('%s already downloaded.', tmp_dict['HASH'])
                        continue
                    try:
                        logger.debug('ACQUIRED BY EATER')
                        queue.put(tmp_dict)
                    except:
                        pass
                    finally:
                        logger.info('%s ADDED, QUEUE SIZE %s', tmp_dict['HASH'], self.queue.qsize())
                        logger.debug('WAIT@EATER.')
                        if len(self.thread_list) == 0:
                            fetcher = Fetcher('Link Downloader', self.queue, thread_list)
                            fetcher.setDaemon(True)
                            self.thread_list.append(fetcher)
                            logger.debug('Thread list contains: %s', thread_list)
                            fetcher.start()
                else:
                    tmp_dict = {
                        'URL': tmp_url,
                        'FILENAME': unquote(tmp_url.split(r'/')[-1]),
                        'HASH': tmp_url.split(r'/')[-2],
                        'APTIME': tmp_time,
                        'FLG': False
                    }
                    logger.debug('\nURL: %s\nFILENAME: %s\nHASH: %s\nAPTIME: %s', tmp_dict['URL'], tmp_dict['FILENAME'], tmp_dict['HASH'], tmp_dict['APTIME'])
                    completed = db_handle.query(tmp_dict['HASH'])
                    if completed == 0:
                        logger.info('%s already downloaded.', tmp_dict['HASH'])
                        continue
                    try:
                        logger.debug('ACQUIRED BY EATER')
                        queue.put(tmp_dict)
                    except:
                        pass
                    finally:
                        logger.info('%s ADDED, QUEUE SIZE %s', tmp_dict['HASH'], self.queue.qsize())
                        if len(self.thread_list) == 0:
                            fetcher = Fetcher('URL doenloader', self.queue,  thread_list)
                            fetcher.setDaemon(True)
                            self.thread_list.append(fetcher)
                            logger.debug('Thread list contains: %s', thread_list)
                            fetcher.start()
                        else:
                            logger.debug('Pool of fetcher is full.')
        except KeyboardInterrupt:
            logger.debug('User aborted, but I will record recent downloads.')
            db_handle.disconnect()
            sys.exit(99)
        finally:
            logger.debug('Thread list contains: %s', thread_list)
            time.sleep(1)

    def run(self):
        self.url_eater(self.queue)


def create_fetcher_pool(queue, size):
    pool = []
    for _ in range(size):
        fetcher = Fetcher(queue)
        fetcher.setDaemon(True)
        pool.append(fetcher)
        fetcher.start()
    return pool


def start_with_gui():
    pass


if __name__ == '__main__':
    set_socks5_proxy()
    log_level = cfg_reader.get_cfg('log', 'level')
    logger.set_logger_level(log_level)
    thread_list = []
    img_queue = Queue.Queue()
    eater = Eater(img_queue, thread_list)
    eater.start()
