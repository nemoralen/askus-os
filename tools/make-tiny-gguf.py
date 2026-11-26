#!/usr/bin/env python3
"""Make a tiny random Qwen2-architecture GGUF model for tests (gibberish output, ~80 MB).
Usage: PYTHONPATH=<llama.cpp>/gguf-py make-tiny-gguf.py VOCAB.gguf OUT.gguf"""
import sys
import gguf
import numpy as np

src = gguf.GGUFReader(sys.argv[1])
kv = {f.name: f for f in src.fields.values()}
w = gguf.GGUFWriter(sys.argv[2], "qwen2")
E, L, H, FF = 64, 2, 4, 128
w.add_name("tiny-test"); w.add_context_length(512); w.add_embedding_length(E); w.add_block_count(L)
w.add_feed_forward_length(FF); w.add_head_count(H); w.add_head_count_kv(H)
w.add_layer_norm_rms_eps(1e-6); w.add_rope_freq_base(10000.0)
for name, f in kv.items():
    if not name.startswith("tokenizer."):
        continue
    t = f.types[0]
    if t == gguf.GGUFValueType.ARRAY:
        if f.types[-1] == gguf.GGUFValueType.STRING:
            w.add_array(name, [f.parts[i].tobytes().decode("utf-8", "replace") for i in f.data])
        else:
            w.add_array(name, [f.parts[i].tolist()[0] for i in f.data])
    elif t == gguf.GGUFValueType.STRING:
        w.add_string(name, f.parts[f.data[0]].tobytes().decode())
    elif t == gguf.GGUFValueType.UINT32:
        w.add_uint32(name, int(f.parts[f.data[0]][0]))
    elif t == gguf.GGUFValueType.BOOL:
        w.add_bool(name, bool(f.parts[f.data[0]][0]))
n_vocab = len(kv["tokenizer.ggml.tokens"].data)
rng = np.random.default_rng(0)
r = lambda *s: (rng.standard_normal(s) * 0.02).astype(np.float32)  # noqa: E731
w.add_tensor("token_embd.weight", r(n_vocab, E))
w.add_tensor("output_norm.weight", np.ones(E, np.float32))
w.add_tensor("output.weight", r(n_vocab, E))
for i in range(L):
    p = f"blk.{i}."
    w.add_tensor(p + "attn_norm.weight", np.ones(E, np.float32))
    w.add_tensor(p + "ffn_norm.weight", np.ones(E, np.float32))
    for n in ("attn_q", "attn_k", "attn_v"):
        w.add_tensor(p + n + ".weight", r(E, E))
        w.add_tensor(p + n + ".bias", np.zeros(E, np.float32))
    w.add_tensor(p + "attn_output.weight", r(E, E))
    w.add_tensor(p + "ffn_gate.weight", r(FF, E))
    w.add_tensor(p + "ffn_up.weight", r(FF, E))
    w.add_tensor(p + "ffn_down.weight", r(E, FF))
w.write_header_to_file(); w.write_kv_data_to_file(); w.write_tensors_to_file(); w.close()
print("wrote", sys.argv[2])
