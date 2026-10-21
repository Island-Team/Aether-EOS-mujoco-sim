# Imported model provenance

The UR5e and Robotiq 2F-85 models and meshes under `menagerie/` come from
[MuJoCo Menagerie](https://github.com/google-deepmind/mujoco_menagerie), commit
`cda5236f98383f6fbaa4820c6b18dba892cd087f`. Their respective `LICENSE`
files are preserved in each imported directory. `generate_scene.py` composes
these models with a holonomic mobile base and benchmark props; the source
model XMLs are unchanged.

The UR5e files retain their [BSD-3-Clause license](menagerie/universal_robots_ur5e/LICENSE); the Robotiq 2F-85 files retain their [BSD-2-Clause license](menagerie/robotiq_2f85/LICENSE). The repository's root Apache-2.0 license applies to package-authored code and documentation and does not replace these model notices.
