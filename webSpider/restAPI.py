# coding=utf-8
import datetime, time
import os, sys
import json
import copy
from io import StringIO
import bson.binary
import traceback
import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from lxml.cssselect import CSSSelector
import subprocess
from pprint import pprint
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from rest_framework import filters, pagination, serializers
from rest_framework.generics import ListAPIView
from rest_framework.views import APIView
from rest_framework.response import Response as restResponse
from rest_framework import status

from .dbDriver import MongoDriver, RedisDriver
from lxml import etree

from .setting import PAGE_SIZE, TEST_SERVER, STATIC_TEMP_DIR, XGSJ_DOMAIN
from .extra_module.json_to_config import JsonToConfig

MDB = MongoDriver()
RDB = RedisDriver()


################# 获取星光数据的参数 ########################
def getXGJSParameterAPI(request):
    xgsjTaskId = request.GET.get('xgsjTaskId')
    url = XGSJ_DOMAIN + '/crawler/' + xgsjTaskId
    r = requests.get(url=url, data={})
    data = json.loads(r.text)

    output = JsonResponse({
        'start_url': data['url'],
        'user_id': 'admin',
        'interval_time': data['interval_time'],
        'clock_time': data['clock_time'],
        'last_modify_time': data['last_modify_time'],
        'dedup_expireat': data['dedup_expireat']
    })
    return HttpResponse(output, content_type='application/json; charset=UTF-8')


def saveXGSJAPI(request):
    xgsjTaskId = request.GET.get('xgsjTaskId')
    url = XGSJ_DOMAIN + '/schema/save.html?id=' + xgsjTaskId
    r = requests.get(url=url, data={})
    output = JsonResponse({
        'status_code': r.status_code
    })
    return HttpResponse(output, content_type='application/json; charset=UTF-8')


def gotoXGSJAPI(request):
    url = XGSJ_DOMAIN + '/crawler/custom.html'
    output = JsonResponse({
        'url': url
    })
    return HttpResponse(output, content_type='application/json; charset=UTF-8')


################# 爬虫后台测试 ########################
def startTestAPI(request):
    proxy = False if request.GET.get('proxy') == 'false' else True
    url = request.GET.get('url')
    func_name = request.GET.get('func_name')
    code = request.GET.get('code')
    r = requests.post(  # POST
        url=TEST_SERVER + '/webspider/run_code',
        data={
            'type': 2,  # 单步调试
            'proxy': False if proxy == 'false' else True,
            'url': url,  # 测试url单步调试使用,第一次单步调试不需要
            'func_name': func_name,  # 单步测试函数名称 默认测试get_start_urls函数 其他按照上次返回值中的函数名确定或人为指定函数
            'code': code
        }
    )
    res = r.text
    output = JsonResponse({
        'ret': res
    })
    return HttpResponse(output, content_type='application/json; charset=UTF-8')


def getTestResultAPI(request):
    uuid = request.GET.get('uuid')
    r = requests.get(
        url=TEST_SERVER + '/webspider/code_result?code=' + uuid,
        data={
        }
    )
    res = eval(r.text)
    res['result'] = eval(res['result'])
    output = JsonResponse({
        'ret': res
    })
    return HttpResponse(output, content_type='application/json; charset=UTF-8')


def checkServiceActiveAPI(request):
    r = requests.get(
        url=TEST_SERVER + '/webspider/alive',
        timeout=3000,
        data={}
    )
    res = eval(r.content.decode('utf-8'))
    output = JsonResponse({
        'ret': res
    })
    return HttpResponse(output, content_type='application/json; charset=UTF-8')


def stopTestAPI(request):
    uuid = request.GET.get('uuid')
    r = requests.get(
        url=TEST_SERVER + '/webspider/kill',
        data={
            'code': uuid
        }
    )
    res = r.text
    output = JsonResponse({
        'ret': res
    })
    return HttpResponse(output, content_type='application/json; charset=UTF-8')


