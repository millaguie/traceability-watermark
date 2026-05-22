# Key derivation and key management (HKDF)

## What it is

A **Key Derivation Function (KDF)** turns one secret (a master key, password, or
Diffie–Hellman output) into one or more cryptographically independent subkeys.
**HKDF** (Krawczyk, 2010; RFC 5869) is the standard HMAC-based KDF, built in two
steps — *extract* (concentrate entropy into a pseudorandom key) and *expand*
(stretch it into as many subkeys as needed, each bound to a distinct `info`
label). Domain separation via different `info` labels guarantees the subkeys are
independent: learning one tells you nothing about another.

The companion principle is **key separation**: never reuse one key for two
purposes (e.g. encryption and PRNG seeding). Derive a dedicated subkey per use.

## How this project uses it

[`keys.py`](../wmlib/keys.py):

- **Master key**: 256 bits, sourced (in order) from `--key-file`, the
  `WATERMARK_KEY` env var, or a config file at `~/.config/watermark/key`. If none
  exists it is generated with `os.urandom` and persisted with `0600` permissions.
  **The secret never lives in code.**
- **Subkeys via HKDF-SHA256** (`derive_subkeys`): two independent keys with
  distinct `info` labels —
  - `prng` — seeds the spread-spectrum carrier plan (coefficient assignment and
    ± chips), see [spread.py](../wmlib/spread.py);
  - `enc` — the AES-256-GCM key, see [authenticated-encryption](authenticated-encryption.md).

So the value that places the mark and the value that encrypts the id are
cryptographically separate, both derived from the one secret the user backs up.

The **public contact** channel instead uses a *fixed, published* PRNG key
(`PUBLIC_PRNG_KEY = SHA-256("watermark/public/v1")`) — by design it carries no
secret, so anyone with the tool can locate and read that mark.

## Trade-offs

- HKDF is the conservative, well-analyzed choice; the only real operational risk
  is **losing the master key** (then existing marks can't be extracted) — hence
  the explicit "back this up" notice on auto-generation.
- A single master with HKDF subkeys (vs. independent stored keys) keeps key
  management to one secret while preserving cryptographic separation.

## References

- H. Krawczyk, "Cryptographic Extraction and Key Derivation: The HKDF Scheme",
  *CRYPTO 2010*. https://doi.org/10.1007/978-3-642-14623-7_34 — full version:
  https://eprint.iacr.org/2010/264
- H. Krawczyk, P. Eronen, *RFC 5869: HMAC-based Extract-and-Expand Key
  Derivation Function (HKDF)*, 2010. https://www.rfc-editor.org/rfc/rfc5869
- NIST, *FIPS 198-1: The Keyed-Hash Message Authentication Code (HMAC)*, 2008.
  https://csrc.nist.gov/pubs/fips/198-1/final
