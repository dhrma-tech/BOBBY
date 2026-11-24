# Maia-3 in the browser: feasibility check (2026-11-24)

This was a time-boxed check. `MaiaAdapter` in `site/src/bridge/engine.ts` is still a stub (`available() === false`), so Bobby uses the Stockfish weak-play strategy (`site/src/bridge/strength.ts`).

## Verified

| Question | Finding | How it was checked |
|---|---|---|
| Upstream code license | AGPL-3.0 | `LICENSE` in github.com/CSSLab/maia3 (fetched raw) |
| Upstream weights | PyTorch checkpoints on Hugging Face (`UofTCSSLab/Maia3-5M`, also 23M and 79M sizes; a 3M ablation). The model card gives "CC BY 4.0 (paper); see repo for code/weights license". No separate weights license is stated. | HF model card |
| ONNX export | A third-party repo, `huggingface.co/bqrio/maia3-onnx`, publishes fp16 and fp32 ONNX graphs for 3M, 5M, 23M and 79M. Its card gives `license: agpl-3.0`. This is not an official CSSLab release. | HF model card + README |
| Size | `maia3-5m.fp16.onnx` is 10,755,531 bytes (about 10.8 MB). Card sizes: 3M fp16 6.7 MB, 23M fp16 45.8 MB, 79M fp16 156 MB. | Downloaded the 5M fp16 file (sha256 `ca22fc30...64fa`) |
| I/O | Inputs `tokens` float32 [batch, 64, 12], `elo_self` [batch], `elo_oppo` [batch]. Outputs `logits_move` [batch, 4352] and `logits_value` [batch, 3]. | Session metadata from onnxruntime-web |
| Runs on onnxruntime-web | Yes. onnxruntime-web 1.23 (wasm backend, 1 thread) under Node: 5M fp16 loaded in about 1.2 s, then about 175-310 ms per inference. The card recommends `graphOptimizationLevel: "basic"` (it reports a LayerNorm fusion bug at higher levels). | `/tmp/ortcheck/check.mjs` (not committed) |
| Runtime cost | The onnxruntime-web wasm binaries are 12-25 MB each (`ort-wasm-simd-threaded*.wasm`). Add that to the model size. | npm package contents |

## Not verified (blocking a real adapter)

- **Move vocabulary.** The 4352 move logits (4096 from-to plus 256 promotion entries, per the card) need the exact index mapping from the Maia3 source. It was not read or tested, so no legal-move decoding exists yet.
- **Token channel order and board orientation.** This covers the 12 piece channels, square order, and whether the board is mirrored when Black is to move. The test used a guessed order, so the outputs are unvalidated.
- **Rating range.** No source checked stated the valid Elo input range. The PLAN's "about 600-2600" figure is not confirmed.
- **Browser main/worker integration.** Only Node was tested. WebGPU, threads (which need COOP/COEP) and real browser timings were not.
- **Quality.** The move predictions were not compared with upstream PyTorch.

## License impact

Bobby is GPL-3.0. GPLv3 section 13 allows combining with AGPLv3 code. However, the AGPL network-use clause would apply to the Maia part of a hosted build. Before shipping weights, confirm the weights license with CSSLab and add the notice to `THIRD_PARTY_NOTICES.md`.

## Path forward

1. Port the Maia3 board tokenisation and move-index mapping from the upstream repo. Add a unit test that checks the top move on known positions against the PyTorch model.
2. Load the 5M fp16 model in a dedicated worker with the onnxruntime-web wasm backend. Mask illegal moves, then sample by temperature.
3. Use Maia for the play engine in its supported range. Keep Stockfish for analysis and as the fallback.