def getTaskStatusAPI(request):
    res = ""
    uuid = request.GET.get('uuid')
    r = requests.get(
        url=TEST_SERVER + '/webspider/status?code=' + uuid,
        data={
        }
    )
    if r.content:
        res = eval(r.content.decode('utf-8'))

    output = JsonResponse({
        'ret': res
    })
    return HttpResponse(output, content_type='application/json; charset=UTF-8')


################# 运行模拟脚本 ########################
def runSimulationScriptAPI(request):
    user_id = request.GET.get('user_id')
    simulatorShow = request.GET.get('simulatorShow')
    start_url = request.GET.get('start_url')
    search_text = request.GET.get('search_text')
    search_btn_selector = request.GET.get('search_btn_selector')
    search_selector = request.GET.get('search_selector')
    result_filter = request.GET.get('result_filter')

    j = {
        'user_id': user_id,
        'simulatorShow': simulatorShow,
        'start_url': start_url,
        'search_text': search_text,
        'search_btn_selector': search_btn_selector,
        'search_selector': search_selector,
        'result_filter': result_filter,
    }

    fs = open('D:\\workspace\\eWorks\\eSpider\\simulator.json', 'w+')
    fs.write(json.dumps(j))
    fs.close()

    cmd = "C:\\nodejs\\node.exe D:\\workspace\\eWorks\\eSpider\\simulator.js"
    sub = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    sub.wait()
    # print(sub.read())
    output = JsonResponse({
        'ret': "ok"
    })
    return HttpResponse(output, content_type='application/json; charset=UTF-8')


def getSimulationResultAPI(request):
    user_id = request.GET.get('user_id')
    start_url = request.GET.get('start_url')
    info = {
        'user_id': user_id,
        'start_url': start_url
    }

    hubs = MDB.get_simulator_info(info)
    output = JsonResponse({
        'hubs': hubs
    })
    return HttpResponse(output, content_type='application/json; charset=UTF-8')


# 目前后台框架支持，所以不需要。
def getNextPage(site_url, url, xpath, page_num):
    hubs = []
    header = {
        "User-Agent": "Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/49.0.2623.13 Safari/537.36"
    }
    rs = requests.Session()
    response = rs.get(url, headers=header)
    htmlparser = etree.HTMLParser()
    tree = etree.parse(response, htmlparser)
    href = tree.xpath(xpath + '//@href')
    # (scheme, netloc, path, params, query, fragment) = urllib.parse.urlparse(url)
    # urllib.parse.urlunparse((scheme, netloc, '', '', '', ''))

    return hubs


import w3lib.encoding


########### 页面下载加工 ###########
def _get_filename(path):
    return path[path.rfind('/') + 1:path.rfind('?')] if path.rfind('?') != -1 else path[path.rfind('/') + 1:]


from backend.settings import TEMP_DIRS


def _downloader(link, part, timeout):
    file_name = _get_filename(link)
    path = os.path.join(os.path.sep, TEMP_DIRS, part)
    full_path = os.path.join(path, file_name)
    if not os.path.exists(full_path):
        r = requests.get(link, timeout=timeout)
        if r.status_code == 200:
            if not os.path.exists(path): os.makedirs(path)
            open(full_path, 'wb').write(r.content)

    return


