import networkx as nx
from itertools import combinations
from collections import Counter
from collections import defaultdict
import math
from termcolor import colored


class EntNetworkMixin:
    """
    实体网络模块：
    - 根据实体在文档中的共现关系
        - 建立全局社交网络
        - 建立以某一个实体为中心的社交网络
    """

    def build_entity_graph(self,
                           docs,
                           min_freq=0,
                           inv_index={},
                           used_types=[]):
        G = nx.Graph()
        links = {}
        if len(inv_index) == 0:
            for i, sent in enumerate(docs):
                entities_info = self.entity_linking(sent)
                if len(used_types) == 0:
                    entities = set(entity
                                   for span, (entity, type0) in entities_info)
                else:
                    entities = set(entity
                                   for span, (entity, type0) in entities_info
                                   if type0[1:-1] in used_types)
                for u, v in combinations(entities, 2):
                    pair0 = tuple(sorted((u, v)))
                    if pair0 not in links:
                        links[pair0] = 1
                    else:
                        links[pair0] += 1
        else:  # 已经有倒排文档，可以更快速检索
            if len(used_types) == 0:
                entities = self.entity_type_dict.keys()
            else:
                entities = iter(entity
                                for (entity,
                                     type0) in self.entity_type_dict.items()
                                if type0 in used_types)
            for u, v in combinations(entities, 2):
                pair0 = tuple(sorted((u, v)))
                ids = inv_index[u] & inv_index[v]
                if len(ids) > 0:
                    links[pair0] = len(ids)
        for (u, v) in links:
            if links[(u, v)] >= min_freq:
                G.add_edge(u, v, weight=links[(u, v)])
        self.entity_graph = G
        return G

    def build_word_graph(self,
                         docs,
                         standard_name=True,
                         len_filter=2,
                         flag_add=False,
                         pos_filter=True,
                         select_type_set={},
                         min_freq_node=0,
                         min_freq_doc=0,
                         min_freq_edge=0,
                         add_single_edge=False,
                         gml_save=True,
                         gexf_save=True,
                         path=f"G文件",
                         stopwords=None):
        '''
        文本各词语的关系图，每个词语与其他词语的关系是共现次数。
        :param docs: 文本的列表
        :param standard_name: 把所有实体的指称化为标准实体名
        :param len_filter: 词语长度限制
        :param flag_add: 是否添加词性符号
        :param pos_filter: 词语词性限制
        :param select_type_set: 只搜索ht字典中特定类别集合的词语,默认为空{}
        :param min_freq_node: 作为节点加入到图中的词的最小提及次数，用于筛掉可能过多的节点
        :param min_freq_doc: 作为节点加入到图中的词的最小文件出现数量，用于筛掉可能过多的节点
        :param min_freq_edge: 作为边加入到图中的最小共现次数，用于筛掉可能过多的边
        :param add_single_edge: 是否添加删选出的单个词语的边
        :param stopwords: 需要过滤的停用词
        :param gml_save: 是否保存为gml格式图文件
        :param path: 保存的路径, gml_save为True时有效
        :return: G,networxX中的Graph对象
        '''
        pos_filter_list = {
            't',
            'm',
            'q',
            'r',
            'e',
            'y',
            'o',
            'w',
            'c',
            'tg',
            'u',
            'x',
            'z',
            'tg',
            'ug',
            'uj',
            'p',
            'd',
            'f',
            'v',
        }
        if len(select_type_set):
            type_list = set(self.entity_type_dict.values())
            type_list = type_list.difference(select_type_set)
            pos_filter_list_strong = type_list.union(pos_filter_list)
            print(f'文本词汇过滤的词性和词汇类别为：{pos_filter_list_strong}')
        G = nx.Graph()
        links = {}
        count_sum = defaultdict(list)
        count_sum_words = 0
        count_sum_links = 0
        for doc in docs:
            if stopwords:
                if pos_filter:
                    if select_type_set:
                        if flag_add:
                            words = list(f'{x}_{flag}'
                                         for x, flag in self.posseg(
                                             doc, standard_name=standard_name)
                                         if flag not in pos_filter_list_strong
                                         if x not in stopwords
                                         if len(x) >= len_filter)
                        else:
                            words = list(x for x, flag in self.posseg(
                                doc, standard_name=standard_name)
                                         if flag not in pos_filter_list_strong
                                         if x not in stopwords
                                         if len(x) >= len_filter)
                    else:
                        if flag_add:
                            words = list(f'{x}_{flag}'
                                         for x, flag in self.posseg(
                                             doc, standard_name=standard_name)
                                         if flag not in pos_filter_list
                                         if x not in stopwords
                                         if len(x) >= len_filter)
                        else:
                            words = list(x for x, flag in self.posseg(
                                doc, standard_name=standard_name)
                                         if flag not in pos_filter_list
                                         if x not in stopwords
                                         if len(x) >= len_filter)
                    # print(colored("==>> words: ", "green"), words)
                else:
                    if flag_add:
                        words = list(
                            f'{x}_{flag}'
                            for x in self.seg(doc, standard_name=standard_name)
                            if x not in stopwords if len(x) >= len_filter)
                    else:
                        words = list(
                            x
                            for x in self.seg(doc, standard_name=standard_name)
                            if x not in stopwords if len(x) >= len_filter)
                    # print(colored("==>> words: ", "green"), words)
            else:
                if pos_filter:
                    if select_type_set:
                        if flag_add:
                            words = list(f'{x}_{flag}'
                                         for x, flag in self.posseg(
                                             doc, standard_name=standard_name)
                                         if flag not in pos_filter_list_strong
                                         if len(x) >= len_filter)
                        else:
                            words = list(x for x, flag in self.posseg(
                                doc, standard_name=standard_name)
                                         if flag not in pos_filter_list_strong
                                         if len(x) >= len_filter)
                    else:
                        if flag_add:
                            words = list(f'{x}_{flag}'
                                         for x, flag in self.posseg(
                                             doc, standard_name=standard_name)
                                         if flag not in pos_filter_list
                                         if len(x) >= len_filter)
                        else:
                            words = list(x for x, flag in self.posseg(
                                doc, standard_name=standard_name)
                                         if flag not in pos_filter_list
                                         if len(x) >= len_filter)
                else:
                    if flag_add:
                        words = list(f'{x}_{flag}' for x, flag in self.posseg(
                            doc, standard_name=standard_name)
                                     if len(x) >= len_filter)
                    else:
                        words = list(
                            x
                            for x in self.seg(doc, standard_name=standard_name)
                            if len(x) >= len_filter)
            count = dict(Counter(words))
            for i in count:
                count_sum[i].append(count[i])
                count_sum_words += count[i]
            # print(colored("==>> count_sum: ", "green"), count_sum)

            temp = []
            [temp.append(i) for i in words if not i in temp]
            # print(colored("==>> temp: ", "green"), temp)

            for u, v in combinations(temp, 2):
                pair0 = tuple(sorted((u, v)))
                if pair0 not in links:
                    links[pair0] = 1
                else:
                    links[pair0] += 1

        for k in list(count_sum):
            if sum(count_sum[k]) >= min_freq_node:
                if len(count_sum[k]) >= min_freq_doc:
                    tf = sum(count_sum[k]) / count_sum_words
                    idf = math.log10(len(docs) / len(count_sum[k]) + 1)
                    tfidf = tf * idf
                    G.add_node(k,
                               weight=sum(count_sum[k]),
                               count=len(count_sum[k]),
                               tfidf=tfidf)
        extra_link = {}
        remove_ = []
        for (u, v) in links:
            count_sum_links += links[(u, v)]
            #保证连边中的节点全部在G之中
            if u in G.nodes() and v in G.nodes():
                w = links[(u, v)]
                if w >= min_freq_edge:
                    G.add_edge(u, v, weight=w)
                else:
                    if add_single_edge:
                        extra_link[(u, v)] = w
        for n in G.nodes():
            if len(G.edges(n)) == 0:
                if add_single_edge:
                    print(f'无连边孤立节点为：{n}, 加入该节点低权重连边')
                    for key in list(extra_link.keys()):
                        if n in key:
                            print(f'加入连边：{key},权重为{extra_link[key]}')
                            G.add_edge(key[0], key[1], weight=extra_link[key])
                            del extra_link[key]
                else:
                    remove_.append(n)
        for n in remove_:
            print(f'删除孤立节点：{n}')
            G.remove_node(n)

        print(f'''
        文本处理信息:
        输入总文本数量为{len(docs)},
        词汇筛选条件为长度大于等于{len_filter},词性过滤为{pos_filter},
        符合筛选条件的词汇的总词频{count_sum_words},
        不重复词汇数量{len(list(count_sum))},
        符合筛选条件的词汇的总共现边次数为{count_sum_links},
        不重复词汇共现边数量为{len(links)},

        G文件处理信息:
        词汇最低词频为{min_freq_node},
        边最低共现次数为{min_freq_edge},
        最低文件出现次数为{min_freq_doc},
        筛选后构造G图像包含节点{len(G.nodes)}个,边{len(G.edges)}个。''')
        G = G.copy()
        # G = G.subgraph(used_nodes).copy()
        if gml_save:
            print(f'保存G文件为GML文件:{path}.graphml')
            nx.write_graphml_lxml(G, path + '.graphml')
        if gexf_save:
            print(f'保存G文件为gexf文件:{path}.gexf')
            nx.write_gexf(G, path + '.gexf')
        return G

    def build_word_ego_graph(self,
                             docs,
                             word,
                             standard_name=True,
                             min_freq=0,
                             other_min_freq=-1,
                             stopwords=None):
        '''根据文本和指定限定词，获得以限定词为中心的各词语的关系。
        限定词可以是一个特定的方面（衣食住行这类文档），这样就可以从词语中心图中获得关于这个方面的简要信息

        :param docs: 文本的列表
        :param word: 限定词
        :param standard_name: 把所有实体的指称化为标准实体名
        :param stopwords: 需要过滤的停用词
        :param min_freq: 作为边加入到图中的与中心词最小共现次数，用于筛掉可能过多的边
        :param other_min_freq: 中心词以外词语关系的最小共现次数
        :return: G（networxX中的Graph）

        '''
        G = nx.Graph()
        links = {}
        if other_min_freq == -1:
            other_min_freq = min_freq
        for doc in docs:
            if stopwords:
                words = set(x
                            for x in self.seg(doc, standard_name=standard_name)
                            if x not in stopwords)
            else:
                words = self.seg(doc, standard_name=standard_name)
            if word in words:
                for u, v in combinations(words, 2):
                    pair0 = tuple(sorted((u, v)))
                    if pair0 not in links:
                        links[pair0] = 1
                    else:
                        links[pair0] += 1

        used_nodes = set([word])  # 关系对中涉及的词语必须与实体有关（>= min_freq）
        for (u, v) in links:
            w = links[(u, v)]
            if word in (u, v) and w >= min_freq:
                used_nodes.add(v if word == u else u)
                G.add_edge(u, v, weight=w)
            elif w >= other_min_freq:
                G.add_edge(u, v, weight=w)
        G = G.subgraph(used_nodes).copy()
        return G

    def build_entity_ego_graph(self,
                               docs,
                               word,
                               min_freq=0,
                               other_min_freq=-1,
                               inv_index={},
                               used_types=[]):
        '''Entity only version of build_word_ego_graph()
        '''
        G = nx.Graph()
        links = {}
        if other_min_freq == -1:
            other_min_freq = min_freq
        if len(inv_index) != 0:
            related_docs = self.search_entity(word, docs, inv_index)
        else:
            related_docs = []
            for doc in docs:
                entities_info = self.entity_linking(doc)
                entities = [
                    entity0 for [[l, r], (entity0, type0)] in entities_info
                ]
                if word in entities:
                    related_docs.append(doc)

        for i, sent in enumerate(related_docs):
            entities_info = self.entity_linking(sent)
            if len(used_types) == 0:
                entities = set(entity
                               for span, (entity, type0) in entities_info)
            else:
                entities = set(entity
                               for span, (entity, type0) in entities_info
                               if type0[1:-1] in used_types)
            for u, v in combinations(entities, 2):
                pair0 = tuple(sorted((u, v)))
                if pair0 not in links:
                    links[pair0] = 1
                else:
                    links[pair0] += 1

        used_nodes = set([word])  # 关系对中涉及的词语必须与实体有关（>= min_freq）
        for (u, v) in links:
            w = links[(u, v)]
            if word in (u, v) and w >= min_freq:
                used_nodes.add(v if word == u else u)
                G.add_edge(u, v, weight=w)
            elif w >= other_min_freq:
                G.add_edge(u, v, weight=w)
        G = G.subgraph(used_nodes).copy()
        return G