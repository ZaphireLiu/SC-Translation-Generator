# `process.py`

翻译文本生成程序的主逻辑
1. ini文件格式为`text_id=text_content`，每行一个
2. 匹配规则保存在json列表里，各个规则依次试图匹配，如果匹配成功，则按照对应的生成规则，使用多个ini文件（目前就是en的英文原文和zh的汉化）来生成目标翻译文件

## 文本文件

所有的文本文件都是ini文件。
格式为`text_id=text_content`，每行一条文本id和文本内容的键值对。
第一个等号前的内容视作文本id，第一个等号作为分隔符，后面的内容（包括更多的等号）都视作文本内容。

## 规则文件

所有的规则文件都是json文件。

### 单规则文件

每个单规则文件内保存一个规则，用于生成最后的整合规则文件。

单规则文件里面只有一个json对象，保存着。。。规则。
规则分为`match`（匹配规则）和`replace`（生成规则）两种，一个完整的规则是由多个子规则层层嵌套完成的。单规则文件的具体格式如下：
1. 一层规则的基本属性包括：
    1. `type`: 表明自己是匹配规则还是生成规则。可选值为`match`（匹配规则）或`replace`（生成规则）
    2. `desc`: 字符串，可以为空字符串，描述。
2. 对于`type == match`的匹配规则，额外的属性包括：
    1. `matchType`: 匹配规则，可选项（目前）包括：
        1. `regex`: 正则表达式匹配
        2. `tag`: 标签匹配（标签的含义后面会说明）
        3. `string`: 单纯的比较匹配
        4. `default`: 全匹配
    2. `rule`: 匹配规则的内容：
        1. 对于`matchType == regex`: 一个字符串，即正则表达式
        2. 对于`matchType == tag`: 一个列表，保存所有的标签
        3. 对于`matchType == string`: 一个字符串，需要比较的对象
        4. 对于`matchType == default`: 无意义，可以直接不包括本条属性
    3. `reject`: 布尔值：
        1. `false`: 匹配成功的视作通过规则
        2. `true`: 匹配成功的视作不通过规则，对于`default`此项规则不起作用，即对于`matchType == default`，`reject`必须为`false`，或直接不包括本条属性
    4. `matchAll`: 布尔值，`matchType == tag`或`matchType == string`才有意义的属性：
        1. 对于`matchType == tag`: `true`则要求id的标签列表里存在所有标签视作成功，`false`则至少匹配一个即视作成功
        2. 对于`matchType == string`: `true`则要求id和`rule`完全相同，`false`则`rule`的内容存在于id中即可（即python里的`if rule in id`）
3. 对于`type == replace`的匹配规则，额外的属性包括`rule`，值是一个列表，每个元素为一个json对象，元素对象的属性包括：
    1. `type`: 本元素需要填充进结果的是什么，可选项包括：
        1. `plainText`: 文本
        2. `iniText`: 需要从ini文本里找的原文/翻译文本
        3. `newLine`: 换行符
    2. `value`: 仅对`type != newLine`有意义
        1. 对`type == plainText`: 字符串，需要填充进去的纯文本
        2. 对`type == iniText`: 字符串，选择的ini文本文件。例：`"value": "zh"`，则需要从`zh.ini`里（实际已经存进python的字典里了）找到文本id对应的文本内容填充进结果。

**标签说明**
在文本文件内，每行的id都是以下划线格式命名的字符串，例如`ATC_Lorville_Gate04`。这样的id被视为拥有三个标签：`['ATC', 'Lorville', 'Gate04']`。标签绝大多数都是字母和数字，但有时有其他符号，比如英文逗号

### 多规则文件（整合文件）

json文件，最外层结构为一个数组，里面每个元素都是一个规则对象。
规则对象除了在单规则里面的所有属性，还包括一个属性`sortOrder`，规定了各个规则的应用顺序（sortOrder更小的有更高的优先级），默认情况下，最前面的应对应的有更高优先级。

## 处理规则

### 匹配规则

匹配规则的执行规则为：
1. 对于尚未匹配的文本，最外层主规则按sortOrder依次运行
2. 每次开始一个主规则，逐层向下检查，若全部满足，则将这行文本按照生成规则生成后从未匹配库里剔除，等最后统一插入新的目标翻译文本文件内
3. 用一个主规则试图匹配完所有文本后，使用下一个主规则再次匹配，如此重复

### 生成规则

匹配规则的执行规则为：按照各个规则依次向结果里拼接，例如：
1. `type=plaintext, value=[`
2. `type=iniText, value=zh`
3. `type=plaintext, value=]`
4. `type=iniText, value=en`
的一个规则，对于成功匹配的一条文本，id为`item_copper`，英文文本为`copper`，中文文本为`铜`，则最终生成结果为`item_copper=[铜]copper`