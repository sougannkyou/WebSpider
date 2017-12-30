# -*- coding: utf-8 -*-
class BackendDBRouter(object):
    """A router to control all database operations on models in
    the myapp application"""

    def db_for_read(self, model, **hints):
        "Point all operations on myapp models to 'other'"
        return self.__app_router(model)

    def db_for_write(self, model, **hints):
        "Point all operations on myapp models to 'other'"
        return self.__app_router(model)

    def allow_relation(self, obj1, obj2, **hints):
        "Allow any relation if a model in myapp is involved"
        return obj1._meta.app_label == obj2._meta.app_label

    def allow_syncdb(self, db, model):
        return self.__app_router(model) == db
    # print "model._meta.app_label = %s, db = %s", (model._meta.app_label, db)
    "Make sure the myapp app only appears on the 'other' db"

    def __app_router(self, model):
        if model._meta.app_label == 'config':
            return 'config'
        else:
            return 'default'
