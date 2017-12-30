#coding:utf8
"""
json配置转换python脚本
"""


header_templete = u"""
#coding:utf8
#############################################################################
# Copyright (c) 2014  - Beijing Intelligent Star, Inc.  All rights reserved


'''
文件名:{filename}
功能: {function}

代码历史:
{history}
'''
import time
import json
import datetime
from urlparse import urljoin

import redis

import log
import util
import spider
import setting
import htmlparser
"""

init_templete = u"""
class MySpider(spider.Spider):
    def __init__(self,
                 proxy_enable={proxy_enable},
                 proxy_max_num=setting.PROXY_MAX_NUM,
                 timeout=setting.HTTP_TIMEOUT,
                 cmd_args=None):
        spider.Spider.__init__(self,
                               proxy_enable,
                               proxy_max_num,
                               timeout=timeout,
                               cmd_args=cmd_args)

        # 网站名称
        self.siteName = "{siteName}"
        # 类别码，01新闻、02论坛、03博客、04微博 05平媒 06微信 07 视频、99搜索引擎
        self.info_flag = "{info_flag}"

        # 入口地址列表
        self.start_urls = {start_urls}
        self.encoding = '{encoding}'
        self.site_domain = '{site_domain}'
        self.request_headers = {request_headers}
        self.max_interval = datetime.timedelta(days={max_interval})
{other_variable}
        # 设置去重库保留时间
        dedup_expireat = self._conf_info.get("dedup_expireat")
        if dedup_expireat:
            self.conn.expireat(self.dedup_key, int(dedup_expireat) / 1000)
        
"""
default_get_start_urls_templete = u"""
    def get_start_urls(self, data=None):
        return self.start_urls
"""

get_start_urls_templete = u"""
    def get_start_urls(self, data=None):
        urls = {urls}
        start_urls = []
        for surl in urls:
            try:
                response = self.download(surl)
                response.encoding = {encoding}
                data = htmlparser.Parser(response.text)
            except Exception as e:
                log.logger.error('get_start_urls(): %s' % e)
                continue
            loops = {loops}
            for item in loops:
{fields}
{filters}
                url = urljoin(surl, url)
                start_urls.append(url)
        return start_urls
"""

parse_templete = u"""
    def {function_name}(self, response=None, url=None):
        url_list = []
        request = url
        list_url = request.get('url') if isinstance(request, dict) else url
        cur_page = request.get('meta', dict()).get('cur_page', 0) + 1 if isinstance(request, dict) else 1
        if response is not None:
            try:
                response.encoding = {encoding}
                unicode_html_body = response.text
                data = htmlparser.Parser(unicode_html_body)
            except Exception as e:
                log.logger.error("parse(): %s" % e)
                return (url_list, None, None)

            {loops}
            for item in loops:
{fields}
{filters}
                url = urljoin(list_url, url)
{request}
                url_list.append(request)
{next_page}
        else:
            return (url_list, None, None)
        return (url_list, {callback}, next_page_url)
"""

to_redis_function = u"""
    def encode_datetime(self, obj):
        if isinstance(obj, datetime.datetime):
            return int(time.mktime(obj.timetuple()))
        return obj

    def before_save_data(self, data, handle=True):
        if not handle:
            try:
                self.to_redis(data)
            except Exception as e:
                log.logger.exception(e)
            return data
        return []
        
    def to_redis(self, data):
        if isinstance(data, dict):
            data = [data]
        if data:
            urls = [x.get('url', '') for x in data]
            data = [json.dumps(x, default=self.encode_datetime) for x in data]
            self.conn.lpush(self.data_key, *data)
            for url in urls:
                self.urldedup.append(url)
        return 1
"""

parse_detail_page_templete = u"""
    def parse_detail_page(self, response=None, url=None):
        request = url
        meta = dict()
        if isinstance(request, dict):
            url = request.get('url')
            meta = request.get('meta')
        is_next_page = meta.get('is_next_page', 0)
        try:
            response.encoding = {encoding}
            data = htmlparser.Parser(response.text)
        except Exception as e:
            log.logger.error("parse_detail_page(): %s" % e)
            return None

        # 清理xpath
        clear_xpath = {clear_xpath}
        for xp in clear_xpath:
            data = util.clear_special_xpath(data, xp)

        result = []

{fields}

        gtime = datetime.datetime.utcnow()
        if ctime < gtime - self.max_interval:
            return []

{next_page}

        # todo next_page_content

{clear_content}

{post}
        result.append(post)
        return result
"""

