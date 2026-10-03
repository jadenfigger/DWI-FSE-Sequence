# koma_sim.jl  -  Bloch simulation of a Pulseq .seq file with KomaMRI.jl
#
# Run from the Julia REPL (use the FULL path to the .seq, include() does not change folders):
#     julia> SEQ_FILE = raw"C:\path\to\my_seq.seq"; include(raw"C:\path\to\koma_sim.jl")
#
# Results are always written as CSV files next to the .seq:
#     <name>_koma_signal.csv     ADC time, real, imag of the raw signal
#     <name>_koma_echoes.csv     echo #, |center sample|, |peak|  (fraction of M0)
#     <name>_koma_snapshots.csv  block, z, Mxy (re, im), Mz of every spin after selected blocks
# Plot them with:  python plot_koma.py <name>
# KomaMRI's own plots (sequence diagram, k-space, signal) are also saved as .html when possible.
#
# What it simulates
#   A "voxel" made of many isochromats:
#     - spread across the slice (z) and the in-plane voxel (x, y), so crushers and
#       imaging gradients dephase it like a real voxel
#     - Lorentzian off-resonance spread (= T2') plus an optional global B0 offset
#   The full sequence with real RF shapes (slice profile included), plus "snapshots":
#   the sequence up to selected blocks, so you can watch the crusher helices and what
#   each RF pulse does to them.
#
# B1 error: make scaled copies of the .seq with scale_b1.py and run each one.

using KomaMRI, Random, Statistics, DelimitedFiles, CUDA

SEQ_FILE = @isdefined(SEQ_FILE) ? SEQ_FILE : "my_seq.seq"
isfile(SEQ_FILE) || error("SEQ_FILE not found: $SEQ_FILE  (use the full path)")
stem = splitext(SEQ_FILE)[1]

# ---------------------------------------------------------------- settings
voxel_xy  = 0.2e-3     # in-plane voxel size [m]
slice_thk = 1.0e-3     # slice thickness [m]; spins span 2x this so the slice edges are included
Nspins    = 20_000
T1, T2    = 1.5, 0.08  # [s]
T2prime   = 0.03       # [s] intravoxel B0 spread (Lorentzian)
B0_Hz     = 0.0        # global off-resonance [Hz]
snap_blocks = Int[]    # blocks to snapshot; empty = right after each RF pulse

# Save a KomaMRI plot to html without needing a plot window (never stops the script)
function save_plot(f, name)
    try
        p = f()
        KomaMRI.KomaMRIPlots.PlotlyJS.savefig(p, name)
        println("saved $name")
    catch err
        println("skipped plot $name: ", sprint(showerror, err)[1:min(end, 120)])
    end
end

# ---------------------------------------------------------------- sequence
seq = read_seq(SEQ_FILE)
println("read $(length(seq)) blocks")
save_plot(() -> plot_seq(seq), stem * "_koma_seq.html")
save_plot(() -> plot_kspace(seq), stem * "_koma_kspace.html")

# ---------------------------------------------------------------- phantom
Random.seed!(1)
x = (rand(Nspins) .- 0.5) .* voxel_xy
y = (rand(Nspins) .- 0.5) .* voxel_xy
z = (rand(Nspins) .- 0.5) .* 2slice_thk
# Lorentzian off-resonance with HWHM 1/(2π T2') Hz  ->  exp(-t/T2') decay of the FID
Δf = clamp.(tan.(π .* (rand(Nspins) .- 0.5)) ./ (2π * T2prime), -2000, 2000) .+ B0_Hz
obj = Phantom(name="voxel", x=x, y=y, z=z,
              ρ=ones(Nspins), T1=fill(T1, Nspins), T2=fill(T2, Nspins),
              Δw=2π .* Δf)       # Δw is in rad/s
sys = Scanner()

# ---------------------------------------------------------------- full simulation
params(rt) = Dict{String,Any}("return_type" => rt)
sig = simulate(obj, seq, sys; sim_params=params("mat"))
sig = vec(sig[:, :, 1]) ./ Nspins          # single coil, normalized to M0
t_adc = try
    get_adc_sampling_times(seq)
catch
    collect(1.0:length(sig))                 # fall back to sample index
end
writedlm(stem * "_koma_signal.csv", hcat(t_adc, real(sig), imag(sig)), ',')

Nadc  = [a.N for a in seq.ADC if a.N > 0]  # samples per ADC window (= per echo)
edges = cumsum([0; Nadc])
echo_center = [abs(sig[edges[i] + Nadc[i] ÷ 2 + 1]) for i in eachindex(Nadc)]
echo_peak   = [maximum(abs.(sig[edges[i]+1:edges[i+1]])) for i in eachindex(Nadc)]
writedlm(stem * "_koma_echoes.csv", hcat(1:length(Nadc), echo_center, echo_peak), ',')
println("echo |center| = ", round.(echo_center, digits=4))

# ---------------------------------------------------------------- snapshots over time
rf_blocks = [i for i in 1:length(seq) if is_RF_on(seq[i])]
blocks = isempty(snap_blocks) ? rf_blocks : snap_blocks
rows = Matrix{Float64}(undef, 0, 5)
for b in blocks
    M = simulate(obj, seq[1:b], sys; sim_params=params("state"))
    global rows = vcat(rows, hcat(fill(b, Nspins), z, real(M.xy), imag(M.xy), M.z))
    println("after block $b: |mean Mxy| = $(round(abs(mean(M.xy)), digits=4)),  mean Mz = $(round(mean(M.z), digits=4))")
end
writedlm(stem * "_koma_snapshots.csv", rows, ',')
println("done. Plot with:  python plot_koma.py \"$stem\"")
