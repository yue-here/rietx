# rietx-kernels

The compiled kernels of [rietx](https://github.com/yue-here/rietx), a
Rietveld refinement package for powder diffraction. Five compute the model's
peak profiles and their derivatives. From 1.1.0, two more draw the structure
figure. From 1.2.0, on x86-64, the two kernels for asymmetric peaks call an
exponential ported from SLEEF, held to its 1.0 ulp bound, and run four wide
where the CPU has AVX2. `exp` exposes the exponential they call so its bound
can be measured. From 1.3.0, two test the dichotomy indexer's boxes. From
1.4.0, three serve the structure-solution engine: the per-site orbit sums of
the structure factor, their one-site twin, and the interatomic contact term.
They are built for rietx and have no other public interface.

The package is one abi3 wheel per platform, built from Rust with PyO3. Its
major version is the kernel interface number, `rietx_kernels.KERNEL_ABI`.
A rietx that calls them pins that major version and checks the integer at
import.

The source lives in the rietx repository under `kernels/`. Build it with
`maturin develop --release -m kernels/Cargo.toml` from the repository root.
