#!/usr/bin/env bash
for t in opam ocaml ocamlfind dune m4 bwrap unzip bzip2 patch make gcc cc; do
  printf '%-9s ' "$t"; command -v "$t" || echo MISSING
done
