# coding=utf-8
from pprint import pprint
import datetime
import json
from django.shortcuts import render, render_to_response
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.views.generic import TemplateView

from .dbDriver import MongoDriver
from django.core.urlresolvers import reverse

MDB = MongoDriver()

# [动态网页]
class SimulatorView(TemplateView):
    queryset = []
    template_name = 'webSpider/simulator.html'

# [Helper]
class GuideView(TemplateView):
    queryset = []
    template_name = 'webSpider/guide.html'

# [数据面板]
class DashBoardView(TemplateView):
    queryset = []
    template_name = 'webSpider/dashBoard.html'

# [入口画面]
class MainView(TemplateView):
    queryset = []
    template_name = 'webSpider/main.html'

# [WEB爬虫画面]
class WebSpiderHubView(TemplateView):
    queryset = []
    template_name = 'webSpider/webSpiderHub.html'


# [WEB爬虫画面]
class WebSpiderDetailView(TemplateView):
    queryset = []
    template_name = 'webSpider/webSpiderDetail.html'


class SpiderTestView(TemplateView):
    queryset = []
    template_name = 'webSpider/webSpiderTest.html'

# [eSpider debug画面]
class ESpiderDebugView(TemplateView):
    queryset = []
    template_name = 'webSpider/eSpiderDebug.html'