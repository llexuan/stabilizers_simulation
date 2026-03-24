stabcodes_repo

Coordinate-free stabilizer-code circuit builder & decoder

Overview

stabcodes_repo builds Stim circuits and Detector Error Models (DEM) from stabilizer descriptions and scheduling information, and evaluates their performance under noise.

The system supports:

Constructing circuits from stabilizer lists
Applying per-stabilizer CNOT layer schedules
Generating Detector Error Models (when valid)
Running decoding experiments using Sinter + PyMatching
Plotting logical error rates across physical noise levels

This repository is designed for coordinate-free stabilizer-code construction, simulation, and decoding experiments, with a focus on flexibility and system-level evaluation.

Features
Build Stim circuits from sparse or dense stabilizer descriptions
Generate Detector Error Models (DEM)
Perform physical error rate sweeps
Decode using PyMatching
Export results in JSON and CSV formats
Automatically generate logical error rate plots
Installation
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
Quick Start
Interactive Build
python -m stabcodes.cli.build

You will be prompted to:

Paste stabilizers (sparse or dense Pauli form)
Enter:
Number of rounds R
Layers per round L
Per-stabilizer layer assignments (1..L)
Build from Benchmark File

Example: d=3 rotated surface code

python -m stabcodes.cli.build \
  --out results/d3_rotated_surface \
  < benchmarks/rotated_surface/d3.txt
Decode and Plot
python -m stabcodes.decode.run \
  --meta results/<run>/build_meta.json \
  --out  results/<run> \
  --shots 200000 \
  --plist 0.001,0.003,0.005,0.007,0.009
Output Files

Each run produces:

circuit.stim — Stim circuit
dem.txt — Detector Error Model (if valid)
build_meta.json — Metadata for decoding
metrics.json
metrics.csv
plot.png — Logical error rate plot
Input File Format

Benchmark files follow this structure:

# Stabilizers (one per line)
Z0 Z1 Z5 Z7
X1 X2 X4 X5
...

<blank line>

R
L

# One line per stabilizer:
# comma-separated layer numbers (1..L)
4,2,3,1
2,1
...
Important Notes
Stabilizers can be:
Sparse (e.g., Z0, X1)
Dense Pauli strings
A blank line must separate stabilizers from parameters
Each layer assignment must match the stabilizer weight exactly
Included Benchmarks
benchmarks/
  rotated_surface/
    d3.txt
    d5.txt
  reption_code/
    repetition.txt
  color_code/
    713_color_code.txt
Reproducing Experiments
d=3 Rotated Surface Code
python -m stabcodes.cli.build \
  --out results/d3_rotated_surface \
  < benchmarks/rotated_surface/d3.txt

python -m stabcodes.decode.run \
  --meta results/d3_rotated_surface/build_meta.json \
  --out  results/d3_rotated_surface \
  --shots 200000 \
  --plist 0.001,0.003,0.005,0.007,0.009
d=5 Rotated Surface Code
python -m stabcodes.cli.build \
  --out results/d5_rotated_surface \
  < benchmarks/rotated_surface/d5.txt

python -m stabcodes.decode.run \
  --meta results/d5_rotated_surface/build_meta.json \
  --out  results/d5_rotated_surface \
  --shots 200000 \
  --plist 0.001,0.003,0.005,0.007,0.009
Repetition Code (Z-only)
python -m stabcodes.cli.build \
  --out results/repetition_code \
  < benchmarks/reption_code/repetition.txt

python -m stabcodes.decode.run \
  --meta results/repetition_code/build_meta.json \
  --out  results/repetition_code \
  --shots 200000 \
  --plist 0.001,0.003,0.005,0.007,0.009
713 Color Code (Z-only)
python -m stabcodes.cli.build \
  --out results/713_color_code \
  < benchmarks/color_code/713_color_code.txt

python -m stabcodes.decode.run \
  --meta results/713_color_code/build_meta.json \
  --out  results/713_color_code \
  --shots 200000 \
  --plist 0.001,0.003,0.005,0.007,0.009
Troubleshooting
Missing stabilizers error

Ensure:

Stabilizers appear before the blank line
No extra text or prompt symbols are included
DEM fails (non-deterministic observables)
Z-only circuits:
Use Z resets and Z logicals
CSS circuits:
Include both X and Z stabilizers
Ensure valid scheduling
Decoder fallback

If compiled sampling fails, the system falls back to:

Stim sampling
PyMatching decoding

Results will still be generated.

Incorrect logical error rates

Check:

Stabilizer definitions
Layer assignments
R and L values
Shot count
--plist values
Noise parameters
Repository Layout
benchmarks/
results/
src/stabcodes/
  cli/
    build.py
  decode/
    run.py
  io/
  model/
  schedule/
  build/