def _getPrettifyHtml_cache(url, load_js, part):
    header = {
        "User-Agent": "Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/49.0.2623.13 Safari/537.36"
    }
    rs = requests.Session()
    response = rs.get(url, headers=header)

    m = re.search('''URL=(.*?)"''', response.text)
    if m:
        redirect = m.group(1)
        url = urljoin(url, redirect)
        response = rs.get(url, headers=header)

    response.encoding = w3lib.encoding.html_body_declared_encoding(response.content)

    try:
        soup = BeautifulSoup(response.text, 'lxml')

        for item in ['a', 'link']:
            elements = soup.find_all(item)
            for element in elements:
                if 'href' in element.attrs:
                    href = element.attrs['href']
                    if href[:4] != "http" and href[:2] != "//":
                        element.attrs['href'] = urljoin(url, href)

                    if href[:2] == "//":
                        element.attrs['href'] = 'http:' + href

        for item in ['iframe', 'embed']:
            elements = soup.find_all(item)
            for element in elements:
                if 'src' in element.attrs:
                    src = element.attrs['src']
                    if src[:4] != "http" and src[:2] != "//":
                        element.attrs['src'] = urljoin(url, src)

        for item in ['object']:
            elements = soup.find_all(item)
            for element in elements:
                if 'data' in element.attrs:
                    href = element.attrs['data']
                    if href[:4] != "http" and href[:2] != "//":
                        element.attrs['data'] = urljoin(url, href)

        # cache all source
        for item in ['img', 'script']:  # img@src, js@src
            elements = soup.find_all(item)
            for element in elements:
                if 'src' in element.attrs:
                    src = element.attrs['src']
                    if src[:4] == "http" or src[:2] == "//":  # 全路径
                        if src[:2] == "//":
                            src = 'http:' + src
                    else:  # 相对路径
                        src = urljoin(url, src)
                    _downloader(src, part, 60)
                    element.attrs['src'] = STATIC_TEMP_DIR + '/static/webSpider/temp/' + part + '/' + \
                                           _get_filename(src)

        # cache all source
        for item in ['link']:  # css@href
            elements = soup.find_all(item)
            for element in elements:
                if 'href' in element.attrs:
                    href = element.attrs['href']
                    if href[:4] == "http" or href[:2] == "//":  # 全路径
                        if href[:2] == "//":
                            href = 'http:' + href
                    else:  # 相对路径
                        href = urljoin(url, href)
                    _downloader(href, part, 180)
                    element.attrs['href'] = STATIC_TEMP_DIR + '/static/webSpider/temp/' + part + '/' + \
                                            _get_filename(href)

        if load_js == 'false':
            [j.extract() for j in soup.find_all('script')]

        for item in soup.find_all(onmouseover=True):
            del item['onmouseover']
            del item['onmouseout']

        # onmouseover="this.className='mouseover'"
        text = soup.prettify()
        title = soup.title.string if soup.title else ""
    except Exception:
        text = ""
        title = "error"
        traceback.format_exc()

    return text, response.encoding, title


def _getPrettifyHtml(url, load_js, part):
    title = '无法加载当前网页'
    encoding = 'utf-8'
    header = {
        "User-Agent": "Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/49.0.2623.13 Safari/537.36"
    }
    try:
        rs = requests.Session()
        response = rs.get(url, headers=header)
        # <META HTTP-EQUIV="REFRESH" CONTENT="0; URL=html/2017-08/13/node_311.htm">
        m = re.search('''URL=(.*?)"''', response.text)
        if m:
            redirect = m.group(1)
            url = urljoin(url, redirect)
            response = rs.get(url, headers=header)

        response.encoding = w3lib.encoding.html_body_declared_encoding(response.content)
        soup = BeautifulSoup(response.text, 'lxml')

        for item in ['a', 'link']:
            elements = soup.find_all(item)
            for element in elements:
                if 'href' in element.attrs:
                    href = element.attrs['href']
                    if href[:4] != "http" and href[:2] != "//":
                        element.attrs['href'] = urljoin(url, href)

                    if href[:2] == "//":
                        element.attrs['href'] = 'http:' + href

        for item in ['img', 'iframe', 'embed', 'script']:
            elements = soup.find_all(item)
            for element in elements:
                if 'src' in element.attrs:
                    src = element.attrs['src']
                    if src[:4] != "http" and src[:2] != "//":
                        element.attrs['src'] = urljoin(url, src)

        for item in ['object']:
            elements = soup.find_all(item)
            for element in elements:
                if 'data' in element.attrs:
                    href = element.attrs['data']
                    if href[:4] != "http" and href[:2] != "//":
                        element.attrs['data'] = urljoin(url, href)

        if load_js == 'false':
            [j.extract() for j in soup.find_all('script')]

        for item in soup.find_all(onmouseover=True):
            del item['onmouseover']
            del item['onmouseout']

        text = soup.prettify()
        encoding = response.encoding
        title = soup.title.string if soup.title else ""
    except requests.exceptions.ConnectionError:
        text = '<h1 align="center" style="margin-top:300px;">无法连接当前url：' + url + '</h1>'
    except requests.exceptions.TooManyRedirects:
        text = '<h1 align="center" style="margin-top:300px;">超过请求次数.</h1>'
    except Exception as e:
        text = '<h1 align="center" style="margin-top:300px;">' + str(e) + '</h1>'

    return text, encoding, title


