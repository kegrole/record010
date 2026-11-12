# 多源数据实体解析与冲突合并工具

本工具只使用 Python 标准库，读取目录中的 CSV 与 JSON 来源文件，完成字段归一化、实体候选生成、相似度匹配、可信级别合并、冲突留存，并输出 SQLite 与 JSON。

## 目录与命令

    python -m entityresolve.cli --sources demo/sources --db out/entities.db --out out/entities.json

来源目录中的 .csv 与 .json 文件都会按文件名排序读取。JSON 支持顶层数组，或 { "records": [...] } 对象。

来源可信级别可通过文件名后缀提供，例如 source_a__3.csv 表示默认可信级别 3；记录中的 trust_level、trust 或 _trust_level 可以覆盖文件默认值。记录中的 source 或 _source 提供来源名，缺省时使用文件名主体。可信级别只能是 1、2、3，3 最高。

## 字段别名

| 标准字段 | 部分别名 |
| --- | --- |
| name | userName、user_name、姓名 |
| phone | phone、mobile、手机号、手机号码 |
| email | email、mail、email_address、邮箱 |
| created_at | createdAt、created_at、创建时间 |
| city | city、city_name、城市 |
| order_id | orderId、order_id、订单号 |

别名匹配会统一大小写、全角半角、空格和下划线。可在代码中通过 AliasResolver.add_alias(canonical_field, alias) 扩展，也可向 AliasResolver(...) 传入自定义别名表。

## 值归一化

- 普通文本：统一全角半角、大小写，折叠连续空白并去除首尾空白。
- 日期：统一输出 YYYY-MM-DD，支持 2024-01-02、2024/1/2、2024年1月2日、ISO 8601 日期时间和带时区时间。
- 手机号：保留数字，剥离 +86、0086、空格和连字符，最终输出 11 位中国大陆手机号；国家码后的本地号码存在额外重复零分隔符时，先归一重复零再截取合法移动号码。
- 邮箱：去除内部空白，统一全角半角并转小写。

## 候选与相似度

1. 先按强标识 phone 与 email 分桶；相同强标识的记录进入同一候选集合。
2. 没有强标识的记录才参与姓名候选，避免仅因姓名相近而覆盖手机号或邮箱不同的记录。
3. 姓名首字相同或字符多重集合相同的记录进入候选，再计算 Damerau-Levenshtein 距离。
4. distance.levenshtein(left, right) 与 distance.damerau_levenshtein(left, right) 可单独调用；后者把相邻字符换位计为 1。
5. 归一化姓名的 Damerau-Levenshtein 距离不超过 1 时判为同一实体。

## 合并与冲突

每个字段先比较不同归一化值的最高来源可信级别：

- 唯一最高可信值进入 entities，较低可信值进入 entity_conflicts，状态为 resolved。
- 多个不同值拥有相同最高可信级别时，该字段不进入实体结果（SQLite 动态列中为 NULL，JSON 实体不包含该键），每个候选值写一条冲突，kept_value 与 kept_source 为空，状态为 unresolved。
- 实体编号、字段顺序和冲突顺序都按稳定键排序，不依赖文件系统遍历顺序或记录输入顺序。

SQLite 输出包含：

- entities：必有 entity_id，其余列为该批数据出现过的标准字段。
- entity_conflicts：包含 entity_id、field、kept_value、dropped_value、kept_source、status。前五个是验收要求字段，status 用于标记 unresolved。

JSON 输出包含 entities 与 conflicts 两个顶层键。

## 测试

    python -m unittest test_entityresolve -v

测试夹具位于 fixtures/sources，demo 数据位于 demo/sources。测试覆盖 11 条记录合并为 4 个实体、手机号与日期归一、姓名换位、可信优先、同级冲突、负例、输出表结构和输入顺序无关性。
