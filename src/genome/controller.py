"""NEAT controller wrapper.

Thin wrapper around `neat-python` that:
- Builds a `neat.Config` from the experiment JSON config
- Exposes the population, statistics, and genome summary for the dashboard
"""
from __future__ import annotations

import os
import tempfile
from typing import Any, Dict, List, Optional

import neat
import numpy as np

from neat.genes import DefaultConnectionGene, DefaultNodeGene


# ---------------------------------------------------------------------------
# NEAT config file generation
# ---------------------------------------------------------------------------

# Values are left at neat-python's own defaults; callers override the
# interesting ones programmatically in ``_build_neat_config``.
_DEFAULT_GENE_VALUES: Dict[str, str] = {
    "bias_init_mean": "0.0",
    "bias_init_stdev": "1.0",
    "bias_init_type": "gaussian",
    "bias_replace_rate": "0.1",
    "bias_mutate_rate": "0.7",
    "bias_mutate_power": "0.5",
    "bias_max_value": "3.0",
    "bias_min_value": "-3.0",
    "response_init_mean": "1.0",
    "response_init_stdev": "0.0",
    "response_init_type": "gaussian",
    "response_replace_rate": "0.0",
    "response_mutate_rate": "0.0",
    "response_mutate_power": "0.0",
    "response_max_value": "30.0",
    "response_min_value": "-30.0",
    "activation_default": "tanh",
    "activation_options": "tanh",
    "activation_mutate_rate": "0.0",
    "aggregation_default": "sum",
    "aggregation_options": "sum",
    "aggregation_mutate_rate": "0.0",
    "time_constant_init_mean": "1.0",
    "time_constant_init_stdev": "0.0",
    "time_constant_init_type": "gaussian",
    "time_constant_replace_rate": "0.0",
    "time_constant_mutate_rate": "0.0",
    "time_constant_mutate_power": "0.0",
    "time_constant_max_value": "10.0",
    "time_constant_min_value": "0.01",
    "weight_init_mean": "0.0",
    "weight_init_stdev": "1.0",
    "weight_init_type": "gaussian",
    "weight_replace_rate": "0.1",
    "weight_mutate_rate": "0.8",
    "weight_mutate_power": "0.5",
    "weight_max_value": "3.0",
    "weight_min_value": "-3.0",
    "enabled_default": "True",
    "enabled_mutate_rate": "0.01",
    "enabled_rate_to_true_add": "0.0",
    "enabled_rate_to_false_add": "0.0",
}


def _attribute_config_keys(gene_cls: type) -> List[str]:
    """Return every config key required by a gene class's attributes."""
    keys: List[str] = []
    for attr in gene_cls._gene_attributes:
        for item in attr._config_items:
            keys.append(f"{attr.name}_{item}")
    return keys


def _generate_neat_config_text() -> str:
    """Generate a complete NEAT .ini from neat-python's own metadata.

    Deriving the keys from the library guarantees the file always
    matches the installed version.
    """
    num_inputs = 15
    num_outputs = 6

    genome_keys = [
        "num_inputs", "num_outputs", "num_hidden", "feed_forward",
        "compatibility_disjoint_coefficient", "compatibility_weight_coefficient",
        "conn_add_prob", "conn_delete_prob", "node_add_prob",
        "node_delete_prob", "single_structural_mutation",
        "structural_mutation_surer", "initial_connection",
    ] + _attribute_config_keys(DefaultNodeGene) + _attribute_config_keys(
        DefaultConnectionGene
    )

    lines = [
        "[NEAT]",
        "fitness_criterion      = max",
        "fitness_threshold      = 100",
        "pop_size               = 50",
        "reset_on_extinction    = True",
        "no_fitness_termination = False",
        "",
        "[DefaultGenome]",
        f"num_inputs = {num_inputs}",
        f"num_outputs = {num_outputs}",
        f"num_hidden = 0",
        "feed_forward = True",
        "compatibility_disjoint_coefficient = 1.0",
        "compatibility_weight_coefficient = 0.5",
        "conn_add_prob = 0.5",
        "conn_delete_prob = 0.2",
        "node_add_prob = 0.3",
        "node_delete_prob = 0.1",
        "single_structural_mutation = False",
        "structural_mutation_surer = default",
        "initial_connection = full_direct",
    ]

    for key in genome_keys:
        if key in lines or any(line.startswith(key + " =") for line in lines):
            continue
        value = _DEFAULT_GENE_VALUES.get(key, "0.0")
        lines.append(f"{key} = {value}")

    lines.extend(
        [
            "",
            "[DefaultSpeciesSet]",
            "compatibility_threshold = 3.0",
            "",
            "[DefaultStagnation]",
            "species_fitness_func = max",
            "max_stagnation = 50",
            "species_elitism = 2",
            "",
            "[DefaultReproduction]",
            "elitism = 2",
            "survival_threshold = 0.2",
            "min_species_size = 1",
            "",
        ]
    )

    return "\n".join(lines)