def getLoadJSAPI(request):
    hub_detail = request.GET.get('hub_detail')
    taskId = int(request.GET.get('taskId'))
    level = request.GET.get('level')

    isLoadJS = False
    if hub_detail == 'hub':
        info = MDB.get_hub_xpath_info(taskId, int(level))
    else:
        info = MDB.get_detail_xpath_info(taskId)

    if info and 'isLoadJS' in info:
        isLoadJS = info['isLoadJS']

    output = JsonResponse({
        'isLoadJS': isLoadJS
    })

    return HttpResponse(output, content_type='application/json; charset=UTF-8')


def getHtmlAPI(request):
    # //www.chinanews.com/gn/2017/06-20/8255459.shtml 使用 // 时，自动匹配http https
    url = request.GET.get('url')  # 列表和详情通用，使用url参数
    load_js = request.GET.get('load_js')
    taskId = request.GET.get('taskId')
    type = request.GET.get('type')
    level = request.GET.get('level')
    # part = taskId + '/' + type + '/' + level + '/'
    part = taskId
    if url[:2] == '//':
        url = 'http:' + url

    # encoding = request.GET.get('encoding')
    text, encoding, title = _getPrettifyHtml(url, load_js, part)

    output = JsonResponse({
        'encoding': encoding,
        'html': text,
        'title': title
    })

    return HttpResponse(output, content_type='application/json; charset=UTF-8')


########### 导航，节点结构 ###########
def getHubUrlAPI(request):
    taskId = int(request.GET.get('taskId'))
    level = int(request.GET.get('level'))
    hub_url = MDB.get_hub_url_by_level(taskId, level)
    output = JsonResponse({
        'hub_url': hub_url
    })
    return HttpResponse(output, content_type='application/json; charset=UTF-8')


def getNavInfoAPI(request):
    taskId = int(request.GET.get('taskId'))  # 列表页查询
    cnt, hasDetail = MDB.get_navInfo(taskId)
    output = JsonResponse({
        'levels_cnt': cnt,
        'hasDetail': hasDetail
    })
    return HttpResponse(output, content_type='application/json; charset=UTF-8')


########### 生成代码 ###########
def _makeJson2Code(webSpider_json):
    result = 'json为空！'
    ret = 'error'

    if webSpider_json:
        try:
            webSpider_args = webSpider_json
            try:
                code_obj = JsonToConfig(config=webSpider_args)
                result = code_obj.create_config()
                ret = 'ok'
            except Exception:
                result = '代码生成错误:' + traceback.format_exc()

            return ret, result

        except Exception:
            result = 'json加载错误:' + traceback.format_exc()

    return ret, result


def _checkNodeListIsSingle(node_list):
    if len(node_list) == 1 and node_list[0]['select_mode'] == 'single':
        return True

    return False


def makeJsonAndCodeAPI(request):
    taskId = int(request.GET.get('taskId'))

    node_list = MDB.get_nodes_list(taskId)
    is_one_level_single = _checkNodeListIsSingle(node_list)
    if not is_one_level_single:
        spider_json, schema_info = MDB.nodesXPath2Json(taskId)
        json_copy = copy.deepcopy(spider_json)  # 防止修改json detail的encoding
        spider_code_ret, spider_code = _makeJson2Code(json_copy)
        MDB.save_spider_json_code(taskId, spider_json, spider_code)
    else:
        schema_info = dict()
        schema_info['id'] = ''
        schema_info['code'] = ''
        schema_info['message'] = ''
        spider_json = ''
        spider_code_ret = ''
        spider_code = ''

    output = JsonResponse({
        'node_list_is_one_single': is_one_level_single,
        'node_list': node_list, 'cnt': len(node_list),
        'schema_id': schema_info['id'], 'schema_code': schema_info['code'], 'schema_msg': schema_info['message'],
        'spider_json': spider_json,
        'spider_code_ret': spider_code_ret, 'spider_code': spider_code,
    })
    return HttpResponse(output, content_type='application/json; charset=UTF-8')


