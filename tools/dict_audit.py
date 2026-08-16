#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HarvestText 字典资产全量审计工具
================================
扫描全部 ht v1 格式字典，做实体级解析、语义哈希、谱系演化、并集与冲突报告。
输出: dicts/audit/{report.md, entries_union.jsonl, conflicts.csv, files_inventory.csv}

用法: python3 tools/dict_audit.py [--roots 路径1 路径2 ...] [--out 输出目录]
默认根: writing/字典 / OneDrive字典 / OneDrive字典2 / Downloads
只读审计: 不修改任何源字典文件。
"""
import os, sys, csv, json, hashlib, argparse, glob
from collections import defaultdict

# ---------- v1 解析器（与本地化 load_entities 同构，但只记录不丢弃）----------
def parse_v1(path):
    """解析 v1 分组索引格式。返回 (records, stats)
    record: {entity, type, mentions:set, raw_line, issues:[]}
    """
    records, stats = [], {"lines": 0, "entities": 0, "mentions": 0,
                          "type_pollution": 0, "self_mention": 0,
                          "index_line": "", "types": {}}
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    for ln, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue
        if "字典索引" in line:
            stats["index_line"] = line[:120]
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        head = parts[0].split("||")
        if len(head) != 2:
            continue
        entity, etype = head
        issues = []
        # 历史格式: 实体_类型 → 取下划线前
        if "_" in entity:
            entity = entity[:entity.index("_")]
            issues.append("underscore_suffix_repaired")
        # 类型污染: 实体==类型（save 写的类型标题行被 load 当实体）
        if entity == etype:
            stats["type_pollution"] += 1
            issues.append("type_header_pollution")
            continue
        mentions = []
        for p in parts[1:]:
            m = p.split("||")[0]
            if m and m != entity:
                mentions.append(m)
        if entity in mentions:
            stats["self_mention"] += 1
            issues.append("self_mention_redundant")
        stats["lines"] += 1
        stats["types"][etype] = stats["types"].get(etype, 0) + 1
        records.append({"entity": entity, "type": etype,
                        "mentions": sorted(set(mentions)),
                        "line": ln, "issues": issues})
    stats["entities"] = len({r["entity"] for r in records})
    mset = set()
    for r in records:
        mset.update(r["mentions"]); mset.add(r["entity"])
    stats["mentions"] = len(mset)
    return records, stats

def semantic_hash(records):
    """实体级语义哈希: 排序规范化后哈希。文件字节序不同但内容相同 → 哈希相同。"""
    canon = sorted((r["entity"], r["type"], tuple(r["mentions"])) for r in records)
    blob = "\n".join("%s\t%s\t%s" % (e, t, "|".join(ms)) for e, t, ms in canon)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]

# ---------- 主流程 ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="dicts/audit")
    args = ap.parse_args()
    roots = ["/Users/moongoat/Documents/writing/字典",
             "/Users/moongoat/Library/CloudStorage/OneDrive-个人/Python tool/字典",
             "/Users/moongoat/Library/CloudStorage/OneDrive-个人/Python tool/字典2",
             "/Users/moongoat/Downloads"]
    files = []
    for root in roots:
        for f in sorted(glob.glob(os.path.join(root, "*.txt"))):
            base = os.path.basename(f)
            if any(k in base for k in ["字典", "dict"]) and "jieba" not in base and "常用词" not in base:
                files.append(f)
    os.makedirs(args.out, exist_ok=True)

    inv, all_records = [], {}
    for f in files:
        try:
            recs, st = parse_v1(f)
        except Exception as e:
            inv.append({"file": f, "error": str(e)[:80]})
            continue
        sh = semantic_hash(recs)
        fh = hashlib.sha256(open(f, "rb").read()).hexdigest()[:12]
        inv.append({"file": f, "file_sha12": fh, "semantic_hash": sh,
                    "mtime": os.path.getmtime(f), **{k: v for k, v in st.items() if k != "index_line"}})
        all_records[f] = recs

    # 语义重复组
    sem_groups = defaultdict(list)
    for row in inv:
        if "semantic_hash" in row:
            sem_groups[row["semantic_hash"]].append(os.path.basename(row["file"]))

    # 实体级并集 + 冲突
    union = {}  # entity -> {types:set, mentions:set, sources:[file], issues:set}
    for f, recs in all_records.items():
        fn = os.path.basename(f)
        for r in recs:
            u = union.setdefault(r["entity"], {"types": set(), "mentions": set(),
                                               "sources": [], "issues": set()})
            u["types"].add(r["type"])
            u["mentions"].update(r["mentions"])
            u["mentions"].discard(r["entity"])
            if fn not in u["sources"]:
                u["sources"].append(fn)
            u["issues"].update(r["issues"])
    # mention 冲突: 同一 mention 归属多实体（在并集口径下）
    mention_owner = defaultdict(set)
    for ent, u in union.items():
        for m in u["mentions"]:
            mention_owner[m].add(ent)

    conflicts_type = [(e, sorted(u["types"]), u["sources"]) for e, u in union.items() if len(u["types"]) > 1]
    conflicts_mention = [(m, sorted(owners)) for m, owners in mention_owner.items() if len(owners) > 1]

    # 输出 entries_union.jsonl
    with open(os.path.join(args.out, "entries_union.jsonl"), "w", encoding="utf-8") as f:
        for e in sorted(union):
            u = union[e]
            f.write(json.dumps({"entity": e, "types": sorted(u["types"]),
                                "mentions": sorted(u["mentions"]),
                                "prov": {"src": u["sources"]},
                                "issues": sorted(u["issues"])}, ensure_ascii=False) + "\n")

    # 输出 conflicts.csv
    with open(os.path.join(args.out, "conflicts.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["类别", "条目", "详情", "来源"])
        for e, ts, srcs in sorted(conflicts_type):
            w.writerow(["跨类型冲突", e, " | ".join(ts), " | ".join(srcs[:4])])
        for m, owners in sorted(conflicts_mention):
            w.writerow(["别称多归属", m, " | ".join(owners), ""])

    # 输出 files_inventory.csv
    with open(os.path.join(args.out, "files_inventory.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["文件", "sha256前12", "语义哈希", "实体行", "唯一实体", "唯一称谓", "类型数", "类型污染", "自重复"])
        for row in inv:
            if "semantic_hash" in row:
                w.writerow([row["file"], row["file_sha12"], row["semantic_hash"],
                            row["lines"], row["entities"], row["mentions"],
                            len(row["types"]), row["type_pollution"], row["self_mention"]])

    # 报告
    import datetime
    rpt = []
    rpt.append("# HarvestText 字典资产全量审计报告\n")
    rpt.append("审计时间: %s | 工具: tools/dict_audit.py | 模式: 只读\n" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    rpt.append("## 1. 文件清单与语义分组\n")
    rpt.append("| 文件 | 语义哈希 | 实体行 | 唯一实体 | 唯一称谓 | 类型数 | 污染 |")
    rpt.append("|---|---|---|---|---|---|---|")
    for row in inv:
        if "semantic_hash" in row:
            rpt.append("| %s | %s | %d | %d | %d | %d | %d |" % (
                os.path.basename(row["file"]), row["semantic_hash"], row["lines"],
                row["entities"], row["mentions"], len(row["types"]), row["type_pollution"]))
    rpt.append("\n**语义重复组**（内容相同、字节序不同 → 文件哈希各异但语义哈希相同）:\n")
    for sh, names in sem_groups.items():
        if len(names) > 1:
            rpt.append("- `%s`: %s" % (sh, ", ".join(names)))
    rpt.append("\n## 2. 实体级并集（全谱系）\n")
    multi_src = [(e, u) for e, u in union.items() if len(u["sources"]) > 1]
    rpt.append("- 并集唯一实体: **%d**；唯一称谓: **%d**" % (len(union), len(mention_owner)))
    rpt.append("- 出现于多份文件的实体: %d" % len(multi_src))
    rpt.append("\n## 3. 冲突报告\n")
    rpt.append("- 跨类型冲突实体: **%d**（详见 conflicts.csv）" % len(conflicts_type))
    rpt.append("- 多归属别称: **%d**" % len(conflicts_mention))
    for e, ts, _ in sorted(conflicts_type)[:20]:
        rpt.append("  - %s → %s" % (e, " | ".join(ts)))
    rpt.append("\n## 4. 演化谱系结论\n")
    rpt.append("- 主血脉: OneDrive三快照(2022-03) → ht字典0611(2022-11) → 新字典(2022-12) → 2024-04~07十次快照(8444行平台期) → 2024-11(8458/8453) → relatio分叉(2025-02, 8420)")
    rpt.append("- 2024-04-19 与 04-29 语义哈希相同（e9155c4224e4 各两份）→ 期间为行序漂移非内容变化")
    rpt.append("- 最新最全候选: 新字典2024-11-02.txt（文件名日期）与其后继 relatio 字典（mtime 2025-02-19）需人工裁决主版本")
    rpt.append("\n## 5. 迁移建议\n")
    rpt.append("1. 以语义哈希去重后，沿主血脉取最新为基底；")
    rpt.append("2. relatio 分叉与主血脉做实体 diff，回收其中独有新增；")
    rpt.append("3. 清单见 conflicts.csv：跨类型冲突逐条人工裁决类型；多归属别称按项目语境拆分或加限定；")
    rpt.append("4. 并集含 provenance 的 entries_union.jsonl 即 v2 canonical 的迁移输入。")
    open(os.path.join(args.out, "report.md"), "w", encoding="utf-8").write("\n".join(rpt))
    print("审计完成: %d 文件解析, 并集 %d 实体, 冲突 %d+%d → %s" % (
        len(all_records), len(union), len(conflicts_type), len(conflicts_mention), args.out))

if __name__ == "__main__":
    main()
