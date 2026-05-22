# Reed–Solomon error correction

## What it is

Reed–Solomon (RS) codes are non-binary block codes over a finite field GF(2^m)
(here GF(256), i.e. bytes). An RS(n, k) code maps `k` data symbols to `n` code
symbols by adding `n−k` parity symbols; it can **correct up to `(n−k)/2` symbol
errors** anywhere in the codeword (or up to `n−k` erasures). Because a symbol is
a whole byte, RS is excellent against **burst errors** — a localized corruption
that wipes several consecutive bytes counts as few symbol errors.

RS is everywhere reliability matters under noise: CDs/DVDs, QR codes, DSL,
deep-space links (it is the classic outer code in concatenated schemes).

## How this project uses it

[`payload.py`](../wmlib/payload.py) and
[`payload_public.py`](../wmlib/payload_public.py) wrap the framed payload with
`reedsolo.RSCodec(PARITY)`, `PARITY = 32`. So the codec adds 32 parity bytes and
**corrects up to 16 corrupted bytes** per codeword.

Why it matters here: blind spread-spectrum detection yields a *mostly* correct
bitstream after an attack (a few percent bit-error rate). RS turns "mostly
correct" into "exactly correct" as long as the residual errors are within
capacity — the difference between a failed extraction and a recovered id. The
spreading also interleaves bits across the whole image, so a localized crop
produces scattered (not catastrophic) symbol errors that RS mops up.

Decode failure (too many errors) raises cleanly and is treated as "no valid
mark", rather than returning garbage — and after RS, AES-GCM still has to verify
([authenticated-encryption](authenticated-encryption.md)), so a wrong-but-RS-valid
result is rejected.

## Trade-offs

- Parity is pure overhead in capacity: 32 of the 94 forensic codeword bytes are
  parity. More parity = more robustness, fewer payload bits. `PARITY = 32` is a
  deliberate margin for the measured post-attack error rates.
- RS works on hard symbol decisions; a soft-decision code (LDPC/turbo) could do
  better at very low SNR but is overkill here.

## References

- I. S. Reed, G. Solomon, "Polynomial Codes over Certain Finite Fields",
  *Journal of the Society for Industrial and Applied Mathematics*, 8(2), 1960.
  https://doi.org/10.1137/0108018
- S. B. Wicker, V. K. Bhargava (eds.), *Reed–Solomon Codes and Their
  Applications*, IEEE Press, 1994.
- `reedsolo` library (the implementation used): https://github.com/tomerfiliba/reedsolomon