########### 对生成代码的测试 ###########
def getTaskCodeAPI(request):
    taskId = int(request.GET.get('taskId'))
    code = MDB.get_task_code(taskId)
    output = JsonResponse({
        'code': code
    })
    return HttpResponse(output, content_type='application/json; charset=UTF-8')


########### 任务控制 ###########
def addTaskInfoAPI(request):
    xgsjTaskId = request.POST.get('xgsjTaskId')
    start_url = request.POST.get('start_url')
    user_id = request.POST.get('user_id')
    interval_time = int(request.POST.get('interval_time', '0'))
    clock_time = request.POST.get('clock_time', '')
    last_modify_time = int(request.POST.get('last_modify_time', '0'))
    dedup_expireat = int(request.POST.get('dedup_expireat', '0'))
    config_status = int(request.POST.get('config_status', '-1'))
    # 初始化 task
    taskId = MDB.init_task(xgsjTaskId=xgsjTaskId,
                           start_url=start_url,
                           user_id=user_id,
                           interval_time=interval_time,
                           clock_time=clock_time,
                           last_modify_time=last_modify_time,
                           dedup_expireat=dedup_expireat,
                           config_status=config_status)  # 停用0  启用1 不变-1

    # 创建编辑 level为0的 hub_xpath
    hub_info = {
        'taskId': taskId,
        'user_id': user_id,
        'start_url': start_url,
        'level': 0,
        'hub_url': start_url,
    }
    MDB.set_hub_xpath_info(hub_info)

    output = JsonResponse({
        'taskId': taskId  # xgsjTaskId为空时，taskId返回-1
    })
    return HttpResponse(output, content_type='application/json; charset=UTF-8')


def startTaskAPI(request):
    ret = 0
    msg = '启动失败或未生成代码。'

    xgsjTaskId = request.GET.get('xgsjTaskId')
    if xgsjTaskId:
        taskId = MDB.init_task(xgsjTaskId=xgsjTaskId,
                               start_url='',
                               user_id='',
                               interval_time=0,
                               clock_time='',
                               last_modify_time=0,
                               dedup_expireat=0,
                               config_status=1)  # 停用0  启用 1
    else:
        taskId = int(request.GET.get('taskId'))

    if taskId != -1:
        entry_info = MDB.get_entry_info(taskId)
        intervaltime = int(request.GET.get('intervaltime', '0'))
        clock_time = request.GET.get('clock_time', '')
        last_modify_time = int(request.GET.get('last_modify_time', '0'))
        dedup_expireat = int(request.GET.get('dedup_expireat')) \
            if request.GET.get('dedup_expireat') else 30 * 24 * 60 * 60 * 1000 + last_modify_time  # 30days(ms)

        task_info = {
            'config_id': taskId,
            'intervaltime': intervaltime,
            'clock_time': clock_time,
            'last_modify_time': last_modify_time,
            'dedup_expireat': dedup_expireat
        }

        if 'spider_code' in entry_info:
            RDB.set_config_info(task_info)
            RDB.set_config_content(taskId, entry_info['spider_code'])
            RDB.start_task(taskId)

            ret = 1
            msg = '启动成功。'

    output = JsonResponse({
        'ret': ret,
        'msg': msg
    })
    return HttpResponse(output, content_type='application/json; charset=UTF-8')


