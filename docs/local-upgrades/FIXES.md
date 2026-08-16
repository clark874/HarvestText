# 本地化缺陷修复记录（v0.8.1.7-cn.2）

结合双评估（GLM 源码诊断 + Codex 实测审计）修复三处已证实缺陷，6/6 专项测试通过。

## Fix 1: save→load 往返污染
- **缺陷**: `save_entity_info` 写入"类型||类型"标题行，`load_entities` 未排除 → 类型名（"生态名"等34个）被登录为实体
- **修复**: load 中 `if entity == etype: continue`
- **测试**: `TestRoundtripNoPollution` — 往返后类型名不得出现在 entity_type_dict

## Fix 2: 保存不确定性与自重复
- **缺陷**: ① set 迭代序不稳定 → 同内容不同字节/SHA（实测：2024-04~07 十四份快照语义全同而哈希各异）② 实体 100% 作为自身别称重复写入
- **修复**: ① mentions 排序输出 ② 剔除与实体相同的别称（load 会自动补回，往返语义不变）③ GBK 排序加 UTF-8 回退（英文实体不再崩溃）
- **测试**: `TestSaveDeterminism`（字节级相同）+ `TestGbSortSafety`（中英混存）

## Fix 3: build_word_graph flag_add NameError
- **缺陷**: `pos_filter=False + flag_add=True`（有停用词）分支中 `f'{x}_{flag}'` 引用 flag，但生成器为 `for x in self.seg(...)`（返回字符串，flag 未绑定）→ NameError
- **修复**: 该分支改用 `self.posseg`（返回 (词, 词性) 元组）
- **测试**: `TestBuildWordGraphFlagAdd`
- **遗留警告**: 历史项目（如《十九大二十大词汇网络ht.py:165》）调用 `community_louvain.best_partition(G, weight="tfidf")`，但图的边只有 `weight` 属性、tfidf 在节点上 → 聚类实际未按预期 TF-IDF 运行。**此为历史结果解读问题，需在论文复现时重新审视，不在本次代码修复范围。**

## 附: 资源文件补齐
sdist 缺 `harvesttext/resources/`（pinyin_adjlist.json 等 7 文件 6.6MB），全新检出无法运行。已从生产环境补齐入版本库。

## 附: 字典资产审计
`tools/dict_audit.py` + `dicts/audit/`：25 文件全量解析，并集 8599 实体，399 跨类型冲突 + 37 多归属别称，语义哈希识别出 14 份字节序漂移快照。entries_union.jsonl 为 v2 canonical 迁移输入。
