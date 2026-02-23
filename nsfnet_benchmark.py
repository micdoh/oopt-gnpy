#!/usr/bin/env python3
"""
NSFNET Benchmark: Simulates 100 optical path requests on the NSFNET topology
and times each request individually.

Topology: 14-node NSFNET with 21 bidirectional links (42 fibers)
Spectrum: 100 channels @ 50 GHz spacing (191.25 - 196.25 THz)
Requests: 100 random source-destination pairs, 100 Gbps each
"""

import json
import random
import time
import logging
from copy import deepcopy
from pathlib import Path

from gnpy.tools.json_io import load_equipments_and_configs, load_network, load_json, requests_from_json
from gnpy.core.network import add_missing_elements_in_network, design_network
from gnpy.core.parameters import SimParams
from gnpy.core.utils import automatic_nch, dbm2watt
from gnpy.core.equipment import trx_mode_params
from gnpy.topology.spectrum_assignment import build_oms_list, pth_assign_spectrum
from gnpy.topology.request import (compute_path_dsjctn, compute_path_with_disjunction,
                                    correct_json_route_list, PathRequest, ResultElement,
                                    deduplicate_disjunctions, requests_aggregation)
from gnpy.tools.json_io import disjunctions_from_json

logging.basicConfig(level=logging.WARNING)

SCRIPT_DIR = Path(__file__).parent
TOPOLOGY_FILE = SCRIPT_DIR / 'nsfnet_topology.json'
EQPT_FILE = SCRIPT_DIR / 'gnpy' / 'example-data' / 'eqpt_config.json'

NODES = ['WA', 'CA1', 'CA2', 'UT', 'CO', 'NE', 'TX', 'IL', 'PA', 'GA', 'MI', 'NY', 'NJ', 'DC']
NUM_REQUESTS = 100
SEED = 42


def build_equipment_with_100ch():
    """Load equipment config and override SI to use 100 channels @ 50 GHz."""
    equipment = load_equipments_and_configs(EQPT_FILE, None, None)
    # Override SI defaults for 100 channels in C-band
    si = equipment['SI']['default']
    si.f_min = 191.3e12
    si.f_max = 196.1e12
    si.spacing = 50e9
    nch = automatic_nch(si.f_min, si.f_max, si.spacing)
    print(f"Spectrum config: {si.f_min/1e12:.2f} - {si.f_max/1e12:.2f} THz, "
          f"{si.spacing/1e9:.0f} GHz spacing, {nch} channels")
    return equipment


def generate_requests(n, seed=SEED):
    """Generate n random source-destination pairs (no self-loops)."""
    rng = random.Random(seed)
    pairs = []
    for _ in range(n):
        src, dst = rng.sample(NODES, 2)
        pairs.append((src, dst))
    return pairs


def build_service_data(pairs):
    """Build a service request JSON structure for all pairs."""
    requests = []
    for i, (src, dst) in enumerate(pairs):
        requests.append({
            "request-id": str(i),
            "source": f"trx {src}",
            "destination": f"trx {dst}",
            "src-tp-id": f"trx {src}",
            "dst-tp-id": f"trx {dst}",
            "bidirectional": False,
            "path-constraints": {
                "te-bandwidth": {
                    "technology": "flexi-grid",
                    "trx_type": "Voyager",
                    "trx_mode": "mode 1",
                    "effective-freq-slot": [{"N": None, "M": None}],
                    "spacing": 50e9,
                    "max-nb-of-channel": None,
                    "output-power": None,
                    "path_bandwidth": 100e9
                }
            }
        })
    return {"path-request": requests, "synchronization": []}


