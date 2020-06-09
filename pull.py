#!/usr/bin/python3
# coding=utf-8

import requests
import sys
import time
import hashlib
import os
import json
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
import re
import logging

logging.basicConfig(level=logging.WARN)

# from termcolor import colored, cprint

__author__ = 'DeppWang (deppwxq@gmail.com)'
__github__ = 'https//github.com/DeppWang/youdaonote-pull'


def timestamp():
    return str(int(time.time() * 1000))


def is_json(my_json):
    try:
        json.loads(my_json)
    except ValueError as e:
        return False
    return True


def check_config(config_name) -> dict:
    with open(config_name, 'rb') as f:
        config_str = f.read().decode('utf-8')
        logging.info(config_str)

    try:
        # 将字符串转换为字典
        config_dict = eval(config_str)
    except SyntaxError:
        raise SyntaxError('请检查 config.json 格式是否为 utf-8 的 json！建议使用 Sublime 编辑 config.json')

    logging.info(config_dict.get('username', True))
    # 如果某个 key 不存在，抛出异常
    # 不存在 key，抛出 True
    try:
        config_dict['username']
        config_dict['password']
        config_dict['local_dir']
        config_dict['ydnote_dir']
        config_dict['smms_secret_token']
    except KeyError:
        raise KeyError('请检查 config.json 的 key 是否分别为 username, password, local_dir, ydnote_dir, smms_secret_token')

    logging.info(config_dict)
    if config_dict['username'] == '' or config_dict['password'] == '':
        raise ValueError('账号密码不能为空，请检查 config.json！')

    return config_dict


def covert_json_str_to_dict(file_name) -> dict:
    if not os.path.exists(file_name):
        logging.info('null')
        raise OSError

    # if not os.lstat(file_name):
    #     raise OSError

    with open(file_name, 'r', encoding='utf-8') as f:
        jsonStr = f.read()

    try:
        # 将字符串转换为字典
        logging.info(jsonStr)
        config_dict = eval(jsonStr)
    except SyntaxError:
        raise SyntaxError('转换「' + file_name + '」为字典出现错误')
    return config_dict


class LoginError(ValueError):
    pass


