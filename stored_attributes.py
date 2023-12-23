#!/usr/bin/env python3

import json
import os

# {
#    "Monitor": {               Klasse
#       "del2433": {            represents instance, string key is from an attribute of it
#          "Setting": {         "special" attribute, which stores Setting class children,
#                                (children of other classes might also exist → other attribute)
#              "brightness": {  again: represents instance...
#                   min: 10,    "normal" attribute, represents its value "only" (lower case name)
#                   delay: 30,  also normal attribute
#               },
#               "contrast": {...}
#          },
#          edid: b"xxxxxx"
#       },
#       "BNQ1234": {
#       },
#    },
# }

class ConfigProperty:
    def __init__(self, jsc):
        self.json_config = jsc

    def __set_name__(self, cls, attr_name):  # python3.6?
        self._attr_name = attr_name
        try:
            descriptors = cls._jsc_descriptors
        except AttributeError:
            cls._jsc_descriptors = descriptors = dict()
        descriptors[attr_name] = self

    def __set__(self, obj, value):
        obj._jsc_dict[self._attr_name] = value
        self.json_config.json_write()

    def __get__(self, obj, obj_type=None):
        return self if obj is None else obj._jsc_dict[self._attr_name]

    def _json(self, obj):
        return self._attr_name, obj._jsc_dict[self._attr_name]


class DistinguishingConfigProperty(ConfigProperty):
    def __set__(self, obj, value):
        obj._jsc_id = value

    def __get__(self, obj, obj_type = None):
        return obj._jsc_id

    def _json(self, obj):
        # does not represent itself
        return None

class ChildrenArrayProperty(ConfigProperty):
    def __get__(self, obj, obj_type=None):
        return self if obj is None else obj._jsc_dict[self._attr_name]

    def __set__(self, obj, value):
        obj._jsc_dict[self._attr_name] = value

    def _json(self, obj):
        return self._attr_name, {child._jsc_id: child for child in self.__get__(obj)}



# https://docs.python.org/3/howto/descriptor.html#invocation-from-an-instance
def find_name_in_mro(cls, name, default):
    for base in cls.__mro__:
        if name in vars(base):
            return vars(base)[name]
    return default

def is_config_prop(instance, name):
    return isinstance(find_name_in_mro(type(instance), name, None), ConfigProp)

class JsonEncodable:
    def json_repr(self):
        return {k: getattr(self, k) for k in dir(self) if is_config_prop(self, k)}

class ConfigEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, 'json_repr'):
            return obj.json_repr()
        else:
            return super().default(obj)


class JsonConfig:
    def __init__(self, file_name):
        self._file_name = file_name
        try:
            json_file = open(file_name)
        except FileNotFoundError:
            self.config = {}
        else:
            with json_file:
                self.config = json.load(json_file) if os.fstat(json_file.fileno()).st_size else {}

    def _rewrite_json(self):
        with open(self._file_name, 'w+') as json_file:
            json.dump(self.config, json_file, cls=ConfigEncoder)


    def is_root(self, class_name):
        self.config[class_name] = {}

    def distinguishing_prop(self):
        pass
    def children_array(self):
        pass

    def stored_attr(self, name):
        def getter(instance):
            print('getter')
            return self.config[name]
        def setter(instance, value):
            print('setter')
            self.config[name] = value
            self._rewrite_json()
        return property(getter, setter)

js = JsonConfig('test_config.json')

class Setting:
    name = js.distinguishing_prop()
    delay = js.stored_attr()

    def __init__(self, name):
        self.name = name

class Monitor:
    js.is_root('Monitor')

    def __init__(self, name):
        self.name = js.distinguishing_prop(self, name)
        self.settings = js.children_array(self, 'settings')


new = True
if new:
    c = C('one')
    c.sth = 4
    print(c.sth)
else:
    c = C('one')
    print('c.sth is:', c.sth)
