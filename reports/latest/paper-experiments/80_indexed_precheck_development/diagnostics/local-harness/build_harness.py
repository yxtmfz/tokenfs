from pathlib import Path
import hashlib,json
repo=Path(__file__).resolve().parents[2]/'tokenfs-eval'
out=Path(__file__).resolve().parent
source=(repo/'src/main.cpp').read_text()
tests=(repo/'tests/policy_metadata_test.cpp').read_text()
# Exact TokenFS and MetadataStore implementation, including Init/Release and
# worker. Only FUSE's unmounted API declarations and unused Linux allocation
# calls are supplied by a platform veneer; YAML/main are not part of this run.
prefix=source[:source.index('TokenFS* g_fs = nullptr;')]
prefix=prefix.replace('#include <fuse3/fuse.h>','').replace('#include <yaml-cpp/yaml.h>','')
veneer='''
#include <cstdint>
#include <sys/types.h>
#include <sys/stat.h>
#include <unistd.h>
#include <cerrno>
struct fuse_file_info { int flags=0; uint64_t fh=0; unsigned direct_io=0; };
enum fuse_readdir_flags { FUSE_READDIR_DEFAULT=0 };
enum fuse_fill_dir_flags { FUSE_FILL_DIR_DEFAULT=0 };
using fuse_fill_dir_t=int(*)(void*,const char*,const struct stat*,off_t,fuse_fill_dir_flags);
struct fuse_context { pid_t pid=0; };
inline fuse_context* fuse_get_context(){return nullptr;}
#ifndef O_DIRECT
#define O_DIRECT 0
#endif
#ifdef __APPLE__
#define FALLOC_FL_KEEP_SIZE 1
inline int fdatasync(int fd){return fsync(fd);}
inline int tokenfs_test_posix_fallocate(int,off_t,off_t){return EOPNOTSUPP;}
#define posix_fallocate tokenfs_test_posix_fallocate
#endif
'''
prefix=veneer+prefix+'\n} // namespace\n'
test_struct=tests[tests.index('namespace {'):tests.index('\nvoid MetricBatchTransactions')]
config_start=test_struct.index('  static void deferred_config_parse(')
config_end=test_struct.index('  static void ',config_start+10)
test_struct=test_struct[:config_start]+test_struct[config_end:]
trace_start=test_struct.index('  static void request_trace_roundtrip(')
trace_end=test_struct.index('  static void ',trace_start+10)
test_struct=test_struct[:trace_start]+test_struct[trace_end:]
main='''
int main() {
  auto root=fs::temp_directory_path()/("tokenfs-index80-local-"+std::to_string(getpid()));
  fs::create_directory(root);
  TokenFSTestAccess::background_metric_fence(root/"legacy-on",true);
  TokenFSTestAccess::background_metric_fence(root/"legacy-off",false);
  TokenFSTestAccess::deferred_background_fence(root/"fence");
  for(int mode=0;mode<3;++mode)TokenFSTestAccess::deferred_background_failure_retry(root/("retry-"+std::to_string(mode)),mode);
  TokenFSTestAccess::deferred_background_queue_shutdown(root/"queue");
  TokenFSTestAccess::readonly_release_fence(root/"release");
  TokenFSTestAccess::deferred_failed_fence_handoff(root/"failed-handoff");
  TokenFSTestAccess::telemetry_retry_and_release_lock(root/"legacy-release");
  TokenFSTestAccess::submission_precheck_decisions(root/"precheck-decisions");
  TokenFSTestAccess::submission_precheck_ablations(root/"precheck-ablations");
  TokenFSTestAccess::submission_precheck_busy(root/"precheck-busy");
  TokenFSTestAccess::submission_precheck_metadata(root/"precheck-metadata");
  TokenFSTestAccess::submission_precheck_startup(root/"precheck-startup");
  TokenFSTestAccess::indexed_precheck_query(root/"indexed-query");
  TokenFSTestAccess::indexed_precheck_eligibility(root/"indexed-eligibility");
  TokenFSTestAccess::indexed_precheck_setup_failure(root/"indexed-failure");
  fs::remove_all(root);
  std::cout<<"PASS: real TokenFS/MetadataStore 80 indexed precheck, 79 precheck, 78 telemetry tests, and legacy fence/release checks (unmounted macOS veneer)\\n";
}
'''
(out/'telemetry_harness.cpp').write_text(prefix+'\n#include <cassert>\n#include <atomic>\n#include <future>\n#include <map>\n#include <tuple>\n'+test_struct+main)
(out/'source-hashes.json').write_text(json.dumps({str(p.relative_to(repo)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [repo/'src/main.cpp',repo/'tests/policy_metadata_test.cpp']},indent=2)+'\n')
