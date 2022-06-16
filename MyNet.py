import collections

from Tessng import PyCustomerNet, tngIFace
from basic_info.info import roads_info, lanes_info
from utils import get_coo_list, get_inter, Road, Section, connect_childs



# 用户插件子类，代表用户自定义与路网相关的实现逻辑，继承自MyCustomerNet
class MyNet(PyCustomerNet):
    def __init__(self):
        super(MyNet, self).__init__()

    # 创建路网
    def createNet(self, roads_info, lanes_info):
        # 代表TESS NG的接口
        iface = tngIFace()
        # 代表TESS NG的路网子接口
        netiface = iface.netInterface()

        # 创建所有的连接段,交叉口本身不作为车道，直接生成连接段
        # 多条车道属于一个road
        def default_dict():
            return {
                'lFromLaneNumber': [],
                'lToLaneNumber': [],
                'lanesWithPoints3': [],
                'infos': [],
            }

        connector_mapping = collections.defaultdict(default_dict)

        road_mapping = dict()
        # 创建基础路段,数据原因，不考虑交叉口
        link_road_ids = [road_id for road_id, road_info in roads_info.items() if road_info['junction_id'] == -1]
        junction_road_ids = [road_id for road_id, road_info in roads_info.items() if road_info['junction_id'] != -1]
        # 创建所有的Link，一个road 通过多个section，左右来向分为多个Link
        for road_id, road_info in roads_info.items():
            if road_info['junction_id'] != -1:
                continue  # 先行创建所有的基本路段
            tess_road = Road(road_id)
            for section_id, lane_section_info in road_info['lane_sections'].items():

                points = road_info['road_points'][section_id]['points']

                section_id = int(section_id)

                section_info = road_info['sections'][section_id]
                left_childs = section_info['left_points']
                right_childs = section_info['right_points']

                tess_section = Section(road_id, int(section_id), lane_section_info['all'])
                tess_road.sections.append(tess_section)

                # 存在左车道
                if lane_section_info['left']:
                    # 对section分段
                    left_links = []
                    # sectionChild = Child(left_childs)
                    # sectionChild.covert_network()
                    # childs = sectionChild.childs
                    childs = left_childs
                    for index in range(len(childs)):
                        child = childs[index]
                        start_index, end_index = child['start'], child['end'] + 1
                        land_ids = sorted(child["point"][0]['lanes'].keys(), reverse=True)
                        lCenterLinePoint = get_coo_list([point["position"] for point in points][::-1][start_index:end_index])
                        lanesWithPoints = [
                            {
                                'left': get_coo_list(
                                    road_info['sections'][section_id]["lanes"][lane_id]['left_vertices'][start_index:end_index],
                                    True),
                                'center': get_coo_list(
                                    road_info['sections'][section_id]["lanes"][lane_id]['center_vertices'][start_index:end_index], True),
                                'right': get_coo_list(
                                    road_info['sections'][section_id]["lanes"][lane_id]['right_vertices'][start_index:end_index],
                                    True),
                            }
                            for lane_id in land_ids  # if roads_info[road_id]['lanes'][lane_id]['type']=='driving'
                        ]
                        link_obj = netiface.createLinkWithLanePoints(lCenterLinePoint, lanesWithPoints,
                                                                               f"{road_id}_{section_id}_{index}_left")
                        left_links.append(
                            {
                                'link': link_obj,
                                'lane_ids': land_ids,
                            }
                        )

                    tess_section.left_link = left_links
                    connect_childs(tess_section.left_link, connector_mapping)
                    # return
                # 存在右车道
                if lane_section_info['right']:
                    # sectionChild = Child(right_childs)
                    # sectionChild.covert_network()
                    # childs = sectionChild.childs
                    right_links = []
                    childs = right_childs
                    # 车道id为负，越小的越先在tess中创建
                    # land_ids = sorted(lane_section_info['right'], reverse=False)
                    for index in range(len(childs)):
                        child = childs[index]
                        start_index, end_index = child['start'], child['end'] + 1
                        land_ids = sorted(child["point"][0]['lanes'].keys(), reverse=False)
                        lCenterLinePoint = get_coo_list(
                            [point["position"] for point in points][start_index:end_index])

                        # TODO 部分
                        lanesWithPoints = [
                            {
                                'left': get_coo_list(road_info['sections'][section_id]["lanes"][lane_id]['left_vertices'][start_index:end_index]),
                                'center': get_coo_list(
                                    road_info['sections'][section_id]["lanes"][lane_id]['center_vertices'][start_index:end_index]),
                                'right': get_coo_list(
                                    road_info['sections'][section_id]["lanes"][lane_id]['right_vertices'][start_index:end_index]),
                            }
                            for lane_id in land_ids  # if roads_info[road_id]['lanes'][lane_id]['type']=='driving'
                        ]

                        link_obj = netiface.createLinkWithLanePoints(lCenterLinePoint, lanesWithPoints,
                                                                     f"{road_id}_{section_id}_{index}_right")
                        right_links.append(
                            {
                                'link': link_obj,
                                'lane_ids': land_ids,
                            }
                        )
                        # right_links.append(netiface.createLinkWithLanePoints(lCenterLinePoint, lanesWithPoints,
                        #                                                             f"{road_id}_{section_id}_{index}_right"))
                    tess_section.right_link = right_links
                    connect_childs(tess_section.right_link, connector_mapping)
                road_mapping[road_id] = tess_road

        # 创建路段间的连接
        for road_id, road_info in roads_info.items():
            if road_info['junction_id'] != -1:
                continue

            # lane_sections 保存基本信息，sections 保存详情
            for section_id, section_info in road_info['sections'].items():
                # section_id = int(section_id)
                # tess_section = road_mapping[road_id].sections[section_id] # 通过下标即可获取section，但注意，需要保证所有的section都被导入了，否则需要通过id判断后准确获取

                # 路段间的连接段只向后连接,本身作为前路段(向前也一样，会重复一次)
                for lane_id, lane_info in section_info["lanes"].items():
                    # 633 路段，L18（-） 只有两个后续车道连接？？？ 已确认，yes
                    predecessor_id = lane_info['name']

                    # 为了和交叉口保持一致，重新获取一次相关信息
                    is_true, from_road_id, from_section_id, from_lane_id, _ = get_inter(predecessor_id)

                    if not is_true:  # 部分车道的连接关系可能是'2.3.None.-1', 需要清除（上一车道宽度归零，不会连接到下一车道）
                        continue

                    from_section = road_mapping[from_road_id].section(from_section_id)
                    from_link = from_section.tess_link(from_lane_id, 'from')
                    from_lane = from_section.tess_lane(from_lane_id, 'from')
                    if not (from_link and from_lane):
                        # 如果车道在此处宽度归零，是不会连接到下一车道的
                        continue

                    for successor_id in lane_info["successor_ids"]:
                        is_true, to_road_id, to_section_id, to_lane_id, _ = get_inter(successor_id)
                        if not is_true:  # 部分车道的连接关系可能是'2.3.None.-1'，需要清除
                            continue
                        if to_road_id not in link_road_ids:  # 只针对性的创建路段间的连接
                            continue

                        to_section = road_mapping[to_road_id].section(to_section_id)
                        to_link = to_section.tess_link(to_lane_id, 'to')
                        to_lane = to_section.tess_lane(to_lane_id, 'to')

                        connector_mapping[f"{from_link.id()}-{to_link.id()}"]['lFromLaneNumber'].append(
                            from_lane.number() + 1)
                        connector_mapping[f"{from_link.id()}-{to_link.id()}"]['lToLaneNumber'].append(
                            to_lane.number() + 1)
                        connector_mapping[f"{from_link.id()}-{to_link.id()}"]['lanesWithPoints3'].append(
                            get_coo_list([lane_info['center_vertices'][-1],
                                          lanes_info[successor_id]['center_vertices'][0]]))  # 注意连接线方向
                        connector_mapping[f"{from_link.id()}-{to_link.id()}"]['infos'].append(
                            {
                                "predecessor_id": predecessor_id,
                                "successor_id": successor_id,
                                'junction': False,
                            }
                        )

        # 仅交叉口
        error_junction = []
        for road_id, road_info in roads_info.items():
            if road_info['junction_id'] == -1:
                continue
            for section_id, section_info in road_info['sections'].items():
                # 获取路口的所有连接关系
                for lane_id, lane_info in section_info["lanes"].items():
                    for predecessor_id in lane_info['predecessor_ids']:
                        is_true, from_road_id, from_section_id, from_lane_id, _ = get_inter(predecessor_id)
                        if not is_true:  # 部分车道的连接关系可能是'2.3.None.-1'，需要清除
                            continue

                        from_section = road_mapping[from_road_id].section(from_section_id)
                        from_link = from_section.tess_link(from_lane_id, 'from')
                        from_lane = from_section.tess_lane(from_lane_id, 'from')

                        for successor_id in lane_info["successor_ids"]:
                            is_true, to_road_id, to_section_id, to_lane_id, _ = get_inter(successor_id)
                            if not is_true:  # 部分车道的连接关系可能是'2.3.None.-1'，需要清除
                                continue

                            to_section = road_mapping[to_road_id].section(to_section_id)
                            to_link = to_section.tess_link(to_lane_id, 'to')
                            to_lane = to_section.tess_lane(to_lane_id, 'to')

                            # TODO 交叉口可能产生自连接，记录并跳过
                            if from_road_id == to_road_id and from_section_id != to_section_id:
                                error_junction.append(
                                    {
                                        "lane": lane_info['name'],
                                        "predecessor": predecessor_id,
                                        "successor": successor_id,
                                    }
                                )
                                continue

                            connector_mapping[f"{from_link.id()}-{to_link.id()}"]['lFromLaneNumber'].append(
                                from_lane.number() + 1)
                            connector_mapping[f"{from_link.id()}-{to_link.id()}"]['lToLaneNumber'].append(
                                to_lane.number() + 1)

                            # 用前后车道的首尾坐标替换原有首尾坐标
                            connector_vertices = lanes_info[predecessor_id]['center_vertices'][-1:] + \
                                                 lane_info['center_vertices'][1:-1] + \
                                                 lanes_info[successor_id]['center_vertices'][:1]
                            # connector_vertices = lane_info['center_vertices']
                            connector_mapping[f"{from_link.id()}-{to_link.id()}"]['lanesWithPoints3'].append(
                                get_coo_list(connector_vertices))  # 注意连接线方向
                            connector_mapping[f"{from_link.id()}-{to_link.id()}"]['infos'].append(
                                {
                                    "predecessor_id": predecessor_id,
                                    "successor_id": successor_id,
                                    "lane_id": lane_info["name"],
                                    "connector_vertices": connector_vertices,
                                    'junction': True,
                                    "from_link": from_link,
                                    "to_link": to_link,
                                }
                            )

        # 创建所有的连接关系
        for link_id, link_info in connector_mapping.items():
            from_link_id = int(link_id.split('-')[0])
            to_link_id = int(link_id.split('-')[1])
            lFromLaneNumber = link_info['lFromLaneNumber']
            lToLaneNumber = link_info['lToLaneNumber']
            lanesWithPoints3 = link_info['lanesWithPoints3']

            types = set(i['junction'] for i in link_info['infos'])
            if True in types and False in types:
                link_type = 'all'
            elif True in types:
                link_type = 'junction'
            else:
                link_type = 'link'

            # 源数据建立连接
            if lanesWithPoints3:
                netiface.createConnectorWithPoints(from_link_id, to_link_id,
                                               lFromLaneNumber, lToLaneNumber,
                                               lanesWithPoints3, f"{from_link_id}-{to_link_id}-{link_type}")
            # TESS 自动计算，建立连接
            else:
                netiface.createConnector(from_link_id, to_link_id, lFromLaneNumber, lToLaneNumber)
        print(error_junction)
        # print(connector_mapping)
        # 创建连接段，自动计算断点
        # #connector2 = netiface.createConnector(link1.id(), link2.id(), lFromLaneNumber, lToLaneNumber)

    def afterLoadNet(self):
        # 代表TESS NG的接口
        iface = tngIFace()
        # 代表TESS NG的路网子接口
        netiface = iface.netInterface()
        # 设置场景大小
        netiface.setSceneSize(1000, 1000)  # 测试数据
        # netiface.setSceneSize(4000, 1000)  # 华为路网
        # netiface.setSceneSize(10000, 3000)  # 深圳路网
        # 获取路段数
        count = netiface.linkCount()
        # if (count == 0):
        #     self.createNet(roads_info, lanes_info)
