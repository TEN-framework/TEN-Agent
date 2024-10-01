# Generate a graph from a JSON file
# Currently it only generate the first graph but it's easy to make it generate all graphs
# Author: Seven Du <dujinfang@gmail.com>
# usage:
#     pip install graphviz
#     python dot.py

import json
import graphviz

COLORS = {
    "flush": "#999",
    "cmd": "#0f0",
    "data": "#00f",
    "text_data": "#f00",
    "pcm_frame": "purple",
}

connection_types = ["data", "cmd", "audio_frame", "video_frame"]


def color(port):
    if port in COLORS:
        return COLORS[port]
    return "#000"


def find_node(nodes, name):
    for node in nodes:
        if node["name"] == name:
            return node
    return None


def create_graph(json_data):
    # Initialize a directed graph
    graph = graphviz.Digraph("G", filename="graph.gv")
    graph.graph_attr["rankdir"] = "LR"
    graph.graph_attr["dpi"] = "150"
    graph.graph_attr["splines"] = "true"
    graph.attr("node", shape="none")

    # Add nodes to the graph
    nodes = json_data["_ten"]["predefined_graphs"][0]["nodes"]
    connections = json_data["_ten"]["predefined_graphs"][0]["connections"]
    for node in nodes:
        node["i_ports"] = ["flush"]
        node["o_ports"] = ["flush"]
    for node in nodes:
        if node["type"] != "extension":
            continue
        for connection in connections:
            if connection["extension"] == node["name"]:
                for connection_type in connection_types:
                    if connection_type in connection:
                        data = connection[connection_type]
                        for item in data:
                            node["o_ports"].append(item["name"])
                            for dest in item["dest"]:
                                dest_node = find_node(nodes, dest["extension"])
                                if dest_node:
                                    dest_node["i_ports"].append(item["name"])
    for node in nodes:
        if node["type"] != "extension":
            continue
        node["i_ports"] = set(node["i_ports"])
        node["o_ports"] = set(node["o_ports"])
        print("====iports: ", node["name"], node["i_ports"])
        print("====oports: ", node["name"], node["o_ports"])
        iports = ""
        for port in node["i_ports"]:
            iports += f'<tr><td align="left" port="i_{port}">⊙ {port}</td></tr>'
        oports = ""
        for port in node["o_ports"]:
            oports += f'<tr><td align="right" port="o_{port}">{port} ⊙</td></tr>'

        # Use HTML-like label for nodes
        label = f"""<
        <table border="0" cellborder="1" cellspacing="0">
            <tr><td colspan="2" bgcolor="#ddd"><b>{node["name"]}</b></td></tr>
            <tr><td colspan="2">properties</td></tr>
            <tr><td colspan="2">extensionGroup<br/>{node["extension_group"]}</td></tr>
            <tr><td>
                <table border="0" cellspacing="0">{iports}</table>
            </td>
            <td>
                <table border="0" cellspacing="0">{oports}</table>
            </td>
        </tr>    
        </table>>"""
        graph.node(node["name"], label)

    # Add edges to the graph
    for connection in connections:
        for connection_type in connection_types:
            if connection_type in connection:
                for data in connection[connection_type]:
                    for dest in data["dest"]:
                        graph.edge(
                            f'{connection["extension"]}:o_{data["name"]}',
                            f'{dest["extension"]}:i_{data["name"]}',
                            color=color(data["name"]),
                            label=connection_type,
                        )

    # Save the graph to a file
    print(graph.source)
    graph.render("graph", format="png")
    graph.view()


# Load the JSON data
with open("../property.json") as f:
    data = json.load(f)

# Create the graph
create_graph(data)