class YoudaoNoteSession(requests.Session):
    """ 继承于 requests.Session """

    def __init__(self):
        requests.Session.__init__(self)

        self.headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.84 Safari/537.36',
            'Accept': '*/*',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'https://note.youdao.com/signIn/index.html?&callback=https%3A%2F%2Fnote.youdao.com%2Fweb%2F&from=web'
        }

    def check_and_login(self, username, password):
        try:
            cookies_dict = covert_json_str_to_dict('cookies.json')
        except OSError or SyntaxError:
            cookies_dict = None

        # 如果有正常的 8 个 cookie，使用 cookie 登录
        if cookies_dict is not None and (len(cookies_dict['cookies']) == 8):
            root_id = self.cookies_login(cookies_dict['cookies'])
            logging.info(root_id)

            # 如果 Cookies 过期等原因导致 Cookies 登录失败，改用使用账号密码登录
            if is_json(root_id):
                root_id = self.login(username, password)
                print('本次使用账号密码登录，已将 Cookies 保存到 cookies.json 中，下次使用 Cookies 登录')
            else:
                print('本次使用 Cookies 登录')
                return root_id
        else:
            root_id = self.login(username, password)
            print('本次使用账号密码登录，已将 Cookies 保存到 cookies.json 中，下次使用 Cookies 登录')

        if is_json(root_id):
            parsed = json.loads(root_id)
            raise LoginError('请检查账号密码是否正确！也可能因操作频繁导致 ip 被封，请切换网络或等待一段时间后重试！',
                             json.dumps(parsed, indent=4, sort_keys=True))

        return root_id

    def login(self, username, password) -> str:
        """ 模拟用户操作，使用账号密码登录，并保存 Cookies """

        # 模拟打开首页
        self.get('https://note.youdao.com/web/')
        self.headers['Referer'] = 'https://note.youdao.com/web/'

        # 模拟跳转到登录页
        self.get('https://note.youdao.com/signIn/index.html?&callback=https%3A%2F%2Fnote.youdao.com%2Fweb%2F&from=web')
        self.headers[
            'Referer'] = 'https://note.youdao.com/signIn/index.html?&callback=https%3A%2F%2Fnote.youdao.com%2Fweb%2F&from=web'

        self.get('https://note.youdao.com/login/acc/pe/getsess?product=YNOTE&_=' + timestamp())
        self.get('https://note.youdao.com/auth/cq.json?app=web&_=' + timestamp())
        self.get('https://note.youdao.com/auth/urs/login.json?app=web&_=' + timestamp())

        data = {
            'username': username,
            'password': hashlib.md5(password.encode('utf-8')).hexdigest()
        }
        # print(hashlib.md5(password.encode('utf-8')).hexdigest())
        # 模拟登陆
        self.post(
            'https://note.youdao.com/login/acc/urs/verify/check?app=web&product=YNOTE&tp=urstoken&cf=6&fr=1&systemName=&deviceType=&ru=https%3A%2F%2Fnote.youdao.com%2FsignIn%2F%2FloginCallback.html&er=https%3A%2F%2Fnote.youdao.com%2FsignIn%2F%2FloginCallback.html&vcode=&systemName=&deviceType=&timestamp=' + timestamp(),
            data=data, allow_redirects=True)

        self.get('https://note.youdao.com/yws/mapi/user?method=get&multilevelEnable=true&_=' + timestamp())

        self.cstk = self.cookies.get('YNOTE_CSTK')

        self.save_cookies()

        return self.get_root_id()

    def save_cookies(self) -> None:
        """ 将 Cookies 保存到 cookies.json """

        cookies_dict = {}
        cookies = []

        # requesetCookieJar 相当于是一个 Map 对象
        RequestsCookieJar = self.cookies
        for cookie in RequestsCookieJar:
            cookieEles = [cookie.name, cookie.value, cookie.domain, cookie.path]
            cookies.append(cookieEles)

        cookies_dict['cookies'] = cookies

        with open('cookies.json', 'wb') as f:
            f.write(str(json.dumps(cookies_dict, indent=4, sort_keys=True)).encode())

    def cookies_login(self, cookies_dict) -> str:
        """ 使用 Cookies 登录 """

        requestsCookieJar = self.cookies
        for cookie in cookies_dict:
            requestsCookieJar.set(cookie[0], cookie[1], domain=cookie[2], path=cookie[3])

        self.cstk = cookies_dict[0][1]

        return self.get_root_id()

    def get_root_id(self) -> str:
        """ 获取有道云笔记 root_id
        root_id 始终不会改变？可保存？可能会改变，几率很小。可以保存，保存又会带来新的复杂度。只要登录后，获取一下也没有影响
        """

        data = {
            'path': '/',
            'entire': 'true',
            'purge': 'false',
            'cstk': self.cstk
        }
        response = self.post(
            'https://note.youdao.com/yws/api/personal/file?method=getByPath&keyfrom=web&cstk=%s' % self.cstk, data=data)
        json_obj = json.loads(response.content)
        try:
            return json_obj['fileEntry']['id']
        except:
            return response.content.decode('utf-8')

    def get_all(self, local_dir, ydnote_dir, smms_secret_token, root_id) -> None:
        """ 下载所有文件 """

        if local_dir == '':
            local_dir = os.path.join(os.getcwd(), 'youdaonote')

        # 如果指定的本地文件夹不存在，创建文件夹
        if not os.path.exists(local_dir):
            try:
                logging.info(local_dir)
                os.mkdir(local_dir)
            except Exception:
                raise Exception('请检查 「' + local_dir + '」 上层文件夹是否存在，并使用绝对路径！')

        # 有道云笔记指定导出文件夹名不为 '' 时，获取文件夹 id
        if ydnote_dir != '':
            root_id = self.get_dir_id(root_id, ydnote_dir)
            if root_id is None:
                raise ValueError('此文件夹 ' + ydnote_dir + ' 不是顶层文件夹，暂不能下载！')

        self.local_dir = local_dir
        logging.info(smms_secret_token)
        self.smms_secret_token = smms_secret_token
        self.get_file_recursively(root_id, local_dir)

    def get_dir_id(self, root_id, ydnote_dir) -> str:
        """ 获取有道云笔记指定文件夹 id，目前指定文件夹只能为顶层文件夹，如果要指定文件夹下面的文件夹，请自己改用递归实现 """

        url = 'https://note.youdao.com/yws/api/personal/file/%s?all=true&f=true&len=30&sort=1&isReverse=false&method=listPageByParentId&keyfrom=web&cstk=%s' % (
            root_id, self.cstk)
        response = self.get(url)
        json_obj = json.loads(response.content)
        for entry in json_obj['entries']:
            file_entry = entry['fileEntry']
            name = file_entry['name']
            if name == ydnote_dir:
                return file_entry['id']

    def get_file_recursively(self, id, local_dir) -> None:
        """ 递归遍历，找到文件夹下的所有文件 """

        url = 'https://note.youdao.com/yws/api/personal/file/%s?all=true&f=true&len=30&sort=1&isReverse=false&method=listPageByParentId&keyfrom=web&cstk=%s' % (
            id, self.cstk)
        lastId = None
        count = 0
        total = 1
        while count < total:
            if lastId is not None:
                url = url + '&lastId=%s' % lastId
                logging.info(url)
            response = self.get(url)
            # 如果 json_obj 不是 json，退出
            try:
                json_obj = json.loads(response.content)
            except ValueError:
                raise ValueError('有道云笔记修改了接口，此脚本暂时不能使用！')
            total = json_obj['count']
            for entry in json_obj['entries']:
                file_entry = entry['fileEntry']
                id = file_entry['id']
                name = file_entry['name']
                # 如果是目录，继续遍历目录下文件
                if file_entry['dir']:
                    sub_dir = os.path.join(local_dir, name)
                    if not os.path.exists(sub_dir):
                        os.mkdir(sub_dir)
                        logging.info(sub_dir, '不存在，新建')
                    self.get_file_recursively(id, sub_dir)
                else:
                    self.judge_add_or_update(id, name, local_dir, file_entry)

            count = count + 1
            lastId = id

    def judge_add_or_update(self, id, name, local_dir, file_entry) -> None:
        """ 判断是新增还是更新 """

        # 如果文件名是网址，避免 open() 函数失败（因为目录名错误），替换 /
        if name.startswith('https'):
            name = name.replace('/', '_')
            logging.info(name)

        youdao_file_suffix = os.path.splitext(name)[1]  # 笔记后缀
        local_file_path = os.path.join(local_dir, name)  # 用于将后缀 .note 转换为 .md
        original_file_path = os.path.join(local_dir, name)  # 保留本身后缀
        local_file_name = os.path.join(local_dir, os.path.splitext(name)[0])  # 没有后缀的本地文件
        tip = youdao_file_suffix
        # 本地 .note 文件均为 .md，使用 .md 后缀判断是否在本地存在
        if youdao_file_suffix == '.note':
            tip = '.md ，「云笔记原格式为 .note」'
            local_file_path = local_file_name + '.md'
        # 如果不存在，则更新
        if not os.path.exists(local_file_path):
            self.get_file(id, original_file_path, youdao_file_suffix)
            print('新增 %s%s' % (local_file_name, tip))
        # 如果已经存在，判断是否需要更新
        else:
            # 如果有道云笔记文件更新时间小于本地文件时间，说明没有更新。跳过本地更新步骤
            if file_entry['modifyTimeForSort'] < os.path.getmtime(local_file_path):
                # print('正在遍历，请稍后 ...，最好一行动态变化')
                return

            print('-----------------------------')
            print('local file modifyTime: ' + str(int(os.path.getmtime(local_file_path))))
            print('youdao file modifyTime: ' + str(file_entry['modifyTimeForSort']))
            self.get_file(id, original_file_path, youdao_file_suffix)
            print('更新 %s%s' % (local_file_name, tip))

    def get_file(self, file_id, file_path, youdao_file_suffix) -> None:
        """ 下载文件。先不管什么文件，均下载。如果是 .note 类型，转换为 Markdown """

        data = {
            'fileId': file_id,
            'version': -1,
            'convert': 'true',
            'editorType': 1,
            'cstk': self.cstk
        }
        url = 'https://note.youdao.com/yws/api/personal/sync?method=download&keyfrom=web&cstk=%s' % self.cstk
        response = self.post(url, data=data)

        if youdao_file_suffix == '.md':
            content = response.content.decode('utf-8')

            content = self.covert_markdown_file_image_url(content, file_path)
            try:
                with open(file_path, 'wb') as f:
                    f.write(content.encode())
            except UnicodeEncodeError as err:
                print(format(err))
            return

        with open(file_path, 'wb') as f:
            f.write(response.content)  # response.content 本身就是字节类型

        # 权限问题，导致下载内容为接口错误提醒值。contentStr = response.content.decode('utf-8')

        # 如果文件是 .note 类型，将其转换为 MarkDown 类型
        if youdao_file_suffix == '.note':
            try:
                self.covert_xml_to_markdown(file_path)
            except FileNotFoundError and ET.ParseError:
                print(file_path + ' 转换失败！请查看文件是否为 xml 格式或是否空！')

    def covert_xml_to_markdown(self, file_path) -> None:
        """ 转换 xml 为 Markdown """

        # 如果文件为 null，结束
        if os.path.getsize(file_path) == 0:
            base = os.path.splitext(file_path)[0]
            os.rename(file_path, base + '.md')
            return
        # 使用 xml.etree.ElementTree 将 xml 文件转换为多维数组
        tree = ET.parse(file_path)
        root = tree.getroot()
        flag = 0  # 用于输出转换提示
        nl = '\r\n'  # Windows 系统换行符为 \r\n
        new_content = f''  # f-string 多行字符串
        # 得到多维数组中的文本，因为是数组，不是对象，所以只能遍历
        for child in root[1]:
            if 'para' in child.tag:
                for child2 in child:
                    if 'text' in child2.tag:
                        # 如果等于 None，字符串加 None 将报错
                        if child2.text is None:
                            child2.text = ''
                        new_content += child2.text + f'{nl}{nl}'
                        break

            elif 'image' in child.tag:
                if flag == 0:
                    self.print_ydnote_file_name(file_path)

                for child2 in child:
                    if 'source' in child2.tag:
                        image_url = ''
                        if child2.text is not None:
                            image_url = f'![%s](' + self.get_new_down_or_upload_url(child2.text) + f'){nl}{nl}'
                            flag += 1

                    elif 'text' in child2.tag:
                        image_name = ''
                        if child2.text is not None:
                            image_name = child2.text
                        new_content += image_url % (image_name)
                        break

            elif 'code' in child.tag:
                for child2 in child:
                    if 'text' in child2.tag:
                        code = f'```%s{nl}' + child2.text + f'{nl}```{nl}{nl}'
                    elif 'language' in child2.tag:
                        language = ''
                        if language is not None:
                            language = child2.text
                        new_content += code % (language)
                        break

            elif 'table' in child.tag:
                for child2 in child:
                    if 'content' in child2.tag:
                        new_content += f'```{nl}原来为 table，需要自己转换一下{nl}' + child2.text + f'{nl}```{nl}{nl}'

        base = os.path.splitext(file_path)[0]
        new_file_path = base + '.md'
        os.rename(file_path, new_file_path)
        with open(new_file_path, 'wb') as f:
            f.write(new_content.encode())

    def covert_markdown_file_image_url(self, content, file_path) -> str:
        """ 将 Markdown 中的有道云图床图片转换为 sm.ms 图床 """

        reg = r'!\[.*?\]\((.*?note\.youdao\.com.*?)\)'
        p = re.compile(reg)
        urls = p.findall(content)
        if len(urls) > 0:
            self.print_ydnote_file_name(file_path)
        for url in urls:
            newUrl = self.get_new_down_or_upload_url(url)
            content = content.replace(url, newUrl)
        return content

    def print_ydnote_file_name(self, file_path):

        ydnote_dirName = file_path.replace(self.local_dir, '')
        print('正在转换有道云笔记「' + ydnote_dirName + '」中的有道云图床图片链接...')

    def get_new_down_or_upload_url(self, url) -> str:
        """ 根据是否存在 smms_secret_token 判断是否需要上传到 sm.ms """

        if 'note.youdao.com' not in url:
            return url
        if self.smms_secret_token == '':
            return self.download_image(url)
        newUrl = self.upload_to_smms(url, self.smms_secret_token)
        if newUrl != url:
            return newUrl
        return self.download_image(url)

    def download_image(self, url) -> str:
        """ 如果 smms_secret_token 为 null，将其下载到本地，返回相对 url """

        response = self.get(url)
        if response.status_code != 200:
            self.print_download_yd_image_error(url)
            return url

        local_image_dir = os.path.join(self.local_dir, 'youdaonote-images')
        if not os.path.exists(local_image_dir):
            os.mkdir(local_image_dir)
        image_name = os.path.basename(urlparse(url).path)
        image_path = os.path.join(local_image_dir, image_name + '.' + response.headers['Content-Type'].split('/')[1])
        try:
            with open(image_path, 'wb') as f:
                f.write(response.content)  # response.content 本身就为字节类型
            print('已将图片 ' + url + ' 转换为 ' + image_path)
        except:
            print(url + ' 图片有误！')
            return url
        return image_path

    def upload_to_smms(self, old_url, smms_secret_token) -> str:

        try:
            smfile = self.get(old_url).content
        except:
            self.print_download_yd_image_error(old_url)
            return old_url

        smms_upload_api = 'https://sm.ms/api/v2/upload'
        logging.info(smms_secret_token)
        headers = {'Authorization': smms_secret_token}
        files = {'smfile': smfile}

        try:
            res = requests.post(smms_upload_api, headers=headers, files=files)
            logging.info(res.json())
        except requests.exceptions.ProxyError as err:
            print('上传 ' + old_url + '到 SM.MS 失败！将下载图片到本地')
            print(format(err))
            return old_url

        res_json = res.json()

        url = old_url
        if res_json['success'] is False:
            if res_json['code'] == 'image_repeated':
                url = res_json['images']
            elif res_json['code'] == 'flood':
                print('每小时只能上传 100 张图片，' + old_url + ' 未转换')
                return old_url
            else:
                print(
                    '上传 ' + old_url + ' 到 SM.MS 失败，请检查图片 url 或 smms_secret_token（' + smms_secret_token + '）是否正确！将下载到本地。')
                return old_url
        else:
            url = res_json['data']['url']
        print('已将图片 ' + old_url + ' 转换为 ' + url)
        return url

    def print_download_yd_image_error(self, url):
        print('下载 ' + url + ' 失败！浏览器登录有道云笔记后，查看图片是否能正常显示（验证登录才能显示）')


if __name__ == '__main__':
    start_time = int(time.time())

    try:
        config_dict = check_config('config.json')
    except Exception as err:
        print(format(err))
        sys.exit(1)

    session = YoudaoNoteSession()

    try:
        root_id = session.check_and_login(config_dict['username'], config_dict['password'])
    except LoginError as err:
        print(format(err.args[0]))
        print(format(err.args[1]))
        print('已终止执行')
        sys.exit(1)

    print('正在 pull，请稍后 ...')
    try:
        session.get_all(config_dict['local_dir'], config_dict['ydnote_dir'], config_dict['smms_secret_token'], root_id)
    except Exception as err:
        print(format(err))
        print('已终止执行')
        sys.exit(1)

    end_time = int(time.time())
    print('运行完成！耗时 ' + str(end_time - start_time) + ' 秒')