test_code_templete = u"""if __name__ == '__main__':
    spider = MySpider()
    spider.proxy_enable = False
    spider.init_dedup()
    spider.init_downloader()

# ------------ get_start_urls() ----------
    # urls = spider.get_start_urls()
    # for url in urls:
    #     print url

# ------------ parse() ----------
    # url = '{test_list_page_url}'
    # resp = spider.download(url)
    # urls, fun, next_url = spider.parse(resp)
    # for url in urls:
    #     print url

# ------------ parse_detail_page() ----------
    url = '{test_detail_page_url}'
    resp = spider.download(url)
    res = spider.parse_detail_page(resp, url)
    for item in res:
        for k, v in item.iteritems():
            print k, v
"""

default_fields = {
    "$now": "datetime.datetime.utcnow()",
    "$siteName": "self.siteName",
    "$list": "[]",
    }

import re
import json
from collections import defaultdict
import functools


class KeySort(object):
    """根据依赖关系排序"""
    def __init__(self):
        self.key_dict = defaultdict(list)
        self._reg_keys = set()

    def register_keys(self, key1, key2):
        """key1 < key2"""
        self.key_dict[key1].append(key2)
        self._reg_keys.add(key1)
        self._reg_keys.add(key2)

    def sort(self, keys):
        last_keys = []
        sort_list = []
        need_sort_keys = []
        for key in keys:
            if key not in self._reg_keys:
                last_keys.append(key)
        #
        while 1:
            #"""拓扑排序。。。"""
            # 
            for key, value in list(self.key_dict.items()):
                for i, v in enumerate(value):
                    # v 不存在于键值中 则为最大
                    if v not in self.key_dict:
                        if v not in sort_list:
                            sort_list.append(v)
                        self.key_dict[key].pop(i)
                        # 值为空 则为最大
                        if not self.key_dict[key]:
                            if key not in sort_list:
                                sort_list.append(key)
                            self.key_dict.pop(key)
            if not self.key_dict:
                break
        return sort_list + last_keys
                

    def compare(self, key1, key2):
        if key1 in self.key_dict:
            if key2 in self.key_dict[key1]:
                return -1
            else:
                return 1
        elif key2 in self.key_dict:
            if key1 in self.key_dict[key2]:
                return 1
            else:
                return -1
        else:
            return 0

