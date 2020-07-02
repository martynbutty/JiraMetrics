from functools import reduce
import operator
import yaml


class Config:

    def __init__(self, yaml_stream):
        self.yaml_config = None

        self.yaml_config = yaml.load(yaml_stream)

    def read_config_key(self, key, default=None):
        try:
            if type(key) is list or type(key) is tuple:
                return reduce(operator.getitem, key, self.yaml_config)
            else:
                return self.yaml_config[key]
        except KeyError:
            return default

    def get_quoted_list(self, key, default=None):
        """
        With a give config file key, read that config, quote all individual items for that keys values and return.
        This is useful when we need the values in the config to quoted for use in things like SQL and JQL

        :param key: The config file key to get the data from
        :param default: default value to return if no data for that key
        :return: quoted data from keys value, else default value if not found
        """

        things = self.read_config_key(key, default)

        quoted_items = []
        for thing in things:
            new_item = '"' + thing + '"'
            quoted_items.append(new_item)

        return quoted_items

    def get_quoted_cs_string(self, key, default=None):
        """
        For a given config key, read it's values, quote each individual value, then combine into comma separated list
        """
        quoted_list = self.get_quoted_list(key, default)
        quoted_cs_string = ','.join(map(str, quoted_list))

        return quoted_cs_string
