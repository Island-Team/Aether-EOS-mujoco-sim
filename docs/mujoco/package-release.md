# Island package release candidate

`tools/build-package-release.py` assembles a local candidate for the curated
Island package center. It runs the existing CTest suite, stages the simulator
binary, scene assets, license files, and EOS configuration templates, then
measures the exact archive size and SHA-256 digest. It does not upload or
publish a release.

Build on each target machine separately. Supply the minimum glibc version
established for that binary and only Ubuntu versions actually tested there:

```sh
python3 tools/build-package-release.py \
  --version 0.1.0 \
  --build-dir build \
  --eos-root ../Island-eos \
  --output /tmp/island-mujoco-release \
  --glibc-min 2.35 \
  --tested-ubuntu 24.04
```

The archive contains `bin/eos-mujoco-sim` as a launcher. It requires an
operator-provided MuJoCo 3.16.0 installation and `MUJOCO_ROOT` pointing at its
root directory. The archive includes neither the MuJoCo library nor EOS. The
candidate manifest lists all SONAMEs reported by `ldd`; `island-pkg doctor`
checks them before installation. Review the full list and the actual target
machine before approval.

The `.manifest.draft.json` file describes the expected GitHub Release asset
URL. After a tag and asset have actually been uploaded, reviewers must check
the source, asset bytes, licenses, digest, requirements, and EOS behavior before
entering this manifest into Island-port. Keep a version immutable after
publication; a changed binary needs a new version.

To inspect archive layout without claiming qualification, pass `--skip-tests`.
Do not submit that candidate for approval. The package's activation templates
generate separate `eos.toml`, `sim.toml`, and `backends/mujoco.toml` files;
they do not edit the operator's existing EOS configuration.