class JsonToConfig(object):
    def __init__(self, file='', config={}):
        if file:
            with open(file) as f:
                self.json_config = json.load(f)
        else:
            if config:
                self.json_config = config
            else:
                raise "not config file"

    def check_rules(self, rules):
        """清洗 rules"""
        _rules = []
        rules = rules if rules else []
        for rule in rules:
            if not rule:
                continue
            if not list(rule.items())[0][1]:
                continue
            _rules.append(rule)
        return _rules

    def make_header(self, description):
        filename = description.get('filename', '')
        function = description.get('function', '')
        history = description.get('history', '')
        history = "\n".join(history)
        return header_templete.format(filename=filename, function=function, history=history)

    def make_init(self, settings, **kwargs):
        """构造初始化函数"""
        proxy_enable = settings.get('proxy_enable')
        proxy_enable = {
            "0": "False",
            "1": "True"
            }.get(proxy_enable, "setting.PROXY_ENABLE")
        # start_urls
        start_urls = settings.get("start_urls")
        start_urls_str = ["["]
        for start_url_info in start_urls:
            url, comment = start_url_info[0], start_url_info[1]
            start_urls_str.append("\"%s\",    #%s" % (url, comment))
        start_urls_str.append("]")
        start_urls_str = "\n".join([" "* 24 + x for x  in start_urls_str]).strip()
        # other_variable
        other_variable = []
        if "data_db" in settings:
            _value = settings['data_db']
            if _value:
                other_variable.append("self.data_db = '%s'" % _value)
        if kwargs.get("json_db_flag", False):
            _value = settings['data_db']
            if _value:
                other_variable.append("self.conn = redis.StrictRedis.from_url('%s')" % _value[:_value.rfind('/')])
                other_variable.append("self.data_key = '%s'" % _value[_value.rfind('/')+1:])
                other_variable.append("self.dedup_uri = '%s'" % _value[:_value.rfind('/')])
                other_variable.append("self.dedup_key = 'dedup_%s'" % kwargs.get("schema_id"))
        other_variable = "\n".join([" " * 8 + x for x in other_variable])
        init_str = init_templete.format(
            info_flag=settings.get("info_flag"),
            siteName=settings.get("siteName"),
            site_domain=settings.get("site_domain"),
            encoding=settings.get("encoding"),
            request_headers=settings.get("request_headers"),
            max_interval=settings.get("max_interval"),
            start_urls=start_urls_str,
            proxy_enable=proxy_enable,
            other_variable=other_variable
            )
        return init_str
        
    def make_loops(self, loops):
        """构造循环体"""
        templete = "loops = data"
        for rule in loops[:-1]:
            if rule:
                templete += ".{}('''{}''')".format(*list(rule.items())[0])
        rule = loops[-1]
        templete += ".{}all('''{}''')".format(*list(rule.items())[0])
        return templete

    def make_fields(self, fields, main='data'):
        """构造字段提取代码"""
        key_sort = KeySort()
        fields_list = []
        field_names = list(fields.keys())
        fields_code_dict = {}
        for field_name, field_info in fields.items():
            _private_list = []
            field_code_str = "{} = {}".format(field_name, main)
            field_type = field_info.get("type")
            
            rules = self.check_rules(field_info.get("rules"))
            default = field_info.get("default")
            field_not = field_info.get("not")

            # 处理从meta中获取数据
            if default and default.startswith("$meta"):
                field_code_str = "{} = meta.get('{}')".format(field_name, field_name)
                _private_list.append(field_code_str)
                fields_code_dict[field_name] = _private_list
                continue
            
            #
            if not field_info.get('is_multi', 0):
                for rule in rules:
                    field_code_str += ".{}('''{}''')".format(*list(rule.items())[0])
                if field_type == 'str':
                    # 字符串类型
                    field_code_str += ".text().strip()"
                    if not rules:
                        field_code_str = "{} = {}".format(field_name, "''")
                elif field_type == 'datetime':
                    # 处理指定时间格式
                    if field_info.get("date_format"):
                        field_code_str += ".text().strip('/')"
                    else:
                        field_code_str += ".datetime()"
                        if not rules:
                            field_code_str = "{} = {}".format(field_name, 'datetime.datetime.utcnow()')
                elif field_type == 'int':
                    # 数字类型
                    field_code_str += ".int()"
                    if not rules:
                        field_code_str = "{} = {}".format(field_name, "0")
                elif field_type == 'list':
                    # 列表类型
                    field_code_str = "".join(list(reversed(field_code_str)))
                    field_code_str = re.sub("(htapx|xeger)\.", "lla\\1.", field_code_str, 1)
                    field_code_str = "".join(list(reversed(field_code_str)))
                    if not rules:
                        field_code_str = "{} = {}".format(field_name, "[]")
                elif field_type == 'const':
                    # 常量类型
                    field_code_str = "{} = '{}'".format(field_name, default)
                _private_list.append(field_code_str)
                # 处理指定时间格式
                if field_info.get("date_format"):
                    _private_list.extend([
                        "try:",
                        "    {} = datetime.datetime.strptime({}, '{}') - datetime.timedelta(hours=8)".format(field_name, field_name, field_info.get("date_format")),
                        "except Exception as e:",
                        "    log.logger.exception(e)",
                                          ])
                # 处理list类型
                if field_type == 'list':
                    _private_list.extend([
                        "{} = [x.text().strip() for x in {}]".format(field_name, field_name),
                                          ])
                    # 处理 pic_urls, video_urls
                    if 'urls' in field_name:
                        _private_list.extend([
                        "{} = [urljoin(url, x) for x in {}]".format(field_name, field_name),
                                          ])
            else:
                # 处理多段拼接
                _private_list.append("{} = ''".format(field_name))
                for rule in rules:
                    _private_list.append("{} += ''.join([item.text().strip() for item in data.{}all('''{}''')])".format(field_name, *list(rule.items())[0]))

            # 处理默认值
            if default is not None:
                if default.startswith("$"):
                    if default[1:] in field_names:
                        key_sort.register_keys(field_name, default[1:])
                        default = default[1:]
                    else:
                        default = default_fields.get(default)
                else:
                    if field_type == 'str':
                        default = "'''{}'''".format(default)
                if rules:
                    _private_list.extend(["if not {}:".format(field_name),
                                      "    {} = {}".format(field_name, default)
                                      ])
            # 处理值为空
            if field_not is not None:
                if field_not in ['1']:
                    _private_list.extend(["if not {}:".format(field_name),
                                          "    return []".format(field_name, default)
                                          ])
            fields_code_dict[field_name] = _private_list
        # 根据字段依赖关系排序后生成代码
        field_names = key_sort.sort(field_names)
        for field_name in field_names:
            fields_list.extend(fields_code_dict[field_name])

        return fields_list, fields_code_dict

    def make_filters(self, filters, fields):
        """构造过滤代码"""
        if not filters:
            return []
        filters_list = []
        for field_name, filter_info in filters.items():
            if field_name not in fields:
                # 对未定义的字段进行过滤
                raise Exception("{} not in items.fields".format(field_name))
            filter_code_list = []
            field_type = fields.get(field_name).get('type')
            if field_type == 'datetime':
                days = filter_info.get('day')
                filters_list.append("if {} < datetime.datetime.utcnow() - datetime.timedelta({}):".format(field_name, days))
                filters_list.append("    continue")
            elif field_type == 'str':
                _in = filter_info.get('in')
                for _in_str in _in:
                    filters_list.append("if '{}' in {}:".format(_in_str, field_name))
                    filters_list.append("    continue")
                _not_in = filter_info.get('not_in')
                for _not_in_str in _not_in:
                    filters_list.append("if '{}' not in {}:".format(_not_in_str, field_name))
                    filters_list.append("    continue")
                
        return filters_list                

    def make_function(self, function_name, **kwargs):
        """使用函数模版生成函数"""
        if function_name == 'default_get_start_urls':
            function = default_get_start_urls_templete
        elif function_name == 'get_start_urls':
            fields = "\n".join([" " * 16 + x for x in kwargs.get('fields')])
            filters = "\n".join([" " * 16 + x for x in kwargs.get('filters')])
            encoding = kwargs.get("encoding")
            if encoding:
                encoding = '"%s"' % encoding
            else:
                encoding = "self.encoding"
            function = get_start_urls_templete.format(
                function_name=function_name,
                urls = kwargs.get('urls'),
                loops = kwargs.get('loops'),
                fields = fields,
                filters = filters,
                encoding = encoding,
                )
        elif function_name == 'parse_detail_page':
            fields = "\n".join([" " * 8 + x for x in kwargs.get('fields')])
            post = "\n".join([" " * 8 + x for x in kwargs.get('post')])
            clear_content = "\n".join([" " * 8 + x for x in kwargs.get('clear_content')])
            next_page = "\n".join([" " * 8 + x for x in kwargs.get('next_page')])
            encoding = kwargs.get("encoding")
            if encoding:
                encoding = '"%s"' % encoding
            else:
                encoding = "self.encoding"
            function = parse_detail_page_templete.format(
                function_name=function_name,
                fields=fields,
                post=post,
                clear_xpath=kwargs.get('clear_xpath'),
                clear_content=clear_content,
                next_page=next_page,
                encoding = encoding,
                )
        elif function_name == 'test_cdoe':
            function = test_code_templete.format(
                test_list_page_url=kwargs.get('test_list_page_url'),
                test_detail_page_url=kwargs.get('test_detail_page_url'),
                )
        else:
            fields = "\n".join([" " * 16 + x for x in kwargs.get('fields')])
            filters = "\n".join([" " * 16 + x for x in kwargs.get('filters')])
            next_page = "\n".join([" " * 12 + x for x in kwargs.get('next_page')])
            request = "\n".join([" " * 16 + x for x in kwargs.get('request')])
            encoding = kwargs.get("encoding")
            if encoding:
                encoding = '"%s"' % encoding
            else:
                encoding = "self.encoding"
            function = parse_templete.format(
                function_name=function_name,
                loops = kwargs.get('loops'),
                fields = fields,
                filters = filters,
                callback=kwargs.get('callback'),
                next_page=next_page,
                request=request,
                encoding = encoding,
                )
        return function

    def make_next_page(self, next_page, type='list'):
        if not next_page:
            return ["next_page_url = None"]
        _code_str_list = []
        if type == 'list':
            rules = self.check_rules(next_page.get("rules"))
            max_page = next_page.get("max_page", 1)
            _code_str = ""
            for rule in rules:
                if rule:
                    _code_str += ".{}('''{}''')".format(*list(rule.items())[0])
            if _code_str:
                _code_str_list = [
                    "next_page_url = data" + _code_str + ".text().strip()",
                    "if not next_page_url:",
                    "    next_page_url = None",
                    "else:",
                    "    next_page_url = urljoin(list_url, next_page_url)",
                    "    next_page_url = {'url': next_page_url, 'meta': {'max_page': %s, 'cur_page': cur_page}}" % max_page,
                    "if cur_page >= %s:" % max_page,
                    "    next_page_url = None",
                    ]
            else:
                _code_str_list = ["next_page_url = None"]
        elif type=='detail':
            rules = self.check_rules(next_page.get("rules"))
            _code_str = ""
            if len(rules) == 1:
                _code_str_list = [
                    "next_page_urls_loop = data.{}all('''{}''')".format(*list(rules[0].items())[0]),
                    "next_page_urls = [item.text().strip() for item in next_page_urls_loop]"
                ] 
            else:
                _code_str_list = ["next_page_urls = ["]
                for rule in rules:
                    _code_str_list.append("    data.{}('''{}''').text().strip(),".format(*list(rule.items())[0]))
                _code_str_list.append("    ]")
            _code_str_list.extend([
                    "if next_page_urls and not is_next_page:",
                    "    _next_page_urls = []",
                    "    for _next_url in next_page_urls:",
                    "        _next_url = urljoin(url, _next_url)",
                    "        if _next_url not in _next_page_urls and _next_url != url:",
                    "            _next_page_urls.append(_next_url)",
                    "    next_page_urls = [{'url': urljoin(url, _next_url), 'meta': {'is_next_page': 1}} for _next_url in _next_page_urls]",
                    "    for _next_url in next_page_urls:",
                    "        _next_response = self.download(_next_url)",
                    "        _next_result = self.parse_detail_page(response=_next_response, url=_next_url)",
                    "        if not _next_result:",
                    "            continue",
                    "        if isinstance(_next_result, list):",
                    "            _next_result = _next_result[0]",
                    "        if not isinstance(_next_result, dict):",
                    "            continue",
                    "        content += _next_result.get('content', '')",
                ])

        return _code_str_list

    def make_post(self, fields):
        """构造返回数据字典"""
        post = [
            "post = {",
            "    'url': url,"
            ]
        exists_keys = fields.keys()
        all_keys = ['title', 'content', 'ctime', 'source', 'channel', 'retweeted_source', 'siteName', 'visit_count', 'reply_count']
        # 构造已知key
        for key in all_keys:
            if key not in exists_keys:
                continue
            if key == 'visit_count':
                key_str = "    'visitCount': [{'count': visit_count, 'spider_time': gtime}],"
            elif key == 'reply_count':
                key_str = "    'replyCount': [{'count': reply_count, 'spider_time': gtime}],"
            elif key == 'siteName':
                key_str = "    'siteName': self.siteName,"
            else:
                key_str = "    '{}': {},".format(key, key)
            post.append(key_str)
        # 构造未知key
        for key in exists_keys:
            if key in all_keys:
                continue
            key_str = "    '{}': {},".format(key, key)
            post.append(key_str)

        post.append("    'gtime': gtime,")
        post.append("    }")
        return post

    def make_request(self, fields):
        """构造列表页解析中的下载对象"""
        requst_str_list = [
            'request = {',
            '   "url": url,',
            '   "meta": {'
            ]
        for key in fields.keys():
            requst_str_list.append('        "%s": %s,' % (key, key))
        requst_str_list.append("            }")
        requst_str_list.append("          }")
        return requst_str_list

    def make_clear_content(self, clear_content):
        """构造 content 清理代码"""
        clear_content_codes = []
        rules = clear_content.get('rules')
        rules = self.check_rules(rules)
        if rules:
            xpath_list = [x.get('xpath') for x in rules if 'xpath' in x]
            xpath_list = [x for x in xpath_list if x]
            regex_list = [x.get('regex') for x in rules if 'regex' in x]
            regex_list = [x for x in regex_list if x]
            replace_list = [x.get('replace') for x in rules if 'replace' in x]
            replace_list = [x for x in replace_list if x]

            if xpath_list:
                clear_content_codes.extend([
                    "clear_content_xpath_list = {}".format(xpath_list),
                    "for xp in clear_content_xpath_list:",
                    "    for clear_data in data.xpathall(xp):",
                    "        content = content.replace(clear_data.text(), '')"
                    ])
            if regex_list:
                clear_content_codes.extend([
                    "clear_content_regex_list = {}".format(regex_list),
                    "for reg in clear_content_regex_list:",
                    "    for clear_data in data.regexall(reg):",
                    "        content = content.replace(clear_data.text(), '')"
                    ])
            if replace_list:
                clear_content_codes.extend([
                    "clear_content_replace_list = {}".format(replace_list),
                    "for clear_data in clear_content_replace_list:",
                    "    content = content.replace(clear_data, '')"
                    ])

        return clear_content_codes

    def create_config(self):
        config = []
        
        # json格式入库标志
        fields = self.json_config.get('fields', {})
        json_db_flag = "schema_id" in fields
        #json_db_flag = False
        if json_db_flag:
            schema_id = fields['schema_id']['default']
        else:
            schema_id = ''
        #header
        description = self.json_config.get('description', {})
        header = self.make_header(description)
        config.append(header)

        # settings
        settings = self.json_config.get('settings', {})
        init_code = self.make_init(settings, json_db_flag=json_db_flag, schema_id=schema_id)
        config.append(init_code)

        # logics
        logic_functions = []
        logics = self.json_config.get('logics', {})
        if logics:
            logic_keys = list(logics.keys())
            logic_keys.sort()
            
            for logic_key in logic_keys:
                logic = logics.get(logic_key)

                # encoding
                encoding = logic.get("encoding")

                # urls
                urls = logic.get('urls')

                # 循环体
                loops = logic.get('loops')
                loops = [x for x in loops if x]
                if not loops:
                    raise Exception("not loops")
                loops = self.make_loops(loops)
                # 解析体
                items = logic.get('items')
                fields, fields_code_dict = self.make_fields(items.get("fields"), main='item')
                filters = self.make_filters(items.get("filters"), items.get("fields"))
                request = self.make_request(items.get("fields"))

                #callback
                callback = logic.get('callback', "")
                if callback:
                    callback_function_name = 'self.parse_next_%s'%callback.strip("#")
                else:
                    callback_function_name = "None"

                # next_page
                next_page = logic.get('next_page', [])
                next_page = self.make_next_page(next_page)

                # 合并
                if logic_key == '#0':
                    function_str = self.make_function('get_start_urls', urls=urls, loops=loops, fields=fields, filters=filters, encoding=encoding)
                elif logic_key == '#1':
                    function_str = self.make_function('parse', urls=urls, loops=loops, fields=fields, filters=filters, callback=callback_function_name, next_page=next_page, request=request, encoding=encoding)
                else:
                    function_str = self.make_function('parse_next_%s'%logic_key.strip("#"), urls=urls, loops=loops, fields=fields, filters=filters, callback=callback_function_name, next_page=next_page, request=request, encoding=encoding)
                logic_functions.append(function_str)

            if "#0" not in logic_keys:
                function_str = self.make_function('default_get_start_urls')
                logic_functions.insert(0, function_str)
        config.extend(logic_functions)
        if json_db_flag:
            config.append(to_redis_function)
        # fields
        fields = self.json_config.get('fields', {})
        encoding = fields.pop("encoding", "")
        clear_xpath = fields.pop("clear_xpath", [])
        clear_content = fields.pop("clear_content", {})
        next_page = fields.pop("next_page", {})
        next_page = self.make_next_page(next_page, type='detail')
        if clear_xpath:
            clear_xpath = [x.get('xpath') for x in self.check_rules(clear_xpath.get('rules'))]
        if clear_content:
            clear_content = self.make_clear_content(clear_content)

        post = self.make_post(fields)
        fields_str, fields_code_dict = self.make_fields(fields)
        
        field_function = self.make_function('parse_detail_page', fields=fields_str, post=post, clear_xpath=clear_xpath, clear_content=clear_content, next_page=next_page, encoding=encoding)
        config.append(field_function)

        # 测试代码
        test_code = self.json_config.get('test', {})
        test_list_page_url = test_code.get("list_page_url", "")
        test_detail_page_url = test_code.get("detail_page_url", "")
        test_code_function = self.make_function('test_cdoe', test_list_page_url=test_list_page_url, test_detail_page_url=test_detail_page_url)
        config.append(test_code_function)
        
        return "\n".join(config)
        
        

if __name__ == "__main__":
    file = "Spider_example.json"
    #file = "test.json"
    with open(file) as f:
        config = json.load(f)
    jc = JsonToConfig(config=config)
    config = jc.create_config()
    print(config)