def stopTaskAPI(request):
    ret = 0
    msg = '停止失败。'

    xgsjTaskId = request.GET.get('xgsjTaskId')
    if xgsjTaskId:
        taskId = MDB.init_task(xgsjTaskId=xgsjTaskId,
                               start_url='',
                               user_id='',
                               interval_time=0,
                               clock_time='',
                               last_modify_time=0,
                               dedup_expireat=0,
                               config_status=0)  # 停用0  启用 1
    else:
        taskId = int(request.GET.get('taskId'))

    if taskId != -1:
        RDB.stop_task(taskId)
        ret = 1
        msg = '停止成功。'

    output = JsonResponse({
        'ret': ret,
        'msg': msg
    })
    return HttpResponse(output, content_type='application/json; charset=UTF-8')


def removeTaskAPI(request):
    ret = 0
    msg = '删除失败。'

    xgsjTaskId = int(request.GET.get('xgsjTaskId'))
    if xgsjTaskId:
        taskId = MDB.init_task(xgsjTaskId=xgsjTaskId,
                               start_url='',
                               user_id='',
                               interval_time=0,
                               clock_time='',
                               last_modify_time=0,
                               dedup_expireat=0,
                               config_status=0)  # 停用0  启用 1
    else:
        taskId = int(request.GET.get('taskId'))

    if taskId != -1:
        RDB.remove_task(taskId)
        ret = 1
        msg = '删除成功。'

    output = JsonResponse({
        'ret': ret,
        'msg': msg
    })
    return HttpResponse(output, content_type='application/json; charset=UTF-8')


########### 再现XPATH选择 ###########
def restoreHubsAPI(request):
    taskId = int(request.GET.get('taskId'))
    level = int(request.GET.get('level'))

    info = MDB.get_node_selector(taskId, level)
    output = JsonResponse({
        'ret': info
    })
    return HttpResponse(output, content_type='application/json; charset=UTF-8')


def restoreDetailAPI(request):
    taskId = int(request.GET.get('taskId'))
    info = MDB.get_detail_selector(taskId)
    output = JsonResponse({
        'ret': info
    })
    return HttpResponse(output, content_type='application/json; charset=UTF-8')


########### 主页面翻页 ###########
def getEntryPaginatorAPI(request):
    user_id = request.GET.get('user_id', '')
    search_url = request.GET.get('search_url')
    page_num = int(request.GET.get('page', 1))

    search_cnt = MDB.get_entry_search_cnt(user_id, search_url)
    paginator = Paginator(range(search_cnt), PAGE_SIZE)
    index = paginator.page(page_num)
    ret = {'search_cnt': search_cnt,
           'current_page': index.number,
           'total_pages': paginator.num_pages,
           'has_prev': index.has_previous(),
           'has_next': index.has_next(),
           }
    output = JsonResponse(ret)
    return HttpResponse(output, content_type='application/json; charset=UTF-8')


