# Bundled OpenSim baselines

`base/Hand_Wrist_Model_for_development.osim` is the exact right-hand baseline used by the scaling adapter. `base/Hand_Wrist_Model_LEFT_GlobalX180.osim` is the supplied left-hand derivative. These are not newly exported personalized results. Both files are copied byte-for-byte from the supplied ARMS model package. The 33 referenced, available VTP assets are in `base/Geometry/`.

The original copyright, use restrictions, citation requirement and disclaimer remain inside each XML's `<publications>` element. In particular, the supplied notice states non-commercial use only and a separate commercial license requirement. Do not treat these assets as covered by the MyoSuite or Three.js licenses. The left-hand derivative is not represented as an unmodified upstream release.

Required acknowledgement from the supplied model: McFarland DC, Binder-Markey BI, Nichols JA, Wohlman SJ, de Bruin M, Murray WM. A Musculoskeletal Model of the Hand and Wrist Capable of Simulating Functional Tasks. 2021; bioRxiv, doi: 10.1101/2021.12.28.474357.

## Known left-hand source issue

The original left XML references `thorax_GlobalX180.vtp`, which was not present in the supplied assets. It is attached to Ground, not the displayed hand. No replacement asset has been fabricated and the original XML has not been edited. `server/left_adapter.py` substitutes `thorax.vtp` with the existing reflection at runtime and applies the reviewed left mesh/path repairs. Opening the raw XML directly in OpenSim may therefore report a missing thorax mesh; it is not equivalent to running the full adapter.

Verify asset hashes and mesh XML availability with `python3 scripts/setup-models.py`. Copy into a private runtime with `python3 scripts/setup-models.py --runtime /absolute/path/runtime`. The script refuses to overwrite different existing assets. It does not establish anatomical or dynamics accuracy.
