set -eu
base=/home/wjxt/tokenfs-affinity-v2d-evidence
project=/home/wjxt/projects/tokenfs-affinity-v2d-20260920
mkdir "$project"
mkdir "$base"
cd "$project"
tar -mxzf /home/wjxt/affinity-v2-src-04.tar.gz
cat > "$base/development-runner.sh" <<'RUNNER'
set -eu
host=$(hostname)
case "$host" in
 cn7) . /home/wjxt/aura-kv-tools/env.sh; remote=/srv/tokenfs/remote-cn7/affinity-v2d; mkdir -p "$remote";;
 cn8) . /home/wjxt/tokenfs-eval-tools-20260919/env.sh; remote=/home/wjxt/tokenfs-round3-directory-backend/affinity-v2d; mkdir -p "$remote";;
 *) exit 2;;
esac
base=/home/wjxt/tokenfs-affinity-v2d-evidence
cd /home/wjxt/projects/tokenfs-affinity-v2d-20260920
export LIBRARY_PATH="$TOKENFS_TOOLS_ROOT/usr/lib/x86_64-linux-gnu"
set +e
(
 set -e
 cmake -S . -B build-release -G Ninja -DCMAKE_BUILD_TYPE=Release
 cmake --build build-release -j 4
 ctest --test-dir build-release --output-on-failure
 python3 -m unittest tests.aura_kv_unit_test tests.evidence_test tests.measured_study_test tests.affinity_joint_test tests.affinity_v2_test
 sha256sum build-release/tokenfs src/main.cpp src/measured_policy.h scripts/affinity_v2_study.py
) > "$base/build.log" 2>&1
status=$?
echo "$status" > "$base/build.exit"
if [ "$status" -ne 0 ]; then exit "$status"; fi
python3 scripts/affinity_v2_study.py run --spec study-configs/affinity-v2-correctness-01.json --binary build-release/tokenfs --remote-root "$remote" --output "$base/affinity-v2-correctness-01" > "$base/affinity-v2-correctness-01.log" 2>&1
status=$?
echo "$status" > "$base/affinity-v2-correctness-01.exit"
if [ "$status" -ne 0 ]; then exit "$status"; fi
if [ "$host" = cn7 ]; then
 python3 scripts/affinity_v2_study.py run --spec study-configs/affinity-v2-development-01.json --binary build-release/tokenfs --remote-root "$remote" --output "$base/affinity-v2-development-01" > "$base/affinity-v2-development-01.log" 2>&1
 status=$?
 echo "$status" > "$base/affinity-v2-development-01.exit"
fi
exit "$status"
RUNNER
nohup sh "$base/development-runner.sh" > "$base/development-runner.log" 2>&1 < /dev/null &
echo $! > "$base/development.pid"
cat "$base/development.pid"
