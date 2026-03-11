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
import sys
from mapf.problem import MAPFProblem
from mapf.roadmap import Roadmap
from sadg.compiler import compile_sadg
from sadg.sadg import SADG
from sadg.status import Status
from sadg.visualizer import Visualizer


def main(agent_count, map_type, trial_sum) -> None:

    # agent_count = 40
    ecbs_w = 1.8

    logger = Logger(__name__, level=DEBUG)

    roadmap_path = f"data/roadmaps/{map_type}"
    roadmap = Roadmap(roadmap_path,map_type)

    for trial in range(5,trial_sum):
        print(f"Trial {trial+1}/{trial_sum} for map {map_type} with {agent_count} agents ...")
        starts, goals = roadmap.random_locations(agent_count,trial)

        problem = MAPFProblem(roadmap, starts, goals, logger, trial)
        plan = problem.solve(suboptimality_factor=ecbs_w)

        sadg: SADG = compile_sadg(plan, logger)
        sadg_visualizer = Visualizer(sadg)

        agent_ids = [f"agent{id}" for id in range(agent_count)]
        agent_curr_vertex = [ sadg.get_first_agent_vertex(agent_id) for agent_id in agent_ids]    

        # Metrics Initialization
        metrics = {aid: {'distance': 0.0, 'duration': 0, 'wait_time': 0, 'tasks': []} for aid in agent_ids}
        current_task_wait = {aid: 0 for aid in agent_ids}
        current_task_start = {aid: None for aid in agent_ids}
        finished_agents = set()

        for sim_iter in range(50):
            # Check if all agents finished
            if len(finished_agents) == len(agent_ids):
                print(f"All agents finished at step {sim_iter}")
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
                        current_task_start[agent_id] = sim_iter
                    else:
                        # print(f"{agent_id}: blocked by dependencies ...")
                        current_task_wait[agent_id] += 1
                        metrics[agent_id]['wait_time'] += 1

                # Agent is at executing current vertex
                elif curr_vertex.get_status() == Status.IN_PROGRESS:

                    # Only set agents 0 and 2 to completed unless 10 time-steps in
                    if idx != 0 or sim_iter > 18:
                        # print(f"{agent_id}: set to COMPLETED ...")
                        curr_vertex.set_status(Status.COMPLETED)

                        # Record Metrics
                        start_time = current_task_start[agent_id]
                        if start_time is not None:
                            duration = sim_iter - start_time
                            dist = curr_vertex.get_distance()
                            wait = current_task_wait[agent_id]
                            
                            metrics[agent_id]['distance'] += dist
                            metrics[agent_id]['duration'] += duration
                            metrics[agent_id]['tasks'].append({
                                'task': curr_vertex.get_shorthand(),
                                'distance': dist,
                                'duration': duration,
                                'wait_time': wait,
                                'start': start_time,
                                'end': sim_iter
                            })
                            
                            # Reset task wait and start
                            current_task_wait[agent_id] = 0
                            current_task_start[agent_id] = None

                elif curr_vertex.get_status() == Status.COMPLETED:
                    if curr_vertex.has_next():
                        # print(f"{agent_id}: next vertex STAGED ...")

                        # Set current vertex of this agent to the next in the sequence
                        agent_curr_vertex[idx] = curr_vertex.get_next()

                    else:
                        # print(f"{agent_id}: finished plan!")
                        finished_agents.add(agent_id)
                else:
                    raise RuntimeError("Should not achieve this state ...")

            sadg_visualizer.refresh()
            print("----------------------------------------")
            sadg.optimize(horizon=2)

        import json
        import os

        output_data = {
            "global_time_consumption": sim_iter,
            "map_type": map_type,
            "agent_count": agent_count,
            "metrics": metrics
        }

        os.makedirs("output", exist_ok=True)
        output_filename = f"output/metrics_{map_type}_{agent_count}_{trial}.json"
        
        with open(output_filename, 'w') as f:
            json.dump(output_data, f, indent=2)

        print(f"Metrics saved to {output_filename}")
        print(f"Global Time Consumption: {sim_iter} steps")


if __name__ == "__main__":
    main(agent_count=int(sys.argv[1]), map_type=sys.argv[2], trial_sum=int(sys.argv[3]))
