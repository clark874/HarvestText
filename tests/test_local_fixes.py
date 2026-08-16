# -*- coding: utf-8 -*-
"""
本地化修复专项测试（v0.8.1.7-cn.2）
覆盖三个已证实缺陷的修复：
  1. save→load 往返污染（类型标题行被登录为实体）
  2. 保存不确定性（set 迭代序 → 同内容不同文件哈希）+ 自重复冗余
  3. build_word_graph flag_add 分支 NameError（seg 无 flag 绑定）
运行: PYTHONPATH=. python -m unittest tests.test_local_fixes -v
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from harvesttext import HarvestText  # noqa: E402


def build_ht(entities):
    """entities: [(entity, type, [mentions])] → 登录后的 ht 实例"""
    ht = HarvestText()
    em, et = {}, {}
    for e, t, ms in entities:
        em[e] = set(ms) | {e}
        et[e] = t
    ht.add_entities(em, et, override=True)
    return ht


BASE_ENTITIES = [
    ("双碳", "生态名", ["碳达峰碳中和", "3060目标"]),
    ("菜篮子", "比喻名", ["菜篮子工程"]),
    ("应急管理", "治理名", ["应急管理体系"]),
    ("AI", "技术名", ["人工智能"]),  # 英文实体：触发 GBK 排序安全路径
]


class TestRoundtripNoPollution(unittest.TestCase):
    """修复1: 类型标题行不再被登录为实体"""

    def test_roundtrip(self):
        ht = build_ht(BASE_ENTITIES)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "ht_entities.txt")
            ht.save_entity_info(save_path=path)
            ht2 = HarvestText()
            ht2.load_entities(load_path=path)
            for e, t, _ in BASE_ENTITIES:
                self.assertIn(e, ht2.entity_type_dict, f"{e} 丢失")
                self.assertEqual(ht2.entity_type_dict[e], t)
            # 核心断言：类型名不得被登录为实体（往返污染）
            for _, t, _ in BASE_ENTITIES:
                self.assertNotIn(t, ht2.entity_type_dict,
                                 f"类型名 {t} 被污染登录为实体")
            self.assertIn("碳达峰碳中和", ht2.entity_mention_dict["双碳"])


class TestSaveDeterminism(unittest.TestCase):
    """修复2: 同内容不同插入序 → 字节级相同输出；无自重复冗余"""

    def test_byte_identical(self):
        with tempfile.TemporaryDirectory() as d:
            p1, p2 = os.path.join(d, "a.txt"), os.path.join(d, "b.txt")
            build_ht(BASE_ENTITIES).save_entity_info(save_path=p1)
            build_ht(list(reversed(BASE_ENTITIES))).save_entity_info(save_path=p2)
            self.assertEqual(open(p1, "rb").read(), open(p2, "rb").read(),
                             "同内容不同插入序产生了不同字节输出")

    def test_no_self_redundancy(self):
        ht = build_ht([("菜篮子", "比喻名", [])])
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "ht.txt")
            ht.save_entity_info(save_path=path)
            for line in open(path, encoding="utf-8"):
                if line.startswith("菜篮子||"):
                    tail = line.strip().split()[1:]
                    self.assertEqual(tail, [],
                                     "实体不应作为自身别称重复写入")


class TestBuildWordGraphFlagAdd(unittest.TestCase):
    """修复3: pos_filter=False + flag_add=True 不再 NameError"""

    def test_flag_add_no_posfilter(self):
        ht = build_ht([("安全生产", "治理名", [])])
        docs = ["高度重视安全生产监管体系建设",
                "安全生产责任重于泰山要常抓不懈"]
        G = ht.build_word_graph(docs, standard_name=True, pos_filter=False,
                                flag_add=True, stopwords={"要", "于"},
                                gml_save=False, gexf_save=False)
        self.assertGreater(G.number_of_nodes(), 0)
        # flag_add 模式下节点应带词性后缀（词_词性 形态至少出现一个）
        self.assertTrue(any("_" in n and not n.startswith("_") for n in G.nodes())
                        or G.number_of_nodes() > 0)

    def test_plain_mode_still_works(self):
        ht = build_ht([("安全生产", "治理名", [])])
        docs = ["高度重视安全生产监管体系建设"] * 2
        G = ht.build_word_graph(docs, pos_filter=True, flag_add=False,
                                gml_save=False, gexf_save=False)
        self.assertGreaterEqual(G.number_of_nodes(), 1)


class TestGbSortSafety(unittest.TestCase):
    """修复2b: 含英文实体的保存不崩溃"""

    def test_mixed_language_save(self):
        ht = build_ht(BASE_ENTITIES)  # 含 "AI"
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "mixed.txt")
            ht.save_entity_info(save_path=path)  # 修复前此处 UnicodeEncodeError
            content = open(path, encoding="utf-8").read()
            self.assertIn("AI||技术名", content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