class MainViewAPI(APIView):
    def _get_data(self, args):
        info_type = args.get('info_type')
        user_id = args.get('user_id', '')
        search_url = args.get('search_url', '')
        taskId = int(args.get('taskId')) if args.get('taskId') else -1

        page = args.get('page', 1)

        if info_type == "list":
            info = MDB.get_entry_list(user_id, search_url, (int(page) - 1) * PAGE_SIZE, PAGE_SIZE)
        else:
            info = MDB.get_entry_info(taskId)

        return info

    def _set_data(self, args):
        ret = 0
        info_type = args.get('info_type')
        if info_type == "item":
            info = {
                'taskId': int(args.get('taskId')),
                'user_id': args.get('user_id'),
                'start_url': args.get('start_url'),
                'site_name': args.get('site_name'),
                'info_flag': args.get('info_flag'),
                'channel_name': args.get('channel_name'),
                'proxy_enable': args.get('proxy_enable'),
                'max_interval': args.get('max_interval'),
                'filename': args.get('filename'),
                'function_description': args.get('function_description'),
                'data_db': args.get('data_db'),
            }
            ret = MDB.set_entry_info(info)

        return ret

    def _remove_data(self, args):
        ret = 0
        msg = '删除失败。'

        xgsjTaskId = args.get('xgsjTaskId')
        if xgsjTaskId:
            taskId = MDB.init_task(xgsjTaskId=xgsjTaskId,
                                   start_url='',
                                   user_id='',
                                   interval_time=0,
                                   clock_time='',
                                   last_modify_time=0,
                                   dedup_expireat=0,
                                   config_status=0)  # 停用0  启用 1
        else:
            taskId = int(args.get('taskId'))

        if taskId != -1:
            info = {
                'taskId': taskId
            }
            RDB.remove_task(taskId)
            MDB.remove_entry_info(info)
            MDB.remove_hub_xpath_tree_info(info)
            MDB.remove_detail_xpath_tree_info(info)

            ret = 1
            msg = '删除了一条信息。'

        return ret, msg

    def get(self, request, *args, **kwargs):
        ret = self._get_data(request.GET)
        output = JsonResponse({'ret': ret})
        return HttpResponse(output, content_type='application/json; charset=UTF-8')

    def post(self, request, *args, **kwargs):
        ret = self._set_data(request.POST)
        # if 'upserted' in ret:
        #     ret.pop('upserted')  # 含有objectId 无法json编码
        output = JsonResponse({'ret': ret})
        return HttpResponse(output, content_type='application/json; charset=UTF-8')

    def put(self, request, *args, **kwargs):
        ret, msg = self._set_data(request.POST)
        output = JsonResponse({'ret': ret, 'msg': msg})
        return HttpResponse(output, content_type='application/json; charset=UTF-8')

    def delete(self, request, *args, **kwargs):
        if request.POST:
            ret, msg = self._remove_data(request.POST)
        else:
            ret, msg = self._remove_data(request.query_params)
        output = JsonResponse({'ret': ret, 'msg': msg})
        return HttpResponse(output, content_type='application/json; charset=UTF-8')


class HubXPathViewAPI(APIView):
    def _get_data(self, args):
        taskId = args.get('taskId')
        level = args.get('level')
        info = MDB.get_hub_xpath_info(taskId, int(level))
        return info

    def _set_data(self, args):
        xgsjTaskId = int(args.get('xgsjTaskId')) if args.get('xgsjTaskId') else -1

        info = {
            'taskId': int(args.get('taskId')),
            'user_id': args.get('user_id'),
            'start_url': args.get('start_url'),
            'level': int(args.get('level')),
            'hub_url': args.get('hub_url'),
            'site_name': args.get('site_name'),
            'encoding': args.get('encoding'),
            'node': args.get('node'),
            'parent_node': args.get('parent_node', 'root'),
            'black_white': args.get('black_white', 'white'),

            'select_mode': args.get('select_mode'),
            'isLoadJS': True if args.get('isLoadJS') == 'true' else False,
            'hubs': eval(args.get('hubs')),

            'hub_xpath': args.get('hub_xpath'),
            'hub_jquery_selector': args.get('hub_jquery_selector'),
            'ctime_xpath': args.get('ctime_xpath'),
            'ctime_jquery_selector': args.get('ctime_jquery_selector'),
            'nextPage_xpath': args.get('nextPage_xpath'),
            'nextPage_jquery_selector': args.get('nextPage_jquery_selector'),
            'max_page': args.get('max_page'),
            'url_time_format': eval(args.get('url_time_format')) if args.get('url_time_format') else '',
        }
        ret = MDB.set_hub_xpath_info(info)
        if ret == 1:
            msg = '[xpath]更新了一条信息。'
        elif ret == 0:
            msg = '[xpath]添加了一条信息。'
        else:
            msg = '[xpath]保存失败。'

        return ret, msg

    def _remove_data(self, args):
        taskId = args.get('taskId')
        hub_url = args.get('hub_url', '')

        ret = MDB.remove_hub_xpath_info(taskId)
        msg = '删除了一条信息。'
        return ret, msg

    def get(self, request, *args, **kwargs):
        ret = self._get_data(request.GET)
        output = JsonResponse(ret)
        return HttpResponse(output, content_type='application/json; charset=UTF-8')

    def post(self, request, *args, **kwargs):
        ret, msg = self._set_data(request.POST)
        # if 'upserted' in ret:
        #     ret.pop('upserted')  # 含有objectId 无法json编码
        output = JsonResponse({'ret': ret, 'msg': msg})
        return HttpResponse(output, content_type='application/json; charset=UTF-8')

    def put(self, request, *args, **kwargs):  # print('put:', request.POST)
        ret, msg = self._set_data(request.POST)
        output = JsonResponse({'ret': ret, 'msg': msg})
        return HttpResponse(output, content_type='application/json; charset=UTF-8')

    def delete(self, request, *args, **kwargs):
        if request.POST:
            ret, msg = self._remove_data(request.POST)
        else:
            ret, msg = self._remove_data(request.query_params)
        output = JsonResponse({'ret': ret, 'msg': msg})
        return HttpResponse(output, content_type='application/json; charset=UTF-8')


