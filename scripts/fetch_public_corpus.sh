#!/usr/bin/env sh
# Clone the public snapshots the default corpus indexes into ./corpus (shallow, read-only).
set -eu
cd "$(dirname "$0")/.."
mkdir -p corpus
for repo in agentops-snapshot workhorse-snapshot studbook-snapshot paddock-snapshot Portfolio; do
  if [ ! -d "corpus/$repo/.git" ] && [ ! -L "corpus/$repo" ]; then
    git clone --quiet --depth 1 "https://github.com/muhibm1/$repo" "corpus/$repo"
  fi
done
echo "corpus ready in $(pwd)/corpus"
