# coding=utf-8
from pprint import pprint
import os, time, datetime
import pymongo
import redis
import json
from bson.objectid import ObjectId
import requests
from urllib.parse import urlparse, urlunparse

# from .setting import MONGODB_SERVER, MONGODB_PORT

# LOCAL_DEBUG = False
#
# if LOCAL_DEBUG:  # os.name == 'nt':
#     MONGODB_SERVER = '127.0.0.1:37017'
#     MONGODB_PORT = 27017
#     REDIS_SERVER = 'redis://127.0.0.1:6379/2'
# else:
#     MONGODB_SERVER = '192.168.16.223:37017'
#     MONGODB_PORT = 37017
#     REDIS_SERVER = 'redis://192.168.16.223:6379/2'

REDIS_SERVER = 'redis://' + os.environ["visual_redis_host"] + '/2'
REDIS_OUTPUT = 'redis://' + os.environ["visual_redis_output"]
MONGODB_SERVER = os.environ["visual_mongo_host"].split(':')[0]
MONGODB_PORT = int(os.environ["visual_mongo_host"].split(':')[1])


# print(REDIS_SERVER)
# print(MONGODB_SERVER,MONGODB_PORT)

# MONGODB_SERVER = '127.0.0.1'
# MONGODB_PORT = 27017
# REDIS_SERVER = 'redis://192.168.16.223:6379/2'

class RedisDriver(object):
    def __init__(self):
        self._conn = redis.StrictRedis.from_url(REDIS_SERVER)
        self.conf_hash_key = 'conf'
        self.conf_content_hash_key = 'conf_content'
        self.pregid1_list_key = 'pregid1'

    def set_config_info(self, task_info):
        # taskId = config_info.pop('taskId')
        # intervaltime clock_time last_modify_time dedup_expireat
        self._conn.hset(self.conf_hash_key, task_info['config_id'], json.dumps(task_info))

    def set_config_content(self, taskId, conf_content):
        self._conn.hset(self.conf_content_hash_key, taskId, conf_content)

    def start_task(self, taskId):
        self._conn.lpush(self.pregid1_list_key, taskId)

    def stop_task(self, taskId):
        if self._conn.exists(self.pregid1_list_key):
            self._conn.lrem(self.pregid1_list_key, 0, taskId)

    def remove_task(self, taskId):
        if self._conn.exists(self.pregid1_list_key):
            self._conn.lrem(self.pregid1_list_key, 0, taskId)

        if self._conn.exists(self.conf_hash_key):
            self._conn.hdel(self.conf_hash_key, taskId)

        if self._conn.exists(self.conf_content_hash_key):
            self._conn.hdel(self.conf_content_hash_key, taskId)


