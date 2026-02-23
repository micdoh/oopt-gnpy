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

### Physical layer model

GNPy's propagation engine tracks signal power, ASE noise, and nonlinear interference (NLI) independently per channel across every network element. The key modelling capabilities are summarised below.

**Nonlinear interference (NLI)**

| Model | Reference | Notes |
|---|---|---|
| GN model (analytical) | Poggiolini et al., [arXiv:1209.0394](https://arxiv.org/abs/1209.0394), Eq. 120 | Closed-form; SPM weight 16/27, XPM weight 2×16/27 |
| GGN model (spectrally separated) | [arXiv:1710.02225](https://arxiv.org/abs/1710.02225), Eq. 21 | More accurate spectral separation of interferers; higher cost |
| GGN approximation | D'Amico et al., [JLT 2022](https://doi.org/10.1364/JLT.451482), Eq. 24-25 | Faster approximation suitable for C+L+S bands |

All three variants compute per-channel NLI power from fibre parameters (gamma, beta2, beta3, effective area) and the full loaded spectrum.

**ISRS (Inter-channel Stimulated Raman Scattering)**

The Raman solver (`RamanSolver` in `gnpy/core/science_utils.py`) computes frequency-dependent power transfer between channels via the Raman gain coefficient matrix. It solves the coupled first-order ODEs along the fibre either perturbatively (Taylor expansion, orders 1-4) or numerically. The resulting per-channel power/loss profiles feed into the NLI and noise calculations. However, ISRS is not yet fully integrated into the GN/GGN model itself for wideband (multi-band) scenarios — the Raman power tilt and the NLI are currently computed in separate steps.

**Distributed Raman amplification**

Fully supported via the `RamanFiber` element. Pump configuration includes:
- Co-propagating and counter-propagating pumps (arbitrary number, frequency, and power)
- Iterative bidirectional solver for co+counter pump interactions
- Spontaneous Raman scattering ASE (thermal noise) from each pump
- Configurable spatial resolution for solver and output

Raman amplification requires a simulation parameters file (`--sim-params`) to be passed at runtime.

**Nyquist subchannels / superchannels**

Not supported. The spectrum representation (`SpectralInformation` in `gnpy/core/info.py`) operates at per-channel granularity — each carrier has a single baud rate, slot width, and roll-off. There is no native subchannel or subcarrier decomposition within a channel. YANG data models reference "subcarrier" definitions but these are protocol-level only and not used in propagation. As a workaround, subchannels could be modelled as separate narrow-bandwidth carriers, but this is not equivalent to a proper Nyquist-WDM subchannel model.

**Other physical layer features**

| Feature | Details |
|---|---|
| ASE noise (EDFA) | Noise figure model (polynomial, dual-stage, or OpenROADM); frequency-dependent gain ripple and dynamic gain tilt |
| ASE noise (Raman) | Spontaneous Raman emission including thermal photon factors |
| Chromatic dispersion | Frequency-dependent via beta2/beta3 or dispersion + slope; cumulative across path |
| PMD | Per-span DGD (`pmd_coef × sqrt(length)`); cumulative RSS across path |
| PDL | Tracked per channel through ROADMs (add/drop/express paths) |
| Fibre nonlinearity | Frequency-dependent gamma from n2 and effective area |
| ROADM impairments | Insertion loss, OSNR penalty, PMD, PDL, power equalisation (per-channel, PSD, or per-slot-width modes) |
| Connector / splice losses | Separate in/out connector loss per fibre span; lumped losses at arbitrary positions |
| Spectrum assignment | First-fit policy on ITU flex-grid (6.25 GHz granularity, configurable guard band) |

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
