# Third-party notices

The visual assets and rendering libraries are derived from the following
open-source projects. The added SHM joint-control table has separate provenance
documented in `docs/data-provenance.json`; it is not native MyoHand kinematics.

## ARMS hand/wrist OpenSim baseline assets

- Files: `models/base/*.osim` and their supplied geometry in `models/base/Geometry/`.
- The original model notices name Northwestern University, Shirley Ryan AbilityLab,
  Drexel University, University of Florida and Edward Hines, Jr. VA Hospital,
  copyright 2021-present. See each XML's `publications` element for the full notice.
- The supplied terms specify non-commercial use and a separate license for
  commercial use, with attribution and disclaimer requirements. These assets
  are not covered by the MyoSuite Apache license or Three.js MIT license.
- Citation specified by the model: McFarland et al., A Musculoskeletal Model of
  the Hand and Wrist Capable of Simulating Functional Tasks (2021),
  doi:10.1101/2021.12.28.474357.
- Both XML files are preserved byte-for-byte. The left-hand file is a supplied
  derivative, not claimed to be an unmodified upstream model. See `models/README.md`
  for source limitations and the runtime adapter.

## MyoHand / MyoSuite

- Source: https://github.com/MyoHub/myo_sim
- Project: https://github.com/MyoHub/myosuite
- License: Apache License 2.0; see `LICENSE-MYOSUITE`.
- Use in this repository: unchanged, quantized public bone geometry, joint
  anchors and 39 exported actuator paths in `model-data.js`. The interface
  exposes the 37 channels referenced by the SHM table; PT and PQ remain hidden.

## Three.js

- Source: https://github.com/mrdoob/three.js
- Version embedded by the atlas: r128
- License: MIT; see `LICENSE-THREEJS`.
- Use in this repository: WebGL rendering and orbit controls, extracted without
  modification into `vendor/three.min.js` and `vendor/orbit-controls.js`.
