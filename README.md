# GNPy: Optical Route Planning and DWDM Network Optimization

## NSFNET Benchmark Experiment

This fork includes an NSFNET benchmark that simulates 100 optical path requests on the classic 14-node NSFNET topology and reports per-request timing.

**Topology:** 14 nodes, 21 bidirectional links (42 fibers), 96 C-band channels @ 50 GHz spacing.

### Setup

```bash
# 1. Clone this fork
git clone https://github.com/micdoh/oopt-gnpy.git
cd oopt-gnpy

# 2. Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Try installing the full package (requires cmake, ninja, and libyang C library)
pip install -e .

# If oopt_gnpy_libyang fails to build (common on macOS), install the core
# dependencies manually instead — the benchmark does not need YANG support:
pip install "numpy>=1.24.4,<2" "scipy<2" networkx pandas tabulate openpyxl xlrd

# Then create a minimal mock for the libyang binding:
mkdir -p .venv/lib/python3.*/site-packages/oopt_gnpy_libyang
cat > .venv/lib/python3.*/site-packages/oopt_gnpy_libyang/__init__.py << 'EOF'
class _MockClass:
    def __init__(self, *a, **kw): pass
    def __getattr__(self, n): return _MockClass()
    def __call__(self, *a, **kw): return _MockClass()
    def __or__(self, o): return self
    def __ror__(self, o): return self
    def __iter__(self): return iter([])
    def __bool__(self): return False
    def __str__(self): return ""
SNode = Context = DataNode = _MockClass
ContextOptions = DataFormat = LogOptions = ParseOptions = PrintFlags = ValidationOptions = _MockClass()
Error = Exception
def set_log_options(*a, **kw): pass
def yang_search_path(): return ""
EOF
```

### Run the benchmark

```bash
# Make sure the venv is active and PYTHONPATH includes the repo root
source .venv/bin/activate
PYTHONPATH=. python3 nsfnet_benchmark.py
```

The script will:
1. Load the NSFNET topology (`nsfnet_topology.json`) and equipment library
2. Auto-design the network (insert amplifiers, split long fibers)
3. Generate 100 random 100 Gbps demands between node pairs
4. Process each request individually (path computation, signal propagation, spectrum assignment) and time it
5. Print per-request results and a timing summary

---

[![Install via pip](https://img.shields.io/pypi/v/gnpy)](https://pypi.org/project/gnpy/)
[![Python versions](https://img.shields.io/pypi/pyversions/gnpy)](https://pypi.org/project/gnpy/)
[![Documentation status](https://readthedocs.org/projects/gnpy/badge/?version=master)](http://gnpy.readthedocs.io/en/master/?badge=master)
[![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/Telecominfraproject/oopt-gnpy/main.yml)](https://github.com/Telecominfraproject/oopt-gnpy/actions/workflows/main.yml)
[![Gerrit](https://img.shields.io/badge/patches-via%20Gerrit-blue)](https://review.gerrithub.io/q/project:Telecominfraproject/oopt-gnpy+is:open)
[![Contributors](https://img.shields.io/github/contributors-anon/Telecominfraproject/oopt-gnpy)](https://github.com/Telecominfraproject/oopt-gnpy/graphs/contributors)
[![Code Coverage via codecov](https://img.shields.io/codecov/c/github/Telecominfraproject/oopt-gnpy)](https://codecov.io/gh/Telecominfraproject/oopt-gnpy)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.3458319.svg)](https://doi.org/10.5281/zenodo.3458319)
[![Matrix chat](https://img.shields.io/matrix/oopt-gnpy:matrix.org)](https://matrix.to/#/%23oopt-gnpy%3Amatrix.org?via=matrix.org)

GNPy is an open-source, community-developed library for building route planning and optimization tools in real-world mesh optical networks.
We are a consortium of operators, vendors, and academic researchers sponsored via the [Telecom Infra Project](http://telecominfraproject.com)'s [OOPT/PSE](https://telecominfraproject.com/open-optical-packet-transport) working group.
Together, we are building this tool for rapid development of production-grade route planning tools which is easily extensible to include custom network elements and performant to the scale of real-world mesh optical networks.

![GNPy with an OLS system](docs/images/GNPy-banner.png)

## Quick Start

Install either via [Docker](https://gnpy.readthedocs.io/en/master/install.html#using-prebuilt-docker-images), or as a [Python package](https://gnpy.readthedocs.io/en/master/install.html#using-python-on-your-computer).
Read our [documentation](https://gnpy.readthedocs.io/), learn from the demos, and [get in touch with us](https://github.com/Telecominfraproject/oopt-gnpy/discussions).

This example demonstrates how GNPy can be used to check the expected SNR at the end of the line by varying the channel input power:

![Running a simple simulation example](docs/images/gnpy-transmission-example.svg)

GNPy can do much more, including acting as a Path Computation Engine, tracking bandwidth requests, or advising the SDN controller about a best possible path through a large DWDM network.
Learn more about this [in the documentation](https://gnpy.readthedocs.io/), or give it a [try online at `gnpy.app`](https://gnpy.app/):

[![Path propagation at gnpy.app](docs/images/2022-04-12-gnpy-app.png)](https://gnpy.app/)

## Project Calendar

See upcoming meetings on the [Project Calendar](https://telecominfraproject.github.io/oopt-gnpy/calendar.html). The calendar is embedded from Google Calendar and updates automatically.