# ---------------------------------------------------------------------------
# Genome serialization
# ---------------------------------------------------------------------------

def serialize_genome_dict(genome: neat.DefaultGenome, config: neat.Config) -> Dict[str, Any]:
    """Serialize a NEAT genome into a JSON-serializable dictionary."""
    enabled_connections = [c for c in genome.connections.values() if c.enabled]
    active_nodes = set()
    for conn in enabled_connections:
        active_nodes.add(conn.key[0])
        active_nodes.add(conn.key[1])

    num_inputs = config.genome_config.num_inputs
    num_outputs = config.genome_config.num_outputs
    input_keys = [-(i + 1) for i in range(num_inputs)]
    output_keys = list(range(num_outputs))

    nodes_list = []
    for nid in sorted(active_nodes):
        node_type = "input" if nid in input_keys else ("output" if nid in output_keys else "hidden")
        gene = genome.nodes.get(nid)
        nodes_list.append({
            "id": int(nid),
            "type": node_type,
            "bias": float(gene.bias) if gene is not None else 0.0,
            "activation": str(getattr(gene, "activation", "tanh")) if gene is not None else "linear",
            "response": float(getattr(gene, "response", 1.0)) if gene is not None else 1.0,
        })

    conns_list = []
    for k, conn in genome.connections.items():
        conns_list.append({
            "from": int(k[0]),
            "to": int(k[1]),
            "weight": float(conn.weight),
            "enabled": bool(conn.enabled),
        })

    return {
        "id": getattr(genome, "key", 0),
        "fitness": float(genome.fitness) if genome.fitness is not None else None,
        "nodes_total": len(genome.nodes),
        "nodes_active": len(active_nodes),
        "connections_total": len(genome.connections),
        "connections_enabled": len(enabled_connections),
        "species_id": getattr(genome, "species_id", -1),
        "is_extinct": (genome.fitness is not None and genome.fitness < -100),
        "node_ids": [int(n) for n in sorted(active_nodes)],
        "nodes": nodes_list,
        "connections": conns_list,
        "connection_weights": {
            str(k): float(c.weight)
            for k, c in genome.connections.items()
            if c.enabled
        },
    }


def serialize_genome(genome: neat.DefaultGenome, config: neat.Config) -> str:
    """Return JSON string representation of a genome."""
    import json
    return json.dumps(serialize_genome_dict(genome, config))


# ---------------------------------------------------------------------------
# NEATController
# ---------------------------------------------------------------------------

