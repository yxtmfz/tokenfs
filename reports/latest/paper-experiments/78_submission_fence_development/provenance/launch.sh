set -eu
. /home/wjxt/aura-kv-tools/env.sh
if pgrep -u "$(id -u)" -x tokenfs >/dev/null; then echo 'Existing own TokenFS process'; exit 2; fi
root=/home/wjxt/tokenfs-submission-fence78-evidence
mkdir "$root"
mkdir /srv/tokenfs/remote-cn7/submission-fence78-20261007
cat > "$root/run.sh" <<'RUN'
#!/bin/bash
set -u
. /home/wjxt/aura-kv-tools/env.sh
cd /home/wjxt/projects/tokenfs-submission-fence78-20261007
root=/home/wjxt/tokenfs-submission-fence78-evidence
python3 scripts/submission_fence_hpj_study.py run --spec study-configs/submission-fence-development.json --output "$root/development" --binary build-release/tokenfs --remote-root /srv/tokenfs/remote-cn7/submission-fence78-20261007 --freeze study-configs/submission-fence-freeze.json
rc=$?
printf '%s\n' "$rc" > "$root/development.exit"
if [ "$rc" -ne 0 ]; then exit "$rc"; fi
python3 scripts/disk_opportunity_correctness.py --study submission_fence_hpj_study --binary build-release/tokenfs --reference-binary /home/wjxt/projects/tokenfs-integrated-hpj-cohort-caller-lazy-20260930/build-release/tokenfs --freeze study-configs/submission-fence-freeze.json --output "$root/correctness" --remote-root /srv/tokenfs/remote-cn7/submission-fence78-20261007
rc=$?
printf '%s\n' "$rc" > "$root/correctness.exit"
exit "$rc"
RUN
nohup bash "$root/run.sh" > "$root/run.log" 2>&1 < /dev/null &