class MongoDriver(object):
    def __init__(self):
        self.local_client = pymongo.MongoClient(host=MONGODB_SERVER, port=MONGODB_PORT)
        self.webspider = self.local_client.webspider
        self.entry_setting = self.webspider.entry_setting
        self.detail_xpath = self.webspider.detail_xpath
        self.hub_xpath = self.webspider.hub_xpath
        self.simulator = self.webspider.simulator

    ################## 入口信息 ########################
    def get_entry_info(self, taskId):
        info = self.entry_setting.find_one({'taskId': taskId})
        if info: info.pop('_id')
        return info

    def _add_task_info(self, xgsjTaskId, start_url, user_id, interval_time, clock_time, last_modify_time,
                       dedup_expireat):
        taskId = 1  # entry_setting collection为空时，taskId初始为1
        m = self.entry_setting.aggregate([{"$group": {'_id': '', 'max_id': {"$max": "$taskId"}}}])
        for i in m:
            taskId = i['max_id'] + 1  # taskId自增

        entry_info = {
            'taskId': taskId,
            'config_id': taskId,
            'xgsjTaskId': xgsjTaskId if xgsjTaskId else -1,
            'user_id': user_id,
            'start_url': start_url,
            'info_flag': '01',
            'channel_name': '',
            'proxy_enable': False,
            'site_name': '',
            'max_interval': 300,
            'interval_time': interval_time,
            'clock_time': clock_time,
            'last_modify_time': last_modify_time,
            'dedup_expireat': dedup_expireat,
            'filename': '',
            'function_description': '',
            'data_db': REDIS_OUTPUT,
        }
        self.entry_setting.insert(entry_info)
        return taskId

    def init_task(self, xgsjTaskId, start_url, user_id, interval_time, clock_time, last_modify_time, dedup_expireat,
                  config_status):
        taskId = -1  # 无效taskId
        if xgsjTaskId:  # 从星光数据系统向自系统映射Task参数
            entry_info = self.entry_setting.find_one({'xgsjTaskId': xgsjTaskId})
            if entry_info:  # entry_setting 初始化
                taskId = entry_info['taskId']

                entry_info['user_id'] = user_id
                entry_info['start_url'] = start_url
                entry_info['interval_time'] = interval_time
                entry_info['clock_time'] = clock_time
                entry_info['last_modify_time'] = last_modify_time
                entry_info['dedup_expireat'] = dedup_expireat
                if config_status != -1:  # 停用0  启用1 不变-1
                    entry_info['config_status'] = config_status
                self.entry_setting.update({'taskId': taskId}, {"$set": entry_info}, upsert=True)
            else:
                taskId = self._add_task_info(xgsjTaskId, start_url, user_id, interval_time, clock_time,
                                             last_modify_time, dedup_expireat)

        else:  # 自系统添加任务
            if start_url:
                taskId = self._add_task_info('', start_url, user_id, interval_time, clock_time, last_modify_time,
                                             dedup_expireat)

        return taskId

    def set_entry_info(self, info):
        ret = self.entry_setting.update({'taskId': info['taskId']}, {"$set": info}, upsert=True)
        return ret['nModified']

    def remove_entry_info(self, info):
        ret = self.entry_setting.remove({'taskId': info['taskId']})
        return ret

    ################## 导航信息 ########################
    def get_navInfo(self, taskId):
        cnt = self.hub_xpath.find({'taskId': taskId}).count()
        if cnt <= 0:
            return 0, False

        detail = self.detail_xpath.find_one({'taskId': taskId})
        return cnt, detail is not None

    def get_hub_url_by_level(self, taskId, level):
        info = self.hub_xpath.find_one({'taskId': taskId, 'level': level})
        return info['hub_url'] if info else ''

    ################## 节点树 ########################
    # def get_nodes(self, user_id, start_url):
    #     ret = []
    #     l = self.hub_xpath.find({'user_id': user_id, 'start_url': start_url}).sort([('level', pymongo.ASCENDING)])
    #     for i in l:
    #         ret.append({'name': i['node'], 'value': i['node']})
    #     else:
    #         ret.append({'name': 'root', 'value': 'root'})
    #     return ret

    def get_nodes_list(self, taskId):
        ret = []
        l = self.hub_xpath.find({'taskId': taskId}).sort([('level', pymongo.ASCENDING)])
        for info in l:
            info.pop('_id')
            if not info['select_mode']: info['select_mode'] = 'multi'  # 如果为空设置默认值
            ret.append(info)

        return ret

    def get_node_selector(self, taskId, level):
        info = self.hub_xpath.find_one({'taskId': taskId, 'level': level})
        if info:
            info['id'] = str(info['_id'])
            info['hubs_cnt'] = len(info['hubs']) if 'hubs' in info else 0
            info.pop('_id')
        return info

    def get_detail_selector(self, taskId):
        info = self.detail_xpath.find_one({'taskId': taskId})
        if info:
            info['id'] = str(info['_id'])
            info.pop('_id')
        return info

    def extract(self, hub_info):
        '''
        Args:
            hub_info:
        Returns:
            row_xpath, hub_xpath(without row_xpath), ctime(without row_xpath), url_time_regex, url_time_date_format
        '''

        # //div[@class='content']/div[@class='mid listOut']/ul/li/a[2]
        # //div[@class='content']/div[@class='mid listOut']/ul/li/span
        row, hub, ctime = [], [], []

        hub_xpath = hub_info['hub_xpath']
        ctime_xpath = hub_info['ctime_xpath']

        if hub_info['url_time_format'] and hub_info['url_time_format']['date_format']:
            # hub_x = '/'.join(hub_xpath.split('/')[:-1])
            return hub_xpath, '//@href', '//@href', hub_info['url_time_format']['regex'], \
                   hub_info['url_time_format']['date_format']

        else:
            if not ctime_xpath:
                return hub_xpath, '//@href', '', '', ''
            else:
                hub = hub_xpath.split('/')
                ctime = ctime_xpath.split('/')
                i = 0
                for i in range(min(len(hub), len(ctime))):
                    if hub[i] == ctime[i]:
                        row.append(hub[i])
                    else:
                        break

                hub_x = '/'.join(hub[i:])
                if hub_x[:4] == '////':
                    hub_x = hub_x[:2]

                if hub_x[:2] != '//':
                    hub_x = '//' + hub_x

                ctime_x = '/'.join(ctime[i:])
                if ctime_x[:4] == '////':
                    ctime_x = ctime_x[:2]

                if ctime_x[:2] != '//':
                    ctime_x = '//' + ctime_x

                return '/'.join(row), hub_x + '/@href', ctime_x, '', ''

    def _getSchemaId(self):
        schema = '''{
              "$schema": "http://json-schema.org/draft-04/schema#",
              "id": "http://schemas.istarshine.com/NEWS",
              "type": "object",
              "properties": {
                "url": {
                  "id": "http://schemas.istarshine.com/NEWS/url",
                  "type": "string",
                  "minLength": 1,
                  "description":"url"
                },
                "title": {
                  "id": "http://schemas.istarshine.com/NEWS/title",
                  "type": "string",
                  "description":"标题",
                  "minLength": 1
                },
                "content": {
                  "id": "http://schemas.istarshine.com/NEWS/content",
                  "description":"内容",
                  "type": "string"
                },
                "siteName": {
                  "id": "http://schemas.istarshine.com/NEWS/siteName",
                  "description":"网站名称",
                  "type": "string"
                },
                "visitCount": {
                  "id": "http://schemas.istarshine.com/NEWS/visitCount",
                  "description":"阅读数",
                  "type": "array",
                  "items":{
                    "type": "object",
                    "description": "包含时间的阅读数",
                    "properties":{
                        "count":{
                            "type": "integer",
                            "description": "阅读数"
                        },
                        "spider_time":{
                            "type": "string",
                            "description": "采集时间"
                        }
                    }
                  }
                },
                "replyCount": {
                  "id": "http://schemas.istarshine.com/NEWS/replyCount",
                  "description":"回复数",
                  "type": "array",
                  "items":{
                    "type": "object",
                    "description": "包含时间的回复数",
                    "properties":{
                        "count":{
                            "type": "integer",
                            "description": "回复数"
                        },
                        "spider_time":{
                            "type": "string",
                            "description": "采集时间"
                        }
                    }
                  }
                },
                "source": {
                  "id": "http://schemas.istarshine.com/NEWS/source",
                  "description":"作者",
                  "type": "string"
                },
                "channel": {
                  "id": "http://schemas.istarshine.com/NEWS/channel",
                  "description":"频道",
                  "type": "string"
                },
                "retweeted_source": {
                  "id": "http://schemas.istarshine.com/NEWS/retweeted_source",
                  "description":"转发来源",
                  "type": "string"
                },
                "ctime": {
                  "id": "http://schemas.istarshine.com/NEWS/ctime",
                  "type": "integer",
                  "description":"发布时间"
                },
                "gtime": {
                  "id": "http://schemas.istarshine.com/NEWS/gtime",
                  "type": "integer",
                  "description":"采集时间"
                }
              },
              "required": [
                  "url",
                  "title",
                  "content"
              ]
            }
            '''

        res = {"code": "100",  # 100为成功，其他代码则为失败
               "message": "添加成功",  # 返回的信息
               "id": "1234567890"  # 如果为100则返回正确id(326885889722368)，否则返回空字符串
               }
        return res

    def getXGSJTaskId(self, taskId):
        info = self.entry_setting.find_one({'taskId': taskId})
        return str(info['xgsjTaskId']) if info else -1

    def nodesXPath2Json(self, taskId):
        schema_info = self._getSchemaId()
        schema_id = self.getXGSJTaskId(taskId)
        schema_info['schema_id'] = schema_id
        schema_code = schema_info['code']
        schema_msg = schema_info['message']

        spider_json = dict()
        start_urls = []
        # node_id = ''
        cond = {'taskId': taskId}

        spider_json['description'] = {
            "filename": "webSpider",  # 必须英文
            "function": "function",
            "history": ["可视化爬虫生成代码"]
        }

        root = self.hub_xpath.find_one({'taskId': taskId, 'level': 0})
        if root['select_mode'] == 'single':
            for i in root['hubs']:
                start_urls.append([i['href'], i['text']])
        else:
            start_urls = [[root['hub_url'], 'channel_name']]

        (scheme, netloc, path, params, query, fragment) = urlparse(root['start_url'])

        setting = self.entry_setting.find_one({'taskId': taskId})
        spider_json['settings'] = {
            "info_flag": setting['info_flag'],
            "siteName": setting['site_name'],
            "site_domain": netloc,
            "encoding": root['encoding'],
            "request_headers": {},
            "proxy_enable": setting['proxy_enable'],
            "start_urls": start_urls,
            "max_interval": setting['max_interval'],
            "data_db": setting['data_db'] if 'data_db' in setting else ''
        }

        spider_json['logics'] = dict()

        cnt = self.hub_xpath.find(cond).count()
        l = self.hub_xpath.find(cond).sort([('level', pymongo.ASCENDING)])
        i = 0
        hub_single = 0
        for hub_info in l:
            if hub_info['select_mode'] == 'single':
                hub_single = hub_single + 1
                continue

            i = i + 1
            # node_id = str(hub_info['_id'])  # 取最后一级

            row, hub, ctime, url_time_regex, url_time_date_format = self.extract(hub_info)
            if ctime:
                fields = {
                    "url": {
                        "type": "str",
                        "rules": [{"xpath": hub}]
                    },
                    "ctime": {
                        "type": "datetime",
                        "rules": [
                            {"xpath": ctime},
                            {"regex": url_time_regex}
                        ],
                        "date_format": url_time_date_format
                    }
                }
                filters = {
                    "ctime": {"day": 1000},
                    # "url": {
                    #     "in": [],
                    #     "not_in": []
                    # }
                }
            else:
                fields = {
                    "url": {
                        "type": "str",
                        "rules": [{"xpath": hub}]
                    }
                }
                filters = {}

            # hub url
            spider_json['logics']['#' + str(i)] = {  # get_detail_page_urls()
                "encoding": hub_info['encoding'],
                "urls": [],
                "loops": [{"xpath": row}],
                "items": {
                    "fields": fields,
                    "filters": filters
                },
                "next_page": {
                    "rules": [
                        {
                            "xpath": hub_info['nextPage_xpath'] + "//@href" if hub_info['nextPage_xpath'] else ''
                        }
                    ],
                    "max_page": hub_info['max_page']
                },
                "callback": '#' + str(i + 1) if i + hub_single != cnt else ''
                # "#2":下一级回调函数, 无回调 则调用详情页解析函数
            }

        detail = self.detail_xpath.find_one({'taskId': taskId})
        if detail:
            title_rules = [{"xpath": detail['title_xpath']}] if detail['title_xpath'] else  []
            content_rules = [{"xpath": detail['content_xpath']}] if detail['content_xpath'] else  []
            clear_content = detail['clear_content'] if 'clear_content' in detail else {}
            ctime_rules = [{"xpath": detail['ctime_xpath']}] if detail['ctime_xpath'] else  []
            source_rules = [{"xpath": detail['source_xpath']}] if detail['source_xpath'] else  []
            retweeted_source_rules = [{"xpath": detail['retweeted_source_xpath']}] \
                if detail['retweeted_source_xpath'] else  []
            channel_rules = [{"xpath": detail['channel_xpath']}] if detail['channel_xpath'] else  []
            pic_urls_rules = [{"xpath": detail['pic_urls_xpath'] + '/@src'}] if detail['pic_urls_xpath'] else  []

            spider_json['fields'] = {  # get_detail_page_info
                "schema_id": {
                    "type": "const",
                    "default": schema_id,
                },
                "encoding": detail['encoding'] if 'encoding' in detail else 'utf-8',
                "title": {
                    "type": "str",
                    "rules": title_rules,
                    # "default": "",
                    "not": ""
                },
                "content": {
                    "type": "str",
                    "rules": content_rules,
                    "default": "$title",
                    "not": "",
                    "is_multi": 0
                },
                "ctime": {
                    "type": "datetime",
                    "rules": ctime_rules,
                    "default": "$now",
                    "not": ""
                },
                "source": {
                    "type": "str",
                    "rules": source_rules,
                    "default": "$siteName",
                    "not": ""
                },
                "retweeted_source": {
                    "type": "str",
                    "rules": retweeted_source_rules,
                    "default": "$siteName",
                    "not": ""
                },
                "channel": {
                    "type": "str",
                    "rules": channel_rules,
                    # "default": "",
                    "not": ""
                },
                "pic_urls": {
                    "type": "list",
                    "rules": pic_urls_rules,
                    # "default": "",
                    "not": ""
                },
                "clear_xpath": {  # 清理html
                    "rules": [
                        {"xpath": "//script|//style"}
                    ]
                },
                "clear_content": {
                    "rules": [
                        {"xpath": "//script|//style"},
                        {"regex": clear_content['regex'].replace('\\\\', '\\') if clear_content else ''},
                        {"replace": clear_content['replace'] if clear_content else ''}
                    ]
                }
            }

        spider_json["test"] = {
            "list_page_url": root['hub_url'],
            "detail_page_url": detail['detail_url'] if detail else ""
        }

        return spider_json, schema_info

    def save_spider_json_code(self, taskId, spider_json, spider_code):
        self.entry_setting.update({'taskId': taskId},
                                  {"$set": {'spider_json': json.dumps(spider_json), 'spider_code': spider_code}})

    ################## 列表节点 ########################
    def get_entry_list(self, user_id, search_url, skip_num, page_size):
        ret = []
        cond = {'user_id': user_id}  # root为根节点
        if search_url:
            cond['start_url'] = {'$regex': search_url}

        l = self.entry_setting.find(cond).sort([('_id', pymongo.DESCENDING)]).skip(skip_num).limit(page_size)
        for entry_info in l:
            taskId = entry_info['taskId']
            hub_cnt = self.hub_xpath.find({'taskId': taskId}).count()
            detail_info = self.detail_xpath.find_one({'taskId': taskId})

            navInfo = dict()
            navInfo['taskId'] = entry_info['taskId']
            navInfo['hasDetail'] = detail_info != None
            navInfo['levels'] = [x for x in range(hub_cnt)]

            ret.append({'start_url': entry_info['start_url'] if entry_info else '',
                        'site_name': entry_info['site_name'] if entry_info else '',
                        'navInfo': navInfo,
                        'detail_url': detail_info['detail_url'] if detail_info else '',
                        'status': '已启用',
                        'taskId': entry_info['taskId'],
                        'xgsjTaskId': entry_info['xgsjTaskId']
                        })

        return ret

    def get_entry_search_cnt(self, user_id, search_url):
        cond = {'user_id': user_id, 'node': 'root'}  # root为根节点
        if search_url:
            cond['start_url'] = {'$regex': search_url}

        cnt = self.hub_xpath.find(cond).count()

        return cnt

    def get_hub_xpath_info(self, taskId, level):
        info = self.hub_xpath.find_one({'taskId': taskId, 'level': level})
        if info:
            info['id'] = str(info['_id'])
            info.pop('_id')
        else:
            info = dict()
            info['id'] = ""

        return info

    def set_hub_xpath_info(self, hub_info):
        ret = self.hub_xpath.update({'taskId': hub_info['taskId'], 'level': hub_info['level']},
                                    {"$set": hub_info},
                                    upsert=True)

        return ret['nModified']

    def remove_hub_xpath_tree_info(self, info):
        # 多级节点，树删除
        cnt = self.hub_xpath.remove({'taskId': info['taskId']})
        return cnt

    def remove_hub_xpath_info(self, taskId):
        # 多级节点，树删除
        cnt = self.hub_xpath.remove({'taskId': taskId})
        return cnt

    ################## 详情节点 ########################
    def get_detail_xpath_info(self, taskId):
        info = self.detail_xpath.find_one({'taskId': taskId})
        if info:
            info.pop('_id')

        return info

    def set_detail_xpath_info(self, info):
        # parent_node_info = self.hub_xpath.find_one({'_id': ObjectId(info['parent_node_id'])})
        # info['start_url'] = parent_node_info['start_url']
        # info = self.detail_xpath.find_one({'user_id': info['user_id'], 'start_url': info['start_url']})
        ret = self.detail_xpath.update({'taskId': info['taskId']},
                                       {"$set": info}, upsert=True)
        return ret['nModified']

    def remove_detail_xpath_tree_info(self, info):
        cnt = self.detail_xpath.remove({'taskId': info['taskId']})
        return cnt

    def remove_detail_xpath_info(self, info):
        cnt = self.detail_xpath.remove({'taskId': info['taskId']})
        return cnt

    ################## simulator节点 ########################
    def get_simulator_info(self, info):
        hubs = []
        i = 1
        ret = self.simulator.find_one({'user_id': info['user_id'], 'start_url': info['start_url']})
        if ret and 'hubs' in ret:
            for hub in ret['hubs']:
                hubs.append({
                    'index': i,
                    'text': hub['text'] if 'text' in hub else '',
                    'href': hub['href'] if 'href' in hub else ''
                })
                i = i + 1
        return hubs

    ################## task管理 ########################
    def get_task_code(self, task_id):
        cond = {'taskId': task_id}
        info = self.entry_setting.find_one(cond)
        return info['spider_code'] if info else 'taskId:' + task_id + ',code not found.'


if __name__ == '__main__':
    # r = RedisDriver()
    # r.init_options()

    db = MongoDriver()
    # a = "//div[@class='wrapper mt20 content']/div[@class='fl cola']/div[@class='haoklil']/div[@class='haoklil1']/dl/dd/span[@class='haoklil113']"
    # b = "//div[@class='wrapper mt20 content']/div[@class='fl cola']/div[@class='haoklil']/div[@class='haoklil1']/div[@class='haoklil11']/span/a"
    # print(db.extract(a, b))
    pprint(db._getSchemaId())
    # pprint(db.get_channel_search_cnt(''))