def main():
    print("=" * 70)
    print("NSFNET Optical Network Benchmark")
    print("=" * 70)

    # Load equipment and network
    print("\n[1/4] Loading equipment and network topology...")
    t0 = time.perf_counter()
    equipment = build_equipment_with_100ch()
    network = load_network(TOPOLOGY_FILE, equipment)
    SimParams.set_params({})
    t_load = time.perf_counter() - t0
    print(f"  Loaded in {t_load:.3f}s")

    # Design network (auto-insert EDFAs, set gains, etc.)
    print("\n[2/4] Designing network (auto-inserting amplifiers)...")
    t0 = time.perf_counter()
    add_missing_elements_in_network(network, equipment)

    si = equipment['SI']['default']
    params = {
        'request_id': 'reference',
        'trx_type': '',
        'trx_mode': '',
        'source': None,
        'destination': None,
        'bidir': False,
        'nodes_list': [],
        'loose_list': [],
        'format': '',
        'path_bandwidth': 0,
        'effective_freq_slot': None,
        'nb_channel': automatic_nch(si.f_min, si.f_max, si.spacing),
        'power': dbm2watt(si.power_dbm),
        'tx_power': dbm2watt(si.power_dbm if si.tx_power_dbm is None else si.tx_power_dbm),
    }
    trx_params = trx_mode_params(equipment)
    params.update(trx_params)
    ref_channel = PathRequest(**params)
    design_network(ref_channel, network, equipment, set_connector_losses=True, verbose=False)

    node_count = len([n for n in network.nodes()])
    t_design = time.perf_counter() - t0
    print(f"  Designed network with {node_count} elements in {t_design:.3f}s")

    # Generate requests
    print(f"\n[3/4] Generating {NUM_REQUESTS} random requests...")
    pairs = generate_requests(NUM_REQUESTS)
    src_dst_summary = {}
    for s, d in pairs:
        key = f"{s}->{d}"
        src_dst_summary[key] = src_dst_summary.get(key, 0) + 1
    print(f"  {len(set(pairs))} unique source-destination pairs")

    # Process all requests as a batch (like gnpy-path-request does) and time it
    print(f"\n[4/4] Processing {NUM_REQUESTS} requests...")
    all_data = build_service_data(pairs)

    # Build OMS list
    oms_list = build_oms_list(network, equipment)

    # Process requests one at a time to get per-request timing
    timings = []
    results_summary = []
    cumulative_oms = oms_list  # shared spectrum state

    for i in range(NUM_REQUESTS):
        single_data = {
            "path-request": [all_data["path-request"][i]],
            "synchronization": []
        }

        t_start = time.perf_counter()

        # Parse request
        rqs = requests_from_json(single_data, equipment)
        rqs = correct_json_route_list(network, rqs)
        dsjn = disjunctions_from_json(single_data)
        dsjn = deduplicate_disjunctions(dsjn)
        rqs, dsjn = requests_aggregation(rqs, dsjn)

        # Compute path
        pths = compute_path_dsjctn(network, equipment, rqs, dsjn)

        # Propagate
        propagatedpths, reversed_pths, reversed_propagatedpths = \
            compute_path_with_disjunction(network, equipment, rqs, pths)

        # Assign spectrum (using shared OMS state so spectrum fills up)
        pth_assign_spectrum(pths, rqs, cumulative_oms, reversed_pths)

        t_elapsed = time.perf_counter() - t_start
        timings.append(t_elapsed)

        # Collect result info
        rq = rqs[0]
        blocked = hasattr(rq, 'blocking_reason') and rq.blocking_reason != 'NO_BLOCKING'
        has_spectrum = hasattr(rq, 'N') and rq.N is not None

        status = "OK"
        if blocked:
            status = f"BLOCKED ({rq.blocking_reason})"
        elif not has_spectrum:
            status = "NO_SPECTRUM"

        results_summary.append({
            'id': i,
            'src': pairs[i][0],
            'dst': pairs[i][1],
            'status': status,
            'time_ms': t_elapsed * 1000
        })

        if (i + 1) % 25 == 0:
            avg_so_far = sum(timings) / len(timings) * 1000
            print(f"  Processed {i+1}/{NUM_REQUESTS} requests (avg {avg_so_far:.1f} ms/req)")

    # Print results
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)

    print(f"\n{'Req':>4} {'Source':>5} -> {'Dest':<5} {'Time (ms)':>10} {'Status'}")
    print("-" * 55)
    for r in results_summary:
        print(f"{r['id']:>4} {r['src']:>5} -> {r['dst']:<5} {r['time_ms']:>10.2f} {r['status']}")

    # Timing statistics
    times_ms = [t * 1000 for t in timings]
    ok_count = sum(1 for r in results_summary if r['status'] == 'OK')
    blocked_count = NUM_REQUESTS - ok_count

    print(f"\n{'=' * 70}")
    print("TIMING SUMMARY")
    print(f"{'=' * 70}")
    print(f"  Total requests:    {NUM_REQUESTS}")
    print(f"  Successful:        {ok_count}")
    print(f"  Blocked:           {blocked_count}")
    print(f"  Total time:        {sum(timings):.3f}s")
    print(f"  Mean per request:  {sum(times_ms)/len(times_ms):.2f} ms")
    print(f"  Median:            {sorted(times_ms)[len(times_ms)//2]:.2f} ms")
    print(f"  Min:               {min(times_ms):.2f} ms")
    print(f"  Max:               {max(times_ms):.2f} ms")
    print(f"  Std dev:           {(sum((t - sum(times_ms)/len(times_ms))**2 for t in times_ms) / len(times_ms))**0.5:.2f} ms")

    # Breakdown by first 25 vs last 25 (to see if spectrum filling slows things down)
    first_25 = times_ms[:25]
    last_25 = times_ms[-25:]
    print(f"\n  First 25 avg:      {sum(first_25)/25:.2f} ms")
    print(f"  Last 25 avg:       {sum(last_25)/25:.2f} ms")


if __name__ == '__main__':
    main()
