# Optimizing LLM Inference

Serving a large language model is expensive in both memory and latency. Several
techniques reduce that cost without changing what the model fundamentally does.

Quantization reduces the numerical precision of model weights to lower memory use
and speed up inference. Instead of storing each weight in 16-bit floating point, a
quantized model stores it in 8-bit or 4-bit form, shrinking the model and letting it
run on smaller hardware. The tradeoff is a potential loss of accuracy relative to
the full-precision model.

KV caching stores previously computed attention keys and values so each new token
does not recompute them. During generation the model attends over all prior tokens;
without a cache it would redo that work at every step. Caching turns repeated
quadratic work into incremental work, which is the single biggest latency win for
long outputs.

Batching multiple requests together improves hardware utilization and throughput.
A GPU processing one request at a time is mostly idle; grouping several requests
into one batch keeps it busy and raises the number of tokens served per second.

Together, quantization, KV caching, and batching are the standard levers for making
inference cheaper and faster.
