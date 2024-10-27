from abc import abstractmethod
from configparser import ConfigParser
from functools import partialmethod, update_wrapper
from pathlib import Path
from typing import Generic, TypeVar

T = TypeVar('T')


class Value[T](property):
    def __init__(self, default=None, doc=None):
        super().__init__(self.get_value, doc=doc)
        self.default = default

    def __set_name__(self, owner, name):
        self.name = name

    @abstractmethod
    def get_value(self, owner: 'Config') -> T:
        ...


class IntValue(Value[int]):
    def get_value(self, owner: 'Config') -> int:
        return owner.getint(self.name, self.default)


class StrValue(Value[str]):
    def get_value(self, owner: 'Config') -> str:
        return owner.getstr(self.name, self.default)


class BoolValue(Value[bool]):
    def get_value(self, owner: 'Config') -> bool:
        return owner.getboolean(self.name, self.default)


class ConfigBase:
    SECTIONNAME = 'timeline'

    def __init__(self):
        # TODO: on python 13.0, add allow_unnamed_section=True
        self.parser = ConfigParser(empty_lines_in_values=False)
        self.parser.optionxform = self.optionxform
        self.parser.read([
            '/etc/timeline.conf',
            Path('~/.config/timeline.conf').expanduser(),
            'timeline.conf',
        ])

    @staticmethod
    def optionxform(optionstr):
        # do not change the case of keys
        return optionstr

    def getstr(self, key: str, fallback: str = None) -> str:
        return self.parser.get(self.SECTIONNAME, key, fallback=fallback)

    def getint(self, key: str, fallback: int = None) -> int:
        return self.parser.getint(self.SECTIONNAME, key, fallback=fallback)

    def getboolean(self, key: str, fallback: bool = None) -> bool:
        return self.parser.getboolean(self.SECTIONNAME, key, fallback=fallback)


class Config(ConfigBase):
    MainFile = StrValue('notes.tln')
    FuzzySearchTolerance = IntValue(75)
    Locale = StrValue('C')
    FilterHistoryCount = IntValue(10)
    FilterHistorySize = IntValue(100000000)
    CaseSensitiveLeave = BoolValue(False)
    CaseSensitiveSearch = BoolValue(False)


config = Config()
__all__ = ['config']
