set -eu
python3 - <<'PY'
import subprocess,json,socket,glob,pathlib,time
def run(args):
 try:
  r=subprocess.run(args,capture_output=True,text=True,timeout=12)
  return dict(returncode=r.returncode,stdout=r.stdout,stderr=r.stderr)
 except (OSError,subprocess.TimeoutExpired) as e:return dict(error=str(e))
out=dict(host=socket.gethostname(),utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()))
out['addresses']=run(['ip','-j','-4','addr','show'])
out['nvidia']=run(['nvidia-smi','--query-gpu=index,name,uuid,pci.bus_id,memory.total,driver_version','--format=csv,noheader'])
out['pci_display']=run(['sh','-c',"lspci -nn | grep -Ei 'VGA|3D controller|Display controller|NVIDIA|AMD/ATI' || true"])
out['gpu_devices']=glob.glob('/dev/nvidia*')+glob.glob('/dev/dri/render*')
out['mounts']=run(['findmnt','-rn','-t','ext4,fuse.tokenfs','-o','SOURCE,TARGET,FSTYPE'])
out['nvme']={}
for p in pathlib.Path('/sys/class/nvme').glob('nvme*'):
 out['nvme'][p.name]={n:(p/n).read_text().strip() for n in ['transport','address','model'] if (p/n).exists()}
out['own_tokenfs_processes']=run(['sh','-c',"ps -u wjxt -o pid=,comm= | grep -E 'tokenfs|hpj' || true"])
print(json.dumps(out,indent=2))
PY