class NEATController:
    """Encapsulates a NEAT population and its configuration.

    Parameters
    ----------
    config : dict
        Full experiment config containing ``controller`` and ``neat_config``.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        self.experiment_config = config
        self.config = self._build_neat_config(config)

        self.population = neat.Population(self.config)
        self.stats = neat.StatisticsReporter()
        self.population.add_reporter(self.stats)
        self.population.add_reporter(neat.StdOutReporter(True))
        self._net_cache: Dict[int, Any] = {}

    # ------------------------------------------------------------------
    # Activation
    # ------------------------------------------------------------------

    def activate(self, genome_key: int, obs: np.ndarray) -> np.ndarray:
        """Run one forward pass of the given genome using cached FeedForwardNetwork."""
        if genome_key not in self._net_cache:
            genome = self.population.population[genome_key]
            self._net_cache[genome_key] = neat.nn.FeedForwardNetwork.create(genome, self.config)
        
        raw = self._net_cache[genome_key].activate(obs)
        return np.asarray(raw, dtype=np.float32)

    def clear_cache(self) -> None:
        """Clear the network cache across generations."""
        self._net_cache.clear()

    # ------------------------------------------------------------------
    # Genome inspection & serialization
    # ------------------------------------------------------------------

    def get_genome_summary(self, genome_key: Optional[int] = None) -> Dict[str, Any]:
        """Return a compact summary of a genome (best by default)."""
        if genome_key is None:
            genome = self.population.best_genome
            if genome is None:
                first_key = next(iter(self.population.population), None)
                genome = self.population.population.get(first_key)
        else:
            genome = self.population.population[genome_key]

        if genome is None:
            return {}

        return serialize_genome_dict(genome, self.config)

    def get_population_stats(self) -> Dict[str, Any]:
        """Return aggregate statistics from the statistics reporter."""
        try:
            stats = self.stats.get_fitness_stat()
        except Exception:
            return {}

        return {
            "generation": self.stats.generation if hasattr(self.stats, "generation") else 0,
            "best_fitness": float(np.max(stats)) if len(stats) else None,
            "mean_fitness": float(np.mean(stats)) if len(stats) else None,
            "worst_fitness": float(np.min(stats)) if len(stats) else None,
            "species_count": len(self.population.species.species) if hasattr(self.population.species, "species") else 0,
        }

    # ------------------------------------------------------------------
    # Config building
    # ------------------------------------------------------------------

    @staticmethod
    def _build_neat_config(config: Dict[str, Any]) -> neat.Config:
        """Build a neat.Config from the experiment JSON structure."""
        ctrl_cfg = config.get("controller", {})
        neat_cfg = config.get("neat_config", {})

        # neat-python requires a real config file path; write the generated
        # template each time (small file) and override values below.
        template_path = os.path.join(
            tempfile.gettempdir(), "icarus_neat_minimal.ini"
        )
        with open(template_path, "w", encoding="utf-8") as fh:
            fh.write(_generate_neat_config_text())

        net = neat.Config(
            neat.DefaultGenome,
            neat.DefaultReproduction,
            neat.DefaultSpeciesSet,
            neat.DefaultStagnation,
            template_path,
        )

        net.pop_size = int(neat_cfg.get("pop_size", 50))
        net.fitness_criterion = neat_cfg.get("fitness_criterion", "max")
        net.fitness_threshold = float(neat_cfg.get("fitness_threshold", 100.0))

        g = net.genome_config
        g.num_inputs = int(ctrl_cfg.get("num_inputs", 15))
        g.num_outputs = int(ctrl_cfg.get("num_outputs", 6))

        g.activation_default = ctrl_cfg.get("activation", "tanh")
        g.activation_mutate_rate = 0.0
        g.output_activation_default = ctrl_cfg.get("output_activation", "sigmoid")

        g.weight_init_mean = 0.0
        g.weight_init_stdev = float(neat_cfg.get("weight_init_std", 1.0))
        g.weight_max_value = float(neat_cfg.get("weight_max", 3.0))
        g.weight_mutate_rate = float(neat_cfg.get("weight_mutate_rate", 0.8))
        g.weight_replace_rate = float(neat_cfg.get("weight_replace_rate", 0.1))

        g.bias_init_mean = 0.0
        g.bias_init_stdev = float(neat_cfg.get("weight_init_std", 1.0))
        g.bias_max_value = float(neat_cfg.get("bias_max", 3.0))
        g.bias_mutate_rate = float(neat_cfg.get("bias_mutate_rate", 0.7))
        g.bias_replace_rate = 0.1

        g.compatibility_threshold = float(neat_cfg.get("compatibility_threshold", 3.0))
        g.compatibility_disjoint_coefficient = 1.0
        g.compatibility_weight_coefficient = 0.5

        g.conn_add_prob = float(neat_cfg.get("conn_add_prob", 0.5))
        g.conn_delete_prob = float(neat_cfg.get("conn_delete_prob", 0.2))
        g.node_add_prob = float(neat_cfg.get("node_add_prob", 0.3))
        g.node_delete_prob = float(neat_cfg.get("node_delete_prob", 0.1))

        g.feed_forward = True

        return net


_MORPHOLOGY_PARAMS = [
    "wingspan",
    "wing_area",
    "h_tail_area",
    "v_tail_area",
    "thrust_to_weight",
    "total_mass",
    "cg_x_offset",
]


def morphology_param_names() -> List[str]:
    """Names of morphology genome parameters, in order."""
    return list(_MORPHOLOGY_PARAMS)