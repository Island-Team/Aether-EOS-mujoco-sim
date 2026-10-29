# Island package release

The v1.0.1 package is an IsOS backend release candidate for `island/mujoco-sim`. It is not published. Build and verify the exact local archive and manifest, then submit them for review before creating or publishing the GitHub release or package-center entry.

`tools/build-package-release.py` assembles a local candidate for the curated
Island package center. It runs the existing CTest suite, stages the simulator
binary, scene assets, license files, and EOS configuration templates, then
measures the exact archive size and SHA-256 digest. It does not upload or
publish a release.

Build on each target machine separately. Supply the minimum glibc version
established for that binary and only Ubuntu versions actually tested there:

```sh
python3.12 tools/build-package-release.py \
  --version 1.0.1 \
  --build-dir build \
  --eos-root ../Island-eos \
  --output /tmp/island-mujoco-release \
  --glibc-min 2.35 \
  --tested-ubuntu 24.04
```

The archive contains `bin/eos-mujoco-sim` as a launcher. It requires an
operator-provided MuJoCo 3.16.0 installation and `MUJOCO_ROOT` pointing at its
root directory. The archive includes neither the MuJoCo library nor EOS. The
candidate manifest lists all SONAMEs reported by `ldd`; IsOS checks host
compatibility during package installation. Review the full list and the actual
target machine before approval.

The builder writes `island-release.<arch>.draft.json` using IsOS release schema v4. Its `assets` entry records the tested Linux architecture and minimum glibc, while `source_commit`, SHA-256, and byte size identify the exact source and archive. Build each target natively, review both drafts and assets, and combine only qualified target entries into the final `island-release.json` uploaded with the GitHub `v1.0.1` release. Do not claim an architecture or Ubuntu version that was not tested.

The activation bundle contains `module.toml`, `eos.toml`, and `binding.toml` from the current EOS layout. IsOS installs the backend but stages activation until the package is selected in the deployment graph and `isos config apply` is run. Installation and apply do not restart a running deployment. The generated EOS module launches the packaged `eos-mujoco-sim`, with sockets under the deployment run directory. MuJoCo 3.16.0 remains an operator-provided dependency.

Before publication, review the release source, asset bytes, licenses, digest,
requirements, and EOS behavior. A member's submission needs an independent
reviewer; a developer can publish a complete manifest directly. A changed
binary needs a new version. Do not publish this candidate before review.

To inspect archive layout without claiming qualification, pass `--skip-tests`. Do not submit that candidate for approval.
