# Stabilizer Circuit Simulation

This project builds noisy stabilizer-code circuits, generates Stim detector error
models, decodes sampled detector events with PyMatching, and measures logical
error rates. Its main purpose is to compare how stabilizer definitions and CNOT
orders affect logical performance.

## What the program does

For a benchmark input, the program:

1. Reads the X and Z stabilizers.
2. Reads the number of syndrome rounds and CNOT layers.
3. Reads the CNOT-layer assignment for each stabilizer.
4. Builds a noisy Stim circuit.
5. Generates a detector error model (DEM).
6. Samples the circuit at several physical error probabilities.
7. Decodes the samples with PyMatching.
8. Reports the logical error rate and its 95% confidence interval.
9. Saves the circuit, numerical results, and a log-log plot.

In Python this process is normally called **running** the program, rather than
compiling it.

## Requirements

- Python 3.10 or newer
- NumPy
- Matplotlib
- Stim
- PyMatching

Create an environment and install the dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install numpy matplotlib stim pymatching
```

Run commands below from the repository root.

## Recommended: build and decode automatically

Give the automatic runner a benchmark path:

```bash
PYTHONPATH=src python -m stabcodes.run \
  benchmarks/rotated_surface/d3.txt
```

It asks for three simulation settings:

```text
Shots per physical error rate [200000]:
Physical error rates (comma-separated) [0.001,0.003,0.005,0.007,0.009]:
Random seed [12345]:
```

Press Enter without typing anything to accept a displayed default.

- **Shots** controls the number of Monte Carlo samples at each physical error
  rate. More shots reduce statistical uncertainty but take longer.
- **Physical error rates** (`p` values) determine the points evaluated and
  plotted.
- **Seed** makes random sampling reproducible. Use the same seed, shot count,
  and `p` values when comparing CNOT schedules.

The output directory is derived automatically from the benchmark path. For
example:

```text
benchmarks/rotated_surface/d3.txt
```

produces:

```text
results/rotated_surface/d3/
```

An output directory can optionally be selected explicitly:

```bash
PYTHONPATH=src python -m stabcodes.run \
  benchmarks/rotated_surface/d3.txt \
  --out results/my_d3_experiment
```

## Included benchmarks

Run the d=3 rotated surface code:

```bash
PYTHONPATH=src python -m stabcodes.run \
  benchmarks/rotated_surface/d3.txt
```

Run the d=5 rotated surface code:

```bash
PYTHONPATH=src python -m stabcodes.run \
  benchmarks/rotated_surface/d5.txt
```

Run the repetition code:

```bash
PYTHONPATH=src python -m stabcodes.run \
  benchmarks/reptition_code/reptition_code.txt
```

The `reptition_code` directory and filename retain their current misspelling.

Run the 7-qubit color-code benchmark:

```bash
PYTHONPATH=src python -m stabcodes.run \
  benchmarks/color_code/713_color_code.txt
```

## Benchmark input format

A benchmark text file contains:

1. One stabilizer per line.
2. A blank line terminating the stabilizer block.
3. The number of measurement rounds, `R`.
4. The number of CNOT layers per round, `L`.
5. One layer-assignment line for every stabilizer.

Example:

```text
Z0 Z1 Z3 Z4
Z2 Z5
X0 X1
X1 X2 X4 X5

1
4
4,2,3,1
4,3
2,1
4,3,2,1
```

Here:

- `R = 1`
- `L = 4`
- Schedule lines correspond to the stabilizers in their original order: all Z
  stabilizers followed by all X stabilizers.

For `Z0 Z1 Z3 Z4`, the support is sorted as `[0, 1, 3, 4]`. Its assignment
`4,2,3,1` means:

- qubit 4 participates in layer 1;
- qubit 1 participates in layer 2;
- qubit 3 participates in layer 3;
- qubit 0 participates in layer 4.

Its effective local CNOT order is therefore `4 -> 1 -> 3 -> 0`.

Every assignment must:

- contain one number per qubit in that stabilizer;
- use layer numbers from `1` through `L`;
- appear in the same order as the stabilizer definitions.

The current circuit builder schedules stabilizers serially. The assignments
control CNOT order within each stabilizer; they do not represent globally
parallel layers across all stabilizers.

## Comparing CNOT orders

Create separate benchmark files with the same stabilizers but different final
schedule lines:

```text
benchmarks/rotated_surface/d3_order_a.txt
benchmarks/rotated_surface/d3_order_b.txt
```

Run each benchmark separately and use identical shots, physical error rates,
and seeds. Their automatically derived output directories will remain separate:

```text
results/rotated_surface/d3_order_a/
results/rotated_surface/d3_order_b/
```

Only the CNOT assignments should change when the goal is to isolate the effect
of ordering.

## Output files

An automatic run produces:

- `circuit.stim` — generated Stim circuit.
- `dem.txt` — detector error model.
- `build_meta.json` — circuit metadata used during decoding.
- `metrics.json` — structured simulation results.
- `metrics.csv` — spreadsheet-friendly simulation results.
- `plot.png` — physical versus logical error-rate plot.
- `run_config.json` — benchmark path, shots, probabilities, seed, and
  completion time.

Each metrics record contains:

- physical error probability;
- shot count;
- observed logical failures;
- logical error rate per shot;
- lower and upper 95% confidence limits;
- the sampling seed used for that probability.

`n` in the console and plot legend means the number of data qubits. For the
d=3 rotated surface benchmark, `n=9`; for d=5, `n=25`.

## Advanced: run build and decode separately

Build only:

```bash
PYTHONPATH=src python -m stabcodes.cli.build \
  --out results/manual_d3 \
  < benchmarks/rotated_surface/d3.txt
```

Decode an existing build:

```bash
PYTHONPATH=src python -m stabcodes.decode.run \
  --meta results/manual_d3/build_meta.json \
  --out results/manual_d3 \
  --shots 200000 \
  --plist 0.001,0.003,0.005,0.007,0.009 \
  --seed 12345
```

The automatic runner is recommended for normal use because it performs both
steps and records the selected settings.

## Troubleshooting

### Module `stabcodes` cannot be found

Run from the repository root and include `PYTHONPATH=src`:

```bash
PYTHONPATH=src python -m stabcodes.run benchmarks/rotated_surface/d3.txt
```

### Benchmark parsing fails

Check that:

- a blank line follows the stabilizer definitions;
- every stabilizer uses only X operators or only Z operators;
- every schedule has one entry per stabilizer qubit;
- every layer number is between `1` and `L`.

### Detector error model construction fails

Check that X and Z stabilizers commute and that the chosen circuit produces
deterministic detectors and logical observables.

### Results vary between runs

Use the same seed, shots, and physical error rates. Small differences are
expected when seeds differ because decoding uses Monte Carlo sampling.