class DetailXPathViewAPI(APIView):
    def _get_data(self, args):
        taskId = int(args.get('taskId'))
        info = MDB.get_detail_xpath_info(taskId)
        return info

    def _set_data(self, args):
        info = {
            'taskId': int(args.get('taskId')),
            'user_id': args.get('user_id'),
            'start_url': args.get('start_url'),
            'parent_node_id': args.get('parent_node_id', ''),
            'encoding': args.get('encoding'),
            'detail_url': args.get('detail_url', ''),
            'isLoadJS': True if args.get('isLoadJS') == 'true' else False,
            'title_xpath': args.get('title_xpath', ''),
            'title_jquery': args.get('title_jquery', ''),
            'content_xpath': args.get('content_xpath', ''),
            'content_jquery': args.get('content_jquery', ''),
            'clear_content': eval(args.get('clear_content')),
            'ctime_xpath': args.get('ctime_xpath', ''),
            'ctime_jquery': args.get('ctime_jquery', ''),
            'source_xpath': args.get('source_xpath', ''),
            'source_jquery': args.get('source_jquery', ''),
            'retweeted_source_xpath': args.get('retweeted_source_xpath', ''),
            'retweeted_source_jquery': args.get('retweeted_source_jquery', ''),
            'channel_xpath': args.get('channel_xpath', ''),
            'channel_jquery': args.get('channel_jquery', ''),
            'pic_urls_xpath': args.get('pic_urls_xpath', ''),
            'pic_urls_jquery': args.get('pic_urls_jquery', ''),
            'page_xpath': args.get('page_xpath', ''),
            'page_jquery': args.get('page_jquery', ''),
        }
        ret = MDB.set_detail_xpath_info(info)
        if ret == 1:
            msg = '更新了一条信息。'
        elif ret == 0:
            msg = '添加了一条信息。'
        else:
            msg = '保存失败。'

        return ret, msg

    def _remove_data(self, args):
        taskId = args.get('taskId')
        ret = MDB.remove_detail_xpath_info(taskId)
        msg = '删除了一条信息。'
        return ret, msg

    def get(self, request, *args, **kwargs):
        # print(request.GET)
        ret = self._get_data(request.GET)
        output = JsonResponse(ret)
        return HttpResponse(output, content_type='application/json; charset=UTF-8')

    def post(self, request, *args, **kwargs):
        ret, msg = self._set_data(request.POST)
        # if 'upserted' in ret:
        #     ret.pop('upserted')  # 含有objectId 无法json编码

        output = JsonResponse({'ret': ret, 'msg': msg})
        return HttpResponse(output, content_type='application/json; charset=UTF-8')

    def put(self, request, *args, **kwargs):  # print('put:', request.POST)
        ret, msg = self._set_data(request.POST)
        output = JsonResponse({'ret': ret, 'msg': msg})
        return HttpResponse(output, content_type='application/json; charset=UTF-8')

    def delete(self, request, *args, **kwargs):
        if request.POST:
            ret, msg = self._remove_data(request.POST)
        else:
            ret, msg = self._remove_data(request.query_params)
        output = JsonResponse({'ret': ret, 'msg': msg})
        return HttpResponse(output, content_type='application/json; charset=UTF-8')
