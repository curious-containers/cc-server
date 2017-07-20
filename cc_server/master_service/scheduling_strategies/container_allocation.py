def binpack(nodes, minimum_ram):
    node_list = [(node['free_ram'], name) for name, node in nodes.items() if node['free_ram'] >= minimum_ram]
    if not node_list:
        return None
    node_list.sort(reverse=False)
    return node_list[0][1]


def spread(nodes, minimum_ram):
    node_list = [(node['free_ram'], name) for name, node in nodes.items() if node['free_ram'] >= minimum_ram]
    if not node_list:
        return None
    node_list.sort(reverse=True)
    return node_list[0][1]
