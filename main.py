import base64
import hashlib
import random
import re
import sys
import time

import pyDes
import requests
from lxml import etree


class Config:
    domain = '你學校的WMPro網址'


class WMPro(Config):
    def __init__(self):
        self.session = requests.session()
        self.session.headers.update(
            {'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.113 Safari/537.36'})
        self.data = {}

    def get_login_key(self):
        a = self.session.get(
            f'{self.domain}/mooc/login.php').text
        parser = etree.HTML(a)
        login_key = parser.xpath('//input[@name="login_key"]')[0].get('value')
        return login_key

    def get_encrypt_pwd(self, passwd):
        m = hashlib.md5()
        m.update(passwd.encode('utf-8'))
        cypkey = m.hexdigest()[0:4] + self.login_key[0:4]
        cypkey = bytes(cypkey, encoding='utf-8')
        self.passwd = base64.b64encode(passwd.encode('utf-8'))
        self.encrypt = base64.b64encode(
            pyDes.des(cypkey, padmode=pyDes.PAD_PKCS5).encrypt(passwd))

    def check_login(self):
        a = self.session.get(
            f'{self.domain}/learn/personal/info.php').text
        parser = etree.HTML(a)
        if parser.xpath('//div[@class="id"]')[0].text != 'guest':
            print('登入成功，目前的身分是{}'.format(
                parser.xpath('//div[@class="id"]')[0].text))
        else:
            print('登入失敗')
            sys.exit(0)

    def login(self, account, passwd):
        self.login_key = self.get_login_key()
        self.get_encrypt_pwd(passwd)
        data = {
            'reurl': '',
            'login_key': self.login_key,
            'encrypt_pwd': self.encrypt,
            'passwd': self.passwd,
            'username': account,
            'password': re.sub(r'(.)', '*', passwd)
        }
        self.session.post(f'{self.domain}/login.php', data=data)
        self.check_login()

    def test(self):
        return self.session

    def get_course(self):
        a = self.session.get(
            f'{self.domain}/learn/mycourse/index.php').text
        parser = etree.HTML(a)
        course = parser.xpath(
            '//table[@class="table subject"]/tr/td[@class="t9"]/div/a')
        for _ in course:
            print(_.text)
        num = int(input('請輸入數字：'))
        id = parser.xpath(
            '//table[@class="table subject"]/tr/td[@class="t9"]/div/a')[num].get('onclick')
        id = re.findall(r'(\d+)', id)[0]
        self.go_course(course_id=id)

    def go_course(self, course_id):
        data = f'<manifest><ticket/><course_id>{course_id}</course_id><env/></manifest>'
        data2 = {
            'action': 'getCourseInfo',
            'cid': course_id
        }

        self.session.post(
            f'{self.domain}/learn/goto_course.php', data=data.encode('utf-8'))
        self.session.post(
            f'{self.domain}/mooc/controllers/course_ajax.php', data=data2)

    def get_servertime(self):
        a = self.session.get(
            f'{self.domain}/learn/path/getServerTime.php').text
        self.servertime = etree.HTML(a).xpath('//root')[0].get('server_time')

    def get_course_data(self):
        html = self.session.get(
            f'{self.domain}/learn/path/SCORM_loadCA.php').text
        a = etree.HTML(html)
        self.data['href'] = random.choice(
            a.xpath('//manifest/resources/resource')).get('href')

    def get_ajax_data(self):
        html = self.session.get(
            f'{self.domain}/learn/path/pathtree.php').text
        a = etree.HTML(html)
        self.data['actid'] = re.findall(
            r"globalCurrentActivity.*'(.*)'", html)[0]
        self.data['cid'] = re.findall(r"cid.*'(.*)'", html)[0]
        self.data['pticket'] = re.findall(r"pTicket.*'(.*)'", html)[0]
        self.data['begin_time'] = a.xpath(
            '//input[@name="begin_time"]')[0].get('value')
        self.data['course_id'] = a.xpath(
            '//input[@name="course_id"]')[0].get('value')
        self.data['read_key'] = a.xpath(
            '//input[@name="read_key"]')[0].get('value')

    def fetch_source(self):
        data = {
            'is_player': 'false',
            'href': '@' + self.data['href'],
            'prev_href': '',
            'prev_node_id': '',
            'prev_node_title': '',
            'begin_time': self.data['begin_time'],
            'course_id': self.data['course_id'],
            'read_key': self.data['read_key'],
            'co_node_type': ''
        }
        a = self.session.post(
            f'{self.domain}/learn/path/SCORM_fetchResource.php', data=data)
        self.data['title'] = re.findall(
            r'\?id=(.*)\"', a.text)[0].split('.')[0]

    def post_reading(self):
        data = {
            'action': 'setReading',
            'ticket': self.data['pticket'],
            'type': 'start',
            'period': '0',
            'enCid': self.data['course_id'],
            'bt': self.data['begin_time'],
            'title': self.data['title'],
            'enUrl': self.data['href'],
            'actid': self.data['actid']
        }

        a = self.session.post(
            f'{self.domain}/mooc/controllers/course_ajax.php', data=data)
        # print(a.json())
        if a.json()['msg'] == 'success':
            print('開始學習')

    def post_keepreading(self):
        data = '<manifest><ticket/><erase>0</erase></manifest>'
        a = self.session.post(
            f'{self.domain}/online/session.php', data=data.encode('utf-8'))
        # print(a.text)
        data = {
            'action': 'setReading',
            'ticket': self.data['pticket'],
            'type': 'end',
            'period': '60000',
            'enCid': self.data['course_id'],
            'bt': self.data['begin_time'],
            'title': self.data['title'],
            'enUrl': self.data['href'],
            'actid': self.data['actid']
        }

        a = self.session.post(
            f'{self.domain}/mooc/controllers/course_ajax.php', data=data)
        # print(a.json())
        if a.json()['msg'] == 'success':
            print('成功向伺服器傳送閱讀資料')


if __name__ == "__main__":
    wmpro = WMPro()
    wmpro.login('帳號', '密碼')
    wmpro.get_course()
    wmpro.get_course_data()
    wmpro.get_ajax_data()
    wmpro.fetch_source()
    wmpro.post_reading()
    while True:
        time.sleep(60)
        wmpro.post_keepreading()
