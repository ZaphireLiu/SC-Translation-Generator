'''
翻译文本生成程序的主逻辑
0. ini文件格式为`text_id=text_content`，每行一个
1. 匹配规则保存在json列表里，各个规则依次试图匹配，如果匹配成功，则按照对应的生成规则，使用多个ini文件（目前就是en的英文原文和zh的汉化）来生成目标翻译文件
'''

import os, re, json
from enum import Enum
        
class RegexPattern(Enum):
    """正则表达式模式枚举类
    
    用于存储各种预定义的正则表达式模式
    """
    TEXT_ONELINE = r'^.*=.*$'  # 匹配文本文件内的单行

class RuleProcessor(object):
    """规则处理器
    
    单例模式实现的规则处理器，用于加载和处理文本规则
    """
    _instance   = None  # 单例实例
    
    def __new__(cls):
        """创建单例实例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, text_file_dir: str = None, rule_file_path: str = None):
        """初始化规则处理器
        
        Args:
            text_file_dir (str, optional): 文本文件目录. Defaults to None.
            rule_file_path (str, optional): 规则文件路径. Defaults to None.
        """
        # 初始化文本字典和规则列表
        if not hasattr(self, '__text_dict') or self.__text_dict is None:
            self.__text_dict = {}
        if not hasattr(self, '__rule_list') or self.__rule_list is None:
            self.__rule_list = []
        
        # 加载翻译文本
        if text_file_dir is None:
            current_path  = os.path.abspath(__file__)
            current_dir   = os.path.dirname(current_path)
            parent_dir    = os.path.dirname(current_dir)
            text_file_dir = os.path.join(parent_dir, 'text_files')
        
        if not os.path.exists(text_file_dir):
            raise FileNotFoundError(f"文本文件目录不存在: {text_file_dir}")
            
        self.__load_text_file(text_file_dir)
        
        # 加载规则文件
        rule_file_autoload = rule_file_path is None
        if rule_file_autoload:
            current_path  = os.path.abspath(__file__)
            current_dir   = os.path.dirname(current_path)
            parent_dir    = os.path.dirname(current_dir)
            rule_file_dir = os.path.join(parent_dir, 'rules', 'summary_rules')
            rule_files = [f for f in os.listdir(rule_file_dir) if f.endswith('.json')]
            if len(rule_files) == 0:
                raise FileNotFoundError("规则文件不存在")
            self.__load_rule_file(os.path.join(
                rule_file_dir, rule_files[0]
            ))
        else: self.__load_rule_file(rule_file_path)

    def __load_text_file(self, dirpath: str):
        """加载文本文件
        
        Args:
            dirpath (str): 文本文件目录路径
            
        Raises:
            FileNotFoundError: 文本文件不存在或过少时抛出
            FileNotFoundError: 英语原文文件不存在时抛出
            RuntimeError: 文本文件格式错误时抛出
        """
        text_files = [f for f in os.listdir(dirpath) if f.endswith('.ini')]
        if len(text_files) <= 1:
            raise FileNotFoundError("文本文件不存在或过少")
        if 'en.ini' not in text_files:
            raise FileNotFoundError("英语原文文件不存在")
        for file in text_files:
            filename = file.replace('.ini', '')
            self.__text_dict[filename] = dict()
            file_path = os.path.join(dirpath, file)
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f.readlines():
                    if not re.match(RegexPattern.TEXT_ONELINE.value, line): continue # 跳过不符合格式的行
                    line_text    = line.strip()
                    text_id      = line_text.split('=')[0]
                    text_content = '='.join(line_text.split('=')[1:])
                    self.__text_dict[filename][text_id] = text_content
    
    def __load_rule_file(self, filepath: str) -> None:
        """加载规则json文件

        Args:
            filepath (str): json文件路径
            
        Raises:
            ValueError: 文件不是JSON格式时抛出
            ValueError: 规则格式不正确时抛出
        """
        
        # 检查文件是否存在
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"规则文件不存在: {filepath}")
        
        # 初始化规则列表
        if self.__rule_list is None:
            self.__rule_list = []
        
        try:
            # 读取并解析JSON文件
            with open(filepath, 'r', encoding='utf-8') as f:
                rule_data = json.load(f)
            # 检查是否为列表
            if not isinstance(rule_data, list):
                raise ValueError("规则文件格式错误: 必须是JSON数组")
            # 逐个检查规则对象
            for rule in rule_data:
                # 检查规则格式
                if not isinstance(rule, dict):
                    raise ValueError("规则格式错误: 规则必须是JSON对象")
                # 检查必要属性
                required_attrs = ['type', 'desc', 'sortOrder']
                for attr in required_attrs:
                    if attr not in rule:
                        raise ValueError(f"规则格式错误: 缺少必要属性 '{attr}'")
                # 检查type属性值
                if rule['type'] != "match":
                    raise ValueError(f"规则格式错误: 'type'属性值必须为'match'，当前值为'{rule['type']}'")
                # 检查通过，添加到规则列表
                self.__rule_list.append(rule)
            
            # 可选：按sort_order排序
            self.__rule_list.sort(key=lambda x: x['sortOrder'])
        
        except json.JSONDecodeError:
            raise ValueError(f"规则文件不是有效的JSON格式: {filepath}")
        
    def generate_result(self, target_path: str) -> None:
        """使用规则生成目标翻译文件，对外的主要接口

        Args:
            target_path (str): 文件路径
        """
        # 获取所有文本ID（以英文文件为基准）
        if 'en' not in self.__text_dict:
            raise ValueError("缺少英文文本文件")
        
        all_text_ids = list(self.__text_dict['en'].keys())
        processed_ids = set()  # 已处理的文本ID集合
        results = []  # 存储生成的结果行
        
        # 按规则顺序处理所有文本
        for rule in self.__rule_list:
            # 只处理匹配规则
            if rule['type'] != 'match':
                continue
            
            # 获取替换规则
            replace_rule = None
            if 'replace' in rule:
                replace_rule = rule['replace']
            
            # 逐个检查所有未处理的文本ID
            for text_id in all_text_ids:
                if text_id in processed_ids:
                    continue
                
                # 检查是否匹配规则
                if self.check_match(rule, text_id):
                    # 生成替换文本
                    if replace_rule:
                        result_text = self.apply_replace(replace_rule, text_id)
                        results.append(f"{text_id}={result_text}")
                    else:
                        # 如果没有替换规则，则保留原文
                        results.append(f"{text_id}={self.__text_dict['en'][text_id]}")
                    
                    # 标记为已处理
                    processed_ids.add(text_id)
        
        # 处理未匹配任何规则的文本ID（默认保留英文原文）
        for text_id in all_text_ids:
            if text_id not in processed_ids:
                results.append(f"{text_id}={self.__text_dict['en'][text_id]}")
        
        # 写入结果文件
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(results))
    
    def apply_replace(self, replace_rule: dict, text_id: str) -> str:
        """应用替换规则到文本ID
        
        Args:
            replace_rule (dict): 替换规则字典
            text_id (str): 文本ID
            
        Returns:
            str: 替换后的文本内容
        """
        result = ""
        
        # 确保替换规则包含规则列表
        if 'rule' not in replace_rule or not isinstance(replace_rule['rule'], list):
            return self.__text_dict['en'].get(text_id, "")
        
        # 逐个应用替换规则元素
        for item in replace_rule['rule']:
            item_type = item.get('type', '')
            
            if item_type == 'plainText':
                # 添加纯文本
                result += item.get('value', '')
            
            elif item_type == 'iniText':
                # 添加指定语言的文本内容
                lang = item.get('value', 'en')
                if lang in self.__text_dict and text_id in self.__text_dict[lang]:
                    result += self.__text_dict[lang][text_id]
                else:
                    # 如果指定语言的文本不存在，则使用英文
                    result += self.__text_dict['en'].get(text_id, "")
            
            elif item_type == 'newLine':
                # 添加换行符
                result += '\n'
        
        return result
    
    def check_match(self, match_rule: dict, text_id: str) -> bool:
        """检查文本ID是否匹配规则
        
        Args:
            match_rule (dict): 匹配规则字典
            text_id (str): 文本ID
            
        Returns:
            bool: 是否匹配
        """
        # 检查规则是否包含matchType
        if 'matchType' not in match_rule:
            return False
        
        match_type = match_rule['matchType']
        rule_content = match_rule.get('rule', None)
        reject = match_rule.get('reject', False)
        match_all = match_rule.get('matchAll', False)
        
        # 根据匹配类型调用对应的规则函数
        if match_type == 'regex':
            if not isinstance(rule_content, str):
                return False
            return self.rulebase_regex(rule_content, text_id, reject)
        
        elif match_type == 'tag':
            if not isinstance(rule_content, list):
                return False
            return self.rulebase_tag(rule_content, text_id, match_all, reject)
        
        elif match_type == 'string':
            if not isinstance(rule_content, str):
                return False
            return self.rulebase_string(rule_content, text_id, match_all, reject)
        
        elif match_type == 'default':
            return self.rulebase_default(text_id)
        
        # 未知匹配类型
        return False
    
    ''' 规则库 '''
    def rulebase_regex(self, regex_pattern: str, text_id: str, reject: bool = False) -> bool:
        """用正则表达式匹配id

        Args:
            regex_pattern (str): 正则表达式
            text_id (str): 文本id

        Returns:
            bool: 是否匹配
        """
        try:
            pattern = re.compile(regex_pattern)
            if pattern.search(text_id):
                return True if not reject else False
            return False if not reject else True
        except re.error:
            # 正则表达式格式错误
            return False if not reject else True

    def rulebase_tag(self, tags: list, text_id: str, match_all: bool = False, reject: bool = False) -> bool:
        """用下划线分割文本id，将分割出的部分作为标签进行匹配

        Args:
            tags (list): 匹配标签列表
            text_id (str): 文本id
            match_all (bool, optional): 是否要求完全匹配. Defaults to False.

        Returns:
            bool: 是否匹配
        """
        if not tags:
            return False
        
        text_tags = text_id.split('_')
        
        if match_all:
            # 要求所有 tags 都在文本标签中
            return all(tag in text_tags for tag in tags) if not reject else not all(tag in text_tags for tag in tags)
        else:
            # 只要有一个 tag 在文本标签中即可
            return any(tag in text_tags for tag in tags) if not reject else not any(tag in text_tags for tag in tags)

    def rulebase_string(self, match_target: str, text_id: str, match_all: bool = False, reject: bool = False) -> bool:
        """直接比较

        Args:
            match_target (str): 目标
            text_id (str): 文本id
            match_all (bool, optional): 是否要求完全匹配，False则`match_target`在`text_id`中即可. Defaults to False.

        Returns:
            bool: 是否匹配
        """
        if match_all:
            # 完全匹配要求 text_id 与 match_target 完全相等
            return text_id == match_target if not reject else text_id != match_target 
        else:
            # 部分匹配要求 match_target 是 text_id 的子串
            return match_target in text_id if not reject else match_target not in text_id

    def rulebase_default(self, text_id: str, *args, **kwargs) -> bool: return True