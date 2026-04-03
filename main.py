# sadg-controller - MAPF execution with Switchable Action Dependency Graphs
# Copyright (c) 2023 Alex Berndt
# Copyright (c) 2023 Niels van Duijkeren, Robert Bosch GmbH
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from logging import DEBUG, Logger
import random
import sys
import time
import json
import os
from mapf.problem import MAPFProblem
from mapf.roadmap import Roadmap
from sadg.compiler import compile_sadg
from sadg.sadg import SADG
from sadg.status import Status
from sadg.visualizer import Visualizer


def main(agent_count, map_type, trial_sum, delay=0.0) -> None:

    # agent_count = 40
    ecbs_w = 1.8
    move_unit = 0.5
    prob_delay = delay

    logger = Logger(__name__, level=DEBUG)

    roadmap_path = f"data/roadmaps/{map_type}"
    roadmap = Roadmap(roadmap_path,map_type)

    for trial in range(21,trial_sum+1):
        start_t = time.time()
        print(f"Trial {trial}/{trial_sum} for map {map_type} with delay_prob {prob_delay} and {agent_count} agents ...")
        starts, goals = roadmap.random_locations(agent_count,trial)

        problem = MAPFProblem(roadmap, starts, goals, logger, trial)
        plan = problem.solve(suboptimality_factor=ecbs_w)

        sadg: SADG = compile_sadg(plan, logger)
        sadg_visualizer = Visualizer(sadg)

        agent_ids = [f"agent{id}" for id in range(agent_count)]
        agent_curr_vertex = [ sadg.get_first_agent_vertex(agent_id) for agent_id in agent_ids]    

        # Metrics Initialization
        metrics = {aid: {'distance': 0.0,'wait_time':0.0, 'finish_time': 0, "action_cost_time":[0], 'tasks': [starts[id].get_row_col(),goals[id].get_row_col()]} for id, aid in enumerate(agent_ids)}
        finished_agents = set()
        final_makespan = None
        for sim_iter in range(20000):
            # Check if all agents finished
            if len(finished_agents) == len(agent_ids):
                print(f"All agents finished at step {sim_iter}")
                final_makespan = sim_iter
                break

            for idx, curr_vertex in enumerate(agent_curr_vertex):
                agent_id = f"agent{idx}"
                
                if agent_id in finished_agents:
                    continue

                # Agent is at current vertex, can execute (not blocked), and status == STAGED
                if curr_vertex.get_status() == Status.STAGED:
                    if curr_vertex.can_execute():
                        # print(f"{agent_id}: set to IN-PROGRESS ...")
                        curr_vertex.set_status(Status.IN_PROGRESS)
                    else:
                        # metrics[agent_id]['wait_time'] += 1
                        print(f"{agent_id}: blocked by dependencies ...")

                # Agent is at executing current vertex
                elif curr_vertex.get_status() == Status.IN_PROGRESS:
                    # Only set agents 0 and 2 to completed unless 10 time-steps in
                    # if idx != 0 or sim_iter > 18:
                    #     # print(f"{agent_id}: set to COMPLETED ...")
                    #     curr_vertex.set_status(Status.COMPLETED)
                    assert len(metrics[agent_id]['action_cost_time']) > 0, f"Action cost should be > 0 for vertex {curr_vertex.get_shorthand()}"
                    if sim_iter - metrics[agent_id]['action_cost_time'][-1] >= curr_vertex.get_distance()/move_unit:
                        # print(f"{agent_id}: set to COMPLETED ...")
                        curr_vertex.set_status(Status.COMPLETED)
                elif curr_vertex.get_status() == Status.COMPLETED:
                    if curr_vertex.has_next():
                        # print(f"{agent_id}: next vertex STAGED ...")
                        # Set current vertex of this agent to the next in the sequence
                        # Considering env delay
                        if random.random() < prob_delay:
                            # print(f"{agent_id}: experienced delay at vertex {curr_vertex.get_shorthand()} ...")
                            # Agent experiences a delay, remains at current vertex for this iteration
                            metrics[agent_id]['wait_time'] += 1
                            continue
                        dist = curr_vertex.get_distance()
                        metrics[agent_id]['distance'] += dist
                        agent_curr_vertex[idx] = curr_vertex.get_next()
                        metrics[agent_id]['action_cost_time'].append(sim_iter)
                    else:
                        # print(f"{agent_id}: finished plan!")
                        dist = curr_vertex.get_distance()
                        metrics[agent_id]['distance'] += dist
                        finished_agents.add(agent_id)
                        # Record Metrics
                        metrics[agent_id]['finish_time'] = sim_iter
                else:
                    raise RuntimeError("Should not achieve this state ...")

            sadg_visualizer.refresh()
            print("----------------------------------------")
            sadg.optimize(horizon=2)

        output_data = {
            "makespan": final_makespan,
            "flowtime": time.time() - start_t,
            "map_type": map_type,
            "agent_count": agent_count,
            "delay_prob": prob_delay,
            "metrics": metrics
        }

        os.makedirs("output", exist_ok=True)
        output_filename = f"output/metrics_{map_type}_{agent_count}_{trial}_{prob_delay}.json"
        
        with open(output_filename, 'w') as f:
            json.dump(output_data, f, indent=2)

        print(f"Metrics saved to {output_filename}")
        print(f"Global Time Consumption: {sim_iter} steps")


if __name__ == "__main__":
    main(agent_count=int(sys.argv[1]), map_type=sys.argv[2], trial_sum=int(sys.argv[3]), delay=float(sys.argv[4]) if len(sys.argv) > 4 else 0.0)
