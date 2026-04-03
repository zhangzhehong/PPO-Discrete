import os
import csv
import json
import yaml
import networkx as nx
import matplotlib.pyplot as plt

def load_dimensions(file_path):
    with open(file_path, 'r') as f:
        data = yaml.safe_load(f)
    return data.get('dimensions', {})

def load_roadmap(file_path):
    grid = []
    with open(file_path, 'r') as f:
        reader = csv.reader(f)
        for row in reader:
             # Filter out empty strings that might appear due to trailing commas
            cleaned_row = [cell.strip() for cell in row if cell.strip()]
            if cleaned_row:
                grid.append(cleaned_row)
    return grid

def create_topology_graph(grid, dimensions):
    G = nx.Graph()
    rows = len(grid)
    cols = len(grid[0]) if rows > 0 else 0
    resolution = dimensions.get('resolution', 1.0)
    x_offset = dimensions.get('x_offset', 0.0)
    y_offset = dimensions.get('y_offset', 0.0)
    print(f"Creating graph with resolution={resolution}, x_offset={x_offset}, y_offset={y_offset} ...")
    # Add nodes
    for r in range(rows):
        for c in range(cols):
            try:
                cell_value = int(grid[r][c])
            except ValueError:
                continue # Skip non-integer cells

            # Assuming 9 is obstacle, everything else is traversable node
            if cell_value != 9:
                node_id = (r, c)
                # Calculate physical position
                # Assuming typical grid map where (r, c) maps to (x, y)
                # x = c * res + x_off
                # y = (rows - 1 - r) * res + y_off  <-- This flips Y to match standard cartesian if grid 0,0 is top-left
                # But let's stick to simple mapping for graph structure
                x = c * resolution + x_offset
                y = r * resolution + y_offset 
                
                G.add_node(node_id, pos=(x, -y), loc=(x, y), type=cell_value) # Negate y for visualization (screen coords)

    # Add edges (4-connectivity)
    for r, c in G.nodes():
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if (nr, nc) in G.nodes():
                G.add_edge((r, c), (nr, nc))
    
    return G

def process_directory(directory):
    roadmap_path = os.path.join(directory, 'roadmap.csv')
    dimensions_path = os.path.join(directory, 'dimensions.yaml')

    if os.path.exists(roadmap_path) and os.path.exists(dimensions_path):
        print(f"Processing {directory}...")
        try:
            dimensions = load_dimensions(dimensions_path)
            grid = load_roadmap(roadmap_path)
            G = create_topology_graph(grid, dimensions)
            
            print(f"  Nodes: {G.number_of_nodes()}, Edges: {G.number_of_edges()}")
            
            # Visualize
            pos = nx.get_node_attributes(G, 'pos')
            if not pos:
                 pos = nx.spring_layout(G)
            
            plt.figure(figsize=(10, 10))
            nx.draw(G, pos, node_size=10, node_color='blue', with_labels=False, width=0.5)
            plt.title(f"Topology Graph: {os.path.basename(directory)}")
            output_path = os.path.join(directory, 'topology_graph.png')
            plt.savefig(output_path)
            plt.close()
            print(f"  Saved graph visualization to {output_path}")

            # Save to JSON
            json_output_path = os.path.join(directory, 'topology_graph.json')
            
            # Construct JSON data manually to include 'topo' and exclude 'links'
            data = {
                "directed": G.is_directed(),
                "multigraph": G.is_multigraph(),
                "graph": G.graph,
                "nodes": [],
                "topo": {}
            }

            for node in G.nodes():
                # Add node to nodes list
                node_data = G.nodes[node].copy()
                node_data['id'] = node
                data['nodes'].append(node_data)

                # Add to topo dictionary
                loc = list(G.nodes[node]['pos'])
                # Ensure float representation for consistency
                loc = [float(x) for x in loc]
                
                adj = []
                for neighbor in G.neighbors(node):
                    neighbor_loc = list(G.nodes[neighbor]['pos'])
                    adj.append([float(x) for x in neighbor_loc])
                
                # Use string representation of list as key, similar to topo_demo.json
                data['topo'][str(loc)] = {
                    "loc": loc,
                    "adj": adj
                }


            with open(json_output_path, 'w') as f:
                json.dump(data, f, indent=4)
            print(f"  Saved graph JSON to {json_output_path}")
            
        except Exception as e:
            print(f"  Error processing {directory}: {e}")
    else:
        # print(f"Skipping {directory} (missing files)")
        pass

def main():
    # Base directory where this script resides
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Iterate over all subdirectories
    for item in os.listdir(base_dir):
        item_path = os.path.join(base_dir, item)
        if os.path.isdir(item_path):
            process_directory(item_path)

if __name__ == "__main__":
    main()
