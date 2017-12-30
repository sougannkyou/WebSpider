# coding=utf-8
from django.conf.urls import patterns, url
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.cache import cache_page

from .views import (
    SimulatorView, GuideView, SpiderTestView, DashBoardView,
    MainView, WebSpiderHubView, WebSpiderDetailView, ESpiderDebugView
)

from .restAPI import (
    getLoadJSAPI,
    getHtmlAPI, getNavInfoAPI, getHubUrlAPI, MainViewAPI,
    DetailXPathViewAPI, HubXPathViewAPI, makeJsonAndCodeAPI, getEntryPaginatorAPI, restoreHubsAPI, restoreDetailAPI,
    getTaskCodeAPI, startTaskAPI, stopTaskAPI,
    addTaskInfoAPI,
    getSimulationResultAPI, runSimulationScriptAPI,
    checkServiceActiveAPI, getTaskStatusAPI, startTestAPI, stopTestAPI, getTestResultAPI,
    getXGJSParameterAPI, saveXGSJAPI, gotoXGSJAPI
)

cache_time_out = 60 * 3

urlpatterns = patterns('',
                       url(r'^simulator/$', SimulatorView.as_view(), name='simulator'),
                       url(r'^guide/$', GuideView.as_view(), name='guide'),
                       url(r'^board/$', DashBoardView.as_view(), name='board'),
                       url(r'^main/$', MainView.as_view(), name='main'),
                       url(r'^hubs/$', WebSpiderHubView.as_view(), name='hubs'),
                       url(r'^detail/$', WebSpiderDetailView.as_view(), name='detail'),
                       url(r'^spiderTest/$', SpiderTestView.as_view(), name='spiderTest'),
                       url(r'^espider/$', ESpiderDebugView.as_view(), name='espider'),

                       url(r'^mainAPI/$', MainViewAPI.as_view(), name='mainAPI'),
                       url(r'^hubXPathAPI/$', HubXPathViewAPI.as_view(), name='hubXPathAPI'),
                       url(r'^detailXPathAPI/$', DetailXPathViewAPI.as_view(), name='detailXPathAPI'),

                       url(r'^getLoadJSAPI/$', getLoadJSAPI, name='getLoadJSAPI'),
                       url(r'^getHtmlAPI/$', getHtmlAPI, name='getHtmlAPI'),
                       # url(r'^getNodesAPI/$', getNodesAPI, name='getNodesAPI'),
                       url(r'^getNavInfoAPI/$', getNavInfoAPI, name='getNavInfoAPI'),
                       url(r'^getHubUrlAPI/$', getHubUrlAPI, name='getHubUrlAPI'),
                       url(r'^restoreHubsAPI/$', restoreHubsAPI, name='restoreHubsAPI'),
                       url(r'^restoreDetailAPI/$', restoreDetailAPI, name='restoreDetailAPI'),

                       url(r'^makeJsonAndCodeAPI/$', makeJsonAndCodeAPI, name='makeJsonAndCodeAPI'),
                       url(r'^getEntryPaginatorAPI/$', getEntryPaginatorAPI, name='getEntryPaginatorAPI'),

                       url(r'^getTaskCodeAPI/$', getTaskCodeAPI, name='getTaskCodeAPI'),
                       url(r'^startTaskAPI/$', startTaskAPI, name='startTaskAPI'),
                       url(r'^stopTaskAPI/$', stopTaskAPI, name='stopTaskAPI'),

                       url(r'^getSimulationResultAPI/$', getSimulationResultAPI, name='getSimulationResultAPI'),
                       url(r'^runSimulationScriptAPI/$', runSimulationScriptAPI, name='runSimulationScriptAPI'),

                       url(r'^addTaskInfoAPI/$', addTaskInfoAPI, name='addTaskInfoAPI'),

                       url(r'^checkServiceActiveAPI/$', checkServiceActiveAPI, name='checkServiceActiveAPI'),
                       url(r'^getTaskStatusAPI/$', getTaskStatusAPI, name='getTaskStatusAPI'),
                       url(r'^startTestAPI/$', startTestAPI, name='startTestAPI'),
                       url(r'^stopTestAPI/$', stopTestAPI, name='stopTestAPI'),
                       url(r'^getTestResultAPI/$', getTestResultAPI, name='getTestResultAPI'),

                       url(r'^getXGJSParameterAPI/$', getXGJSParameterAPI, name='getXGJSParameterAPI'),
                       url(r'^saveXGSJAPI/$', saveXGSJAPI, name='saveXGSJAPI'),
                       url(r'^gotoXGSJAPI/$', gotoXGSJAPI, name='gotoXGSJAPI'),
                       )
