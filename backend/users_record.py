# coding:utf-8
from backend_admin.models import UserLog


# 用户操作类型判断
# 记录用户信息

def record(user, app_label, objtype, obj, operate_type, operate, comment, time):
    '''

    :param user: 用户id
    :param app_labbel: 所在
    :param objtype: 对象类型
    :param obj: 具体对象
    :param operate_type: 操作类型
    :param operate: 操作
    :param comment: 备注
    :param time: 时间
    :return:
    '''
    u_record = UserLog(user_id=user.id, app_label=app_label, author=user.nickname, obj_type=objtype, obj=obj,
                       operate_type=operate_type, operate=operate, comment=comment, time=time)
    u_record.save()
