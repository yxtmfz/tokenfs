
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
#define FUSE_USE_VERSION 35


#include <sqlite3.h>

#include "measured_policy.h"
#include "sieve_policy.h"
#include "request_trace.h"
#include "read_fill.h"
#include "request_read_cost.h"
#include "copy_cost.h"
#include "aligned_read.h"

#include <algorithm>
#include <cerrno>
#include <chrono>
#include <cctype>
#include <cstring>
#include <cstdlib>
#include <condition_variable>
#include <deque>
#include <functional>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <iterator>
#include <limits>
#include <mutex>
#include <optional>
#include <set>
#include <sstream>
#include <string>
#include <thread>
#include <unordered_map>
#include <vector>

#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>

namespace fs = std::filesystem;

namespace {

struct BackendConfig {
  std::string id;
  std::string type;
  fs::path root;
};

struct GpuConfig {
  int gpu_id = -1;
  std::string logical_root;
  fs::path local_root;
  uint64_t local_quota_bytes = 0;
  std::string remote_backend;
};

struct Config {
  fs::path mount_point;
  fs::path metadata_db;
  std::string temp_suffix = ".tokenfs_tmp";
  std::string checksum = "none";
  std::string local_eviction_policy = "value_aware";
  std::string placement_policy = "value_aware";
  uint64_t default_recompute_cost = 10;
  uint64_t default_remote_access_cost = 10;
  uint64_t value_promote_threshold = 100;
  bool measured_policy = false;
  uint64_t measured_window = 128;
  bool measured_aging = true;
  bool measured_admission = true;
  bool measured_cost = true;
  bool measured_value_victim = true;
  bool measured_size_aware = true;
  bool measured_frequency_admission = false;
  bool measured_shift_reset = false;
  bool measured_causal_window = false;
  bool measured_burst_reuse = false;
  bool incremental_copy_cost = false;
  bool coalesce_pending_reads = false;
  bool adaptive_reuse_control = false;
  bool efficient_measured_planning = false;
  bool burst_interval_survival = false;
  bool reuse_scaled_exploration = false;
  bool persistent_run_reuse = false;
  bool persistent_reuse_immediate_decay = false;
  bool measured_static_reuse_value = false;
  bool novel_reuse_decay = false;
  bool profile_control_path = false;
  bool batch_background_metrics = false;
  bool defer_background_submission_metrics = false;
  bool precheck_shared_submission = false;
  bool indexed_shared_precheck = false;
  bool batch_policy_events = false;
  std::string request_trace_path;
  bool foreground_read_fill = false;
  bool retain_read_fill = false;
  bool ram_first_routing = false;
  bool capture_local_reads = false;
  bool bounded_cost_warmup = false;
  bool cohort_reuse_prior = false;
  bool object_weighted_cohort_prior = false;
  bool recent_value_floor = false;
  bool disk_opportunity_value=false;
  bool request_read_costs = false;
  bool reuse_direct_read_tail = false;
  uint64_t read_fill_buffer_bytes = 4*1024*1024;
  bool compact_measured_planning = false;
  bool lean_read_accounting = false;
  bool private_cache_domains = false;
  bool peer_cache_reads = false;
  bool shared_value_placement = false;
  // Ablation: keep shared demand/read paths, restrict only the destination set.
  bool shared_caller_only = false;
  bool shared_pool_cache = false;
  bool measured_track_affinity = false;
  bool measured_affinity_gate = false;
  bool measured_affinity_recent_demand = false;
  bool measured_affinity_handover_epoch = false;
  bool measured_joint_admission = true;
  uint64_t measured_affinity_window = 128;
  uint64_t measured_shift_window = 8;
  bool adaptive_migration = false;
  uint64_t adaptive_remote_promote_us = 10000;
  uint64_t qos_read_iops_per_gpu = 0;
  uint64_t qos_write_iops_per_gpu = 0;
  uint64_t qos_background_iops_per_gpu = 0;
  uint64_t qos_background_mib_per_sec_per_gpu = 0;
  uint64_t affinity_dominant_threshold_x100 = 70;
  uint64_t affinity_shared_threshold_x100 = 55;
  uint64_t affinity_short_window_sec = 300;
  uint64_t affinity_long_window_sec = 3600;
  uint64_t affinity_trend_min_reads = 3;
  uint64_t affinity_hot_read_threshold = 4;
  uint64_t affinity_warm_read_threshold = 2;
  uint64_t max_local_replicas_per_file = 2;
  uint64_t affinity_replica_cooldown_sec = 30;
  uint64_t affinity_replica_min_residency_sec = 120;
  bool cross_gpu_local_cache = false;
  bool affinity_placement = true;
  bool gain_admission = true;
  bool trend_prediction = true;
  bool fuse_direct_io = false;
  bool backend_direct_io = false;
  bool readonly_canonical = false;
  bool physical_dedup = false;
  bool promote_on_read = false;
  bool async_promote_on_read = false;
  bool read_through_cache = false;
  uint64_t read_through_min_reads = 2;
  uint64_t promote_read_threshold = 2;
  uint64_t migration_min_reuse_reads = 6;
  uint64_t migration_min_benefit_x100 = 150;
  uint64_t migration_copy_cost_per_mib = 8;
  bool durable_local_cache = false;
  bool fast_local_cache_hit = true;
  bool speculative_copy_may_evict = false;
  bool prefetch_on_read = false;
  bool async_cross_gpu_replica = false;
  std::unordered_map<std::string, BackendConfig> backends;
  std::vector<GpuConfig> gpus;
};

struct FileMeta {
  std::string logical_path;
  int gpu_id = -1;
  std::string tier;
  std::string backend_id;
  fs::path physical_path;
  uint64_t size_bytes = 0;
  std::string checksum;
  std::string state = "COMMITTED";
  uint64_t read_count = 0;
  std::string content_key;
  uint64_t recompute_cost = 10;
  uint64_t remote_access_cost = 10;
  uint64_t producer_gpu = 0;
  uint64_t share_count = 1;
  std::string primary_tier = "local";
  bool has_remote_copy = false;
  int local_cache_owner_gpu = -1;
  std::string replica_state = "LOCAL_ONLY";
  uint64_t cache_generation = 0;
  uint64_t last_promoted_at = 0;
  uint64_t last_demoted_at = 0;
  int dominant_gpu_id = -1;
  uint64_t dominant_gpu_read_share_x100 = 0;
  int recent_dominant_gpu_id = -1;
  uint64_t recent_dominant_gpu_read_share_x100 = 0;
  uint64_t recent_read_count = 0;
  std::string affinity_trend = "STABLE";
  uint64_t target_local_replica_count = 0;
  std::string affinity_state = "UNKNOWN";
  uint64_t affinity_updated_at = 0;
};

struct ContentRefResult {
  bool duplicate = false;
  uint64_t ref_count = 0;
  std::string primary_logical_path;
  fs::path primary_physical_path;
};

struct EvictionCandidate {
  int replica_gpu = -1;
  FileMeta meta;
  uint64_t last_access_at = 0;
};

struct LocalReplica {
  std::string logical_path;
  int gpu_id = -1;
  fs::path physical_path;
  uint64_t size_bytes = 0;
  uint64_t cache_generation = 0;
  uint64_t created_at = 0;
  uint64_t last_access_at = 0;
  std::string state = "READY";
};

struct Handle {
  int fd = -1;
  std::string logical_path;
  int gpu_id = -1;
  int caller_gpu_id = -1;
  std::string tier;
  std::string backend_id;
  fs::path physical_path;
  int flags = 0;
  bool writable = false;
  bool created_remote = false;
  std::string state = "COMMITTED";
  std::string last_checksum;
  bool pending_physical_dedup = false;
  fs::path dedup_primary_path;
  std::shared_ptr<ReadFillPool::Buffer> read_fill;
  std::shared_ptr<ReadFillPool::Buffer> borrowed_capture;
  std::shared_ptr<RequestReadCost> read_cost;
  std::shared_ptr<AlignedReadTail> direct_read_tail;
};

struct PolicyEvent {
  std::string action, path;
  int gpu;
  uint64_t bytes;
  std::string reason;
  double score;
};

class MetadataStore {
  friend struct TokenFSTestAccess;
 public:
  explicit MetadataStore(const fs::path& db_path) : db_path_(db_path) {}

  ~MetadataStore() {
    for(const auto& [sql,stmt]:cached_statements_){(void)sql;sqlite3_finalize(stmt);}
    if (db_ != nullptr) {
      sqlite3_close(db_);
    }
  }

  void Open() {
    fs::create_directories(db_path_.parent_path());
    if (sqlite3_open(db_path_.c_str(), &db_) != SQLITE_OK) {
      throw std::runtime_error(sqlite3_errmsg(db_));
    }
    Exec("PRAGMA journal_mode=WAL;");
    Exec("PRAGMA synchronous=FULL;");
    Exec("CREATE TABLE IF NOT EXISTS files ("
         "logical_path TEXT PRIMARY KEY,"
         "gpu_id INTEGER NOT NULL,"
         "tier TEXT NOT NULL,"
         "backend_id TEXT NOT NULL,"
         "physical_path TEXT NOT NULL,"
         "size_bytes INTEGER NOT NULL DEFAULT 0,"
         "checksum TEXT,"
         "state TEXT NOT NULL,"
         "created_at INTEGER NOT NULL,"
         "updated_at INTEGER NOT NULL,"
         "last_access_at INTEGER,"
         "read_count INTEGER NOT NULL DEFAULT 0,"
         "content_key TEXT,"
         "recompute_cost INTEGER NOT NULL DEFAULT 10,"
         "remote_access_cost INTEGER NOT NULL DEFAULT 10,"
         "producer_gpu INTEGER NOT NULL DEFAULT 0,"
         "share_count INTEGER NOT NULL DEFAULT 1,"
         "primary_tier TEXT NOT NULL DEFAULT 'local',"
         "has_remote_copy INTEGER NOT NULL DEFAULT 0,"
         "local_cache_owner_gpu INTEGER NOT NULL DEFAULT -1,"
         "replica_state TEXT NOT NULL DEFAULT 'LOCAL_ONLY',"
         "cache_generation INTEGER NOT NULL DEFAULT 0,"
         "last_promoted_at INTEGER NOT NULL DEFAULT 0,"
         "last_demoted_at INTEGER NOT NULL DEFAULT 0,"
         "dominant_gpu_id INTEGER NOT NULL DEFAULT -1,"
         "dominant_gpu_read_share_x100 INTEGER NOT NULL DEFAULT 0,"
         "recent_dominant_gpu_id INTEGER NOT NULL DEFAULT -1,"
         "recent_dominant_gpu_read_share_x100 INTEGER NOT NULL DEFAULT 0,"
         "recent_read_count INTEGER NOT NULL DEFAULT 0,"
         "affinity_trend TEXT NOT NULL DEFAULT 'STABLE',"
         "target_local_replica_count INTEGER NOT NULL DEFAULT 0,"
         "affinity_state TEXT NOT NULL DEFAULT 'UNKNOWN',"
         "affinity_updated_at INTEGER NOT NULL DEFAULT 0"
         ");");
    EnsureColumn("files", "checksum", "TEXT");
    EnsureColumn("files", "read_count", "INTEGER NOT NULL DEFAULT 0");
    EnsureColumn("files", "content_key", "TEXT");
    EnsureColumn("files", "recompute_cost", "INTEGER NOT NULL DEFAULT 10");
    EnsureColumn("files", "remote_access_cost", "INTEGER NOT NULL DEFAULT 10");
    EnsureColumn("files", "producer_gpu", "INTEGER NOT NULL DEFAULT 0");
    EnsureColumn("files", "share_count", "INTEGER NOT NULL DEFAULT 1");
    EnsureColumn("files", "primary_tier", "TEXT NOT NULL DEFAULT 'local'");
    EnsureColumn("files", "has_remote_copy", "INTEGER NOT NULL DEFAULT 0");
    EnsureColumn("files", "local_cache_owner_gpu",
                 "INTEGER NOT NULL DEFAULT -1");
    EnsureColumn("files", "replica_state",
                 "TEXT NOT NULL DEFAULT 'LOCAL_ONLY'");
    EnsureColumn("files", "cache_generation", "INTEGER NOT NULL DEFAULT 0");
    EnsureColumn("files", "last_promoted_at", "INTEGER NOT NULL DEFAULT 0");
    EnsureColumn("files", "last_demoted_at", "INTEGER NOT NULL DEFAULT 0");
    EnsureColumn("files", "dominant_gpu_id", "INTEGER NOT NULL DEFAULT -1");
    EnsureColumn("files", "dominant_gpu_read_share_x100",
                 "INTEGER NOT NULL DEFAULT 0");
    EnsureColumn("files", "recent_dominant_gpu_id",
                 "INTEGER NOT NULL DEFAULT -1");
    EnsureColumn("files", "recent_dominant_gpu_read_share_x100",
                 "INTEGER NOT NULL DEFAULT 0");
    EnsureColumn("files", "recent_read_count", "INTEGER NOT NULL DEFAULT 0");
    EnsureColumn("files", "affinity_trend",
                 "TEXT NOT NULL DEFAULT 'STABLE'");
    EnsureColumn("files", "target_local_replica_count",
                 "INTEGER NOT NULL DEFAULT 0");
    EnsureColumn("files", "affinity_state",
                 "TEXT NOT NULL DEFAULT 'UNKNOWN'");
    EnsureColumn("files", "affinity_updated_at", "INTEGER NOT NULL DEFAULT 0");
    Exec("CREATE TABLE IF NOT EXISTS metrics ("
         "name TEXT PRIMARY KEY,"
         "value INTEGER NOT NULL DEFAULT 0"
         ");");
    Exec("CREATE TABLE IF NOT EXISTS gpu_access ("
         "logical_path TEXT NOT NULL,"
         "gpu_id INTEGER NOT NULL,"
         "read_count INTEGER NOT NULL DEFAULT 0,"
         "last_access_at INTEGER,"
         "PRIMARY KEY(logical_path,gpu_id)"
         ");");
    EnsureColumn("gpu_access", "access_order", "INTEGER NOT NULL DEFAULT 0");
    sqlite3_stmt* sequence_stmt = nullptr;
    Prepare("SELECT COALESCE(MAX(access_order),0) FROM gpu_access;", &sequence_stmt);
    if (sqlite3_step(sequence_stmt) == SQLITE_ROW) access_sequence_ = sqlite3_column_int64(sequence_stmt, 0);
    sqlite3_finalize(sequence_stmt);
    Exec("CREATE TABLE IF NOT EXISTS gpu_access_events ("
         "logical_path TEXT NOT NULL,"
         "gpu_id INTEGER NOT NULL,"
         "access_at INTEGER NOT NULL"
         ");");
    Exec("CREATE INDEX IF NOT EXISTS idx_gpu_access_events_path_time "
         "ON gpu_access_events(logical_path,access_at);");
    Exec("CREATE TABLE IF NOT EXISTS local_replicas ("
         "logical_path TEXT NOT NULL,"
         "gpu_id INTEGER NOT NULL,"
         "physical_path TEXT NOT NULL,"
         "size_bytes INTEGER NOT NULL DEFAULT 0,"
         "cache_generation INTEGER NOT NULL DEFAULT 0,"
         "created_at INTEGER NOT NULL,"
         "last_access_at INTEGER NOT NULL,"
         "state TEXT NOT NULL DEFAULT 'READY',"
         "PRIMARY KEY(logical_path,gpu_id)"
         ");");
    Exec("CREATE TABLE IF NOT EXISTS policy_events (seq INTEGER PRIMARY KEY, action TEXT NOT NULL, logical_path TEXT NOT NULL, gpu_id INTEGER, bytes INTEGER, reason TEXT, score REAL);");
    Exec("CREATE TABLE IF NOT EXISTS content_refs ("
         "content_key TEXT PRIMARY KEY,"
         "primary_logical_path TEXT NOT NULL,"
         "physical_path TEXT NOT NULL,"
         "size_bytes INTEGER NOT NULL DEFAULT 0,"
         "ref_count INTEGER NOT NULL DEFAULT 0,"
         "first_seen_at INTEGER NOT NULL,"
         "last_seen_at INTEGER NOT NULL"
         ");");
    Exec("CREATE TABLE IF NOT EXISTS content_members ("
         "content_key TEXT NOT NULL,"
         "logical_path TEXT NOT NULL,"
         "PRIMARY KEY(content_key,logical_path)"
         ");");
  }

  std::optional<FileMeta> Get(const std::string& logical_path) {
    std::lock_guard<std::mutex> lock(mu_);
    const char* sql =
        "SELECT logical_path,gpu_id,tier,backend_id,physical_path,size_bytes,"
        "COALESCE(checksum,''),state,COALESCE(read_count,0),"
        "COALESCE(content_key,''),COALESCE(recompute_cost,10),"
        "COALESCE(remote_access_cost,10),COALESCE(producer_gpu,0),"
        "COALESCE(share_count,1),COALESCE(primary_tier,'local'),"
        "COALESCE(has_remote_copy,0),COALESCE(local_cache_owner_gpu,-1),"
        "COALESCE(replica_state,'LOCAL_ONLY'),COALESCE(cache_generation,0),"
        "COALESCE(last_promoted_at,0),COALESCE(last_demoted_at,0),"
        "COALESCE(dominant_gpu_id,-1),"
        "COALESCE(dominant_gpu_read_share_x100,0),"
        "COALESCE(recent_dominant_gpu_id,-1),"
        "COALESCE(recent_dominant_gpu_read_share_x100,0),"
        "COALESCE(recent_read_count,0),"
        "COALESCE(affinity_trend,'STABLE'),"
        "COALESCE(target_local_replica_count,0),"
        "COALESCE(affinity_state,'UNKNOWN'),COALESCE(affinity_updated_at,0) "
        "FROM files WHERE logical_path=?;";
    auto lease=CachedStatement(sql);
    auto* stmt=lease.get();
    sqlite3_bind_text(stmt, 1, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    int rc = sqlite3_step(stmt);
    if (rc == SQLITE_DONE) {
      return std::nullopt;
    }
    if (rc != SQLITE_ROW) {
      std::string err = sqlite3_errmsg(db_);
      throw std::runtime_error(err);
    }
    FileMeta meta;
    meta.logical_path = ColumnText(stmt, 0);
    meta.gpu_id = sqlite3_column_int(stmt, 1);
    meta.tier = ColumnText(stmt, 2);
    meta.backend_id = ColumnText(stmt, 3);
    meta.physical_path = ColumnText(stmt, 4);
    meta.size_bytes = static_cast<uint64_t>(sqlite3_column_int64(stmt, 5));
    meta.checksum = ColumnText(stmt, 6);
    meta.state = ColumnText(stmt, 7);
    meta.read_count = static_cast<uint64_t>(sqlite3_column_int64(stmt, 8));
    meta.content_key = ColumnText(stmt, 9);
    meta.recompute_cost = static_cast<uint64_t>(sqlite3_column_int64(stmt, 10));
    meta.remote_access_cost =
        static_cast<uint64_t>(sqlite3_column_int64(stmt, 11));
    meta.producer_gpu = static_cast<uint64_t>(sqlite3_column_int64(stmt, 12));
    meta.share_count = static_cast<uint64_t>(sqlite3_column_int64(stmt, 13));
    meta.primary_tier = ColumnText(stmt, 14);
    meta.has_remote_copy = sqlite3_column_int64(stmt, 15) != 0;
    meta.local_cache_owner_gpu = sqlite3_column_int(stmt, 16);
    meta.replica_state = ColumnText(stmt, 17);
    meta.cache_generation =
        static_cast<uint64_t>(sqlite3_column_int64(stmt, 18));
    meta.last_promoted_at =
        static_cast<uint64_t>(sqlite3_column_int64(stmt, 19));
    meta.last_demoted_at =
        static_cast<uint64_t>(sqlite3_column_int64(stmt, 20));
    meta.dominant_gpu_id = sqlite3_column_int(stmt, 21);
    meta.dominant_gpu_read_share_x100 =
        static_cast<uint64_t>(sqlite3_column_int64(stmt, 22));
    meta.recent_dominant_gpu_id = sqlite3_column_int(stmt, 23);
    meta.recent_dominant_gpu_read_share_x100 =
        static_cast<uint64_t>(sqlite3_column_int64(stmt, 24));
    meta.recent_read_count =
        static_cast<uint64_t>(sqlite3_column_int64(stmt, 25));
    meta.affinity_trend = ColumnText(stmt, 26);
    meta.target_local_replica_count =
        static_cast<uint64_t>(sqlite3_column_int64(stmt, 27));
    meta.affinity_state = ColumnText(stmt, 28);
    meta.affinity_updated_at =
        static_cast<uint64_t>(sqlite3_column_int64(stmt, 29));
    return meta;
  }

  void Upsert(const FileMeta& meta) {
    std::lock_guard<std::mutex> lock(mu_);
    UpsertLocked(meta);
  }

 private:
  void UpsertLocked(const FileMeta& meta) {
    const auto now = UnixNow();
    const char* sql =
        "INSERT INTO files(logical_path,gpu_id,tier,backend_id,physical_path,"
        "size_bytes,checksum,state,created_at,updated_at,last_access_at,read_count,"
        "content_key,recompute_cost,remote_access_cost,producer_gpu,share_count,"
        "primary_tier,has_remote_copy,local_cache_owner_gpu,replica_state,"
        "cache_generation,last_promoted_at,last_demoted_at,dominant_gpu_id,"
        "dominant_gpu_read_share_x100,recent_dominant_gpu_id,"
        "recent_dominant_gpu_read_share_x100,recent_read_count,affinity_trend,"
        "target_local_replica_count,affinity_state,affinity_updated_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(logical_path) DO UPDATE SET "
        "gpu_id=excluded.gpu_id,"
        "tier=excluded.tier,"
        "backend_id=excluded.backend_id,"
        "physical_path=excluded.physical_path,"
        "size_bytes=excluded.size_bytes,"
        "checksum=excluded.checksum,"
        "state=excluded.state,"
        "content_key=excluded.content_key,"
        "recompute_cost=excluded.recompute_cost,"
        "remote_access_cost=excluded.remote_access_cost,"
        "producer_gpu=excluded.producer_gpu,"
        "share_count=excluded.share_count,"
        "primary_tier=excluded.primary_tier,"
        "has_remote_copy=excluded.has_remote_copy,"
        "local_cache_owner_gpu=excluded.local_cache_owner_gpu,"
        "replica_state=excluded.replica_state,"
        "cache_generation=excluded.cache_generation,"
        "last_promoted_at=excluded.last_promoted_at,"
        "last_demoted_at=excluded.last_demoted_at,"
        "dominant_gpu_id=excluded.dominant_gpu_id,"
        "dominant_gpu_read_share_x100=excluded.dominant_gpu_read_share_x100,"
        "recent_dominant_gpu_id=excluded.recent_dominant_gpu_id,"
        "recent_dominant_gpu_read_share_x100=excluded.recent_dominant_gpu_read_share_x100,"
        "recent_read_count=excluded.recent_read_count,"
        "affinity_trend=excluded.affinity_trend,"
        "target_local_replica_count=excluded.target_local_replica_count,"
        "affinity_state=excluded.affinity_state,"
        "affinity_updated_at=excluded.affinity_updated_at,"
        "updated_at=excluded.updated_at;";
    sqlite3_stmt* stmt = nullptr;
    Prepare(sql, &stmt);
    sqlite3_bind_text(stmt, 1, meta.logical_path.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int(stmt, 2, meta.gpu_id);
    sqlite3_bind_text(stmt, 3, meta.tier.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 4, meta.backend_id.c_str(), -1, SQLITE_TRANSIENT);
    const auto physical = meta.physical_path.string();
    sqlite3_bind_text(stmt, 5, physical.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int64(stmt, 6, static_cast<sqlite3_int64>(meta.size_bytes));
    sqlite3_bind_text(stmt, 7, meta.checksum.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 8, meta.state.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int64(stmt, 9, now);
    sqlite3_bind_int64(stmt, 10, now);
    sqlite3_bind_int64(stmt, 11, now);
    sqlite3_bind_int64(stmt, 12, static_cast<sqlite3_int64>(meta.read_count));
    sqlite3_bind_text(stmt, 13, meta.content_key.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int64(stmt, 14, static_cast<sqlite3_int64>(meta.recompute_cost));
    sqlite3_bind_int64(stmt, 15,
                       static_cast<sqlite3_int64>(meta.remote_access_cost));
    sqlite3_bind_int64(stmt, 16, static_cast<sqlite3_int64>(meta.producer_gpu));
    sqlite3_bind_int64(stmt, 17, static_cast<sqlite3_int64>(meta.share_count));
    sqlite3_bind_text(stmt, 18, meta.primary_tier.c_str(), -1,
                      SQLITE_TRANSIENT);
    sqlite3_bind_int64(stmt, 19, meta.has_remote_copy ? 1 : 0);
    sqlite3_bind_int(stmt, 20, meta.local_cache_owner_gpu);
    sqlite3_bind_text(stmt, 21, meta.replica_state.c_str(), -1,
                      SQLITE_TRANSIENT);
    sqlite3_bind_int64(stmt, 22,
                       static_cast<sqlite3_int64>(meta.cache_generation));
    sqlite3_bind_int64(stmt, 23,
                       static_cast<sqlite3_int64>(meta.last_promoted_at));
    sqlite3_bind_int64(stmt, 24,
                       static_cast<sqlite3_int64>(meta.last_demoted_at));
    sqlite3_bind_int(stmt, 25, meta.dominant_gpu_id);
    sqlite3_bind_int64(
        stmt, 26,
        static_cast<sqlite3_int64>(meta.dominant_gpu_read_share_x100));
    sqlite3_bind_int(stmt, 27, meta.recent_dominant_gpu_id);
    sqlite3_bind_int64(
        stmt, 28,
        static_cast<sqlite3_int64>(meta.recent_dominant_gpu_read_share_x100));
    sqlite3_bind_int64(stmt, 29,
                       static_cast<sqlite3_int64>(meta.recent_read_count));
    sqlite3_bind_text(stmt, 30, meta.affinity_trend.c_str(), -1,
                      SQLITE_TRANSIENT);
    sqlite3_bind_int64(
        stmt, 31,
        static_cast<sqlite3_int64>(meta.target_local_replica_count));
    sqlite3_bind_text(stmt, 32, meta.affinity_state.c_str(), -1,
                      SQLITE_TRANSIENT);
    sqlite3_bind_int64(stmt, 33,
                       static_cast<sqlite3_int64>(meta.affinity_updated_at));
    StepDone(stmt);
  }

 public:
  void CommitLocalCache(const FileMeta& meta, int gpu_id, const fs::path& local, uint64_t size) {
    std::lock_guard<std::mutex> lock(mu_);
    sqlite3_stmt* stmt = nullptr;
    Prepare("UPDATE files SET tier='local',backend_id='local',physical_path=?,size_bytes=?,"
            "primary_tier='remote',has_remote_copy=1,local_cache_owner_gpu=?,"
            "replica_state='REMOTE_WITH_LOCAL_CACHE',cache_generation=cache_generation+1,"
            "last_promoted_at=?,state='COMMITTED' WHERE logical_path=?;", &stmt);
    const auto path = local.string();
    sqlite3_bind_text(stmt,1,path.c_str(),-1,SQLITE_TRANSIENT);
    sqlite3_bind_int64(stmt,2,size); sqlite3_bind_int(stmt,3,gpu_id);
    sqlite3_bind_int64(stmt,4,UnixNow());
    sqlite3_bind_text(stmt,5,meta.logical_path.c_str(),-1,SQLITE_TRANSIENT); StepDone(stmt);
  }

  void RecordReplicaPromotion(const std::string& path) {
    std::lock_guard<std::mutex> lock(mu_);
    sqlite3_stmt* stmt = nullptr;
    Prepare("UPDATE files SET last_promoted_at=?,target_local_replica_count=MAX(target_local_replica_count,1) WHERE logical_path=?;", &stmt);
    sqlite3_bind_int64(stmt,1,UnixNow()); sqlite3_bind_text(stmt,2,path.c_str(),-1,SQLITE_TRANSIENT); StepDone(stmt);
  }

  uint64_t IncrementReadCount(const std::string& logical_path, int gpu_id,
                              uint64_t dominant_threshold_x100,
                              uint64_t shared_threshold_x100,
                              uint64_t short_window_sec,
                              uint64_t long_window_sec,
                              uint64_t trend_min_reads,
                              uint64_t hot_read_threshold,
                              uint64_t warm_read_threshold,
                              uint64_t max_local_replicas, bool legacy_affinity=true, int replica_gpu=-1,
                              const FileMeta* discovered=nullptr) {
    std::lock_guard<std::mutex> lock(mu_);
    if(discovered && (discovered->logical_path!=logical_path || discovered->read_count!=0))
      throw std::runtime_error("invalid initial read metadata");
    const auto now = UnixNow();
    const auto event_now = UnixNowMillis();
    Exec("BEGIN IMMEDIATE;");
    try {
      if(discovered) {
        // Register an unknown object and its first read in one FULL-WAL
        // transaction. A failed read-accounting write rolls both back.
        {
          auto lease=CachedStatement("SELECT 1 FROM files WHERE logical_path=?;");
          sqlite3_bind_text(lease.get(),1,logical_path.c_str(),-1,SQLITE_TRANSIENT);
          const int rc=sqlite3_step(lease.get());
          if(rc!=SQLITE_DONE)throw std::runtime_error(rc==SQLITE_ROW?"initial read metadata already exists":sqlite3_errmsg(db_));
        }
        UpsertLocked(*discovered);
      }
      auto execute=[&](const char* sql,auto bind) {
        auto lease=CachedStatement(sql);auto* stmt=lease.get();bind(stmt);
        if(sqlite3_step(stmt)!=SQLITE_DONE)throw std::runtime_error(sqlite3_errmsg(db_));
      };
      execute("UPDATE files SET read_count=COALESCE(read_count,0)+1,last_access_at=? WHERE logical_path=?;",[&](auto* stmt){
        sqlite3_bind_int64(stmt,1,now);sqlite3_bind_text(stmt,2,logical_path.c_str(),-1,SQLITE_TRANSIENT);
      });
      execute("INSERT INTO gpu_access(logical_path,gpu_id,read_count,last_access_at,access_order) "
              "VALUES(?,?,1,?,?) ON CONFLICT(logical_path,gpu_id) DO UPDATE SET "
              "read_count=read_count+1,last_access_at=excluded.last_access_at,access_order=excluded.access_order;",[&](auto* stmt){
        sqlite3_bind_text(stmt,1,logical_path.c_str(),-1,SQLITE_TRANSIENT);sqlite3_bind_int(stmt,2,gpu_id);
        sqlite3_bind_int64(stmt,3,now);sqlite3_bind_int64(stmt,4,++access_sequence_);
      });
      if(replica_gpu>=0)execute("UPDATE local_replicas SET last_access_at=? WHERE logical_path=? AND gpu_id=?;",[&](auto* stmt){
        sqlite3_bind_int64(stmt,1,now);sqlite3_bind_text(stmt,2,logical_path.c_str(),-1,SQLITE_TRANSIENT);sqlite3_bind_int(stmt,3,replica_gpu);
      });
      if(legacy_affinity) {
        execute("INSERT INTO gpu_access_events(logical_path,gpu_id,access_at) VALUES(?,?,?);",[&](auto* stmt){
          sqlite3_bind_text(stmt,1,logical_path.c_str(),-1,SQLITE_TRANSIENT);sqlite3_bind_int(stmt,2,gpu_id);sqlite3_bind_int64(stmt,3,event_now);
        });
        execute("DELETE FROM gpu_access_events WHERE logical_path=? AND access_at<?;",[&](auto* stmt){
          sqlite3_bind_text(stmt,1,logical_path.c_str(),-1,SQLITE_TRANSIENT);
          sqlite3_bind_int64(stmt,2,event_now-1000*static_cast<sqlite3_int64>(std::max<uint64_t>(long_window_sec,short_window_sec)));
        });
      }
      execute("UPDATE files SET share_count=(SELECT COUNT(*) FROM gpu_access WHERE logical_path=?) WHERE logical_path=?;",[&](auto* stmt){
        sqlite3_bind_text(stmt,1,logical_path.c_str(),-1,SQLITE_TRANSIENT);sqlite3_bind_text(stmt,2,logical_path.c_str(),-1,SQLITE_TRANSIENT);
      });
      if(legacy_affinity)UpdateAffinityLocked(logical_path,dominant_threshold_x100,shared_threshold_x100,
        short_window_sec,long_window_sec,trend_min_reads,hot_read_threshold,warm_read_threshold,max_local_replicas);
      uint64_t count=0;
      {
        auto lease=CachedStatement("SELECT COALESCE(read_count,0) FROM files WHERE logical_path=?;");auto* stmt=lease.get();
        sqlite3_bind_text(stmt,1,logical_path.c_str(),-1,SQLITE_TRANSIENT);
        const int rc=sqlite3_step(stmt);
        if(rc!=SQLITE_ROW)throw std::runtime_error(rc==SQLITE_DONE?"missing file metadata":sqlite3_errmsg(db_));
        count=static_cast<uint64_t>(sqlite3_column_int64(stmt,0));
      }
      Exec("COMMIT;");return count;
    } catch (...) {Exec("ROLLBACK;");throw;}
  }

  void Remove(const std::string& logical_path) {
    std::lock_guard<std::mutex> lock(mu_);
    sqlite3_stmt* stmt = nullptr;
    Prepare("DELETE FROM local_replicas WHERE logical_path=?;", &stmt);
    sqlite3_bind_text(stmt, 1, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    StepDone(stmt);
    Prepare("DELETE FROM gpu_access WHERE logical_path=?;", &stmt);
    sqlite3_bind_text(stmt, 1, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    StepDone(stmt);
    Prepare("DELETE FROM gpu_access_events WHERE logical_path=?;", &stmt);
    sqlite3_bind_text(stmt, 1, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    StepDone(stmt);
    Prepare("DELETE FROM content_members WHERE logical_path=?;", &stmt);
    sqlite3_bind_text(stmt, 1, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    StepDone(stmt);
    Prepare("DELETE FROM files WHERE logical_path=?;", &stmt);
    sqlite3_bind_text(stmt, 1, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    StepDone(stmt);
  }

  void AddMetric(const std::string& name, uint64_t delta) {
    std::lock_guard<std::mutex> lock(mu_);
    sqlite3_stmt* stmt = nullptr;
    Prepare("INSERT INTO metrics(name,value) VALUES(?,?) "
            "ON CONFLICT(name) DO UPDATE SET value=value+excluded.value;",
            &stmt);
    sqlite3_bind_text(stmt, 1, name.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int64(stmt, 2, static_cast<sqlite3_int64>(delta));
    StepDone(stmt);
  }

  void RecordPolicyEvent(const std::string& action, const std::string& path, int gpu,
                         uint64_t bytes, const std::string& reason, double score = 0) {
    std::lock_guard<std::mutex> lock(mu_);
    sqlite3_stmt* stmt = nullptr;
    Prepare("INSERT INTO policy_events(action,logical_path,gpu_id,bytes,reason,score) VALUES(?,?,?,?,?,?);", &stmt);
    sqlite3_bind_text(stmt,1,action.c_str(),-1,SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt,2,path.c_str(),-1,SQLITE_TRANSIENT);
    sqlite3_bind_int(stmt,3,gpu); sqlite3_bind_int64(stmt,4,bytes);
    sqlite3_bind_text(stmt,5,reason.c_str(),-1,SQLITE_TRANSIENT);
    sqlite3_bind_double(stmt,6,score); StepDone(stmt);
  }

  void ApplyMetricBatch(const std::unordered_map<std::string, uint64_t>& deltas,
                        const std::unordered_map<std::string, uint64_t>& maxima,
                        const std::vector<PolicyEvent>& events = {}) {
    std::lock_guard<std::mutex> lock(mu_);
    Exec("BEGIN IMMEDIATE;");
    try {
      // Rebind one statement per operation; preserve the FULL-WAL transaction
      // and delta-before-maximum semantics, including rollback on any failure.
      auto apply=[&](const auto& values,const char* sql) {
        if(values.empty())return;
        auto stmt=CachedStatement(sql);auto* raw=stmt.get();
        for(const auto& [name,value]:values) {
          sqlite3_bind_text(raw,1,name.c_str(),-1,SQLITE_TRANSIENT);
          sqlite3_bind_int64(raw,2,static_cast<sqlite3_int64>(value));
          if(sqlite3_step(raw)!=SQLITE_DONE)throw std::runtime_error(sqlite3_errmsg(db_));
          if(sqlite3_reset(raw)!=SQLITE_OK)throw std::runtime_error(sqlite3_errmsg(db_));
          sqlite3_clear_bindings(raw);
        }
      };
      apply(deltas,"INSERT INTO metrics(name,value) VALUES(?,?) ON CONFLICT(name) DO UPDATE SET value=value+excluded.value;");
      apply(maxima,"INSERT INTO metrics(name,value) VALUES(?,?) ON CONFLICT(name) DO UPDATE SET value=MAX(value,excluded.value);");
      if(!events.empty()) {
        auto stmt=CachedStatement("INSERT INTO policy_events(action,logical_path,gpu_id,bytes,reason,score) VALUES(?,?,?,?,?,?);");
        auto* raw=stmt.get();
        for(const auto& e:events) {
          sqlite3_bind_text(raw,1,e.action.c_str(),-1,SQLITE_TRANSIENT);
          sqlite3_bind_text(raw,2,e.path.c_str(),-1,SQLITE_TRANSIENT);
          sqlite3_bind_int(raw,3,e.gpu);sqlite3_bind_int64(raw,4,e.bytes);
          sqlite3_bind_text(raw,5,e.reason.c_str(),-1,SQLITE_TRANSIENT);
          sqlite3_bind_double(raw,6,e.score);
          if(sqlite3_step(raw)!=SQLITE_DONE)throw std::runtime_error(sqlite3_errmsg(db_));
          if(sqlite3_reset(raw)!=SQLITE_OK)throw std::runtime_error(sqlite3_errmsg(db_));
          sqlite3_clear_bindings(raw);
        }
      }
      Exec("COMMIT;");
    } catch (...) { Exec("ROLLBACK;"); throw; }
  }

  void SetMetricMax(const std::string& name, uint64_t value) {
    std::lock_guard<std::mutex> lock(mu_);
    sqlite3_stmt* stmt = nullptr;
    Prepare("INSERT INTO metrics(name,value) VALUES(?,?) "
            "ON CONFLICT(name) DO UPDATE SET "
            "value=CASE WHEN excluded.value > value THEN excluded.value ELSE value END;",
            &stmt);
    sqlite3_bind_text(stmt, 1, name.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int64(stmt, 2, static_cast<sqlite3_int64>(value));
    StepDone(stmt);
  }

  uint64_t AccessAffinityX100(const std::string& logical_path, int gpu_id) {
    std::lock_guard<std::mutex> lock(mu_);
    sqlite3_stmt* stmt = nullptr;
    Prepare("SELECT "
            "COALESCE((SELECT read_count FROM gpu_access "
            "          WHERE logical_path=? AND gpu_id=?),0),"
            "COALESCE((SELECT SUM(read_count) FROM gpu_access "
            "          WHERE logical_path=?),0);",
            &stmt);
    sqlite3_bind_text(stmt, 1, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int(stmt, 2, gpu_id);
    sqlite3_bind_text(stmt, 3, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    uint64_t affinity = 0;
    if (sqlite3_step(stmt) == SQLITE_ROW) {
      uint64_t gpu_reads = static_cast<uint64_t>(sqlite3_column_int64(stmt, 0));
      uint64_t total_reads = static_cast<uint64_t>(sqlite3_column_int64(stmt, 1));
      if (total_reads > 0) {
        affinity = std::max<uint64_t>(1, gpu_reads * 100 / total_reads);
      }
    }
    sqlite3_finalize(stmt);
    return affinity;
  }

  std::optional<LocalReplica> GetLocalReplica(const std::string& logical_path,
                                               int gpu_id) {
    std::lock_guard<std::mutex> lock(mu_);
    auto lease=CachedStatement("SELECT logical_path,gpu_id,physical_path,size_bytes,"
            "cache_generation,created_at,last_access_at,state "
            "FROM local_replicas WHERE logical_path=? AND gpu_id=?;");
    auto* stmt=lease.get();
    sqlite3_bind_text(stmt, 1, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int(stmt, 2, gpu_id);
    int rc = sqlite3_step(stmt);
    if (rc == SQLITE_DONE) {
      return std::nullopt;
    }
    if (rc != SQLITE_ROW) {
      std::string err = sqlite3_errmsg(db_);
      throw std::runtime_error(err);
    }
    LocalReplica replica;
    replica.logical_path = ColumnText(stmt, 0);
    replica.gpu_id = sqlite3_column_int(stmt, 1);
    replica.physical_path = ColumnText(stmt, 2);
    replica.size_bytes = static_cast<uint64_t>(sqlite3_column_int64(stmt, 3));
    replica.cache_generation =
        static_cast<uint64_t>(sqlite3_column_int64(stmt, 4));
    replica.created_at = static_cast<uint64_t>(sqlite3_column_int64(stmt, 5));
    replica.last_access_at =
        static_cast<uint64_t>(sqlite3_column_int64(stmt, 6));
    replica.state = ColumnText(stmt, 7);
    return replica;
  }

  std::vector<LocalReplica> LocalReplicas(const std::string& logical_path) {
    std::lock_guard<std::mutex> lock(mu_);
    auto lease=CachedStatement("SELECT logical_path,gpu_id,physical_path,size_bytes,"
            "cache_generation,created_at,last_access_at,state "
            "FROM local_replicas WHERE logical_path=? "
            "ORDER BY last_access_at ASC,created_at ASC;");
    auto* stmt=lease.get();
    sqlite3_bind_text(stmt, 1, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    std::vector<LocalReplica> out;
    while (true) {
      int rc = sqlite3_step(stmt);
      if (rc == SQLITE_DONE) {
        break;
      }
      if (rc != SQLITE_ROW) {
        std::string err = sqlite3_errmsg(db_);
        throw std::runtime_error(err);
      }
      LocalReplica replica;
      replica.logical_path = ColumnText(stmt, 0);
      replica.gpu_id = sqlite3_column_int(stmt, 1);
      replica.physical_path = ColumnText(stmt, 2);
      replica.size_bytes = static_cast<uint64_t>(sqlite3_column_int64(stmt, 3));
      replica.cache_generation =
          static_cast<uint64_t>(sqlite3_column_int64(stmt, 4));
      replica.created_at = static_cast<uint64_t>(sqlite3_column_int64(stmt, 5));
      replica.last_access_at =
          static_cast<uint64_t>(sqlite3_column_int64(stmt, 6));
      replica.state = ColumnText(stmt, 7);
      out.push_back(std::move(replica));
    }
    return out;
  }

  void UpsertLocalReplica(const LocalReplica& replica,bool publish_promotion=false) {
    std::lock_guard<std::mutex> lock(mu_);
    if(publish_promotion)Exec("BEGIN IMMEDIATE;");
    try {
    sqlite3_stmt* stmt = nullptr;
    const auto physical = replica.physical_path.string();
    Prepare("INSERT INTO local_replicas(logical_path,gpu_id,physical_path,"
            "size_bytes,cache_generation,created_at,last_access_at,state) "
            "VALUES(?,?,?,?,?,?,?,?) "
            "ON CONFLICT(logical_path,gpu_id) DO UPDATE SET "
            "physical_path=excluded.physical_path,"
            "size_bytes=excluded.size_bytes,"
            "cache_generation=excluded.cache_generation,"
            "last_access_at=excluded.last_access_at,"
            "state=excluded.state;",
            &stmt);
    sqlite3_bind_text(stmt, 1, replica.logical_path.c_str(), -1,
                      SQLITE_TRANSIENT);
    sqlite3_bind_int(stmt, 2, replica.gpu_id);
    sqlite3_bind_text(stmt, 3, physical.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int64(stmt, 4, static_cast<sqlite3_int64>(replica.size_bytes));
    sqlite3_bind_int64(
        stmt, 5, static_cast<sqlite3_int64>(replica.cache_generation));
    sqlite3_bind_int64(stmt, 6, static_cast<sqlite3_int64>(replica.created_at));
    sqlite3_bind_int64(stmt, 7,
                       static_cast<sqlite3_int64>(replica.last_access_at));
    sqlite3_bind_text(stmt, 8, replica.state.c_str(), -1, SQLITE_TRANSIENT);
    StepDone(stmt);
    if(publish_promotion) {
      Prepare("UPDATE files SET last_promoted_at=?,target_local_replica_count=MAX(target_local_replica_count,1) WHERE logical_path=?;",&stmt);
      sqlite3_bind_int64(stmt,1,UnixNow());sqlite3_bind_text(stmt,2,replica.logical_path.c_str(),-1,SQLITE_TRANSIENT);StepDone(stmt);
      if(sqlite3_changes(db_)!=1)throw std::runtime_error("replica publication requires its canonical metadata");
      Exec("COMMIT;");
    }
    }catch(...){if(publish_promotion)Exec("ROLLBACK;");throw;}
  }

  void TouchLocalReplica(const std::string& logical_path, int gpu_id) {
    std::lock_guard<std::mutex> lock(mu_);
    sqlite3_stmt* stmt = nullptr;
    Prepare("UPDATE local_replicas SET last_access_at=? "
            "WHERE logical_path=? AND gpu_id=?;",
            &stmt);
    sqlite3_bind_int64(stmt, 1, UnixNow());
    sqlite3_bind_text(stmt, 2, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int(stmt, 3, gpu_id);
    StepDone(stmt);
  }

  void RemoveLocalReplica(const std::string& logical_path, int gpu_id) {
    std::lock_guard<std::mutex> lock(mu_);
    sqlite3_stmt* stmt = nullptr;
    Prepare("DELETE FROM local_replicas WHERE logical_path=? AND gpu_id=?;",
            &stmt);
    sqlite3_bind_text(stmt, 1, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int(stmt, 2, gpu_id);
    StepDone(stmt);
  }

  void RemoveLocalReplicas(const std::string& logical_path) {
    std::lock_guard<std::mutex> lock(mu_);
    sqlite3_stmt* stmt = nullptr;
    Prepare("DELETE FROM local_replicas WHERE logical_path=?;", &stmt);
    sqlite3_bind_text(stmt, 1, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    StepDone(stmt);
  }

  ContentRefResult RegisterContentRef(const std::string& content_key,
                                      const std::string& logical_path,
                                      const fs::path& physical_path,
                                      uint64_t size_bytes) {
    ContentRefResult result;
    if (content_key.empty()) {
      return result;
    }
    std::lock_guard<std::mutex> lock(mu_);
    sqlite3_stmt* stmt = nullptr;
    Prepare("SELECT primary_logical_path,physical_path,ref_count "
            "FROM content_refs WHERE content_key=?;",
            &stmt);
    sqlite3_bind_text(stmt, 1, content_key.c_str(), -1, SQLITE_TRANSIENT);
    if (sqlite3_step(stmt) == SQLITE_ROW) {
      result.primary_logical_path = ColumnText(stmt, 0);
      result.primary_physical_path = ColumnText(stmt, 1);
      result.ref_count = static_cast<uint64_t>(sqlite3_column_int64(stmt, 2));
    }
    sqlite3_finalize(stmt);

    Prepare("SELECT COUNT(*) FROM content_members "
            "WHERE content_key=? AND logical_path != ?;",
            &stmt);
    sqlite3_bind_text(stmt, 1, content_key.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 2, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    if (sqlite3_step(stmt) == SQLITE_ROW) {
      result.duplicate = sqlite3_column_int64(stmt, 0) > 0;
    }
    sqlite3_finalize(stmt);

    const auto now = UnixNow();
    const auto physical = physical_path.string();
    Prepare("INSERT OR IGNORE INTO content_refs("
            "content_key,primary_logical_path,physical_path,size_bytes,"
            "ref_count,first_seen_at,last_seen_at) "
            "VALUES(?,?,?,?,0,?,?);",
            &stmt);
    sqlite3_bind_text(stmt, 1, content_key.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 2, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 3, physical.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int64(stmt, 4, static_cast<sqlite3_int64>(size_bytes));
    sqlite3_bind_int64(stmt, 5, now);
    sqlite3_bind_int64(stmt, 6, now);
    StepDone(stmt);

    Prepare("INSERT OR IGNORE INTO content_members(content_key,logical_path) "
            "VALUES(?,?);",
            &stmt);
    sqlite3_bind_text(stmt, 1, content_key.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 2, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    StepDone(stmt);

    Prepare("UPDATE content_refs SET "
            "size_bytes=?,"
            "last_seen_at=?,"
            "ref_count=(SELECT COUNT(*) FROM content_members "
            "           WHERE content_key=?) "
            "WHERE content_key=?;",
            &stmt);
    sqlite3_bind_int64(stmt, 1, static_cast<sqlite3_int64>(size_bytes));
    sqlite3_bind_int64(stmt, 2, now);
    sqlite3_bind_text(stmt, 3, content_key.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 4, content_key.c_str(), -1, SQLITE_TRANSIENT);
    StepDone(stmt);

    Prepare("SELECT primary_logical_path,physical_path,ref_count "
            "FROM content_refs WHERE content_key=?;",
            &stmt);
    sqlite3_bind_text(stmt, 1, content_key.c_str(), -1, SQLITE_TRANSIENT);
    if (sqlite3_step(stmt) == SQLITE_ROW) {
      result.primary_logical_path = ColumnText(stmt, 0);
      result.primary_physical_path = ColumnText(stmt, 1);
      result.ref_count = static_cast<uint64_t>(sqlite3_column_int64(stmt, 2));
    }
    sqlite3_finalize(stmt);
    return result;
  }

  std::vector<FileMeta> ChildrenUnder(const std::string& logical_dir) {
    std::lock_guard<std::mutex> lock(mu_);
    std::string prefix = logical_dir;
    if (prefix != "/" && prefix.back() != '/') {
      prefix += "/";
    }
    sqlite3_stmt* stmt = nullptr;
    Prepare("SELECT logical_path,gpu_id,tier,backend_id,physical_path,size_bytes,"
            "COALESCE(checksum,''),state "
            "FROM files WHERE logical_path LIKE ?;",
            &stmt);
    const std::string like = prefix + "%";
    sqlite3_bind_text(stmt, 1, like.c_str(), -1, SQLITE_TRANSIENT);
    std::vector<FileMeta> out;
    while (true) {
      int rc = sqlite3_step(stmt);
      if (rc == SQLITE_DONE) {
        break;
      }
      if (rc != SQLITE_ROW) {
        std::string err = sqlite3_errmsg(db_);
        sqlite3_finalize(stmt);
        throw std::runtime_error(err);
      }
      FileMeta meta;
      meta.logical_path = ColumnText(stmt, 0);
      meta.gpu_id = sqlite3_column_int(stmt, 1);
      meta.tier = ColumnText(stmt, 2);
      meta.backend_id = ColumnText(stmt, 3);
      meta.physical_path = ColumnText(stmt, 4);
      meta.size_bytes = static_cast<uint64_t>(sqlite3_column_int64(stmt, 5));
      meta.checksum = ColumnText(stmt, 6);
      meta.state = ColumnText(stmt, 7);
      out.push_back(std::move(meta));
    }
    sqlite3_finalize(stmt);
    return out;
  }

  std::vector<FileMeta> IncompleteFiles() {
    std::lock_guard<std::mutex> lock(mu_);
    sqlite3_stmt* stmt = nullptr;
    Prepare("SELECT logical_path,gpu_id,tier,backend_id,physical_path,size_bytes,"
            "COALESCE(checksum,''),state "
            "FROM files WHERE state != 'COMMITTED';",
            &stmt);
    std::vector<FileMeta> out;
    while (true) {
      int rc = sqlite3_step(stmt);
      if (rc == SQLITE_DONE) {
        break;
      }
      if (rc != SQLITE_ROW) {
        std::string err = sqlite3_errmsg(db_);
        sqlite3_finalize(stmt);
        throw std::runtime_error(err);
      }
      FileMeta meta;
      meta.logical_path = ColumnText(stmt, 0);
      meta.gpu_id = sqlite3_column_int(stmt, 1);
      meta.tier = ColumnText(stmt, 2);
      meta.backend_id = ColumnText(stmt, 3);
      meta.physical_path = ColumnText(stmt, 4);
      meta.size_bytes = static_cast<uint64_t>(sqlite3_column_int64(stmt, 5));
      meta.checksum = ColumnText(stmt, 6);
      meta.state = ColumnText(stmt, 7);
      out.push_back(std::move(meta));
    }
    sqlite3_finalize(stmt);
    return out;
  }

  struct PlanningResident {
    std::string key;
    int location=0;
    fs::path physical;
    uint64_t bytes=0,recency=0;
  };
  struct ReadyResidentBytes {
    int location;
    fs::path physical;
    uint64_t bytes;
  };
  static constexpr const char* kReadyResidentBytesSql="SELECT gpu_id,physical_path,size_bytes FROM files WHERE tier='local' AND state='COMMITTED' UNION ALL SELECT r.gpu_id,r.physical_path,r.size_bytes FROM local_replicas r JOIN files f ON f.logical_path=r.logical_path WHERE r.state='READY' AND f.state='COMMITTED';";
  bool CreateSharedPrecheckIndexes() {
    std::lock_guard<std::mutex> lock(mu_);
    if(!sqlite3_get_autocommit(db_))throw std::runtime_error("shared precheck index setup requires an idle transaction");
    try {
      Exec("BEGIN IMMEDIATE;");
      auto ensure=[&](const char* name,const char* definition) {
        Exec((std::string("CREATE INDEX IF NOT EXISTS ")+definition+";").c_str());
        // IF NOT EXISTS alone also accepts a same-name, incompatible index.
        // Confirm our exact definition; conservatively retain and fall back
        // for foreign definitions rather than replacing persisted schema.
        auto lease=CachedStatement("SELECT sql FROM sqlite_master WHERE type='index' AND name=?;");
        sqlite3_bind_text(lease.get(),1,name,-1,SQLITE_TRANSIENT);
        if(sqlite3_step(lease.get())!=SQLITE_ROW ||
           ColumnText(lease.get(),0)!=std::string("CREATE INDEX ")+definition)
          throw std::runtime_error("incompatible shared precheck index definition");
      };
      ensure("idx_files_shared_precheck_local","idx_files_shared_precheck_local ON files(gpu_id,physical_path,size_bytes) WHERE tier='local' AND state='COMMITTED'");
      ensure("idx_replicas_shared_precheck_ready","idx_replicas_shared_precheck_ready ON local_replicas(logical_path,gpu_id,physical_path,size_bytes) WHERE state='READY'");
      Exec("COMMIT;");return true;
    } catch(...) {
      // DDL is transactional: preserve existing schema but roll back all new
      // indexes on ordinary failure. Never continue Init with a stuck write
      // transaction if rollback itself failed.
      if(!sqlite3_get_autocommit(db_))sqlite3_exec(db_,"ROLLBACK;",nullptr,nullptr,nullptr);
      if(!sqlite3_get_autocommit(db_))throw std::runtime_error("shared precheck index rollback failed");
      return false;
    }
  }
  bool TryEmptyResidentState() {
    std::unique_lock<std::mutex> lock(mu_,std::try_to_lock);
    if(!lock.owns_lock())return false;
    try {
      // Do not hide orphan/stale replicas behind a JOIN: later discovery of
      // their canonical file could otherwise resurrect nonexistent occupancy.
      auto lease=CachedStatement("SELECT NOT EXISTS(SELECT 1 FROM files WHERE tier='local') AND NOT EXISTS(SELECT 1 FROM local_replicas);");
      return sqlite3_step(lease.get())==SQLITE_ROW && sqlite3_column_int(lease.get(),0)==1;
    } catch(const std::exception&) {return false;}
  }
  bool TryReadyResidentBytes(std::vector<ReadyResidentBytes>& rows) {
    std::unique_lock<std::mutex> lock(mu_,std::try_to_lock);
    if(!lock.owns_lock())return false;
    // The same read-only query serves indexed and unindexed prechecks. Without
    // the optional partial indexes it still scans the local-state predicates.
    try {
      auto lease=CachedStatement(kReadyResidentBytesSql);
      auto* stmt=lease.get();std::vector<ReadyResidentBytes> found;
      for(int rc;(rc=sqlite3_step(stmt))!=SQLITE_DONE;) {
        if(rc!=SQLITE_ROW || sqlite3_column_type(stmt,0)!=SQLITE_INTEGER ||
           sqlite3_column_type(stmt,1)!=SQLITE_TEXT || sqlite3_column_type(stmt,2)!=SQLITE_INTEGER)return false;
        const auto domain=sqlite3_column_int64(stmt,0),bytes=sqlite3_column_int64(stmt,2);
        if(domain<0 || domain>std::numeric_limits<int>::max() || bytes<0 || found.size()>=4096)return false;
        const auto physical=ColumnText(stmt,1);if(physical.empty())return false;
        found.push_back({static_cast<int>(domain),physical,static_cast<uint64_t>(bytes)});
      }
      rows=std::move(found);return true;
    } catch(const std::exception&) {return false;}
  }
  std::vector<PlanningResident> PlanningResidents() {
    std::lock_guard<std::mutex> lock(mu_);
    sqlite3_stmt* stmt=nullptr;
    // One read transaction/statement, without per-resident Get/access queries.
    Prepare("SELECT f.logical_path,f.gpu_id,f.physical_path,f.size_bytes,COALESCE(a.access_order,0) "
            "FROM files f LEFT JOIN gpu_access a ON a.logical_path=f.logical_path AND a.gpu_id=f.gpu_id "
            "WHERE f.tier='local' AND f.state='COMMITTED' "
            "UNION ALL "
            "SELECT r.logical_path,r.gpu_id,r.physical_path,r.size_bytes,COALESCE(a.access_order,0) "
            "FROM local_replicas r JOIN files f ON f.logical_path=r.logical_path "
            "LEFT JOIN gpu_access a ON a.logical_path=r.logical_path AND a.gpu_id=r.gpu_id "
            "WHERE r.state='READY' AND f.state='COMMITTED';", &stmt);
    std::vector<PlanningResident> out;
    for(int rc;(rc=sqlite3_step(stmt))!=SQLITE_DONE;) {
      if(rc!=SQLITE_ROW) {std::string err=sqlite3_errmsg(db_);sqlite3_finalize(stmt);throw std::runtime_error(err);}
      out.push_back({ColumnText(stmt,0),sqlite3_column_int(stmt,1),ColumnText(stmt,2),
                    static_cast<uint64_t>(sqlite3_column_int64(stmt,3)),
                    static_cast<uint64_t>(sqlite3_column_int64(stmt,4))});
    }
    sqlite3_finalize(stmt);return out;
  }

  std::vector<EvictionCandidate> LocalEvictionCandidates(
      int gpu_id, const std::string& protected_logical_path) {
    std::unique_lock<std::mutex> lock(mu_);
    sqlite3_stmt* stmt = nullptr;
    Prepare("SELECT logical_path,gpu_id,tier,backend_id,physical_path,size_bytes,"
            "COALESCE(checksum,''),state,COALESCE(read_count,0),"
            "COALESCE(last_access_at,0),COALESCE(content_key,''),"
            "COALESCE(recompute_cost,10),COALESCE(remote_access_cost,10),"
            "COALESCE(producer_gpu,0),COALESCE(share_count,1),"
            "COALESCE(primary_tier,'local'),COALESCE(has_remote_copy,0),"
            "COALESCE(local_cache_owner_gpu,-1),"
            "COALESCE(replica_state,'LOCAL_ONLY'),COALESCE(cache_generation,0),"
            "COALESCE(last_promoted_at,0),COALESCE(last_demoted_at,0),"
            "COALESCE(dominant_gpu_id,-1),"
            "COALESCE(dominant_gpu_read_share_x100,0),"
            "COALESCE(recent_dominant_gpu_id,-1),"
            "COALESCE(recent_dominant_gpu_read_share_x100,0),"
            "COALESCE(recent_read_count,0),"
            "COALESCE(affinity_trend,'STABLE'),"
            "COALESCE(target_local_replica_count,0),"
            "COALESCE(affinity_state,'UNKNOWN'),COALESCE(affinity_updated_at,0) "
            "FROM files WHERE gpu_id=? AND tier='local' AND state='COMMITTED' "
            "AND logical_path != ? "
            "ORDER BY COALESCE(read_count,0) ASC,"
            "COALESCE(last_access_at,0) ASC,"
            "size_bytes DESC;",
            &stmt);
    sqlite3_bind_int(stmt, 1, gpu_id);
    sqlite3_bind_text(stmt, 2, protected_logical_path.c_str(), -1,
                      SQLITE_TRANSIENT);
    std::vector<EvictionCandidate> out;
    while (true) {
      int rc = sqlite3_step(stmt);
      if (rc == SQLITE_DONE) {
        break;
      }
      if (rc != SQLITE_ROW) {
        std::string err = sqlite3_errmsg(db_);
        sqlite3_finalize(stmt);
        throw std::runtime_error(err);
      }
      EvictionCandidate candidate;
      candidate.meta.logical_path = ColumnText(stmt, 0);
      candidate.meta.gpu_id = sqlite3_column_int(stmt, 1);
      candidate.meta.tier = ColumnText(stmt, 2);
      candidate.meta.backend_id = ColumnText(stmt, 3);
      candidate.meta.physical_path = ColumnText(stmt, 4);
      candidate.meta.size_bytes =
          static_cast<uint64_t>(sqlite3_column_int64(stmt, 5));
      candidate.meta.checksum = ColumnText(stmt, 6);
      candidate.meta.state = ColumnText(stmt, 7);
      candidate.meta.read_count =
          static_cast<uint64_t>(sqlite3_column_int64(stmt, 8));
      candidate.last_access_at =
          static_cast<uint64_t>(sqlite3_column_int64(stmt, 9));
      candidate.meta.content_key = ColumnText(stmt, 10);
      candidate.meta.recompute_cost =
          static_cast<uint64_t>(sqlite3_column_int64(stmt, 11));
      candidate.meta.remote_access_cost =
          static_cast<uint64_t>(sqlite3_column_int64(stmt, 12));
      candidate.meta.producer_gpu =
          static_cast<uint64_t>(sqlite3_column_int64(stmt, 13));
      candidate.meta.share_count =
          static_cast<uint64_t>(sqlite3_column_int64(stmt, 14));
      candidate.meta.primary_tier = ColumnText(stmt, 15);
      candidate.meta.has_remote_copy = sqlite3_column_int64(stmt, 16) != 0;
      candidate.meta.local_cache_owner_gpu = sqlite3_column_int(stmt, 17);
      candidate.meta.replica_state = ColumnText(stmt, 18);
      candidate.meta.cache_generation =
          static_cast<uint64_t>(sqlite3_column_int64(stmt, 19));
      candidate.meta.last_promoted_at =
          static_cast<uint64_t>(sqlite3_column_int64(stmt, 20));
      candidate.meta.last_demoted_at =
          static_cast<uint64_t>(sqlite3_column_int64(stmt, 21));
      candidate.meta.dominant_gpu_id = sqlite3_column_int(stmt, 22);
      candidate.meta.dominant_gpu_read_share_x100 =
          static_cast<uint64_t>(sqlite3_column_int64(stmt, 23));
      candidate.meta.recent_dominant_gpu_id = sqlite3_column_int(stmt, 24);
      candidate.meta.recent_dominant_gpu_read_share_x100 =
          static_cast<uint64_t>(sqlite3_column_int64(stmt, 25));
      candidate.meta.recent_read_count =
          static_cast<uint64_t>(sqlite3_column_int64(stmt, 26));
      candidate.meta.affinity_trend = ColumnText(stmt, 27);
      candidate.meta.target_local_replica_count =
          static_cast<uint64_t>(sqlite3_column_int64(stmt, 28));
      candidate.meta.affinity_state = ColumnText(stmt, 29);
      candidate.meta.affinity_updated_at =
          static_cast<uint64_t>(sqlite3_column_int64(stmt, 30));
      out.push_back(std::move(candidate));
    }
    sqlite3_finalize(stmt);
    Prepare("SELECT logical_path,physical_path,size_bytes FROM local_replicas "
            "WHERE gpu_id=? AND state='READY' AND logical_path != ?;", &stmt);
    sqlite3_bind_int(stmt, 1, gpu_id);
    sqlite3_bind_text(stmt, 2, protected_logical_path.c_str(), -1, SQLITE_TRANSIENT);
    std::vector<EvictionCandidate> extra;
    while (sqlite3_step(stmt) == SQLITE_ROW) {
      EvictionCandidate c;
      c.meta.logical_path = ColumnText(stmt, 0);
      c.meta.physical_path = ColumnText(stmt, 1);
      c.meta.size_bytes = sqlite3_column_int64(stmt, 2);
      c.replica_gpu = gpu_id;
      extra.push_back(c);
    }
    sqlite3_finalize(stmt);
    lock.unlock();
    for (auto& c : extra) {
      if (auto m = Get(c.meta.logical_path)) {
        const auto physical = c.meta.physical_path;
        c.meta = *m;
        c.meta.physical_path = physical;
        out.push_back(c);
      }
    }
    lock.lock();
    for (auto& c : out) {
      Prepare("SELECT read_count,access_order FROM gpu_access WHERE logical_path=? AND gpu_id=?;", &stmt);
      sqlite3_bind_text(stmt, 1, c.meta.logical_path.c_str(), -1, SQLITE_TRANSIENT);
      sqlite3_bind_int(stmt, 2, gpu_id);
      if (sqlite3_step(stmt) == SQLITE_ROW) {
        c.meta.read_count = sqlite3_column_int64(stmt, 0);
        c.last_access_at = sqlite3_column_int64(stmt, 1);
      } else { c.meta.read_count = 0; c.last_access_at = 0; }
      sqlite3_finalize(stmt);
    }
    return out;
  }

 private:
  void UpdateAffinityLocked(const std::string& logical_path,
                            uint64_t dominant_threshold_x100,
                            uint64_t shared_threshold_x100,
                            uint64_t short_window_sec,
                            uint64_t long_window_sec,
                            uint64_t trend_min_reads,
                            uint64_t hot_read_threshold,
                            uint64_t warm_read_threshold,
                            uint64_t max_local_replicas) {
    struct AccessStats {
      int dominant_gpu = -1;
      uint64_t dominant_reads = 0;
      uint64_t total_reads = 0;
      uint64_t gpu_count = 0;
      uint64_t dominant_share_x100 = 0;
    };

    auto finalize_stats = [](AccessStats stats) {
      if (stats.total_reads > 0) {
        stats.dominant_share_x100 =
            stats.dominant_reads * 100 / stats.total_reads;
      }
      return stats;
    };

    sqlite3_stmt* stmt = nullptr;
    Prepare("SELECT gpu_id,read_count FROM gpu_access WHERE logical_path=? "
            "ORDER BY read_count DESC,gpu_id ASC;",
            &stmt);
    sqlite3_bind_text(stmt, 1, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    AccessStats cumulative;
    while (true) {
      int rc = sqlite3_step(stmt);
      if (rc == SQLITE_DONE) {
        break;
      }
      if (rc != SQLITE_ROW) {
        std::string err = sqlite3_errmsg(db_);
        sqlite3_finalize(stmt);
        throw std::runtime_error(err);
      }
      const int current_gpu = sqlite3_column_int(stmt, 0);
      const uint64_t current_reads =
          static_cast<uint64_t>(sqlite3_column_int64(stmt, 1));
      if (cumulative.gpu_count == 0) {
        cumulative.dominant_gpu = current_gpu;
        cumulative.dominant_reads = current_reads;
      }
      cumulative.total_reads += current_reads;
      ++cumulative.gpu_count;
    }
    sqlite3_finalize(stmt);
    cumulative = finalize_stats(cumulative);

    auto read_window_stats = [&](uint64_t window_sec) {
      AccessStats stats;
      const auto now = UnixNowMillis();
      Prepare("SELECT gpu_id,COUNT(*) FROM gpu_access_events "
              "WHERE logical_path=? AND access_at>=? "
              "GROUP BY gpu_id ORDER BY COUNT(*) DESC,gpu_id ASC;",
              &stmt);
      sqlite3_bind_text(stmt, 1, logical_path.c_str(), -1, SQLITE_TRANSIENT);
      sqlite3_bind_int64(stmt, 2,
                         now - 1000 * static_cast<sqlite3_int64>(window_sec));
      while (true) {
        int rc = sqlite3_step(stmt);
        if (rc == SQLITE_DONE) {
          break;
        }
        if (rc != SQLITE_ROW) {
          std::string err = sqlite3_errmsg(db_);
          sqlite3_finalize(stmt);
          throw std::runtime_error(err);
        }
        const int current_gpu = sqlite3_column_int(stmt, 0);
        const uint64_t current_reads =
            static_cast<uint64_t>(sqlite3_column_int64(stmt, 1));
        if (stats.gpu_count == 0) {
          stats.dominant_gpu = current_gpu;
          stats.dominant_reads = current_reads;
        }
        stats.total_reads += current_reads;
        ++stats.gpu_count;
      }
      sqlite3_finalize(stmt);
      return finalize_stats(stats);
    };

    const AccessStats recent = read_window_stats(short_window_sec);
    const AccessStats longer = read_window_stats(long_window_sec);

    std::string state = "UNKNOWN";
    std::string trend = "STABLE";
    uint64_t target_local_replicas = 0;
    const uint64_t replica_cap = std::max<uint64_t>(1, max_local_replicas);

    if (recent.total_reads == 0) {
      state = "UNKNOWN";
    } else if (recent.total_reads < warm_read_threshold) {
      state = "REMOTE_COLD";
    } else if (recent.total_reads >= trend_min_reads &&
               recent.dominant_gpu >= 0 &&
               cumulative.dominant_gpu >= 0 &&
               recent.dominant_gpu != cumulative.dominant_gpu &&
               recent.dominant_share_x100 >= dominant_threshold_x100) {
      state = "AFFINITY_SHIFTING";
      trend = "SHIFTING_TO_GPU" + std::to_string(recent.dominant_gpu);
      target_local_replicas = 1;
    } else if (recent.gpu_count > 1 &&
               recent.dominant_share_x100 <= shared_threshold_x100) {
      if (recent.total_reads >= hot_read_threshold) {
        state = "REMOTE_SHARED_HOT";
        target_local_replicas = std::min<uint64_t>(recent.gpu_count, replica_cap);
      } else {
        state = "CROSS_GPU_SHARED";
      }
    } else if (recent.dominant_share_x100 >= dominant_threshold_x100) {
      if (recent.total_reads >= hot_read_threshold) {
        state = "GPU_LOCAL_HOT";
      } else {
        state = "GPU_LOCAL_WARM";
      }
      target_local_replicas = 1;
    } else {
      state = "MIXED_AFFINITY";
      target_local_replicas = 1;
    }

    if (trend == "STABLE" && longer.dominant_gpu >= 0 &&
        recent.dominant_gpu >= 0 && longer.dominant_gpu != recent.dominant_gpu) {
      trend = "OBSERVING_GPU" + std::to_string(recent.dominant_gpu);
    }

    Prepare("UPDATE files SET dominant_gpu_id=?,"
            "dominant_gpu_read_share_x100=?,recent_dominant_gpu_id=?,"
            "recent_dominant_gpu_read_share_x100=?,recent_read_count=?,"
            "affinity_trend=?,target_local_replica_count=?,"
            "affinity_state=?,affinity_updated_at=? WHERE logical_path=?;",
            &stmt);
    sqlite3_bind_int(stmt, 1, cumulative.dominant_gpu);
    sqlite3_bind_int64(
        stmt, 2, static_cast<sqlite3_int64>(cumulative.dominant_share_x100));
    sqlite3_bind_int(stmt, 3, recent.dominant_gpu);
    sqlite3_bind_int64(
        stmt, 4, static_cast<sqlite3_int64>(recent.dominant_share_x100));
    sqlite3_bind_int64(stmt, 5, static_cast<sqlite3_int64>(recent.total_reads));
    sqlite3_bind_text(stmt, 6, trend.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int64(stmt, 7,
                       static_cast<sqlite3_int64>(target_local_replicas));
    sqlite3_bind_text(stmt, 8, state.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int64(stmt, 9, UnixNow());
    sqlite3_bind_text(stmt, 10, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    StepDone(stmt);
  }

  static sqlite3_int64 UnixNowMillis() {
    return std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();
  }

  static sqlite3_int64 UnixNow() {
    return static_cast<sqlite3_int64>(
        std::chrono::duration_cast<std::chrono::seconds>(
            std::chrono::system_clock::now().time_since_epoch())
            .count());
  }

  static std::string ColumnText(sqlite3_stmt* stmt, int col) {
    const auto* text = sqlite3_column_text(stmt, col);
    return text == nullptr ? "" : reinterpret_cast<const char*>(text);
  }

  void Exec(const char* sql) {
    char* err = nullptr;
    if (sqlite3_exec(db_, sql, nullptr, nullptr, &err) != SQLITE_OK) {
      std::string message = err == nullptr ? sqlite3_errmsg(db_) : err;
      sqlite3_free(err);
      throw std::runtime_error(message);
    }
  }

  void Prepare(const char* sql, sqlite3_stmt** stmt) {
    if (sqlite3_prepare_v2(db_, sql, -1, stmt, nullptr) != SQLITE_OK) {
      throw std::runtime_error(sqlite3_errmsg(db_));
    }
  }

  void EnsureColumn(const std::string& table, const std::string& column,
                    const std::string& definition) {
    sqlite3_stmt* stmt = nullptr;
    const std::string pragma = "PRAGMA table_info(" + table + ");";
    Prepare(pragma.c_str(), &stmt);
    bool found = false;
    while (sqlite3_step(stmt) == SQLITE_ROW) {
      if (ColumnText(stmt, 1) == column) {
        found = true;
        break;
      }
    }
    sqlite3_finalize(stmt);
    if (!found) {
      const std::string sql =
          "ALTER TABLE " + table + " ADD COLUMN " + column + " " + definition + ";";
      Exec(sql.c_str());
    }
  }

  void StepDone(sqlite3_stmt* stmt) {
    int rc = sqlite3_step(stmt);
    if (rc != SQLITE_DONE) {
      std::string err = sqlite3_errmsg(db_);
      sqlite3_finalize(stmt);
      throw std::runtime_error(err);
    }
    sqlite3_finalize(stmt);
  }

  // A fixed set of hot queries and accounting writes is serialized by mu_.
  // Reuse programs, never results; scoped reset ends every active statement.
  struct ResetCachedStatement {
    void operator()(sqlite3_stmt* stmt) const {sqlite3_reset(stmt);sqlite3_clear_bindings(stmt);}
  };
  std::unique_ptr<sqlite3_stmt,ResetCachedStatement> CachedStatement(const char* sql) {
    auto& stmt=cached_statements_[sql];
    if(!stmt)Prepare(sql,&stmt);
    return std::unique_ptr<sqlite3_stmt,ResetCachedStatement>(stmt);
  }
  std::unordered_map<std::string,sqlite3_stmt*> cached_statements_;
  uint64_t access_sequence_ = 0;
  fs::path db_path_;
  sqlite3* db_ = nullptr;
  std::mutex mu_;
};

class TokenFS {
  friend struct TokenFSTestAccess;
 public:
  explicit TokenFS(Config config)
      : config_(std::move(config)), trace_(config_.request_trace_path), fills_(config_.read_fill_buffer_bytes,config_.retain_read_fill), metadata_(config_.metadata_db) {}

  void Init() {
    if(config_.defer_background_submission_metrics && !config_.batch_background_metrics)
      throw std::runtime_error("deferred background submission metrics require batched durable telemetry");
    if(config_.ram_first_routing && !config_.retain_read_fill)
      throw std::runtime_error("RAM-first routing requires validated retained captures");
    if(config_.reuse_direct_read_tail && (!config_.readonly_canonical || !config_.backend_direct_io))
      throw std::runtime_error("direct read tail reuse requires immutable canonical O_DIRECT readers");
    if(config_.disk_opportunity_value && (!config_.persistent_run_reuse ||
       !config_.retain_read_fill || !config_.capture_local_reads ||
       !config_.measured_causal_window || !config_.shared_value_placement || !config_.measured_burst_reuse))
      throw std::runtime_error("disk opportunity value requires retained causal shared run reuse");
    if(config_.shared_caller_only && !config_.shared_value_placement)
      throw std::runtime_error("caller-only placement requires shared value placement");
    if(config_.capture_local_reads && !config_.retain_read_fill)
      throw std::runtime_error("local capture requires canonical-validated retained memory");
    if(config_.retain_read_fill && !config_.coalesce_pending_reads)
      throw std::runtime_error("retained capture requires bounded immutable read sharing");
    if(config_.coalesce_pending_reads && (!config_.foreground_read_fill || !config_.request_read_costs))
      throw std::runtime_error("pending read sharing requires immutable captured request-level reads");
    if(config_.incremental_copy_cost && (!config_.foreground_read_fill || !config_.request_read_costs || !config_.adaptive_reuse_control))
      throw std::runtime_error("incremental copy cost requires captured request-level adaptive control");
    if(config_.foreground_read_fill && (!config_.readonly_canonical || !config_.peer_cache_reads ||
       !(config_.shared_value_placement || config_.shared_pool_cache) || config_.checksum!="fnv1a64" ||
       config_.read_fill_buffer_bytes==0 || config_.read_fill_buffer_bytes>64*1024*1024))
      throw std::runtime_error("foreground read fill requires verified immutable shared caching and a bounded buffer");
    if (config_.peer_cache_reads && (!config_.readonly_canonical || config_.private_cache_domains))
      throw std::runtime_error("peer cache reads require immutable canonical data and a shared address space");
    if ((config_.shared_value_placement || config_.shared_pool_cache) &&
        (!config_.peer_cache_reads || (config_.shared_value_placement && !config_.measured_policy) ||
         (config_.shared_value_placement && config_.shared_pool_cache)))
      throw std::runtime_error("shared placement requires peer reads, a compatible policy and one placement mode");
    if(config_.lean_read_accounting && (!config_.readonly_canonical || config_.affinity_placement || config_.prefetch_on_read || (!config_.measured_policy && !config_.read_through_cache)))
      throw std::runtime_error("lean accounting requires immutable readers without legacy affinity or prefetch consumers");
    if(config_.adaptive_reuse_control && (!config_.measured_burst_reuse || !config_.compact_measured_planning))
      throw std::runtime_error("adaptive reuse requires compact burst-aware control");
    if(config_.measured_burst_reuse && (!config_.measured_causal_window || !config_.shared_value_placement || !config_.measured_admission || !config_.measured_cost))
      throw std::runtime_error("burst reuse requires causal shared cost-based admission");
    if(config_.compact_measured_planning && (!config_.measured_policy || !config_.measured_causal_window || !config_.readonly_canonical))
      throw std::runtime_error("compact measured planning requires causal immutable measured mode");
    for (const auto& gpu : config_.gpus) {
      fs::create_directories(gpu.local_root);
      auto* backend = Backend(gpu.remote_backend);
      fs::create_directories(backend->root / GpuDirName(gpu.gpu_id));
    }
    fs::create_directories(config_.mount_point);
    metadata_.Open();
    if(config_.batch_policy_events && !config_.batch_background_metrics)
      throw std::runtime_error("batched policy events require a durable background metric fence");
    RecoverIncompleteFiles();
    InitializeSubmissionPrecheck();
    background_worker_ = std::thread([this] {
      for (;;) {
        std::function<void()> task;
        {
          std::unique_lock<std::mutex> lock(background_mu_);
          background_cv_.wait(lock, [this] { return background_stopping_ || !background_tasks_.empty(); });
          if (background_tasks_.empty() && background_stopping_) break;
          task = std::move(background_tasks_.front());
          background_tasks_.pop_front();
        }
        if(config_.defer_background_submission_metrics) {
          bool task_failed=false;
          try {task();}
          catch(const std::exception& e) {
            task_failed=true;
            std::cerr<<"background task failed: "<<e.what()<<std::endl;
          }
          catch(...) {
            task_failed=true;
            std::cerr<<"background task failed: unknown exception"<<std::endl;
          }
          {
            // The task has ended. A foreground fence may now publish this
            // outcome too, together with all still-pending task telemetry.
            // SubmitBackground records accepted submissions before the worker
            // can take a task, so completion cannot overtake submission.
            std::lock_guard<std::mutex> lock(buffered_metrics_mu_);
            if(task_failed)++buffered_metrics_["background_error_count"];
            ++buffered_metrics_["background_completed"];
          }
          try {FlushBufferedMetrics(0,true);}
          catch(const std::exception& e) {
            // Flush restored the entire transaction, including this one
            // completion. Never add it again or bypass the durable fence.
            std::cerr<<"background telemetry failed: "<<e.what()<<std::endl;
          }
          catch(...) {
            std::cerr<<"background telemetry failed: unknown exception"<<std::endl;
          }
          continue;
        }
        bool completion_durable=false;
        try {
          task();
          // Completion is published only after auxiliary statistics are durable.
          if(config_.batch_background_metrics) {
            FlushBufferedMetrics(1);
            completion_durable=true;
          }
        }
        catch (const std::exception& e) {
          std::cerr << "background task failed: " << e.what() << std::endl;
          metadata_.AddMetric("background_error_count", 1);
        }
        if(!completion_durable)metadata_.AddMetric("background_completed", 1);
      }
    });
  }

  ~TokenFS() {
    {
      std::lock_guard<std::mutex> lock(background_mu_);
      background_stopping_ = true;
    }
    background_cv_.notify_all();
    if (background_worker_.joinable()) background_worker_.join();
    FlushBufferedMetrics();
    if(!trace_.Dump())std::cerr<<"request trace output failed\n";
  }

  bool SubmitBackground(std::function<void()> task) {
    std::lock_guard<std::mutex> lock(background_mu_);
    if (background_stopping_ || background_tasks_.size() >= 64) {
      if(config_.defer_background_submission_metrics)AddBufferedMetric("background_queue_rejected",1);
      else metadata_.AddMetric("background_queue_rejected", 1);
      return false;
    }
    if(config_.defer_background_submission_metrics) {
      background_tasks_.push_back(std::move(task));
      try {AddBufferedMetric("background_submitted",1);}
      catch(...) {
        // The queue mutex still excludes the worker. An allocation failure
        // while recording acceptance must not leave an uncounted task queued.
        background_tasks_.pop_back();throw;
      }
    } else {
      metadata_.AddMetric("background_submitted", 1);
      background_tasks_.push_back(std::move(task));
    }
    background_cv_.notify_one();
    return true;
  }

  int GetAttr(const char* cpath, struct stat* stbuf, fuse_file_info*) {
    RequestTrace::Span diagnostic(trace_,"getattr");
    if(diagnostic.Enabled())diagnostic.e.path=cpath;
    // Eviction removes the old cache path before committing the remote layout.
    // Serialize lookup/stat with that transition so a valid canonical object
    // cannot transiently become ENOENT in FUSE's lookup before Open is called.
    std::lock_guard<std::mutex> layout_lock(layout_mu_);
    if(diagnostic.Enabled())diagnostic.e.wait_ns=RequestTrace::Now()-diagnostic.e.start_ns;
    memset(stbuf, 0, sizeof(*stbuf));
    const std::string path = Normalize(cpath);
    if (path == "/") {
      stbuf->st_mode = S_IFDIR | 0755;
      stbuf->st_nlink = 2;
      return 0;
    }
    if (const auto* gpu = GpuForRoot(path); gpu != nullptr) {
      stbuf->st_mode = S_IFDIR | 0755;
      stbuf->st_nlink = 2;
      return 0;
    }
    auto parsed = ParseGpuPath(path);
    if (!parsed) {
      return -ENOENT;
    }
    if (auto meta = metadata_.Get(path)) {
      return StatPhysical(meta->physical_path, stbuf);
    }
    const auto [gpu, rel] = *parsed;
    const auto local = gpu->local_root / rel;
    if (fs::exists(local)) {
      return StatPhysical(local, stbuf);
    }
    const auto remote = RemotePath(*gpu, rel);
    if (fs::exists(remote)) {
      return StatPhysical(remote, stbuf);
    }
    return -ENOENT;
  }

  int ReadDir(const char* cpath, void* buf, fuse_fill_dir_t filler, off_t,
              fuse_file_info*, enum fuse_readdir_flags) {
    const std::string path = Normalize(cpath);
    filler(buf, ".", nullptr, 0, static_cast<fuse_fill_dir_flags>(0));
    filler(buf, "..", nullptr, 0, static_cast<fuse_fill_dir_flags>(0));
    if (path == "/") {
      for (const auto& gpu : config_.gpus) {
        filler(buf, GpuDirName(gpu.gpu_id).c_str(), nullptr, 0,
               static_cast<fuse_fill_dir_flags>(0));
      }
      return 0;
    }

    auto parsed = ParseGpuPath(path);
    if (!parsed) {
      return -ENOENT;
    }
    const auto [gpu, rel] = *parsed;
    std::set<std::string> names;
    AddDirectoryNames(gpu->local_root / rel, names);
    AddDirectoryNames(RemotePath(*gpu, rel), names);
    const std::string prefix = path == gpu->logical_root ? path : path + "/";
    for (const auto& meta : metadata_.ChildrenUnder(path)) {
      std::string rest = meta.logical_path.substr(prefix.size());
      auto slash = rest.find('/');
      names.insert(slash == std::string::npos ? rest : rest.substr(0, slash));
    }
    for (const auto& name : names) {
      filler(buf, name.c_str(), nullptr, 0, static_cast<fuse_fill_dir_flags>(0));
    }
    return 0;
  }

  int MkDir(const char* cpath, mode_t mode) {
    if (config_.readonly_canonical) return -EROFS;
    auto parsed = ParseGpuPath(Normalize(cpath));
    if (!parsed) {
      return -EINVAL;
    }
    const auto [gpu, rel] = *parsed;
    std::error_code ec;
    fs::create_directories(gpu->local_root / rel, ec);
    if (ec) {
      return -ec.value();
    }
    fs::create_directories(RemotePath(*gpu, rel), ec);
    if (ec) {
      return -ec.value();
    }
    chmod((gpu->local_root / rel).c_str(), mode);
    chmod(RemotePath(*gpu, rel).c_str(), mode);
    return 0;
  }

  int RmDir(const char* cpath) {
    if (config_.readonly_canonical) return -EROFS;
    auto parsed = ParseGpuPath(Normalize(cpath));
    if (!parsed) {
      return -EINVAL;
    }
    const auto [gpu, rel] = *parsed;
    std::error_code local_ec;
    std::error_code remote_ec;
    fs::remove(gpu->local_root / rel, local_ec);
    fs::remove(RemotePath(*gpu, rel), remote_ec);
    if (local_ec && remote_ec) {
      return -local_ec.value();
    }
    return 0;
  }

  int Create(const char* cpath, mode_t mode, fuse_file_info* fi) {
    if (config_.readonly_canonical) return -EROFS;
    const std::string path = Normalize(cpath);
    auto parsed = ParseGpuPath(path);
    if (!parsed) {
      return -EINVAL;
    }
    const auto [gpu, rel] = *parsed;
    FileMeta meta = SelectNewFile(*gpu, rel, path);
    fs::create_directories(meta.physical_path.parent_path());
    int fd = open(meta.physical_path.c_str(), fi->flags | O_CREAT, mode);
    if (fd < 0) {
      return -errno;
    }
    metadata_.Upsert(meta);
    Handle handle;
    handle.fd = fd;
    handle.logical_path = path;
    handle.gpu_id = gpu->gpu_id;
    handle.caller_gpu_id = DetectCallerGpuId(gpu->gpu_id);
    handle.tier = meta.tier;
    handle.backend_id = meta.backend_id;
    handle.physical_path = meta.physical_path;
    handle.flags = fi->flags;
    handle.writable = true;
    handle.created_remote = meta.tier == "remote";
    handle.state = "CREATING";
    fi->fh = StoreHandle(std::move(handle));
    return 0;
  }

  int Open(const char* cpath, fuse_file_info* fi) {
    RequestTrace::Span diagnostic(trace_,"open");
    if(diagnostic.Enabled())diagnostic.e.path=cpath;
    const auto open_start=Clock::now();
    std::unique_lock<std::mutex> layout_lock(layout_mu_);
    if(diagnostic.Enabled())diagnostic.e.wait_ns=RequestTrace::Now()-diagnostic.e.start_ns;
    if(config_.profile_control_path) {
      const auto wait=ElapsedMicros(open_start);
      AddBufferedMetric("open_layout_wait_us",wait);SetBufferedMetricMax("open_layout_wait_us_max",wait);
    }
    if (config_.readonly_canonical && IsWritable(fi->flags)) return -EROFS;
    const std::string path = Normalize(cpath);
    auto parsed = ParseGpuPath(path);
    if (!parsed) {
      return -EINVAL;
    }
    const auto [gpu, rel] = *parsed;
    FileMeta meta;
    std::optional<FileMeta> discovered;
    if (auto existing = metadata_.Get(path)) {
      meta = *existing;
    } else {
      auto local = gpu->local_root / rel;
      if (fs::exists(local)) {
        meta.logical_path = path;
        meta.gpu_id = gpu->gpu_id;
        meta.tier = "local";
        meta.backend_id = "local";
        meta.physical_path = local;
        meta.size_bytes = FileSizeNoThrow(local);
        meta.state = "COMMITTED";
        meta.producer_gpu = static_cast<uint64_t>(gpu->gpu_id);
        meta.primary_tier = "local";
        meta.has_remote_copy = false;
        meta.local_cache_owner_gpu = gpu->gpu_id;
        meta.replica_state = "LOCAL_ONLY";
      } else {
        auto remote = RemotePath(*gpu, rel);
        if (!fs::exists(remote)) {
          return -ENOENT;
        }
        meta.logical_path = path;
        meta.gpu_id = gpu->gpu_id;
        meta.tier = "remote";
        meta.backend_id = gpu->remote_backend;
        meta.physical_path = remote;
        meta.size_bytes = FileSizeNoThrow(remote);
        meta.state = "COMMITTED";
        meta.producer_gpu = static_cast<uint64_t>(gpu->gpu_id);
        meta.primary_tier = "remote";
        meta.has_remote_copy = true;
        meta.local_cache_owner_gpu = -1;
        meta.replica_state = "REMOTE_ONLY";
      }
      if(IsWritable(fi->flags))metadata_.Upsert(meta);
      else discovered=meta;
    }
    const bool writable = IsWritable(fi->flags);
    const int caller_gpu_id = DetectCallerGpuId(gpu->gpu_id);
    bool borrowed_peer = false;
    int resident_gpu_id = gpu->gpu_id;
    std::shared_ptr<ReadFillPool::Buffer> borrowed_capture;
    int fd=-1;
    struct OpenSourceGuard {int& fd;~OpenSourceGuard(){if(fd>=0)close(fd);}} source_guard{fd};
    auto try_retained_capture=[&] {
      if(!config_.retain_read_fill || writable || !meta.has_remote_copy)return false;
      const auto source=RemotePath(*gpu,rel);
      auto capture=fills_.FindComplete(path,source.string(),meta.size_bytes);
      if(!capture)return false;
      int source_fd=open(source.c_str(),fi->flags | (config_.backend_direct_io?O_DIRECT:0));
      if(source_fd<0)return false;
      if(!capture->MatchesFd(source_fd)){close(source_fd);return false;}
      fd=source_fd;borrowed_capture=std::move(capture);meta.physical_path=source;
      meta.tier="inflight";meta.backend_id="retained-capture";
      AddBufferedMetric("retained_capture_hit",1);
      return true;
    };
    // Update policy state on every logical read, including local fast hits.
    if (!writable) {
      auto record_read=[&](int replica_gpu) {
        const auto count=metadata_.IncrementReadCount(path, caller_gpu_id,
          config_.affinity_dominant_threshold_x100, config_.affinity_shared_threshold_x100,
          config_.affinity_short_window_sec,
          config_.trend_prediction ? config_.affinity_long_window_sec : config_.affinity_short_window_sec,
          config_.affinity_trend_min_reads, config_.affinity_hot_read_threshold,
          config_.affinity_warm_read_threshold, config_.max_local_replicas_per_file,!config_.lean_read_accounting,replica_gpu,
          discovered?&*discovered:nullptr);
        discovered.reset();
        return count;
      };
      int touched_replica=-1;
      if(!config_.lean_read_accounting) {
        record_read(-1);meta=*metadata_.Get(path);
      }
      // RAM serves this request independently of a disk replica. Validate and
      // pin the canonical source first, then avoid crediting unused disk paths.
      // Logical access accounting and policy observations still happen once.
      const bool canonical_local=meta.tier=="local";
      if(config_.ram_first_routing && try_retained_capture()) {
        AddBufferedMetric("ram_first_routing_hit",1);
        // Keep SIEVE's logical access stream unchanged when RAM wins routing.
        // This visits only an already published resident, without probing its
        // disk path or claiming a local/peer data read that never happened.
        if(config_.local_eviction_policy=="sieve" &&
           HitSieveLogicalResident(path,gpu->gpu_id,caller_gpu_id,canonical_local))
          AddBufferedMetric("sieve_ram_logical_hit",1);
      }
      // Optional isolated access-domain topology: another domain's canonical
      // local copy is not addressable. Every compared policy uses this routing.
      if(!borrowed_capture && config_.private_cache_domains && caller_gpu_id!=gpu->gpu_id) {
        if(meta.tier=="local")AddBufferedMetric("private_domain_owner_copy_bypassed",1);
        meta.tier="remote";meta.backend_id=gpu->remote_backend;
        meta.physical_path=RemotePath(*gpu,rel);
        AddBufferedMetric("private_domain_read_count",1);
      }
      if (!borrowed_capture && caller_gpu_id != gpu->gpu_id) {
        if (auto replica = metadata_.GetLocalReplica(path, caller_gpu_id);
            replica && replica->state == "READY" && fs::exists(replica->physical_path)) {
          meta.tier = "local";
          meta.backend_id = "local-replica";
          meta.physical_path = replica->physical_path;
          resident_gpu_id = caller_gpu_id;
          touched_replica=caller_gpu_id;
          if(!config_.lean_read_accounting)metadata_.TouchLocalReplica(path, caller_gpu_id);
          AddBufferedMetric("cross_gpu_local_replica_hit", 1);
        }
      }
      if (!borrowed_capture && config_.peer_cache_reads && meta.tier != "local") {
        if (auto peer = ReadablePeer(path, caller_gpu_id)) {
          meta.tier = "local";
          meta.backend_id = "local-peer";
          meta.physical_path = peer->physical_path;
          borrowed_peer = true;
          resident_gpu_id = peer->gpu_id;
          touched_replica=peer->gpu_id;
          if(!config_.lean_read_accounting)metadata_.TouchLocalReplica(path, peer->gpu_id);
          AddBufferedMetric("peer_cache_hit", 1);
        }
      }
      if(config_.lean_read_accounting) {
        // Persist counts and the selected replica timestamp in ONE FULL-WAL
        // transaction. Durability is unchanged; avoid a second hit-path fsync.
        meta.read_count=record_read(touched_replica);
        AddBufferedMetric("legacy_affinity_statistics_skipped",1);
        if(touched_replica>=0)AddBufferedMetric("replica_touch_batched",1);
      }
      if(config_.local_eviction_policy=="sieve" && meta.tier=="local")
        sieve_.Hit(resident_gpu_id,path);

    }
    // Preserve the legacy ordering when disabled, and allow a capture that
    // completed during ordinary routing to be validated before opening disk.
    if(fd<0)try_retained_capture();
    if(fd<0)fd=open(meta.physical_path.c_str(),fi->flags | ((!writable && config_.backend_direct_io)?O_DIRECT:0));
    if(fd<0)return -errno;
    if(config_.coalesce_pending_reads && !config_.retain_read_fill && !writable && meta.tier=="remote") {
      bool pending=false;
      {std::lock_guard<std::mutex> pending_lock(shared_placement_mu_);pending=shared_placement_inflight_.count(path)!=0;}
      if(pending) {
        borrowed_capture=fills_.FindComplete(path,meta.physical_path.string(),meta.size_bytes);
        if(borrowed_capture && !borrowed_capture->MatchesFd(fd))borrowed_capture.reset();
        if(borrowed_capture) {meta.tier="inflight";meta.backend_id="inflight";}
      }
    }
    if(borrowed_capture)AddBufferedMetric("inflight_capture_borrowed",1);
    if(!writable) {
      bool affinity_reset=false;
      if((config_.measured_policy || config_.measured_track_affinity || (config_.private_cache_domains && config_.read_through_cache && config_.read_through_min_reads>1)) && measured_.Observe(caller_gpu_id,path,MeasuredOptions(),meta.tier!="remote",&affinity_reset))
        AddBufferedMetric("measured_shift_resets",1);
      if(affinity_reset)AddBufferedMetric("measured_affinity_context_resets",1);
      AddBufferedMetric("read_open_count",1);
      AddBufferedMetric(meta.tier+"_read_open_count",1);
    }
    if (writable) {
      meta.state = "CREATING";
      metadata_.Upsert(meta);
    }
    Handle handle;
    handle.fd = fd;
    handle.borrowed_capture=std::move(borrowed_capture);
    handle.logical_path = path;
    handle.gpu_id = gpu->gpu_id;
    handle.caller_gpu_id = caller_gpu_id;
    handle.tier = meta.tier;
    handle.backend_id = meta.backend_id;
    handle.physical_path = meta.physical_path;
    handle.flags = fi->flags;
    handle.writable = writable;
    handle.state = meta.state;
    if(config_.reuse_direct_read_tail && !writable && !handle.borrowed_capture)
      handle.direct_read_tail=std::make_shared<AlignedReadTail>();
    if(config_.request_read_costs && !writable)handle.read_cost=std::make_shared<RequestReadCost>(meta.size_bytes);
    if(config_.foreground_read_fill && !writable &&
       (meta.tier=="remote" || (config_.capture_local_reads && meta.tier=="local" && meta.has_remote_copy))) {
      handle.read_fill=fills_.Acquire(path,fd,meta.size_bytes,config_.capture_local_reads?RemotePath(*gpu,rel).string():"");
      if(meta.tier=="local")AddBufferedMetric(handle.read_fill?"local_capture_started":"local_capture_unavailable",1);
      AddBufferedMetric(handle.read_fill?"read_fill_capture_started":"read_fill_capture_unavailable",1);
      SetBufferedMetricMax("read_fill_buffer_peak_bytes",fills_.PeakBytes());
    }
    const bool deferred_fill=bool(handle.read_fill);
    const bool coalesced=bool(handle.borrowed_capture);
    fi->fh = StoreHandle(std::move(handle));
    fd=-1; // The handle table now owns the pinned source descriptor.
    fi->direct_io = config_.fuse_direct_io;
    if(diagnostic.Enabled()) {
      diagnostic.e.handle=fi->fh;diagnostic.e.caller=caller_gpu_id;diagnostic.e.tier=meta.tier;
      // Record the actual disk location, not the consumer. RAM hits must not
      // be credited to a disk replica that happened to be present too.
      diagnostic.e.location=meta.tier=="local"?resident_gpu_id:-1;
      diagnostic.e.selected_ns=RequestTrace::Now();
    }
    layout_lock.unlock();
    // Pin the selected source before future placement work; this miss remains a miss.
    if (!writable && (config_.shared_value_placement || config_.shared_pool_cache)) {
      if (meta.tier == "remote" && !deferred_fill && !coalesced) ScheduleSharedPlacement(*metadata_.Get(path), caller_gpu_id);
    } else if (!writable && !borrowed_peer) {
      FileMeta canonical = *metadata_.Get(path);
      MaybeManageCrossGpuReplica(canonical, caller_gpu_id);
      if (canonical.tier == "remote" && ShouldPromoteOnRead(canonical, canonical.read_count, caller_gpu_id)) {
        if (config_.async_promote_on_read) SchedulePromoteToLocal(*gpu, rel, path, "promote", true);
        else PromoteToLocal(*gpu, rel, canonical, "promote");
      }
      if (caller_gpu_id == gpu->gpu_id) MaybeSchedulePrefetch(*gpu, rel);
    }
    AddBufferedMetric("open_"+meta.tier,1);
    if(config_.profile_control_path)RecordLatency("open_control",meta.tier,ElapsedMicros(open_start));
    return 0;
  }

  int Read(const char*, char* buf, size_t size, off_t offset,
           fuse_file_info* fi) {
    RequestTrace::Span diagnostic(trace_,"read");
    const auto start = Clock::now();
    auto* handle = FindHandle(fi);
    if (handle == nullptr) {
      return -EBADF;
    }
    if(diagnostic.Enabled()){diagnostic.e.handle=fi->fh;diagnostic.e.path=handle->logical_path;diagnostic.e.caller=handle->caller_gpu_id;diagnostic.e.tier=handle->tier;}
    ApplyQos(*handle, false, size);
    ssize_t n;
    if(handle->borrowed_capture) {
      n=handle->borrowed_capture->ReadCaptured(handle->fd,buf,size,offset);
      if(n<0){AddBufferedMetric("inflight_source_error_count",1);return static_cast<int>(n);}
    } else if(handle->direct_read_tail) {
      AlignedReadTail::Stats stats;
      n=handle->direct_read_tail->Read(handle->fd,buf,size,offset,stats,diagnostic.Enabled());
      const int saved_errno=errno;
      if(diagnostic.Enabled())diagnostic.e.pread_ns=stats.pread_ns;
      AddBufferedMetric("direct_backend_pread_ops",stats.pread_ops);
      AddBufferedMetric("direct_backend_pread_bytes",stats.pread_bytes);
      AddBufferedMetric("direct_read_tail_hits",stats.tail_hits);
      AddBufferedMetric("direct_read_tail_bytes",stats.tail_bytes);
      AddBufferedMetric("direct_read_tail_invalidations",stats.invalidations);
      errno=saved_errno;
    } else if (config_.backend_direct_io) {
      // Both tiers use the same 4 KiB aligned bounce buffer; no silent buffered fallback.
      const off_t aligned_offset = offset / 4096 * 4096;
      const size_t skip = static_cast<size_t>(offset - aligned_offset);
      const size_t aligned_size = (size + skip + 4095) / 4096 * 4096;
      void* aligned = nullptr;
      if (posix_memalign(&aligned, 4096, std::max<size_t>(4096, aligned_size)) != 0) return -ENOMEM;
      const auto pread_start=diagnostic.Enabled()?RequestTrace::Now():0;
      n = pread(handle->fd, aligned, aligned_size, aligned_offset);
      const int saved_errno = errno;
      if(diagnostic.Enabled())diagnostic.e.pread_ns=RequestTrace::Now()-pread_start;
      AddBufferedMetric("direct_backend_pread_ops",1);
      if(n>0)AddBufferedMetric("direct_backend_pread_bytes",static_cast<uint64_t>(n));
      if (n >= 0) {
        n = n <= static_cast<ssize_t>(skip) ? 0 : std::min<ssize_t>(size, n - skip);
        if (n) memcpy(buf, static_cast<char*>(aligned) + skip, n);
      }
      free(aligned);
      errno = saved_errno;
    } else {
      const auto pread_start=diagnostic.Enabled()?RequestTrace::Now():0;
      n = pread(handle->fd, buf, size, offset);
      const int saved_errno=errno;
      if(diagnostic.Enabled())diagnostic.e.pread_ns=RequestTrace::Now()-pread_start;
      errno=saved_errno;
    }
    if (n < 0) {
      if(handle->read_fill)handle->read_fill->Invalidate();
      return -errno;
    }
    if(diagnostic.Enabled())diagnostic.e.bytes=static_cast<uint64_t>(n);
    AddBufferedMetric("read_ops", 1);
    AddBufferedMetric("read_bytes", static_cast<uint64_t>(n));
    if (handle->backend_id == "local-peer")
      AddBufferedMetric("peer_cache_read_bytes", static_cast<uint64_t>(n));
    AddBufferedMetric("qos_gpu" + std::to_string(handle->caller_gpu_id) +
                          "_read_ops",
                      1);
    AddBufferedMetric("qos_gpu" + std::to_string(handle->caller_gpu_id) +
                          "_read_bytes",
                      static_cast<uint64_t>(n));
    AddBufferedMetric("read_"+handle->tier+"_ops",1);
    AddBufferedMetric("read_"+handle->tier+"_bytes",static_cast<uint64_t>(n));
    const uint64_t latency_us = ElapsedMicros(start);
    RecordLatency("read", handle->tier, latency_us);
    if (n > 0) {
      if(!config_.request_read_costs && handle->tier!="inflight" && (config_.measured_policy || config_.measured_track_affinity)) measured_.ReadSample(handle->tier=="local",static_cast<uint64_t>(n),latency_us,config_.bounded_cost_warmup);
      MaybeAdaptivePromote(*handle, latency_us);
    }
    if(handle->read_cost)AccountRequestReadCost(*handle,n>0?handle->read_cost->Add(offset,n,latency_us):handle->read_cost->Finish());
    if(handle->read_fill) {
      const auto capture_start=ReadFillPool::NowNs();
      const bool complete=handle->read_fill->Append(offset,buf,static_cast<size_t>(n),handle->fd);
      AddBufferedMetric("read_fill_capture_us",(ReadFillPool::NowNs()-capture_start+999)/1000);
      if(complete) {
        fills_.Retain(handle->read_fill);
        AddBufferedMetric("read_fill_capture_complete",1);
        AddBufferedMetric("read_fill_capture_bytes",handle->read_fill->Data().size());
        if(handle->tier=="remote")if(auto meta=metadata_.Get(handle->logical_path))
          ScheduleSharedPlacement(*meta,handle->caller_gpu_id,handle->read_fill);
      }
    }
    return static_cast<int>(n);
  }

  int Write(const char*, const char* buf, size_t size, off_t offset,
            fuse_file_info* fi) {
    const auto start = Clock::now();
    auto* handle = FindHandle(fi);
    if (handle == nullptr) {
      return -EBADF;
    }
    ApplyQos(*handle, true, size);
    if (int rc = SpillIfNeeded(*handle, static_cast<uint64_t>(offset + size));
        rc != 0) {
      return rc;
    }
    ssize_t n = pwrite(handle->fd, buf, size, offset);
    if (n < 0) {
      return -errno;
    }
    handle->state = "CREATING";
    UpdateHandleMeta(*handle, "CREATING");
    AddBufferedMetric("write_ops", 1);
    AddBufferedMetric("write_bytes", static_cast<uint64_t>(n));
    AddBufferedMetric("qos_gpu" + std::to_string(handle->caller_gpu_id) +
                          "_write_ops",
                      1);
    AddBufferedMetric("qos_gpu" + std::to_string(handle->caller_gpu_id) +
                          "_write_bytes",
                      static_cast<uint64_t>(n));
    AddBufferedMetric(handle->tier == "local" ? "write_local_ops"
                                               : "write_remote_ops",
                      1);
    AddBufferedMetric(handle->tier == "local" ? "write_local_bytes"
                                               : "write_remote_bytes",
                      static_cast<uint64_t>(n));
    const uint64_t latency_us = ElapsedMicros(start);
    RecordLatency("write", handle->tier, latency_us);
    return static_cast<int>(n);
  }

  int Release(const char*, fuse_file_info* fi) {
    RequestTrace::Span diagnostic(trace_,"release");
    std::unique_lock<std::mutex> lock(handles_mu_);
    auto it = handles_.find(fi->fh);
    if (it == handles_.end()) {
      lock.unlock();
      FlushBufferedMetrics();
      return 0;
    }
    const bool readonly=!it->second.writable;
    bool should_dedup = false;
    if(diagnostic.Enabled()){diagnostic.e.wait_ns=RequestTrace::Now()-diagnostic.e.start_ns;diagnostic.e.handle=fi->fh;diagnostic.e.path=it->second.logical_path;diagnostic.e.caller=it->second.caller_gpu_id;diagnostic.e.tier=it->second.tier;}
    if (it->second.fd >= 0) {
      if (it->second.writable) {
        int rc = CommitHandle(it->second);
        if (rc != 0) {
          close(it->second.fd);
          if(it->second.direct_read_tail)--direct_read_tail_handles_;
          handles_.erase(it);
          lock.unlock();
          FlushBufferedMetrics();
          return rc;
        }
      }
      close(it->second.fd);
      it->second.fd = -1;
      should_dedup = it->second.pending_physical_dedup;
    }
    if (should_dedup) {
      ApplyPhysicalDedup(it->second);
    }
    if(it->second.read_cost)AccountRequestReadCost(it->second,it->second.read_cost->Finish());
    const bool fallback=it->second.read_fill && !it->second.read_fill->Dispatched();
    const auto fallback_path=fallback?it->second.logical_path:std::string{};
    const int fallback_caller=it->second.caller_gpu_id;
    if(it->second.direct_read_tail)--direct_read_tail_handles_;
    handles_.erase(it);
    // No handle remains to protect. Do not hold the pin table across SQLite
    // telemetry fsyncs: background capacity checks also need this mutex.
    lock.unlock();
    if(fallback) {
      AddBufferedMetric("read_fill_partial_fallback",1);
      if(auto meta=metadata_.Get(fallback_path))ScheduleSharedPlacement(*meta,fallback_caller);
    }
    // The release fence publishes any fallback submission before a benchmark
    // may treat submitted==completed as a fully observed queue drain. Count a
    // valid read handle exactly once; repeated Release only retries the fence.
    if(readonly)AddBufferedMetric("read_release_count",1);
    const auto flush_start=diagnostic.Enabled()?RequestTrace::Now():0;
    FlushBufferedMetrics();
    if(diagnostic.Enabled())diagnostic.e.flush_ns=RequestTrace::Now()-flush_start;
    return 0;
  }

  int Fsync(const char*, int datasync, fuse_file_info* fi) {
    auto* handle = FindHandle(fi);
    if (handle == nullptr) {
      return -EBADF;
    }
    if (handle->writable) {
      metadata_.AddMetric("fsync_ops", 1);
      return CommitHandle(*handle);
    }
    int rc = datasync ? fdatasync(handle->fd) : fsync(handle->fd);
    if (rc != 0) {
      return -errno;
    }
    metadata_.AddMetric("fsync_ops", 1);
    return 0;
  }

  int Fallocate(const char*, int mode, off_t offset, off_t length,
                fuse_file_info* fi) {
    if ((mode & ~(FALLOC_FL_KEEP_SIZE)) != 0) {
      return -EOPNOTSUPP;
    }
    auto* handle = FindHandle(fi);
    if (handle == nullptr) {
      return -EBADF;
    }
    const uint64_t end = static_cast<uint64_t>(offset + length);
    if ((mode & FALLOC_FL_KEEP_SIZE) == 0) {
      if (int rc = SpillIfNeeded(*handle, end); rc != 0) {
        return rc;
      }
    }
    int rc = posix_fallocate(handle->fd, offset, length);
    if (rc != 0) {
      return -rc;
    }
    handle->state = "CREATING";
    UpdateHandleMeta(*handle, "CREATING");
    metadata_.AddMetric("fallocate_ops", 1);
    metadata_.AddMetric("fallocate_bytes", static_cast<uint64_t>(length));
    return 0;
  }

  int Truncate(const char* cpath, off_t size, fuse_file_info* fi) {
    if (config_.readonly_canonical) return -EROFS;
    std::string path = Normalize(cpath);
    if (fi != nullptr && fi->fh != 0) {
      auto* handle = FindHandle(fi);
      if (handle == nullptr) {
        return -EBADF;
      }
      if (int rc = SpillIfNeeded(*handle, static_cast<uint64_t>(size)); rc != 0) {
        return rc;
      }
      if (ftruncate(handle->fd, size) != 0) {
        return -errno;
      }
      handle->state = "CREATING";
      UpdateHandleMeta(*handle, "CREATING");
      return CommitHandle(*handle);
    }
    auto parsed = ParseGpuPath(path);
    if (!parsed) {
      return -EINVAL;
    }
    fuse_file_info tmp{};
    tmp.flags = O_RDWR;
    int rc = Open(cpath, &tmp);
    if (rc != 0) {
      return rc;
    }
    rc = Truncate(cpath, size, &tmp);
    Release(cpath, &tmp);
    return rc;
  }

  int Unlink(const char* cpath) {
    if (config_.readonly_canonical) return -EROFS;
    const std::string path = Normalize(cpath);
    auto parsed = ParseGpuPath(path);
    if (!parsed) {
      return -EINVAL;
    }
    const auto [gpu, rel] = *parsed;
    bool removed = false;
    if (auto meta = metadata_.Get(path)) {
      std::error_code ec;
      removed = fs::remove(meta->physical_path, ec) || removed;
    }
    for (const auto& replica : metadata_.LocalReplicas(path)) {
      std::error_code ec;
      removed = fs::remove(replica.physical_path, ec) || removed;
    }
    std::error_code local_ec;
    std::error_code remote_ec;
    removed = fs::remove(gpu->local_root / rel, local_ec) || removed;
    removed = fs::remove(RemotePath(*gpu, rel), remote_ec) || removed;
    metadata_.Remove(path);
    return removed ? 0 : -ENOENT;
  }

  int Rename(const char* cfrom, const char* cto, unsigned int flags) {
    if (config_.readonly_canonical) return -EROFS;
    if (flags != 0) {
      return -EINVAL;
    }
    const std::string from = Normalize(cfrom);
    const std::string to = Normalize(cto);
    auto from_parsed = ParseGpuPath(from);
    auto to_parsed = ParseGpuPath(to);
    if (!from_parsed || !to_parsed ||
        (*from_parsed).first->gpu_id != (*to_parsed).first->gpu_id) {
      return -EINVAL;
    }
    const auto [gpu, from_rel] = *from_parsed;
    const auto to_rel = (*to_parsed).second;
    if (auto meta = metadata_.Get(from)) {
      fs::path dest = meta->tier == "local" ? gpu->local_root / to_rel
                                            : RemotePath(*gpu, to_rel);
      fs::create_directories(dest.parent_path());
      std::error_code ec;
      fs::rename(meta->physical_path, dest, ec);
      if (ec) {
        return -ec.value();
      }
      if (meta->has_remote_copy && meta->tier == "local") {
        const fs::path old_remote = RemotePath(*gpu, from_rel);
        const fs::path new_remote = RemotePath(*gpu, to_rel);
        if (fs::exists(old_remote)) {
          fs::create_directories(new_remote.parent_path());
          std::error_code remote_ec;
          fs::rename(old_remote, new_remote, remote_ec);
          if (remote_ec) {
            return -remote_ec.value();
          }
        }
      }
      for (const auto& replica : metadata_.LocalReplicas(from)) {
        std::error_code replica_ec;
        fs::remove(replica.physical_path, replica_ec);
      }
      metadata_.RemoveLocalReplicas(from);
      meta->logical_path = to;
      meta->physical_path = dest;
      metadata_.Remove(from);
      metadata_.Upsert(*meta);
      return 0;
    }
    std::error_code local_ec;
    std::error_code remote_ec;
    fs::rename(gpu->local_root / from_rel, gpu->local_root / to_rel, local_ec);
    fs::rename(RemotePath(*gpu, from_rel), RemotePath(*gpu, to_rel), remote_ec);
    if (local_ec && remote_ec) {
      return -local_ec.value();
    }
    return 0;
  }

 private:
  static std::string Normalize(const char* cpath) {
    std::string path = cpath == nullptr ? "/" : cpath;
    if (path.empty()) {
      path = "/";
    }
    while (path.size() > 1 && path.back() == '/') {
      path.pop_back();
    }
    return path;
  }

  static std::string GpuDirName(int gpu_id) { return "gpu" + std::to_string(gpu_id); }

  const BackendConfig* Backend(const std::string& id) const {
    auto it = config_.backends.find(id);
    if (it == config_.backends.end()) {
      throw std::runtime_error("unknown backend: " + id);
    }
    return &it->second;
  }

  fs::path RemotePath(const GpuConfig& gpu, const fs::path& rel) const {
    return Backend(gpu.remote_backend)->root / GpuDirName(gpu.gpu_id) / rel;
  }

  const GpuConfig* GpuForRoot(const std::string& path) const {
    for (const auto& gpu : config_.gpus) {
      if (path == gpu.logical_root) {
        return &gpu;
      }
    }
    return nullptr;
  }

  const GpuConfig* GpuById(int gpu_id) const {
    for (const auto& gpu : config_.gpus) {
      if (gpu.gpu_id == gpu_id) {
        return &gpu;
      }
    }
    return nullptr;
  }

  std::optional<std::pair<const GpuConfig*, fs::path>> ParseGpuPath(
      const std::string& path) const {
    for (const auto& gpu : config_.gpus) {
      const std::string prefix = gpu.logical_root + "/";
      if (path.rfind(prefix, 0) == 0) {
        return std::make_pair(&gpu, fs::path(path.substr(prefix.size())));
      }
    }
    return std::nullopt;
  }

  fs::path CrossGpuReplicaPath(const GpuConfig& caller_gpu,
                               const GpuConfig& owner_gpu,
                               const fs::path& rel) const {
    return caller_gpu.local_root / ".tokenfs-replicas" /
           GpuDirName(owner_gpu.gpu_id) / rel;
  }

  bool KnownGpuId(int gpu_id) const {
    return std::any_of(config_.gpus.begin(), config_.gpus.end(),
                       [gpu_id](const GpuConfig& gpu) {
                         return gpu.gpu_id == gpu_id;
                       });
  }

  // Called under layout_mu_. Preserve ordinary routing priority for logical
  // SIEVE hits while an upper-tier capture supplies the bytes. READY metadata
  // and SIEVE's verified resident index are both required; no filesystem probe
  // or replica timestamp write is performed for an unused disk source.
  bool HitSieveLogicalResident(const std::string& path,int owner,int caller,bool canonical_local) {
    if(!KnownGpuId(owner) || !KnownGpuId(caller))return false;
    if(caller!=owner && KnownGpuId(caller)) {
      if(auto replica=metadata_.GetLocalReplica(path,caller);
         replica && replica->state=="READY" && sieve_.HitKnown(caller,path))return true;
    }
    if(canonical_local && KnownGpuId(owner) &&
       (!config_.private_cache_domains || caller==owner) && sieve_.HitKnown(owner,path))return true;
    if(config_.peer_cache_reads && !config_.private_cache_domains) {
      for(const auto& replica:metadata_.LocalReplicas(path))
        if(replica.gpu_id!=caller && KnownGpuId(replica.gpu_id) && replica.state=="READY" &&
           sieve_.HitKnown(replica.gpu_id,path))return true;
    }
    return false;
  }

  // Called under layout_mu_; Open pins the selected file before releasing it.
  // This is shared-host storage reuse, not CUDA peer access or remote RPC.
  std::optional<LocalReplica> ReadablePeer(const std::string& path, int caller) {
    for (const auto& replica : metadata_.LocalReplicas(path)) {
      if (replica.gpu_id != caller && KnownGpuId(replica.gpu_id) &&
          replica.state == "READY" && fs::is_regular_file(replica.physical_path))
        return replica;
    }
    return std::nullopt;
  }

  int DetectCallerGpuId(int fallback_gpu_id) {
    auto* ctx = fuse_get_context();
    if (ctx == nullptr || ctx->pid <= 0) {
      return fallback_gpu_id;
    }
    const fs::path environ_path =
        fs::path("/proc") / std::to_string(ctx->pid) / "environ";
    std::ifstream in(environ_path, std::ios::binary);
    if (!in) {
      AddBufferedMetric("affinity_caller_env_unreadable", 1);
      return fallback_gpu_id;
    }
    std::string env((std::istreambuf_iterator<char>(in)),
                    std::istreambuf_iterator<char>());
    auto read_env_value = [&env](const std::string& key) -> std::optional<std::string> {
      size_t pos = 0;
      const std::string prefix = key + "=";
      while (pos < env.size()) {
        const size_t end = env.find('\0', pos);
        const size_t item_end = end == std::string::npos ? env.size() : end;
        std::string item = env.substr(pos, item_end - pos);
        if (item.rfind(prefix, 0) == 0) {
          return item.substr(prefix.size());
        }
        if (end == std::string::npos) {
          break;
        }
        pos = end + 1;
      }
      return std::nullopt;
    };

    auto parse_gpu = [](const std::string& value) -> std::optional<int> {
      std::string digits;
      for (char ch : value) {
        if (std::isdigit(static_cast<unsigned char>(ch))) {
          digits.push_back(ch);
        } else if (!digits.empty()) {
          break;
        }
      }
      if (digits.empty()) {
        return std::nullopt;
      }
      try {
        return std::stoi(digits);
      } catch (...) {
        return std::nullopt;
      }
    };

    for (const char* key : {"TOKENFS_GPU_ID", "CUDA_VISIBLE_DEVICES"}) {
      auto value = read_env_value(key);
      if (!value) {
        continue;
      }
      auto parsed = parse_gpu(*value);
      if (parsed && KnownGpuId(*parsed)) {
        if (*parsed != fallback_gpu_id) {
          // Caller identity is read fresh; only this diagnostic counter joins
          // the existing durable telemetry fence instead of a separate fsync.
          AddBufferedMetric("affinity_cross_gpu_caller_count", 1);
        }
        return *parsed;
      }
      AddBufferedMetric("affinity_caller_env_invalid", 1);
    }
    return fallback_gpu_id;
  }

  static uint64_t FileSizeNoThrow(const fs::path& path) {
    std::error_code ec;
    auto size = fs::file_size(path, ec);
    return ec ? 0 : static_cast<uint64_t>(size);
  }

  static uint64_t UnixNowSeconds() {
    return static_cast<uint64_t>(
        std::chrono::duration_cast<std::chrono::seconds>(
            std::chrono::system_clock::now().time_since_epoch())
            .count());
  }

  static uint64_t DataValueScore(const FileMeta& meta, uint64_t affinity_x100) {
    const uint64_t size_mib = std::max<uint64_t>(1, meta.size_bytes / 1024 / 1024);
    const uint64_t heat = meta.read_count;
    const uint64_t reuse_probability_x100 = std::min<uint64_t>(100, heat * 20);
    const uint64_t share_bonus = std::max<uint64_t>(1, meta.share_count);
    const uint64_t remote_cost_factor_x100 =
        std::max<uint64_t>(1, meta.remote_access_cost * 10);
    return
        (std::max<uint64_t>(1, reuse_probability_x100) *
         std::max<uint64_t>(1, meta.recompute_cost) *
         std::max<uint64_t>(1, affinity_x100) *
         remote_cost_factor_x100 *
         share_bonus) /
        (size_mib * 100);
  }

  static int64_t ValueAwareEvictionScore(const EvictionCandidate& candidate,
                                         uint64_t now) {
    const uint64_t size_mib =
        std::max<uint64_t>(1, candidate.meta.size_bytes / 1024 / 1024);
    (void)now;
    const uint64_t age_minutes = 0;
    const uint64_t affinity_x100 =
        candidate.meta.producer_gpu == static_cast<uint64_t>(candidate.meta.gpu_id)
            ? 100
            : 40;
    const uint64_t data_value = DataValueScore(candidate.meta, affinity_x100);

    return static_cast<int64_t>(size_mib * 1000 + age_minutes) -
           static_cast<int64_t>(data_value * 1000);
  }

  static double EvictionAuditScore(const std::string& policy,
                                   const EvictionCandidate& candidate,
                                   uint64_t now) {
    // Convert each branch before combining signed value scores with unsigned counters.
    if (policy == "lru") return static_cast<double>(candidate.last_access_at);
    if (policy == "lfu") return static_cast<double>(candidate.meta.read_count);
    return static_cast<double>(ValueAwareEvictionScore(candidate, now));
  }

  uint64_t CurrentAffinityX100(const FileMeta& meta, int gpu_id) {
    if (!config_.affinity_placement) return 100;
    uint64_t affinity = metadata_.AccessAffinityX100(meta.logical_path, gpu_id);
    if (affinity == 0 && meta.producer_gpu == static_cast<uint64_t>(gpu_id)) {
      affinity = 100;
    }
    return affinity == 0 ? 40 : affinity;
  }

  uint64_t EstimatedFutureReuseReads(const FileMeta& meta,
                                     uint64_t read_count) const {
    uint64_t expected = std::max(read_count, meta.recent_read_count);
    if (!config_.trend_prediction) return std::min<uint64_t>(64, expected);
    if (meta.affinity_trend == "RISING") {
      expected += config_.affinity_trend_min_reads;
    } else if (meta.affinity_trend == "FALLING" && expected > 1) {
      expected /= 2;
    }
    return std::min<uint64_t>(64, expected);
  }

  uint64_t MigrationBenefitX100(const FileMeta& meta, uint64_t read_count,
                                int gpu_id) {
    const uint64_t size_mib =
        std::max<uint64_t>(1, (meta.size_bytes + 1024 * 1024 - 1) / 1024 / 1024);
    const uint64_t future_reads = EstimatedFutureReuseReads(meta, read_count);
    const uint64_t affinity_x100 = CurrentAffinityX100(meta, gpu_id);
    const uint64_t saved_remote_cost =
        future_reads * std::max<uint64_t>(1, meta.remote_access_cost) *
        std::max<uint64_t>(1, affinity_x100);
    const uint64_t copy_cost =
        size_mib * std::max<uint64_t>(1, config_.migration_copy_cost_per_mib) *
        100;
    return copy_cost == 0 ? 0 : saved_remote_cost * 100 / copy_cost;
  }

  static bool IsWritable(int flags) {
    const int mode = flags & O_ACCMODE;
    return mode == O_WRONLY || mode == O_RDWR || (flags & O_TRUNC) != 0;
  }

  static uint64_t DirectoryBytes(const fs::path& root) {
    uint64_t total = 0;
    std::error_code ec;
    if (!fs::exists(root, ec)) {
      return 0;
    }
    for (fs::recursive_directory_iterator it(root, fs::directory_options::skip_permission_denied, ec), end;
         it != end && !ec; it.increment(ec)) {
      if (it->is_regular_file(ec)) {
        total += static_cast<uint64_t>(it->file_size(ec));
      }
    }
    return total;
  }

  static std::optional<fs::path> NextSequentialRelPath(const fs::path& rel) {
    const std::string filename = rel.filename().string();
    const size_t dot = filename.rfind('.');
    const size_t number_end = dot == std::string::npos ? filename.size() : dot;
    size_t number_begin = number_end;
    while (number_begin > 0 &&
           std::isdigit(static_cast<unsigned char>(filename[number_begin - 1]))) {
      --number_begin;
    }
    if (number_begin == number_end) {
      return std::nullopt;
    }

    const std::string digits = filename.substr(number_begin, number_end - number_begin);
    uint64_t value = 0;
    try {
      value = std::stoull(digits);
    } catch (...) {
      return std::nullopt;
    }
    std::ostringstream next_digits;
    next_digits << std::setw(static_cast<int>(digits.size())) << std::setfill('0')
                << (value + 1);
    fs::path next =
        filename.substr(0, number_begin) + next_digits.str() + filename.substr(number_end);
    if (!rel.parent_path().empty()) {
      next = rel.parent_path() / next;
    }
    return next;
  }

  bool HasLocalCapacity(const GpuConfig& gpu, uint64_t new_file_size,
                        const fs::path* existing_file = nullptr) const {
    uint64_t used = DirectoryBytes(gpu.local_root);
    if (existing_file != nullptr) {
      uint64_t existing_size = FileSizeNoThrow(*existing_file);
      if (used >= existing_size) {
        used -= existing_size;
      }
    }
    return used + new_file_size <= gpu.local_quota_bytes;
  }

  tokenfs_policy::Options MeasuredOptions() const {
    return {static_cast<size_t>(config_.measured_window),config_.measured_aging,
            config_.measured_admission,config_.measured_cost,
            config_.measured_value_victim,config_.measured_size_aware,config_.measured_frequency_admission,config_.measured_shift_reset,static_cast<size_t>(config_.measured_shift_window),
            config_.measured_track_affinity,config_.measured_affinity_gate,config_.measured_joint_admission,static_cast<size_t>(config_.measured_affinity_window),config_.measured_affinity_recent_demand,config_.measured_affinity_handover_epoch,config_.shared_value_placement,config_.measured_causal_window,config_.measured_burst_reuse,config_.adaptive_reuse_control,config_.efficient_measured_planning,config_.burst_interval_survival,config_.reuse_scaled_exploration,config_.persistent_run_reuse,config_.persistent_reuse_immediate_decay,config_.measured_static_reuse_value,config_.novel_reuse_decay,config_.retain_read_fill && config_.capture_local_reads,config_.bounded_cost_warmup,config_.cohort_reuse_prior,config_.recent_value_floor,config_.disk_opportunity_value,config_.object_weighted_cohort_prior};
  }

  double MarginalCoverage(const FileMeta& meta, int location) {
    if (!config_.shared_value_placement) return 1.0;
    if (auto canonical=metadata_.Get(meta.logical_path); canonical && canonical->tier=="local" &&
        canonical->gpu_id!=location && fs::is_regular_file(canonical->physical_path)) return 0.0;
    for (const auto& peer:metadata_.LocalReplicas(meta.logical_path))
      if (peer.gpu_id!=location && peer.state=="READY" && fs::is_regular_file(peer.physical_path)) return 0.0;
    return 1.0;
  }

  using PlanningSnapshot=std::unordered_map<int,std::vector<tokenfs_policy::Item>>;
  PlanningSnapshot SnapshotMeasuredResidents(const std::string& protected_path) {
    auto rows=metadata_.PlanningResidents();
    std::erase_if(rows,[this](const auto& row){return !GpuById(row.location) || !fs::is_regular_file(row.physical);});
    std::unordered_map<std::string,std::unordered_set<int>> covered;
    for(const auto& row:rows)
      covered[row.key].insert(row.location);
    PlanningSnapshot snapshot;
    for(const auto& row:rows) {
      if(row.key==protected_path || IsOpenLogicalPath(row.key) || !covered[row.key].count(row.location))continue;
      const double coverage=config_.shared_value_placement && covered[row.key].size()>1?0.0:1.0;
      snapshot[row.location].push_back({row.key,row.bytes,row.recency,coverage});
    }
    AddBufferedMetric("compact_planning_snapshots",1);
    AddBufferedMetric("compact_planning_residents",rows.size());
    return snapshot;
  }

  tokenfs_policy::Decision MeasuredPlan(const GpuConfig& gpu,const FileMeta& incoming,
      const PlanningSnapshot* snapshot=nullptr,std::optional<uint64_t> known_used=std::nullopt) {
    // If even an empty cache cannot repay copying, no resident scan can make
    // the net gain positive. Keep the same execution-time capacity recheck.
    if(config_.measured_causal_window && !config_.adaptive_reuse_control) {
      const auto lower=measured_.Plan(gpu.gpu_id,{incoming.logical_path,incoming.size_bytes,0},
          {},0,gpu.local_quota_bytes,MeasuredOptions());
      if(!lower.allowed)return lower;
    }
    std::vector<tokenfs_policy::Item> residents;
    PlanningSnapshot owned;
    if(config_.compact_measured_planning) {
      if(!snapshot){owned=SnapshotMeasuredResidents(incoming.logical_path);snapshot=&owned;}
      if(auto it=snapshot->find(gpu.gpu_id);it!=snapshot->end())residents=it->second;
    } else {
      for(const auto& c:metadata_.LocalEvictionCandidates(gpu.gpu_id,incoming.logical_path)) {
        if(!IsOpenLogicalPath(c.meta.logical_path))
          residents.push_back({c.meta.logical_path,c.meta.size_bytes,c.last_access_at,MarginalCoverage(c.meta,gpu.gpu_id)});
      }
    }
    const auto plan=measured_.Plan(gpu.gpu_id,{incoming.logical_path,incoming.size_bytes,0},
        std::move(residents),known_used?*known_used:DirectoryBytes(gpu.local_root),gpu.local_quota_bytes,MeasuredOptions());
    if(plan.cohort_disk_reuse>0)AddBufferedMetric("measured_cohort_prior_plans",1);
    if(plan.uncertainty_us>0)AddBufferedMetric("measured_uncertainty_plans",1);
    if(plan.burst_remaining>0)AddBufferedMetric("measured_burst_forecast_plans",1);
    if(plan.survival_adjusted_items) {
      AddBufferedMetric("measured_survival_discounted_plans",1);
      AddBufferedMetric("measured_survival_discounted_items",plan.survival_adjusted_items);
    }
    if(plan.persistent_reuse_adjusted_items) {
      AddBufferedMetric("measured_persistent_reuse_plans",1);
      AddBufferedMetric("measured_persistent_reuse_items",plan.persistent_reuse_adjusted_items);
    }
    if(plan.affinity_adjusted_items) {
      AddBufferedMetric("measured_affinity_reweighted_plans",1);
      AddBufferedMetric("measured_affinity_reweighted_items",plan.affinity_adjusted_items);
    }
    return plan;
  }

  bool MeasuredMayAdmit(const FileMeta& incoming,int gpu_id) {
    const auto* gpu=GpuById(gpu_id);if(!gpu)return false;
    if(incoming.size_bytes>gpu->local_quota_bytes){AddBufferedMetric("measured_precheck_oversize",1);return false;}
    if(config_.measured_admission && measured_.AdmissionFrequency(gpu_id,incoming.logical_path,MeasuredOptions())<2){AddBufferedMetric("measured_precheck_no_reuse",1);return false;}
    const auto plan=MeasuredPlan(*gpu,incoming);
    AddBufferedMetric("measured_precheck_"+plan.reason,1);
    return plan.allowed;
  }

  bool EnsureLocalCapacity(const GpuConfig& gpu, uint64_t required_size,
                           const std::string& protected_logical_path,
                           const fs::path* existing_file = nullptr, uint64_t* planning_us = nullptr) {
    const auto planning_start=Clock::now();
    std::lock_guard<std::mutex> layout_lock(layout_mu_);
    if (required_size > gpu.local_quota_bytes) {
      return false;
    }
    uint64_t used = DirectoryBytes(gpu.local_root);
    if (existing_file != nullptr) {
      uint64_t existing_size = FileSizeNoThrow(*existing_file);
      if (used >= existing_size) {
        used -= existing_size;
      }
    }
    tokenfs_policy::Decision committed_plan;
    if(config_.measured_policy) {
      auto incoming=metadata_.Get(protected_logical_path);
      if(!incoming)return false;
      incoming->size_bytes=required_size;
      const auto plan=MeasuredPlan(gpu,*incoming,nullptr,config_.compact_measured_planning?std::optional<uint64_t>(used):std::nullopt);
      committed_plan=plan;
      AddBufferedMetric("measured_commit_"+plan.reason,1);
      if(!plan.allowed)return false;
      if(planning_us)*planning_us=ElapsedMicros(planning_start);
      std::ostringstream detail;
      detail << plan.reason << ";incoming=" << plan.incoming_us
             << ";displaced=" << plan.displaced_us << ";copy=" << plan.copy_us
             << ";frequency=" << plan.incoming_count << ";calibrated=" << plan.costs_calibrated
             << ";affinity_count=" << plan.affinity_incoming_count
             << ";affinity_adjusted_items=" << plan.affinity_adjusted_items
             << ";burst_remaining=" << plan.burst_remaining << ";uncertainty=" << plan.uncertainty_us
             << ";explore=" << plan.explore_headroom << ";cohort_disk_reuse=" << plan.cohort_disk_reuse;
      RecordPolicyEvent("ADMIT",protected_logical_path,gpu.gpu_id,required_size,
          detail.str(),plan.incoming_us-plan.displaced_us-plan.uncertainty_us-plan.copy_us);
    }
    if (used + required_size <= gpu.local_quota_bytes) {
      return true;
    }
    const std::string policy = config_.local_eviction_policy;
    if (policy == "sieve") {
      auto residents = metadata_.LocalEvictionCandidates(gpu.gpu_id, protected_logical_path);
      std::unordered_set<std::string> eligible;
      for (const auto& c : residents)
        if (!IsOpenLogicalPath(c.meta.logical_path) && fs::exists(c.meta.physical_path))
          eligible.insert(c.meta.logical_path);
      while (used + required_size > gpu.local_quota_bytes) {
        const auto key = sieve_.Victim(gpu.gpu_id, eligible);
        if (key.empty()) return false;
        eligible.erase(key);
        auto found = std::find_if(residents.begin(), residents.end(),
            [&](const auto& c) { return c.meta.logical_path == key; });
        if (found == residents.end()) return false;
        auto candidate = *found;
        const auto bytes = std::max(candidate.meta.size_bytes, FileSizeNoThrow(candidate.meta.physical_path));
        int rc = 0;
        if (candidate.replica_gpu >= 0) {
          std::error_code ec;
          fs::remove(candidate.meta.physical_path, ec);
          rc = ec ? -ec.value() : 0;
          if (!rc) {
            metadata_.RemoveLocalReplica(key, candidate.replica_gpu);
            AddBackgroundMetric("evict_count", 1);
            AddBackgroundMetric("cross_gpu_replica_delete_count", 1);
          }
        } else rc = EvictLocalFile(gpu, candidate.meta);
        if (rc) { AddBackgroundMetric("evict_error_count", 1); return false; }
        sieve_.Removed(gpu.gpu_id, key);
        AddBackgroundMetric("evict_policy_sieve", 1);
        RecordPolicyEvent("EVICT", key, gpu.gpu_id, bytes, "sieve", 0);
        used = used > bytes ? used - bytes : 0;
      }
      return true;
    }
    if (policy != "cost_aware" && policy != "value_aware" &&
        policy != "lru" && policy != "lfu") {
      return false;
    }

    std::vector<EvictionCandidate> candidates;
    if(config_.compact_measured_planning) {
      // This plan was just revalidated while holding layout_mu_. Fetch only the
      // selected victims, preserving that plan's multi-victim cost and order.
      for(const auto& key:committed_plan.victims) {
        auto canonical=metadata_.Get(key);if(!canonical)return false;
        EvictionCandidate c;c.meta=*canonical;
        if(canonical->tier!="local" || canonical->gpu_id!=gpu.gpu_id) {
          auto replica=metadata_.GetLocalReplica(key,gpu.gpu_id);
          if(!replica || replica->state!="READY")return false;
          c.meta.physical_path=replica->physical_path;c.meta.size_bytes=replica->size_bytes;c.replica_gpu=gpu.gpu_id;
        }
        candidates.push_back(std::move(c));
      }
      AddBufferedMetric("compact_committed_victims",candidates.size());
    } else candidates=metadata_.LocalEvictionCandidates(gpu.gpu_id, protected_logical_path);
    const uint64_t now = UnixNowSeconds();
    if(config_.compact_measured_planning) {
      AddBackgroundMetric("evict_policy_measured",1);
    } else if(config_.measured_policy) {
      std::vector<tokenfs_policy::Item> items;
      for(const auto& c:candidates)items.push_back({c.meta.logical_path,c.meta.size_bytes,c.last_access_at,MarginalCoverage(c.meta,gpu.gpu_id)});
      const auto ranked=measured_.Ranked(gpu.gpu_id,std::move(items),MeasuredOptions());
      std::unordered_map<std::string,size_t> order;
      for(size_t i=0;i<ranked.size();++i)order[ranked[i].key]=i;
      std::sort(candidates.begin(),candidates.end(),[&](const auto& a,const auto& b){return order.at(a.meta.logical_path)<order.at(b.meta.logical_path);});
      AddBackgroundMetric("evict_policy_measured",1);
    } else if (policy == "lru") {
      AddBackgroundMetric("evict_policy_lru", 1);
      std::sort(candidates.begin(), candidates.end(),
                [](const EvictionCandidate& lhs,
                   const EvictionCandidate& rhs) {
                  if (lhs.last_access_at != rhs.last_access_at) {
                    return lhs.last_access_at < rhs.last_access_at;
                  }
                  if (lhs.meta.read_count != rhs.meta.read_count) {
                    return lhs.meta.read_count < rhs.meta.read_count;
                  }
                  return lhs.meta.size_bytes > rhs.meta.size_bytes;
                });
    } else if (policy == "lfu") {
      AddBackgroundMetric("evict_policy_lfu", 1);
      std::sort(candidates.begin(), candidates.end(),
                [](const EvictionCandidate& lhs,
                   const EvictionCandidate& rhs) {
                  if (lhs.meta.read_count != rhs.meta.read_count) {
                    return lhs.meta.read_count < rhs.meta.read_count;
                  }
                  if (lhs.last_access_at != rhs.last_access_at) {
                    return lhs.last_access_at < rhs.last_access_at;
                  }
                  return lhs.meta.size_bytes > rhs.meta.size_bytes;
                });
    } else {
      AddBackgroundMetric("evict_policy_value_aware", 1);
      std::sort(candidates.begin(), candidates.end(),
                [now](const EvictionCandidate& lhs,
                      const EvictionCandidate& rhs) {
                  const auto lhs_score = ValueAwareEvictionScore(lhs, now);
                  const auto rhs_score = ValueAwareEvictionScore(rhs, now);
                  if (lhs_score != rhs_score) {
                    return lhs_score > rhs_score;
                  }
                  return lhs.meta.size_bytes > rhs.meta.size_bytes;
                });
    }

    for (auto candidate : candidates) {
      if (IsOpenLogicalPath(candidate.meta.logical_path)) {
        AddBackgroundMetric("evict_skip_open", 1);
        continue;
      }

      const uint64_t candidate_size =
          std::max(candidate.meta.size_bytes, FileSizeNoThrow(candidate.meta.physical_path));
      if (candidate_size == 0 || !fs::exists(candidate.meta.physical_path)) {
        continue;
      }
      int rc = 0;
      if (candidate.replica_gpu >= 0) {
        std::error_code ec;
        fs::remove(candidate.meta.physical_path, ec);
        rc = ec ? -ec.value() : 0;
        if (!rc) {
          metadata_.RemoveLocalReplica(candidate.meta.logical_path, candidate.replica_gpu);
          AddBackgroundMetric("evict_count", 1);
          AddBackgroundMetric("cross_gpu_replica_delete_count", 1);
        }
      } else rc = EvictLocalFile(gpu, candidate.meta);
      if (rc != 0) {
        AddBackgroundMetric("evict_error_count", 1);
        continue;
      }
      RecordPolicyEvent("EVICT", candidate.meta.logical_path, gpu.gpu_id, candidate_size,
          config_.measured_policy?"measured":policy,
          config_.measured_policy?static_cast<double>(measured_.Frequency(gpu.gpu_id,candidate.meta.logical_path)):EvictionAuditScore(policy,candidate,now));
      used = used > candidate_size ? used - candidate_size : 0;
      if (used + required_size <= gpu.local_quota_bytes) {
        return true;
      }
    }
    return used + required_size <= gpu.local_quota_bytes;
  }

  FileMeta SelectNewFile(const GpuConfig& gpu, const fs::path& rel,
                         const std::string& logical_path) const {
    const uint64_t used = DirectoryBytes(gpu.local_root);
    FileMeta meta;
    meta.logical_path = logical_path;
    meta.gpu_id = gpu.gpu_id;
    meta.recompute_cost = config_.default_recompute_cost;
    meta.remote_access_cost = config_.default_remote_access_cost;
    meta.producer_gpu = static_cast<uint64_t>(gpu.gpu_id);
    meta.share_count = 1;
    meta.state = "CREATING";
    if (used < gpu.local_quota_bytes) {
      meta.tier = "local";
      meta.backend_id = "local";
      meta.physical_path = gpu.local_root / rel;
      meta.primary_tier = "local";
      meta.has_remote_copy = false;
      meta.local_cache_owner_gpu = gpu.gpu_id;
      meta.replica_state = "LOCAL_ONLY";
      return meta;
    }
    meta.tier = "remote";
    meta.backend_id = gpu.remote_backend;
    meta.physical_path = RemotePath(gpu, rel);
    meta.primary_tier = "remote";
    meta.has_remote_copy = true;
    meta.local_cache_owner_gpu = -1;
    meta.replica_state = "REMOTE_ONLY";
    return meta;
  }

  bool ShouldPromoteOnRead(FileMeta meta, uint64_t read_count, int gpu_id) {
    if (meta.state != "COMMITTED" || meta.tier != "remote") {
      return false;
    }
    meta.read_count = read_count;
    if(config_.measured_policy) return config_.promote_on_read && gpu_id==meta.gpu_id && MeasuredMayAdmit(meta,gpu_id);
    if (!config_.promote_on_read &&
        !(config_.placement_policy == "value_aware" &&
          config_.adaptive_migration)) {
      return false;
    }
    if (config_.read_through_cache) {
      if(config_.private_cache_domains && config_.read_through_min_reads>1)
        read_count=measured_.Frequency(gpu_id,meta.logical_path);
      if (gpu_id != meta.gpu_id) {
        metadata_.AddMetric("read_through_skip_cross_gpu", 1);
        return false;
      }
      if (read_count < config_.read_through_min_reads) {
        metadata_.AddMetric("read_through_skip_low_reuse", 1);
        return false;
      }
      metadata_.AddMetric("read_through_promote_request", 1);
      return true;
    }
    if (gpu_id != meta.gpu_id) {
      metadata_.AddMetric("affinity_cross_gpu_promote_skip", 1);
      return false;
    }
    if (config_.affinity_placement && (meta.affinity_state == "REMOTE_SHARED_HOT" ||
        meta.affinity_state == "CROSS_GPU_SHARED")) {
      metadata_.AddMetric("affinity_shared_remote_preferred_skip", 1);
      return false;
    }
    if (config_.affinity_placement && meta.affinity_state == "REMOTE_COLD") {
      metadata_.AddMetric("affinity_remote_cold_promote_skip", 1);
      return false;
    }
    if (config_.affinity_placement && meta.dominant_gpu_id >= 0 && meta.dominant_gpu_id != gpu_id &&
        meta.dominant_gpu_read_share_x100 >=
            config_.affinity_dominant_threshold_x100) {
      metadata_.AddMetric("affinity_non_dominant_promote_skip", 1);
      return false;
    }
    if (!config_.gain_admission) return true;
    const uint64_t min_reads =
        std::max(config_.promote_read_threshold,
                 config_.migration_min_reuse_reads);
    if (read_count < min_reads) {
      metadata_.AddMetric("promote_skip_low_reuse", 1);
      return false;
    }
    const uint64_t value =
        DataValueScore(meta, CurrentAffinityX100(meta, gpu_id));
    if (value < config_.value_promote_threshold) {
      metadata_.AddMetric("promote_skip_low_value", 1);
      return false;
    }
    const uint64_t benefit_x100 = MigrationBenefitX100(meta, read_count, gpu_id);
    if (benefit_x100 < config_.migration_min_benefit_x100) {
      metadata_.AddMetric("promote_skip_low_benefit", 1);
      return false;
    }
    metadata_.AddMetric("promote_benefit_x100_total", benefit_x100);
    metadata_.SetMetricMax("promote_benefit_x100_max", benefit_x100);
    return true;
  }

  void PlaceShared(const std::string& path, int caller,std::shared_ptr<ReadFillPool::Buffer> fill={}) {
    const auto plan_start=Clock::now();
    RequestTrace::Span planning(trace_,"shared_plan");
    if(planning.Enabled()){planning.e.path=path;planning.e.caller=caller;planning.e.tier="rejected";}
    auto parsed=ParseGpuPath(path);if(!parsed)return;
    const auto [owner,rel]=*parsed;
    std::optional<GpuConfig> destination;
    FileMeta incoming;
    {
      std::unique_lock<std::mutex> lock(layout_mu_);
      auto current=metadata_.Get(path);
      if(!current || current->state!="COMMITTED" || !current->has_remote_copy)return;
      if(current->tier=="local" || ReadablePeer(path,-1)) {
        AddBufferedMetric("shared_placement_already_covered",1);return;
      }
      incoming=*current;
      if(config_.shared_pool_cache) {
        if(incoming.read_count<config_.read_through_min_reads)return;
        destination=*owner;
      } else {
        double best=0;tokenfs_policy::Decision chosen;
        // Prefer the caller for an equal net gain; compare all permitted locations.
        auto locations=config_.gpus;
        if(config_.shared_caller_only)
          std::erase_if(locations,[caller](const auto& gpu){return gpu.gpu_id!=caller;});
        std::stable_sort(locations.begin(),locations.end(),[caller](const auto& a,const auto& b){return (a.gpu_id==caller)>(b.gpu_id==caller);});
        std::unordered_map<int,uint64_t> usage;
        if(config_.adaptive_reuse_control) {
          for(const auto& gpu:locations)usage[gpu.gpu_id]=DirectoryBytes(gpu.local_root);
          if(config_.measured_causal_window) {
            const auto options=MeasuredOptions();
            std::erase_if(locations,[&](const auto& gpu) {
              const bool possible=measured_.PotentiallyProfitable(gpu.gpu_id,
                  {incoming.logical_path,incoming.size_bytes,0},usage.at(gpu.gpu_id),
                  gpu.local_quota_bytes,options);
              if(!possible)AddBufferedMetric("shared_optimistic_rejects",1);
              return !possible;
            });
            if(locations.empty()) {
              AddBufferedMetric("shared_snapshot_avoided",1);
              AddBufferedMetric("shared_placement_no_gain",1);return;
            }
          }
        }
        std::optional<PlanningSnapshot> snapshot;
        if(config_.compact_measured_planning)snapshot=SnapshotMeasuredResidents(path);
        if(config_.adaptive_reuse_control) {
          // Advisory rejection and snapshot only. Final admission still
          // rechecks live capacity, pins, demand and costs before any eviction.
          lock.unlock();
        }
        for(const auto& gpu:locations) {
          const auto plan=MeasuredPlan(gpu,incoming,snapshot?&*snapshot:nullptr,config_.adaptive_reuse_control?std::optional<uint64_t>(usage.at(gpu.gpu_id)):std::nullopt);
          AddBufferedMetric("shared_placement_plans",1);
          const double net=plan.incoming_us-plan.copy_us-(config_.measured_joint_admission?plan.displaced_us+plan.uncertainty_us:0);
          if(plan.allowed && plan.explore_headroom) {best=net;destination=gpu;chosen=plan;break;}
          if(plan.allowed && net>best) {best=net;destination=gpu;chosen=plan;}
          // Zero charged displacement is the exact upper bound: incoming value
          // and copy cost are location-independent on this shared-host backend.
          if(config_.measured_causal_window && plan.allowed &&
              (!config_.measured_joint_admission || plan.displaced_us+plan.uncertainty_us==0))break;
        }
        if(!destination){AddBufferedMetric("shared_placement_no_gain",1);return;}
        std::ostringstream detail;detail<<"caller="<<caller<<";incoming="<<chosen.incoming_us
          <<";victim_loss="<<chosen.displaced_us<<";copy="<<chosen.copy_us<<";burst_remaining="<<chosen.burst_remaining<<";uncertainty="<<chosen.uncertainty_us<<";explore="<<chosen.explore_headroom<<";exploration_reads="<<chosen.exploration_reads<<";cohort_disk_reuse="<<chosen.cohort_disk_reuse;
        RecordPolicyEvent("SHARED_PLACE",path,destination->gpu_id,incoming.size_bytes,detail.str(),best);
        AddBufferedMetric("shared_placement_selected",1);
        if(chosen.explore_headroom)AddBufferedMetric("shared_free_exploration_selected",1);
        if(chosen.burst_remaining>0 && chosen.affinity_incoming_count<2)AddBufferedMetric("shared_burst_first_read_selected",1);
        if(destination->gpu_id!=caller)AddBufferedMetric("shared_placement_relocated",1);
      }
    }
    if(planning.Enabled()){planning.e.location=destination->gpu_id;planning.e.tier="selected";}
    planning.Finish();
    if(config_.profile_control_path)RecordLatency("shared_plan","background",ElapsedMicros(plan_start));
    // Existing copy/commit path rechecks quota and benefit using current evidence.
    if(destination->gpu_id==owner->gpu_id)PromoteToLocal(*destination,rel,incoming,"promote",true,fill);
    else CreateCrossGpuReplica(*destination,*owner,rel,incoming,fill);
  }

  bool SubmissionPrecheckSupported() const {
    return config_.precheck_shared_submission && config_.readonly_canonical &&
      config_.measured_policy && config_.shared_value_placement && !config_.shared_pool_cache &&
      config_.adaptive_reuse_control && config_.measured_causal_window && !config_.measured_affinity_gate;
  }

  static bool PathWithin(const fs::path& path,const fs::path& root) {
    auto p=path.begin();
    for(auto r=root.begin();r!=root.end();++r,++p)if(p==path.end() || *p!=*r)return false;
    return p!=path.end(); // a resident is a descendant file, never the root itself.
  }

  void InitializeSubmissionPrecheck() {
    if(!SubmissionPrecheckSupported())return;
    // A READY byte count is a lower bound only for this fresh, exclusively
    // managed immutable cache lifecycle. Do not trust persisted READY rows or
    // pre-existing paths, and never claim protection against external rm or
    // truncate. Internal measured-cache removals are serialized by layout_mu_.
    try {
      std::unordered_map<int,fs::path> roots;std::vector<fs::path> resolved;
      for(const auto& gpu:config_.gpus) {
        if(gpu.gpu_id<0 || roots.count(gpu.gpu_id) || !fs::is_empty(gpu.local_root))return;
        auto canonical=fs::canonical(gpu.local_root);
        for(const auto& other:resolved)
          if(canonical==other || PathWithin(canonical,other) || PathWithin(other,canonical))return;
        resolved.push_back(canonical);roots.emplace(gpu.gpu_id,fs::absolute(gpu.local_root).lexically_normal());
      }
      if(roots.empty() || !metadata_.TryEmptyResidentState())return;
      submission_precheck_roots_=std::move(roots);submission_precheck_ready_=true;
      AddBufferedMetric("submission_precheck_enabled",1);
    } catch(const std::exception&) {return;}
    // Build only after fresh-lifecycle eligibility succeeds. Unsupported
    // SIEVE and disabled controls create no indexes in fresh databases. Existing
    // indexes are never dropped. Keep this outside the eligibility catch so an
    // unrecoverable SQLite transaction aborts Init rather than hiding corruption.
    if(config_.indexed_shared_precheck)
      AddBufferedMetric(metadata_.CreateSharedPrecheckIndexes()?"submission_precheck_index_enabled":"submission_precheck_index_fallback",1);
  }

  bool PrecheckSharedSubmission(const FileMeta& meta,int caller,const std::shared_ptr<ReadFillPool::Buffer>& fill) {
    if(!submission_precheck_ready_ || !SubmissionPrecheckSupported())return false;
    // Only an immediately completed, source-validated capture supplies a
    // trustworthy size. Open-time and partial-release submissions fall back.
    if(!fill || !fill->Dispatched() || !meta.size_bytes || fill->Data().size()!=meta.size_bytes)return false;
    AddBufferedMetric("submission_precheck_attempts",1);
    struct Timer {
      TokenFS& owner;std::chrono::steady_clock::time_point start=std::chrono::steady_clock::now();
      ~Timer(){const auto us=ElapsedMicros(start);owner.AddBufferedMetric("submission_precheck_us",us);owner.SetBufferedMetricMax("submission_precheck_us_max",us);}
    } timer{*this};
    std::unique_lock<std::mutex> layout_lock(layout_mu_,std::try_to_lock);
    if(!layout_lock.owns_lock()){AddBufferedMetric("submission_precheck_layout_busy",1);return false;}
    std::vector<MetadataStore::ReadyResidentBytes> rows;
    if(!metadata_.TryReadyResidentBytes(rows)){AddBufferedMetric("submission_precheck_metadata_fallback",1);return false;}
    std::unordered_map<int,uint64_t> used;
    std::unordered_map<std::string,std::pair<int,uint64_t>> physicals;
    for(const auto& row:rows) {
      auto root=submission_precheck_roots_.find(row.location);
      const auto path=row.physical.lexically_normal();
      if(root==submission_precheck_roots_.end() || !row.physical.is_absolute() || !PathWithin(path,root->second)) {
        AddBufferedMetric("submission_precheck_invalid_metadata",1);return false;
      }
      auto [entry,inserted]=physicals.emplace(path.string(),std::pair{row.location,row.bytes});
      if(!inserted) {
        if(entry->second!=std::pair{row.location,row.bytes}) {
          AddBufferedMetric("submission_precheck_invalid_metadata",1);return false;
        }
        continue; // canonical/replica aliases must not inflate occupied bytes.
      }
      if(row.bytes>std::numeric_limits<uint64_t>::max()-used[row.location]) {
        AddBufferedMetric("submission_precheck_invalid_metadata",1);return false;
      }
      used[row.location]+=row.bytes;
    }
    const GpuConfig* representative=nullptr;size_t allowed=0;
    for(const auto& gpu:config_.gpus) {
      if(config_.shared_caller_only && gpu.gpu_id!=caller)continue;
      ++allowed;
      const uint64_t occupied=used[gpu.gpu_id];
      if(occupied<gpu.local_quota_bytes && meta.size_bytes<=gpu.local_quota_bytes-occupied) {
        AddBufferedMetric("submission_precheck_headroom",1);return false;
      }
      if(meta.size_bytes<=gpu.local_quota_bytes)representative=&gpu;
    }
    if(!allowed)return false;
    // In this restricted shared+causal, affinity-gate-free mode, incoming
    // value and noise are location independent. All allowed domains lack
    // headroom; one original optimistic call at used=quota is their common
    // upper bound, under one policy lock. Oversize domains cannot admit.
    // Keep each arm's original Options, including NoHotspot and NoJoint.
    if(representative && measured_.PotentiallyProfitable(representative->gpu_id,
       {meta.logical_path,meta.size_bytes,0},representative->local_quota_bytes,
       representative->local_quota_bytes,MeasuredOptions())) {
      AddBufferedMetric("submission_precheck_possible",1);return false;
    }
    AddBufferedMetric("submission_precheck_rejected",1);
    return true;
  }

  void ScheduleSharedPlacement(const FileMeta& meta, int caller,std::shared_ptr<ReadFillPool::Buffer> fill={}) {
    if(meta.state!="COMMITTED" || !meta.has_remote_copy)return;
    if(config_.shared_value_placement && !measured_.HasReuseEvidence(caller,meta.logical_path,MeasuredOptions()))return;
    if(config_.shared_pool_cache && meta.read_count<config_.read_through_min_reads)return;
    // This is a decision at submission time, not equivalence to a queued task
    // consulting later observations/costs. No negative-key result is cached.
    if(PrecheckSharedSubmission(meta,caller,fill))return;
    const auto path=meta.logical_path;
    {
      std::lock_guard<std::mutex> lock(shared_placement_mu_);
      if(!shared_placement_inflight_.insert(path).second) {
        AddBufferedMetric("shared_placement_coalesced",1);return;
      }
    }
    auto release=[this,path] {std::lock_guard<std::mutex> lock(shared_placement_mu_);shared_placement_inflight_.erase(path);};
    if(!SubmitBackground([this,path,caller,release,fill] {
      try {PlaceShared(path,caller,fill);} catch(...) {release();throw;}
      release();
    }))release();
  }

  bool ShouldCreateCrossGpuReplica(const FileMeta& meta, int caller_gpu_id) {
    if (!config_.cross_gpu_local_cache || caller_gpu_id == meta.gpu_id ||
        meta.state != "COMMITTED" || !meta.has_remote_copy) return false;
    if(config_.measured_policy) {
      // An already readable owner-local copy saves the same remote read in this
      // shared-host architecture; do not consume another domain just to duplicate it.
      if(meta.tier=="local" && !config_.private_cache_domains)return false;
      return MeasuredMayAdmit(meta,caller_gpu_id);
    }
    if (config_.read_through_cache) return
        (config_.private_cache_domains && config_.read_through_min_reads>1 ? measured_.Frequency(caller_gpu_id,meta.logical_path) : meta.read_count) >= config_.read_through_min_reads;
    if (config_.affinity_placement) {
      if (meta.target_local_replica_count == 0) return false;
      if (meta.affinity_state != "REMOTE_SHARED_HOT" && meta.affinity_state != "AFFINITY_SHIFTING" &&
          meta.affinity_state != "GPU_LOCAL_HOT" && meta.affinity_state != "GPU_LOCAL_WARM") return false;
      if (meta.affinity_state != "REMOTE_SHARED_HOT" && meta.recent_dominant_gpu_id != caller_gpu_id) return false;
      if (meta.last_promoted_at && UnixNowSeconds() < meta.last_promoted_at + config_.affinity_replica_cooldown_sec) return false;
    }
    if (!config_.gain_admission) return true;
    if (meta.read_count < config_.migration_min_reuse_reads) return false;
    if (DataValueScore(meta, CurrentAffinityX100(meta, caller_gpu_id)) < config_.value_promote_threshold) return false;
    return MigrationBenefitX100(meta, meta.read_count, caller_gpu_id) >= config_.migration_min_benefit_x100;
  }

  void MaybeManageCrossGpuReplica(const FileMeta& meta, int caller_gpu_id) {
    ReconcileCrossGpuReplicas(meta);
    auto parsed = ParseGpuPath(meta.logical_path);
    if (!parsed) {
      return;
    }
    const auto [owner_gpu, rel] = *parsed;
    const auto* caller_gpu = GpuById(caller_gpu_id);
    if (caller_gpu == nullptr || caller_gpu->gpu_id == owner_gpu->gpu_id) {
      return;
    }
    if (auto existing =
            metadata_.GetLocalReplica(meta.logical_path, caller_gpu_id)) {
      if (existing->state == "READY" && fs::exists(existing->physical_path)) {
        metadata_.TouchLocalReplica(meta.logical_path, caller_gpu_id);
        metadata_.AddMetric("cross_gpu_replica_reuse_count", 1);
        return;
      }
      metadata_.RemoveLocalReplica(meta.logical_path, caller_gpu_id);
    }
    if (!ShouldCreateCrossGpuReplica(meta, caller_gpu_id)) {
      return;
    }
    if (!config_.measured_policy && !config_.read_through_cache && config_.affinity_placement &&
        metadata_.LocalReplicas(meta.logical_path).size() >= meta.target_local_replica_count) {
      ReconcileCrossGpuReplicas(meta);
      if (metadata_.LocalReplicas(meta.logical_path).size() >=
          meta.target_local_replica_count) {
        metadata_.AddMetric("cross_gpu_replica_skip_cap", 1);
        return;
      }
    }
    if (config_.async_cross_gpu_replica) {
      ScheduleCrossGpuReplica(*caller_gpu, *owner_gpu, rel, meta);
      return;
    }
    CreateCrossGpuReplica(*caller_gpu, *owner_gpu, rel, meta);
  }

  void ScheduleCrossGpuReplica(const GpuConfig& caller_gpu,
                               const GpuConfig& owner_gpu, const fs::path& rel,
                               const FileMeta& meta) {
    const std::string key =
        meta.logical_path + "|" + std::to_string(caller_gpu.gpu_id);
    {
      std::lock_guard<std::mutex> lock(cross_gpu_replica_mu_);
      if (cross_gpu_replica_inflight_.count(key) != 0) {
        metadata_.AddMetric("cross_gpu_replica_skip_inflight", 1);
        return;
      }
      cross_gpu_replica_inflight_.insert(key);
    }
    metadata_.AddMetric("cross_gpu_replica_request_count", 1);
    if (!SubmitBackground([this, caller_gpu, owner_gpu, rel, meta, key]() {
      CreateCrossGpuReplica(caller_gpu, owner_gpu, rel, meta);
      std::lock_guard<std::mutex> lock(cross_gpu_replica_mu_);
      cross_gpu_replica_inflight_.erase(key);
    })) {
      std::lock_guard<std::mutex> lock(cross_gpu_replica_mu_);
      cross_gpu_replica_inflight_.erase(key);
    }
  }

  bool CopyOrFill(const fs::path& source,const fs::path& temporary,uint64_t size,
                  const std::shared_ptr<ReadFillPool::Buffer>& fill,std::error_code& ec) {
    const bool reuse=config_.foreground_read_fill && fill && fill->Matches(source.string(),size);
    if(!reuse) {
      if(fill)AddBufferedMetric("read_fill_source_changed_fallback",1);
      fs::copy_file(source,temporary,fs::copy_options::overwrite_existing,ec);
      return false;
    }
    int fd=open(temporary.c_str(),O_WRONLY|O_CREAT|O_TRUNC,0600);
    if(fd<0){ec=std::error_code(errno,std::generic_category());return true;}
    size_t offset=0;const auto& bytes=fill->Data();
    while(offset<bytes.size()) {
      const auto n=write(fd,bytes.data()+offset,bytes.size()-offset);
      if(n<0 && errno==EINTR)continue;
      if(n<=0){ec=std::error_code(n<0?errno:EIO,std::generic_category());break;}
      offset+=static_cast<size_t>(n);
    }
    if(close(fd)!=0 && !ec)ec=std::error_code(errno,std::generic_category());
    return true;
  }

  void RecordReadFillCommit(uint64_t size,const std::shared_ptr<ReadFillPool::Buffer>& fill) {
    AddBufferedMetric("read_fill_copy_count",1);
    AddBufferedMetric("read_fill_copy_bytes",size);
    AddBufferedMetric("read_fill_committed_capture_us",fill->CaptureUs());
  }

  void RecordCopyCost(uint64_t size,const CopyCostSample& sample) {
    if(!config_.measured_policy)return;
    measured_.CopySample(size,sample.Charge(config_.incremental_copy_cost),config_.bounded_cost_warmup);
    AddBufferedMetric("copy_cost_samples",1);
    AddBufferedMetric("copy_cost_full_us",sample.Full());
    AddBufferedMetric("copy_cost_planning_us",sample.planning_us);
    AddBufferedMetric("copy_cost_capture_us",sample.capture_us);
    AddBufferedMetric("copy_cost_remaining_us",sample.Remaining());
    AddBufferedMetric("copy_cost_charged_us",sample.Charge(config_.incremental_copy_cost));
  }

  void AccountRequestReadCost(const Handle& handle,const std::optional<RequestReadCost::Sample>& sample) {
    if(!sample)return;
    const auto& tier=handle.tier;
    AddBufferedMetric(std::string("request_cost_")+tier+"_samples",1);
    AddBufferedMetric(std::string("request_cost_")+tier+"_bytes",sample->bytes);
    AddBufferedMetric(std::string("request_cost_")+tier+"_us",sample->micros);
    if(handle.tier!="inflight" && (config_.measured_policy || config_.measured_track_affinity))
      measured_.ReadSample(handle.tier=="local",sample->bytes,sample->micros,config_.bounded_cost_warmup);
  }

  void CreateCrossGpuReplica(const GpuConfig& caller_gpu,
                             const GpuConfig& owner_gpu, const fs::path& rel,
                             FileMeta meta,std::shared_ptr<ReadFillPool::Buffer> fill={}) {
    fs::path source = RemotePath(owner_gpu, rel);
    if (!fs::exists(source)) {
      source = meta.physical_path;
    }
    if (!fs::exists(source)) {
      AddBackgroundMetric("cross_gpu_replica_skip_missing_source", 1);
      return;
    }
    RequestTrace::Span attempt(trace_,"copy_attempt");
    if(attempt.Enabled()){attempt.e.path=meta.logical_path;attempt.e.location=caller_gpu.gpu_id;}
    std::lock_guard<std::mutex> copy_lock(copy_mu_);
    if(attempt.Enabled())attempt.e.wait_ns=RequestTrace::Now()-attempt.e.start_ns;
    const auto copy_start=Clock::now();
    uint64_t planning_us=0;
    const uint64_t size = FileSizeNoThrow(source);
    fs::path local = CrossGpuReplicaPath(caller_gpu, owner_gpu, rel);
    if (!config_.speculative_copy_may_evict &&
        !HasLocalCapacity(caller_gpu, size,
                          fs::exists(local) ? &local : nullptr)) {
      AddBackgroundMetric("cross_gpu_replica_skip_no_headroom", 1);
      return;
    }
    if (!EnsureLocalCapacity(caller_gpu, size, meta.logical_path,
                             fs::exists(local) ? &local : nullptr,&planning_us)) {
      AddBackgroundMetric("cross_gpu_replica_skip_no_space", 1);
      return;
    }
    ApplyBackgroundQos(caller_gpu.gpu_id, size, "cross_gpu_replica");
    RequestTrace::Span diagnostic(trace_,"copy_pipeline");
    if(diagnostic.Enabled()){diagnostic.e.path=meta.logical_path;diagnostic.e.caller=caller_gpu.gpu_id;diagnostic.e.bytes=size;}
    fs::create_directories(local.parent_path());
    fs::path tmp = local;
    tmp += config_.temp_suffix + ".xgpu";
    std::error_code ec;
    fs::remove(tmp, ec);
    ec.clear();
    const auto copy_io_start=diagnostic.Enabled()?RequestTrace::Now():0;
    const bool reused=CopyOrFill(source,tmp,size,fill,ec);
    if(diagnostic.Enabled())diagnostic.e.copy_ns=RequestTrace::Now()-copy_io_start;
    if (ec) {
      fs::remove(tmp, ec);
      AddBackgroundMetric("cross_gpu_replica_error_count", 1);
      return;
    }
    if (config_.durable_local_cache) {
      int fd = open(tmp.c_str(), O_RDONLY);
      if (fd >= 0) {
        fsync(fd);
        close(fd);
      }
    } else {
      AddBackgroundMetric("local_cache_fsync_skipped", 1);
      AddBackgroundMetric("local_cache_fsync_skipped_bytes", size);
    }
    if (config_.checksum != "none") {
      const auto verify_start=diagnostic.Enabled()?RequestTrace::Now():0;
      bool verified=false;
      if(reused) {
        verified=fill->VerifyFileBytes(tmp.string()) && fill->Matches(source.string(),size);
        if(verified)AddBufferedMetric("read_fill_exact_verify_count",1);
      } else {
        const auto source_hash=ChecksumFile(source),copy_hash=ChecksumFile(tmp);
        verified=source_hash && copy_hash && *source_hash==*copy_hash;
      }
      if(diagnostic.Enabled())diagnostic.e.verify_ns=RequestTrace::Now()-verify_start;
      if (!verified) {
        fs::remove(tmp, ec);
        AddBackgroundMetric("copy_checksum_error_count", 1);
        return;
      }
    }
    fs::rename(tmp, local, ec);
    if (ec) {
      fs::remove(tmp, ec);
      AddBackgroundMetric("cross_gpu_replica_error_count", 1);
      return;
    }
    if (auto latest = metadata_.Get(meta.logical_path)) meta = *latest;
    const uint64_t now = UnixNowSeconds();
    LocalReplica replica;
    replica.logical_path = meta.logical_path;
    replica.gpu_id = caller_gpu.gpu_id;
    replica.physical_path = local;
    replica.size_bytes = size;
    replica.cache_generation = meta.cache_generation + 1;
    replica.created_at = now;
    replica.last_access_at = now;
    replica.state = "READY";
    if(config_.local_eviction_policy=="sieve")sieve_.Ready(caller_gpu.gpu_id,meta.logical_path);
    metadata_.UpsertLocalReplica(replica,true);
    RecordPolicyEvent("REPLICATE_READY", meta.logical_path, caller_gpu.gpu_id, size, "cross_gpu");
    if(reused)RecordReadFillCommit(size,fill);
    RecordCopyCost(size,{ElapsedMicros(copy_start),planning_us,reused?fill->CaptureUs():0});
    AddBackgroundMetric("cross_gpu_replica_create_count", 1);
    AddBackgroundMetric("cross_gpu_replica_create_bytes", size);
  }

  void ReconcileCrossGpuReplicas(const FileMeta& meta) {
    if (config_.measured_policy || config_.read_through_cache || !config_.affinity_placement) return;
    auto replicas = metadata_.LocalReplicas(meta.logical_path);
    if (replicas.empty()) {
      return;
    }
    const uint64_t now = UnixNowSeconds();
    const uint64_t target = meta.target_local_replica_count;
    if (replicas.size() <= target) {
      return;
    }
    std::sort(replicas.begin(), replicas.end(),
              [](const LocalReplica& lhs, const LocalReplica& rhs) {
                if (lhs.last_access_at != rhs.last_access_at) {
                  return lhs.last_access_at < rhs.last_access_at;
                }
                return lhs.created_at < rhs.created_at;
              });
    while (replicas.size() > target) {
      const auto replica = replicas.front();
      if (now < replica.created_at + config_.affinity_replica_min_residency_sec) {
        metadata_.AddMetric("cross_gpu_replica_keep_min_residency", 1);
        break;
      }
      std::error_code ec;
      fs::remove(replica.physical_path, ec);
      metadata_.RemoveLocalReplica(replica.logical_path, replica.gpu_id);
      metadata_.AddMetric("cross_gpu_replica_delete_count", 1);
      metadata_.AddMetric("cross_gpu_replica_delete_bytes", replica.size_bytes);
      replicas.erase(replicas.begin());
    }
  }

  int PromoteToLocal(const GpuConfig& gpu, const fs::path& rel, FileMeta& meta,
                     const std::string& metric_prefix,
                     bool allow_eviction = true,std::shared_ptr<ReadFillPool::Buffer> fill={}) {
    RequestTrace::Span attempt(trace_,"copy_attempt");
    if(attempt.Enabled()){attempt.e.path=meta.logical_path;attempt.e.location=gpu.gpu_id;}
    std::lock_guard<std::mutex> copy_lock(copy_mu_);
    if(attempt.Enabled())attempt.e.wait_ns=RequestTrace::Now()-attempt.e.start_ns;
    const auto copy_start=Clock::now();
    uint64_t planning_us=0;
    if (auto current = metadata_.Get(meta.logical_path); current && current->tier == "local") return 0;
    const uint64_t size = FileSizeNoThrow(meta.physical_path);
    fs::path local = gpu.local_root / rel;
    const fs::path source = meta.physical_path;
    if (!allow_eviction &&
        !HasLocalCapacity(gpu, size, fs::exists(local) ? &local : nullptr)) {
      AddBackgroundMetric(metric_prefix + "_skip_no_headroom", 1);
      return 0;
    }
    if (!EnsureLocalCapacity(gpu, size, meta.logical_path,
                             fs::exists(local) ? &local : nullptr,&planning_us)) {
      AddBackgroundMetric(metric_prefix + "_skip_no_space", 1);
      return 0;
    }
    ApplyBackgroundQos(gpu.gpu_id, size, metric_prefix);

    RequestTrace::Span diagnostic(trace_,"copy_pipeline");
    if(diagnostic.Enabled()){diagnostic.e.path=meta.logical_path;diagnostic.e.caller=gpu.gpu_id;diagnostic.e.bytes=size;}
    fs::create_directories(local.parent_path());
    fs::path tmp = local;
    tmp += config_.temp_suffix + ".promote";

    std::error_code ec;
    fs::remove(tmp, ec);
    ec.clear();

    AddBackgroundMetric("migration_to_local_begin", 1);
    if (config_.durable_local_cache) {
      FileMeta migrating = meta;
      migrating.state = "COPYING_TO_LOCAL";
      metadata_.Upsert(migrating);
    }

    const auto copy_io_start=diagnostic.Enabled()?RequestTrace::Now():0;
    const bool reused=CopyOrFill(source,tmp,size,fill,ec);
    if(diagnostic.Enabled())diagnostic.e.copy_ns=RequestTrace::Now()-copy_io_start;
    if (ec) {
      const int error=ec.value();
      fs::remove(tmp, ec);
      return -error;
    }

    if (config_.durable_local_cache) {
      int fd = open(tmp.c_str(), O_RDONLY);
      if (fd < 0) {
        fs::remove(tmp, ec);
        return -errno;
      }
      if (fsync(fd) != 0) {
        int err = errno;
        close(fd);
        fs::remove(tmp, ec);
        return -err;
      }
      close(fd);
    } else {
      AddBackgroundMetric("local_cache_fsync_skipped", 1);
      AddBackgroundMetric("local_cache_fsync_skipped_bytes", size);
    }

    if (config_.checksum != "none") {
      const auto verify_start=diagnostic.Enabled()?RequestTrace::Now():0;
      bool verified=false;
      if(reused) {
        verified=fill->VerifyFileBytes(tmp.string()) && fill->Matches(source.string(),size);
        if(verified)AddBufferedMetric("read_fill_exact_verify_count",1);
      } else {
        const auto source_hash=ChecksumFile(source),copy_hash=ChecksumFile(tmp);
        verified=source_hash && copy_hash && *source_hash==*copy_hash;
      }
      if(diagnostic.Enabled())diagnostic.e.verify_ns=RequestTrace::Now()-verify_start;
      if (!verified) {
        fs::remove(tmp, ec);
        AddBackgroundMetric("copy_checksum_error_count", 1);
        return -EIO;
      }
    }
    fs::rename(tmp, local, ec);
    if (ec) {
      const int error=ec.value();
      fs::remove(tmp, ec);
      return -error;
    }

    if(config_.local_eviction_policy=="sieve")sieve_.Ready(gpu.gpu_id,meta.logical_path);
    metadata_.CommitLocalCache(meta, gpu.gpu_id, local, size);
    meta = *metadata_.Get(meta.logical_path);
    RecordPolicyEvent("PROMOTE_READY", meta.logical_path, gpu.gpu_id, size, metric_prefix);
    if(reused)RecordReadFillCommit(size,fill);
    if(config_.measured_policy) {
      const CopyCostSample sample{ElapsedMicros(copy_start),planning_us,reused?fill->CaptureUs():0};
      RecordCopyCost(size,sample);
      AddBufferedMetric("measured_verified_copy_us",sample.Full());
      SetBufferedMetricMax("measured_history_entries_max",measured_.Entries());
    }
    AddBackgroundMetric("migration_to_local_commit", 1);
    AddBackgroundMetric("local_cache_create_count", 1);
    AddBackgroundMetric(metric_prefix + "_count", 1);
    AddBackgroundMetric(metric_prefix + "_bytes", size);
    return 0;
  }

  void SchedulePromoteToLocal(const GpuConfig& gpu, const fs::path& rel,
                              const std::string& logical_path,
                              const std::string& metric_prefix,
                              bool allow_eviction = true) {
    {
      std::lock_guard<std::mutex> lock(promote_mu_);
      if (promote_inflight_.count(logical_path) != 0) {
        metadata_.AddMetric(metric_prefix + "_skip_inflight", 1);
        return;
      }
      promote_inflight_.insert(logical_path);
    }
    metadata_.AddMetric(metric_prefix + "_request_count", 1);
    if (!SubmitBackground([this, gpu, rel, logical_path, metric_prefix, allow_eviction]() {
      if (auto current = metadata_.Get(logical_path);
          current && current->tier == "remote" && current->state == "COMMITTED") {
        FileMeta meta = *current;
        if (int rc = PromoteToLocal(gpu, rel, meta, metric_prefix,
                                    allow_eviction);
            rc != 0) {
          metadata_.AddMetric(metric_prefix + "_error_count", 1);
        }
      } else {
        metadata_.AddMetric(metric_prefix + "_skip_stale", 1);
      }
      std::lock_guard<std::mutex> lock(promote_mu_);
      promote_inflight_.erase(logical_path);
    })) {
      std::lock_guard<std::mutex> lock(promote_mu_);
      promote_inflight_.erase(logical_path);
    }
  }

  void MaybeSchedulePrefetch(const GpuConfig& gpu, const fs::path& rel) {
    if (!config_.prefetch_on_read) {
      return;
    }
    auto next_rel = NextSequentialRelPath(rel);
    if (!next_rel) {
      return;
    }
    const std::string next_logical =
        gpu.logical_root + "/" + next_rel->generic_string();
    const fs::path local = gpu.local_root / *next_rel;
    if (fs::exists(local)) {
      metadata_.AddMetric("prefetch_skip_local", 1);
      return;
    }
    const fs::path remote = RemotePath(gpu, *next_rel);
    if (!fs::exists(remote)) {
      if (auto meta = metadata_.Get(next_logical); !meta || meta->tier != "remote") {
        metadata_.AddMetric("prefetch_skip_missing", 1);
        return;
      }
    }

    {
      std::lock_guard<std::mutex> lock(prefetch_mu_);
      if (prefetch_inflight_.count(next_logical) != 0) {
        return;
      }
      prefetch_inflight_.insert(next_logical);
    }

    metadata_.AddMetric("prefetch_request_count", 1);
    if (!SubmitBackground([this, gpu, next_rel = *next_rel, next_logical]() {
      PrefetchToLocal(gpu, next_rel, next_logical);
      std::lock_guard<std::mutex> lock(prefetch_mu_);
      prefetch_inflight_.erase(next_logical);
    })) {
      std::lock_guard<std::mutex> lock(prefetch_mu_);
      prefetch_inflight_.erase(next_logical);
    }
  }

  void PrefetchToLocal(const GpuConfig& gpu, const fs::path& rel,
                       const std::string& logical_path) {
    FileMeta meta;
    if (auto existing = metadata_.Get(logical_path)) {
      meta = *existing;
      if (meta.tier == "local") {
        metadata_.AddMetric("prefetch_skip_local", 1);
        return;
      }
    } else {
      fs::path remote = RemotePath(gpu, rel);
      if (!fs::exists(remote)) {
        metadata_.AddMetric("prefetch_skip_missing", 1);
        return;
      }
      meta.logical_path = logical_path;
      meta.gpu_id = gpu.gpu_id;
      meta.tier = "remote";
      meta.backend_id = gpu.remote_backend;
      meta.physical_path = remote;
      meta.size_bytes = FileSizeNoThrow(remote);
      meta.state = "COMMITTED";
      meta.recompute_cost = config_.default_recompute_cost;
      meta.remote_access_cost = config_.default_remote_access_cost;
      meta.producer_gpu = static_cast<uint64_t>(gpu.gpu_id);
      meta.share_count = 1;
      metadata_.Upsert(meta);
    }

    if (meta.state != "COMMITTED" || !fs::exists(meta.physical_path)) {
      metadata_.AddMetric("prefetch_skip_missing", 1);
      return;
    }
    if (int rc = PromoteToLocal(gpu, rel, meta, "prefetch",
                                config_.speculative_copy_may_evict);
        rc != 0) {
      metadata_.AddMetric("prefetch_error_count", 1);
    }
  }

  int SpillIfNeeded(Handle& handle, uint64_t new_size) {
    if (handle.tier != "local") {
      return 0;
    }
    const GpuConfig* gpu = nullptr;
    for (const auto& item : config_.gpus) {
      if (item.gpu_id == handle.gpu_id) {
        gpu = &item;
        break;
      }
    }
    if (gpu == nullptr) {
      return -EINVAL;
    }
    uint64_t current = FileSizeNoThrow(handle.physical_path);
    uint64_t used_without_file = DirectoryBytes(gpu->local_root);
    if (used_without_file >= current) {
      used_without_file -= current;
    }
    if (used_without_file + new_size <= gpu->local_quota_bytes) {
      return 0;
    }
    if (EnsureLocalCapacity(*gpu, new_size, handle.logical_path,
                            &handle.physical_path)) {
      return 0;
    }

    auto parsed = ParseGpuPath(handle.logical_path);
    if (!parsed) {
      return -EINVAL;
    }
    fs::path remote = RemotePath(*gpu, parsed->second);
    const uint64_t moved_bytes = FileSizeNoThrow(handle.physical_path);
    fs::create_directories(remote.parent_path());
    if (handle.fd >= 0) {
      fsync(handle.fd);
      close(handle.fd);
      handle.fd = -1;
    }
    std::error_code ec;
    fs::rename(handle.physical_path, remote, ec);
    if (ec) {
      fs::copy_file(handle.physical_path, remote,
                    fs::copy_options::overwrite_existing, ec);
      if (ec) {
        return -ec.value();
      }
      fs::remove(handle.physical_path, ec);
    }
    handle.physical_path = remote;
    handle.tier = "remote";
    handle.backend_id = gpu->remote_backend;
    handle.created_remote = false;
    handle.fd = open(handle.physical_path.c_str(), handle.flags);
    if (handle.fd < 0) {
      return -errno;
    }
    UpdateHandleMeta(handle, handle.state);
    if (auto meta = metadata_.Get(handle.logical_path)) {
      meta->primary_tier = "remote";
      meta->has_remote_copy = true;
      meta->local_cache_owner_gpu = -1;
      meta->replica_state = "REMOTE_ONLY";
      meta->last_demoted_at = UnixNowSeconds();
      metadata_.Upsert(*meta);
    }
    metadata_.AddMetric("spill_count", 1);
    metadata_.AddMetric("spill_bytes", std::max(moved_bytes, new_size));
    return 0;
  }

  int EvictLocalFile(const GpuConfig& gpu, FileMeta& meta) {
    auto parsed = ParseGpuPath(meta.logical_path);
    if (!parsed) {
      return -EINVAL;
    }
    fs::path remote = RemotePath(gpu, parsed->second);
    const uint64_t size = FileSizeNoThrow(meta.physical_path);
    const fs::path source = meta.physical_path;
    ApplyBackgroundQos(gpu.gpu_id, size, "evict");

    std::error_code ec;
    if (meta.has_remote_copy && fs::exists(remote, ec)) {
      FileMeta deleting = meta;
      deleting.state = "DELETING_CACHE";
      metadata_.Upsert(deleting);

      fs::remove(source, ec);
      if (ec) {
        return -ec.value();
      }

      meta.tier = "remote";
      meta.backend_id = gpu.remote_backend;
      meta.physical_path = remote;
      meta.size_bytes = std::max(size, FileSizeNoThrow(remote));
      meta.primary_tier = "remote";
      meta.has_remote_copy = true;
      meta.local_cache_owner_gpu = -1;
      meta.replica_state = "REMOTE_ONLY";
      meta.last_demoted_at = UnixNowSeconds();
      meta.state = "COMMITTED";
      metadata_.Upsert(meta);
      AddBackgroundMetric("local_cache_delete_count", 1);
      AddBackgroundMetric("local_cache_delete_bytes", size);
      AddBackgroundMetric("evict_count", 1);
      AddBackgroundMetric("evict_bytes", size);
      return 0;
    }

    fs::create_directories(remote.parent_path());
    fs::path tmp = remote;
    tmp += config_.temp_suffix + ".evict";

    fs::remove(tmp, ec);
    ec.clear();

    FileMeta migrating = meta;
    migrating.state = "COPYING_TO_REMOTE";
    metadata_.Upsert(migrating);
    AddBackgroundMetric("migration_to_remote_begin", 1);

    fs::copy_file(source, tmp, fs::copy_options::overwrite_existing, ec);
    if (ec) {
      fs::remove(tmp, ec);
      return -ec.value();
    }
    if (int fd = open(tmp.c_str(), O_RDONLY); fd >= 0) {
      fsync(fd);
      close(fd);
    }
    fs::rename(tmp, remote, ec);
    if (ec) {
      fs::remove(tmp, ec);
      return -ec.value();
    }

    meta.tier = "remote";
    meta.backend_id = gpu.remote_backend;
    meta.physical_path = remote;
    meta.size_bytes = size;
    meta.primary_tier = "remote";
    meta.has_remote_copy = true;
    meta.local_cache_owner_gpu = -1;
    meta.replica_state = "REMOTE_ONLY";
    meta.last_demoted_at = UnixNowSeconds();
    meta.state = "REMOTE_READY";
    metadata_.Upsert(meta);
    meta.state = "COMMITTED";
    metadata_.Upsert(meta);
    fs::remove(source, ec);
    AddBackgroundMetric("migration_to_remote_commit", 1);
    AddBackgroundMetric("evict_count", 1);
    AddBackgroundMetric("evict_bytes", size);
    return 0;
  }

  void UpdateHandleMeta(const Handle& handle, const std::string& state,
                        const std::string& checksum = "") {
    FileMeta meta;
    if (auto existing = metadata_.Get(handle.logical_path)) {
      meta = *existing;
    }
    meta.logical_path = handle.logical_path;
    meta.gpu_id = handle.gpu_id;
    meta.tier = handle.tier;
    meta.backend_id = handle.backend_id;
    meta.physical_path = handle.physical_path;
    meta.size_bytes = FileSizeNoThrow(handle.physical_path);
    meta.checksum = checksum;
    if (config_.physical_dedup && !checksum.empty()) {
      meta.content_key = checksum;
    }
    if (meta.recompute_cost == 0) {
      meta.recompute_cost = config_.default_recompute_cost;
    }
    if (meta.remote_access_cost == 0) {
      meta.remote_access_cost = config_.default_remote_access_cost;
    }
    if (meta.producer_gpu == 0 && handle.gpu_id != 0) {
      meta.producer_gpu = static_cast<uint64_t>(handle.gpu_id);
    }
    if (meta.share_count == 0) {
      meta.share_count = 1;
    }
    if (handle.tier == "remote") {
      meta.primary_tier = "remote";
      meta.has_remote_copy = true;
      meta.local_cache_owner_gpu = -1;
      meta.replica_state = "REMOTE_ONLY";
    } else if (meta.primary_tier.empty()) {
      meta.primary_tier = "local";
      meta.has_remote_copy = false;
      meta.local_cache_owner_gpu = handle.gpu_id;
      meta.replica_state = "LOCAL_ONLY";
    } else if (meta.primary_tier == "local" && !meta.has_remote_copy) {
      meta.local_cache_owner_gpu = handle.gpu_id;
      meta.replica_state = "LOCAL_ONLY";
    }
    meta.state = state;
    metadata_.Upsert(meta);
  }

  int CommitHandle(Handle& handle) {
    if (handle.fd < 0) {
      return -EBADF;
    }
    if (fsync(handle.fd) != 0) {
      return -errno;
    }
    std::string checksum;
    if (config_.checksum != "none") {
      auto calculated = ChecksumFile(handle.physical_path);
      if (!calculated) {
        return -EIO;
      }
      checksum = *calculated;
    }
    handle.state = "COMMITTED";
    UpdateHandleMeta(handle, "COMMITTED", checksum);
    handle.last_checksum = checksum;
    if (config_.physical_dedup && !checksum.empty()) {
      auto content_ref = metadata_.RegisterContentRef(
          checksum, handle.logical_path, handle.physical_path,
          FileSizeNoThrow(handle.physical_path));
      if (content_ref.duplicate) {
        metadata_.AddMetric("dedup_duplicate_content_count", 1);
      }
      metadata_.AddMetric("content_ref_register_count", 1);
      if (config_.physical_dedup && content_ref.duplicate &&
          !content_ref.primary_physical_path.empty() &&
          content_ref.primary_physical_path != handle.physical_path) {
        handle.pending_physical_dedup = true;
        handle.dedup_primary_path = content_ref.primary_physical_path;
        metadata_.AddMetric("physical_dedup_candidate_count", 1);
      }
    }
    if (handle.created_remote) {
      metadata_.AddMetric("remote_place_count", 1);
      handle.created_remote = false;
    }
    return 0;
  }

  int ApplyPhysicalDedup(const Handle& handle) {
    if (!config_.physical_dedup || !handle.pending_physical_dedup ||
        handle.dedup_primary_path.empty()) {
      return 0;
    }
    std::error_code ec;
    if (!fs::exists(handle.dedup_primary_path, ec) ||
        !fs::exists(handle.physical_path, ec)) {
      metadata_.AddMetric("physical_dedup_skip_missing", 1);
      return 0;
    }
    ec.clear();
    if (fs::equivalent(handle.dedup_primary_path, handle.physical_path, ec)) {
      return 0;
    }

    fs::path tmp = handle.physical_path;
    tmp += config_.temp_suffix + ".dedup";
    fs::remove(tmp, ec);
    ec.clear();
    fs::create_hard_link(handle.dedup_primary_path, tmp, ec);
    if (ec) {
      metadata_.AddMetric("physical_dedup_hardlink_fail", 1);
      return 0;
    }
    ec.clear();
    fs::rename(tmp, handle.physical_path, ec);
    if (ec) {
      fs::remove(tmp, ec);
      metadata_.AddMetric("physical_dedup_rename_fail", 1);
      return 0;
    }
    metadata_.AddMetric("physical_dedup_count", 1);
    metadata_.AddMetric("physical_dedup_bytes", FileSizeNoThrow(handle.physical_path));
    return 0;
  }

  std::optional<std::string> ChecksumFile(const fs::path& path) const {
    if (config_.checksum != "fnv1a64") {
      return "";
    }
    int fd = open(path.c_str(), O_RDONLY);
    if (fd < 0) {
      return std::nullopt;
    }
    constexpr uint64_t kOffset = 14695981039346656037ULL;
    constexpr uint64_t kPrime = 1099511628211ULL;
    uint64_t hash = kOffset;
    std::vector<unsigned char> buffer(1024 * 1024);
    while (true) {
      ssize_t n = read(fd, buffer.data(), buffer.size());
      if (n < 0) {
        if (errno == EINTR) {
          continue;
        }
        close(fd);
        return std::nullopt;
      }
      if (n == 0) {
        break;
      }
      for (ssize_t i = 0; i < n; ++i) {
        hash ^= buffer[static_cast<size_t>(i)];
        hash *= kPrime;
      }
    }
    close(fd);
    std::ostringstream out;
    out << "fnv1a64:" << std::hex << std::setw(16) << std::setfill('0') << hash;
    return out.str();
  }

  void RecoverIncompleteFiles() {
    for (const auto& meta : metadata_.IncompleteFiles()) {
      if (meta.state == "DELETING_CACHE") {
        FileMeta recovered = meta;
        auto parsed = ParseGpuPath(meta.logical_path);
        if (parsed) {
          const auto [gpu, rel] = *parsed;
          recovered.tier = "remote";
          recovered.backend_id = gpu->remote_backend;
          recovered.physical_path = RemotePath(*gpu, rel);
          recovered.primary_tier = "remote";
          recovered.has_remote_copy = true;
          recovered.local_cache_owner_gpu = -1;
          recovered.replica_state = "REMOTE_ONLY";
          recovered.state = "COMMITTED";
          recovered.last_demoted_at = UnixNowSeconds();
          std::error_code ec;
          fs::remove(meta.physical_path, ec);
          metadata_.Upsert(recovered);
          metadata_.AddMetric("cache_delete_recovered_count", 1);
          continue;
        }
      }
      if (meta.state == "COPYING_TO_REMOTE" || meta.state == "COPYING_TO_LOCAL" ||
          meta.state == "REMOTE_READY" || meta.state == "LOCAL_READY") {
        FileMeta recovered = meta;
        recovered.state = "COMMITTED";
        metadata_.Upsert(recovered);
        metadata_.AddMetric("migration_recovered_count", 1);
        continue;
      }
      std::error_code ec;
      fs::remove(meta.physical_path, ec);
      metadata_.Remove(meta.logical_path);
    }
    for (const auto& gpu : config_.gpus) {
      RemoveTempFiles(gpu.local_root);
      RemoveTempFiles(RemotePath(gpu, ""));
    }
  }

  void RemoveTempFiles(const fs::path& root) const {
    std::error_code ec;
    if (!fs::exists(root, ec)) {
      return;
    }
    for (fs::recursive_directory_iterator it(root, fs::directory_options::skip_permission_denied, ec), end;
         it != end && !ec; it.increment(ec)) {
      const auto filename = it->path().filename().string();
      if (filename.find(config_.temp_suffix) != std::string::npos) {
        fs::remove(it->path(), ec);
      }
    }
  }

  uint64_t StoreHandle(Handle handle) {
    std::lock_guard<std::mutex> lock(handles_mu_);
    uint64_t id = next_handle_++;
    const bool has_tail=bool(handle.direct_read_tail);
    handles_.emplace(id, std::move(handle));
    if(has_tail) {
      ++direct_read_tail_handles_;
      AddBufferedMetric("direct_read_tail_buffers_created",1);
      SetBufferedMetricMax("direct_read_tail_buffer_bytes_peak",direct_read_tail_handles_*AlignedReadTail::kAlignment);
    }
    return id;
  }

  Handle* FindHandle(const fuse_file_info* fi) {
    std::lock_guard<std::mutex> lock(handles_mu_);
    auto it = handles_.find(fi->fh);
    if (it == handles_.end()) {
      return nullptr;
    }
    return &it->second;
  }

  bool IsOpenLogicalPath(const std::string& logical_path) {
    std::lock_guard<std::mutex> lock(handles_mu_);
    for (const auto& [_, handle] : handles_) {
      if (handle.logical_path == logical_path) {
        return true;
      }
    }
    return false;
  }

  static void AddDirectoryNames(const fs::path& dir, std::set<std::string>& names) {
    std::error_code ec;
    if (!fs::is_directory(dir, ec)) {
      return;
    }
    for (const auto& entry : fs::directory_iterator(dir, ec)) {
      const auto name = entry.path().filename().string();
      if (name == ".tokenfs-replicas") {
        continue;
      }
      names.insert(name);
    }
  }

  static int StatPhysical(const fs::path& path, struct stat* stbuf) {
    if (lstat(path.c_str(), stbuf) != 0) {
      return -errno;
    }
    return 0;
  }

  using Clock = std::chrono::steady_clock;

  static uint64_t ElapsedMicros(Clock::time_point start) {
    return static_cast<uint64_t>(
        std::chrono::duration_cast<std::chrono::microseconds>(Clock::now() - start)
            .count());
  }

  static std::string LatencyBucket(uint64_t latency_us) {
    if (latency_us <= 100) {
      return "le_100us";
    }
    if (latency_us <= 1000) {
      return "le_1ms";
    }
    if (latency_us <= 10000) {
      return "le_10ms";
    }
    if (latency_us <= 100000) {
      return "le_100ms";
    }
    return "gt_100ms";
  }

  void RecordLatency(const std::string& op, const std::string& tier,
                     uint64_t latency_us) {
    AddBufferedMetric(op + "_latency_us_total", latency_us);
    AddBufferedMetric(op + "_" + tier + "_latency_us_total", latency_us);
    SetBufferedMetricMax(op + "_latency_us_max", latency_us);
    SetBufferedMetricMax(op + "_" + tier + "_latency_us_max", latency_us);
    const std::string bucket = LatencyBucket(latency_us);
    AddBufferedMetric(op + "_latency_bucket_" + bucket, 1);
    AddBufferedMetric(op + "_" + tier + "_latency_bucket_" + bucket, 1);
  }

  void AddBackgroundMetric(const std::string& name,uint64_t delta) {
    if(config_.batch_background_metrics)AddBufferedMetric(name,delta);
    else metadata_.AddMetric(name,delta);
  }

  void RecordPolicyEvent(const std::string& action,const std::string& path,int gpu,
                         uint64_t bytes,const std::string& reason,double score=0) {
    if(trace_.Enabled()) {
      RequestTrace::Event event;
      event.op="policy_"+action;event.path=path;event.location=gpu;event.bytes=bytes;
      event.tier=reason.substr(0,reason.find(';'));
      event.start_ns=event.end_ns=RequestTrace::Now();
      trace_.Add(std::move(event));
    }
    if(!config_.batch_policy_events) {
      metadata_.RecordPolicyEvent(action,path,gpu,bytes,reason,score);return;
    }
    // Diagnostic events are not the cache-state transaction. Publish them in
    // order at the existing FULL-WAL telemetry fence, before task completion.
    std::lock_guard<std::mutex> lock(buffered_metrics_mu_);
    buffered_policy_events_.push_back({action,path,gpu,bytes,reason,score});
  }

  void AddBufferedMetric(const std::string& name, uint64_t delta) {
    if (delta == 0) {
      return;
    }
    std::lock_guard<std::mutex> lock(buffered_metrics_mu_);
    buffered_metrics_[name] += delta;
  }

  void SetBufferedMetricMax(const std::string& name, uint64_t value) {
    std::lock_guard<std::mutex> lock(buffered_metrics_mu_);
    auto [it, inserted] = buffered_metric_max_.emplace(name, value);
    if (!inserted) {
      it->second = std::max(it->second, value);
    }
  }

  void FlushBufferedMetrics(uint64_t completed_tasks=0,bool count_background_failure=false) {
    // A concurrent flush must finish before background_completed can advance.
    std::lock_guard<std::mutex> flush_lock(flush_metrics_mu_);
    std::unordered_map<std::string, uint64_t> pending;
    std::unordered_map<std::string, uint64_t> pending_max;
    std::vector<PolicyEvent> events;
    {
      std::lock_guard<std::mutex> lock(buffered_metrics_mu_);
      if (!completed_tasks && buffered_metrics_.empty() && buffered_metric_max_.empty() && buffered_policy_events_.empty()) {
        return;
      }
      pending.swap(buffered_metrics_);
      pending_max.swap(buffered_metric_max_);
      events.swap(buffered_policy_events_);
    }
    // The legacy worker adds a temporary completion only for this attempt.
    // Deferred submissions instead buffer terminal outcomes before entering
    // the fence, so a failed batch retains its completion for an exact retry.
    if(completed_tasks)pending["background_completed"]+=completed_tasks;
    try {metadata_.ApplyMetricBatch(pending, pending_max, events);}
    catch (...) {
      // The transaction rolled back. Retain observations for retry, ahead of
      // newer events, without duplicating already durable data.
      std::lock_guard<std::mutex> lock(buffered_metrics_mu_);
      if(completed_tasks)pending["background_completed"]-=completed_tasks;
      // Keep the failure signal with the restored completion while the fence
      // remains locked. Otherwise a foreground retry could publish completion
      // before the worker's outer catch had buffered its error observation.
      if(count_background_failure)++pending["background_error_count"];
      for(const auto& [key,value]:pending)buffered_metrics_[key]+=value;
      for(const auto& [key,value]:pending_max)buffered_metric_max_[key]=std::max(buffered_metric_max_[key],value);
      events.insert(events.end(),buffered_policy_events_.begin(),buffered_policy_events_.end());
      buffered_policy_events_.swap(events);
      throw;
    }
  }

  void ApplyQos(const Handle& handle, bool write, uint64_t bytes) {
    const uint64_t limit =
        write ? config_.qos_write_iops_per_gpu : config_.qos_read_iops_per_gpu;
    if (limit == 0) {
      AddBufferedMetric(write ? "qos_foreground_write_ops"
                              : "qos_foreground_read_ops",
                        1);
      return;
    }
    AddBufferedMetric(write ? "qos_foreground_write_ops"
                            : "qos_foreground_read_ops",
                      1);
    const auto gap = std::chrono::microseconds(
        std::max<uint64_t>(1, 1000000ULL / std::max<uint64_t>(1, limit)));
    const std::string key =
        std::to_string(handle.caller_gpu_id) + (write ? ":fg_write" : ":fg_read");
    Clock::duration delay{};
    {
      std::lock_guard<std::mutex> lock(qos_mu_);
      const auto now = Clock::now();
      auto& next = qos_next_[key];
      if (next > now) {
        delay = next - now;
        next += gap;
      } else {
        next = now + gap;
      }
    }
    if (delay.count() <= 0) {
      return;
    }
    const auto delay_us =
        std::chrono::duration_cast<std::chrono::microseconds>(delay).count();
    AddBufferedMetric("qos_delay_us_total", static_cast<uint64_t>(delay_us));
    AddBufferedMetric("qos_delay_ops", 1);
    AddBufferedMetric("qos_foreground_delay_ops", 1);
    AddBufferedMetric("qos_foreground_delay_us_total",
                      static_cast<uint64_t>(delay_us));
    AddBufferedMetric("qos_gpu" + std::to_string(handle.caller_gpu_id) +
                          "_delay_us_total",
                      static_cast<uint64_t>(delay_us));
    AddBufferedMetric("qos_gpu" + std::to_string(handle.caller_gpu_id) +
                          "_delayed_bytes",
                      bytes);
    std::this_thread::sleep_for(delay);
  }

  void ApplyBackgroundQos(int gpu_id, uint64_t bytes,
                          const std::string& activity) {
    AddBackgroundMetric("qos_background_ops", 1);
    AddBackgroundMetric("qos_background_bytes", bytes);
    AddBackgroundMetric("qos_background_" + activity + "_ops", 1);
    AddBackgroundMetric("qos_background_" + activity + "_bytes", bytes);

    Clock::duration delay{};
    if (config_.qos_background_iops_per_gpu > 0) {
      const auto gap = std::chrono::microseconds(std::max<uint64_t>(
          1, 1000000ULL / config_.qos_background_iops_per_gpu));
      const std::string key = std::to_string(gpu_id) + ":bg_op";
      std::lock_guard<std::mutex> lock(qos_mu_);
      const auto now = Clock::now();
      auto& next = qos_next_[key];
      if (next > now) {
        delay = std::max(delay, next - now);
        next += gap;
      } else {
        next = now + gap;
      }
    }
    if (config_.qos_background_mib_per_sec_per_gpu > 0 && bytes > 0) {
      const uint64_t mib = std::max<uint64_t>(1, bytes / 1024 / 1024);
      const uint64_t delay_us =
          mib * 1000000ULL / config_.qos_background_mib_per_sec_per_gpu;
      delay = std::max(
          delay,
          std::chrono::duration_cast<Clock::duration>(
              std::chrono::microseconds(delay_us)));
    }
    if (delay.count() <= 0) {
      return;
    }
    const auto delay_us =
        std::chrono::duration_cast<std::chrono::microseconds>(delay).count();
    AddBackgroundMetric("qos_delay_us_total", static_cast<uint64_t>(delay_us));
    AddBackgroundMetric("qos_delay_ops", 1);
    AddBackgroundMetric("qos_background_delay_ops", 1);
    AddBackgroundMetric("qos_background_delay_us_total",
                        static_cast<uint64_t>(delay_us));
    AddBackgroundMetric("qos_gpu" + std::to_string(gpu_id) +
                            "_background_delay_us_total",
                        static_cast<uint64_t>(delay_us));
    std::this_thread::sleep_for(delay);
  }

  void MaybeAdaptivePromote(const Handle& handle, uint64_t latency_us) {
    if (!config_.adaptive_migration || handle.tier != "remote" ||
        latency_us < config_.adaptive_remote_promote_us) {
      return;
    }
    auto parsed = ParseGpuPath(handle.logical_path);
    if (!parsed) {
      return;
    }
    const auto [gpu, rel] = *parsed;
    auto existing = metadata_.Get(handle.logical_path);
    if (!existing || existing->tier != "remote" || existing->state != "COMMITTED") {
      return;
    }
    FileMeta meta = *existing;
    if (!ShouldPromoteOnRead(meta, meta.read_count, handle.caller_gpu_id)) {
      metadata_.AddMetric("adaptive_promote_skip_unprofitable", 1);
      return;
    }
    metadata_.AddMetric("adaptive_promote_trigger_count", 1);
    if (config_.async_promote_on_read) {
      SchedulePromoteToLocal(*gpu, rel, handle.logical_path, "adaptive_promote",
                             true);
    } else {
      if (int rc = PromoteToLocal(*gpu, rel, meta, "adaptive_promote"); rc != 0) {
        metadata_.AddMetric("adaptive_promote_error_count", 1);
      }
    }
  }

  std::mutex layout_mu_;
  std::mutex copy_mu_;
  std::mutex background_mu_;
  std::condition_variable background_cv_;
  std::deque<std::function<void()>> background_tasks_;
  std::thread background_worker_;
  bool background_stopping_ = false;
  Config config_;
  RequestTrace trace_;
  ReadFillPool fills_;
  tokenfs_policy::MeasuredPolicy measured_;
  tokenfs_policy::SievePolicy sieve_;
  MetadataStore metadata_;
  std::mutex handles_mu_;
  std::unordered_map<uint64_t, Handle> handles_;
  uint64_t next_handle_ = 1;
  uint64_t direct_read_tail_handles_ = 0; // guarded by handles_mu_, excludes capture RAM
  std::mutex prefetch_mu_;
  std::set<std::string> prefetch_inflight_;
  std::mutex promote_mu_;
  std::set<std::string> promote_inflight_;
  std::mutex cross_gpu_replica_mu_;
  std::set<std::string> cross_gpu_replica_inflight_;
  std::mutex shared_placement_mu_;
  std::set<std::string> shared_placement_inflight_;
  bool submission_precheck_ready_=false;
  std::unordered_map<int,fs::path> submission_precheck_roots_;
  std::mutex buffered_metrics_mu_;
  std::mutex flush_metrics_mu_;
  std::unordered_map<std::string, uint64_t> buffered_metrics_;
  std::unordered_map<std::string, uint64_t> buffered_metric_max_;
  std::vector<PolicyEvent> buffered_policy_events_;
  std::mutex qos_mu_;
  std::unordered_map<std::string, Clock::time_point> qos_next_;
};


} // namespace

#include <cassert>
#include <atomic>
#include <future>
#include <map>
#include <tuple>
namespace {
struct TokenFSTestAccess {
  struct TelemetryProbe {
    sqlite3* db=nullptr;
    explicit TelemetryProbe(const fs::path& path) {
      assert(sqlite3_open(path.c_str(),&db)==SQLITE_OK);
      assert(sqlite3_busy_timeout(db,3000)==SQLITE_OK);
    }
    ~TelemetryProbe(){sqlite3_close(db);}
    void Exec(const char* sql){assert(sqlite3_exec(db,sql,nullptr,nullptr,nullptr)==SQLITE_OK);}
    uint64_t Metric(const char* name) {
      sqlite3_stmt* st=nullptr;
      assert(sqlite3_prepare_v2(db,"SELECT value FROM metrics WHERE name=?",-1,&st,nullptr)==SQLITE_OK);
      sqlite3_bind_text(st,1,name,-1,SQLITE_TRANSIENT);const int rc=sqlite3_step(st);
      assert(rc==SQLITE_ROW || rc==SQLITE_DONE);
      const uint64_t n=rc==SQLITE_ROW?sqlite3_column_int64(st,0):0;sqlite3_finalize(st);return n;
    }
    // Read both counters from one SQLite statement/snapshot, even while a
    // worker is committing. Two separate SELECTs can invent an ordering bug.
    std::pair<uint64_t,uint64_t> Counts() {
      sqlite3_stmt* st=nullptr;
      assert(sqlite3_prepare_v2(db,"SELECT COALESCE((SELECT value FROM metrics WHERE name='background_submitted'),0),COALESCE((SELECT value FROM metrics WHERE name='background_completed'),0)",-1,&st,nullptr)==SQLITE_OK);
      assert(sqlite3_step(st)==SQLITE_ROW);
      const std::pair<uint64_t,uint64_t> n{sqlite3_column_int64(st,0),sqlite3_column_int64(st,1)};
      sqlite3_finalize(st);assert(n.second<=n.first);return n;
    }
    std::vector<std::string> Events() {
      std::vector<std::string> out;sqlite3_stmt* st=nullptr;
      assert(sqlite3_prepare_v2(db,"SELECT action FROM policy_events ORDER BY seq",-1,&st,nullptr)==SQLITE_OK);
      int rc;while((rc=sqlite3_step(st))==SQLITE_ROW)out.emplace_back(reinterpret_cast<const char*>(sqlite3_column_text(st,0)));
      assert(rc==SQLITE_DONE);sqlite3_finalize(st);return out;
    }
  };
  template<class Predicate> static void Await(Predicate ready) {
    const auto until=std::chrono::steady_clock::now()+std::chrono::seconds(3);
    while(!ready()){assert(std::chrono::steady_clock::now()<until);std::this_thread::yield();}
  }
  static Config DeferredConfig(const fs::path& root) {
    Config cfg;cfg.mount_point=root/"mnt";cfg.metadata_db=root/"state.db";
    cfg.batch_background_metrics=true;cfg.batch_policy_events=true;cfg.defer_background_submission_metrics=true;
    return cfg;
  }
  static void deferred_background_fence(const fs::path& root) {
    auto cfg=DeferredConfig(root);TokenFS filesystem(cfg);filesystem.Init();TelemetryProbe probe(cfg.metadata_db);
    std::unique_lock<std::mutex> fence(filesystem.flush_metrics_mu_);
    std::promise<void> started,proceed;auto started_f=started.get_future();auto proceed_f=proceed.get_future().share();
    auto submitted=std::async(std::launch::async,[&]{return filesystem.SubmitBackground([&]{
      started.set_value();proceed_f.wait();filesystem.AddBackgroundMetric("fence_value",7);
      filesystem.RecordPolicyEvent("fenced","/gpu0/k",0,4096,"test");
    });});
    // An accepted submission has no synchronous durable fence of its own.
    assert(submitted.wait_for(std::chrono::seconds(3))==std::future_status::ready && submitted.get());
    assert(started_f.wait_for(std::chrono::seconds(3))==std::future_status::ready);
    assert((probe.Counts()==std::pair<uint64_t,uint64_t>{0,0}));
    proceed.set_value();
    Await([&]{std::lock_guard<std::mutex> lock(filesystem.buffered_metrics_mu_);return filesystem.buffered_metrics_["background_completed"]==1;});
    assert((probe.Counts()==std::pair<uint64_t,uint64_t>{0,0}));
    assert(probe.Metric("fence_value")==0 && probe.Events().empty());
    fence.unlock();Await([&]{return probe.Counts().second==1;});
    assert(probe.Metric("fence_value")==7 && probe.Events()==std::vector<std::string>{"fenced"});
    // Both exception kinds are terminal task outcomes, each counted once.
    assert(filesystem.SubmitBackground([&]{filesystem.AddBackgroundMetric("fence_value",3);throw std::runtime_error("task injected");}));
    Await([&]{return probe.Counts().second==2;});
    assert(filesystem.SubmitBackground([&]{filesystem.AddBackgroundMetric("fence_value",5);throw 17;}));
    Await([&]{return probe.Counts().second==3;});
    filesystem.FlushBufferedMetrics();filesystem.FlushBufferedMetrics();
    assert((probe.Counts()==std::pair<uint64_t,uint64_t>{3,3}));
    assert(probe.Metric("fence_value")==15 && probe.Metric("background_error_count")==2);
  }
  static void deferred_background_failure_retry(const fs::path& root,int retry_mode) {
    auto cfg=DeferredConfig(root);auto filesystem=std::make_unique<TokenFS>(cfg);filesystem->Init();TelemetryProbe probe(cfg.metadata_db);
    const char* triggers[]={
      "CREATE TRIGGER reject_batch BEFORE INSERT ON metrics WHEN NEW.name='background_submitted' BEGIN SELECT RAISE(ABORT,'injected submitted'); END;",
      "CREATE TRIGGER reject_batch BEFORE INSERT ON policy_events WHEN NEW.action='reject' BEGIN SELECT RAISE(ABORT,'injected event'); END;",
      "CREATE TRIGGER reject_batch BEFORE INSERT ON metrics WHEN NEW.name='background_completed' BEGIN SELECT RAISE(ABORT,'injected completed'); END;"};
    probe.Exec(triggers[retry_mode]);
    assert(filesystem->SubmitBackground([&]{
      filesystem->AddBackgroundMetric("retry_value",7);
      filesystem->RecordPolicyEvent("reject","/gpu0/k",0,4096,"test");
      if(retry_mode==1)throw std::runtime_error("task and fence injected");
      if(retry_mode==2)throw 23;
    }));
    const uint64_t expected_errors=retry_mode?2:1;
    Await([&]{std::lock_guard<std::mutex> lock(filesystem->buffered_metrics_mu_);return filesystem->buffered_metrics_["background_error_count"]==expected_errors;});
    assert((probe.Counts()==std::pair<uint64_t,uint64_t>{0,0}));
    assert(probe.Metric("retry_value")==0 && probe.Events().empty());
    {std::lock_guard<std::mutex> lock(filesystem->buffered_metrics_mu_);
      assert(filesystem->buffered_metrics_.at("background_submitted")==1);
      assert(filesystem->buffered_metrics_.at("background_completed")==1);}
    bool failed=false;try{filesystem->FlushBufferedMetrics();}catch(const std::runtime_error&){failed=true;}
    assert(failed && probe.Events().empty());
    assert((probe.Counts()==std::pair<uint64_t,uint64_t>{0,0}));
    probe.Exec("DROP TRIGGER reject_batch;");
    if(retry_mode==0) {filesystem->FlushBufferedMetrics();filesystem->FlushBufferedMetrics();}
    if(retry_mode==1) {
      assert(filesystem->SubmitBackground([&]{filesystem->AddBackgroundMetric("retry_value",5);filesystem->RecordPolicyEvent("newer","/gpu0/k",0,4096,"test");}));
      Await([&]{return probe.Counts().second==2;});filesystem->FlushBufferedMetrics();
    }
    if(retry_mode==2)filesystem.reset(); // join, then the destructor's existing fence retries.
    const uint64_t expected_tasks=retry_mode==1?2:1;
    assert((probe.Counts()==std::pair<uint64_t,uint64_t>{expected_tasks,expected_tasks}));
    assert(probe.Metric("retry_value")==uint64_t(retry_mode==1?12:7));
    assert(probe.Metric("background_error_count")==expected_errors);
    assert(probe.Events()==(retry_mode==1?std::vector<std::string>{"reject","newer"}:std::vector<std::string>{"reject"}));
  }
  static void deferred_background_queue_shutdown(const fs::path& root) {
    auto cfg=DeferredConfig(root);auto filesystem=std::make_unique<TokenFS>(cfg);filesystem->Init();TelemetryProbe probe(cfg.metadata_db);
    std::atomic<unsigned> ran{0};std::promise<void> started,proceed;auto started_f=started.get_future();auto proceed_f=proceed.get_future().share();
    assert(filesystem->SubmitBackground([&]{started.set_value();proceed_f.wait();++ran;}));
    assert(started_f.wait_for(std::chrono::seconds(3))==std::future_status::ready);
    for(int i=0;i<64;++i)assert(filesystem->SubmitBackground([&]{++ran;}));
    assert(!filesystem->SubmitBackground([&]{assert(false);}));
    {std::lock_guard<std::mutex> lock(filesystem->background_mu_);filesystem->background_stopping_=true;}
    filesystem->background_cv_.notify_all();
    assert(!filesystem->SubmitBackground([&]{assert(false);}));
    assert((probe.Counts()==std::pair<uint64_t,uint64_t>{0,0}));
    proceed.set_value();filesystem.reset(); // A real join, not submitted==completed polling.
    assert(ran==65 && (probe.Counts()==std::pair<uint64_t,uint64_t>{65,65}));
    assert(probe.Metric("background_queue_rejected")==2 && probe.Metric("background_error_count")==0);
  }
  static void deferred_failed_fence_handoff(const fs::path& root) {
    auto cfg=DeferredConfig(root);TokenFS filesystem(cfg);filesystem.Init();TelemetryProbe probe(cfg.metadata_db);
    // Model an ended task whose worker is descheduled in its outer catch.
    // A foreground retry must already have the failure signal in its batch.
    filesystem.AddBufferedMetric("background_submitted",1);filesystem.AddBufferedMetric("background_completed",1);
    probe.Exec("CREATE TRIGGER reject_handoff BEFORE INSERT ON metrics WHEN NEW.name='background_completed' BEGIN SELECT RAISE(ABORT,'injected handoff'); END;");
    std::promise<void> caught,finish;auto caught_f=caught.get_future();auto finish_f=finish.get_future().share();
    auto failed_fence=std::async(std::launch::async,[&]{
      try{filesystem.FlushBufferedMetrics(0,true);assert(false);}
      catch(const std::runtime_error&){caught.set_value();finish_f.wait();}
    });
    assert(caught_f.wait_for(std::chrono::seconds(3))==std::future_status::ready);
    assert((probe.Counts()==std::pair<uint64_t,uint64_t>{0,0}));
    probe.Exec("DROP TRIGGER reject_handoff;");filesystem.FlushBufferedMetrics();
    assert((probe.Counts()==std::pair<uint64_t,uint64_t>{1,1}));
    assert(probe.Metric("background_error_count")==1);
    finish.set_value();failed_fence.get();filesystem.FlushBufferedMetrics();
    assert(probe.Metric("background_error_count")==1);
  }
  static void readonly_release_fence(const fs::path& root) {
    assert(!Config{}.defer_background_submission_metrics);
    auto invalid=DeferredConfig(root/"invalid");invalid.batch_background_metrics=false;bool rejected=false;
    try{TokenFS bad(invalid);bad.Init();}catch(const std::runtime_error&){rejected=true;}assert(rejected);
    auto cfg=DeferredConfig(root);cfg.request_read_costs=true;
    cfg.gpus.push_back({0,"/gpu0",root/"local",8192,"remote"});
    cfg.backends.emplace("remote",BackendConfig{"remote","directory",root/"remote"});
    TokenFS filesystem(cfg);filesystem.Init();TelemetryProbe probe(cfg.metadata_db);
    std::ofstream(root/"remote/gpu0/k")<<std::string(4096,'x');
    fuse_file_info fi{};fi.flags=O_RDONLY;char bytes[2048];
    assert(filesystem.Open("/gpu0/k",&fi)==0);
    assert(filesystem.Read("/gpu0/k",bytes,sizeof(bytes),0,&fi)==2048);
    probe.Exec("CREATE TRIGGER reject_release BEFORE INSERT ON metrics WHEN NEW.name='read_release_count' BEGIN SELECT RAISE(ABORT,'injected release'); END;");
    bool failed=false;try{filesystem.Release("/gpu0/k",&fi);}catch(const std::runtime_error&){failed=true;}
    assert(failed && filesystem.FindHandle(&fi)==nullptr);
    assert(probe.Metric("read_release_count")==0 && probe.Metric("read_bytes")==0);
    assert(filesystem.buffered_metrics_.at("read_release_count")==1);
    probe.Exec("DROP TRIGGER reject_release;");
    assert(filesystem.Release("/gpu0/k",&fi)==0); // unknown handle retries only the failed fence.
    assert(probe.Metric("read_release_count")==1 && probe.Metric("read_bytes")==2048);
    assert(filesystem.Release("/gpu0/k",&fi)==0 && probe.Metric("read_release_count")==1);
    fuse_file_info writable{};writable.flags=O_RDWR;
    assert(filesystem.Open("/gpu0/k",&writable)==0);
    assert(filesystem.Release("/gpu0/k",&writable)==0 && probe.Metric("read_release_count")==1);
  }
  static Config PrecheckConfig(const fs::path& root,int domains=3) {
    auto cfg=DeferredConfig(root);cfg.precheck_shared_submission=true;
    cfg.readonly_canonical=true;cfg.peer_cache_reads=true;cfg.shared_value_placement=true;
    cfg.measured_policy=true;cfg.measured_causal_window=true;cfg.measured_burst_reuse=true;
    cfg.adaptive_reuse_control=true;cfg.compact_measured_planning=true;cfg.bounded_cost_warmup=true;
    for(int gpu=0;gpu<domains;++gpu)
      cfg.gpus.push_back({gpu,"/gpu"+std::to_string(gpu),root/("local"+std::to_string(gpu)),8192,"remote"});
    cfg.backends.emplace("remote",BackendConfig{"remote","directory",root/"remote"});return cfg;
  }
  struct PrecheckFixture {
    Config cfg;TokenFS filesystem;FileMeta incoming;std::shared_ptr<ReadFillPool::Buffer> fill;
    explicit PrecheckFixture(const fs::path& root,int domains=3):cfg(PrecheckConfig(root,domains)),filesystem(cfg) {
      filesystem.Init();assert(filesystem.submission_precheck_ready_);
      incoming.logical_path="/gpu0/incoming";incoming.gpu_id=0;incoming.tier="remote";
      incoming.backend_id="remote";incoming.physical_path=root/"remote/gpu0/incoming";
      incoming.has_remote_copy=true;incoming.size_bytes=4096;incoming.state="COMMITTED";
      const std::string bytes(4096,'x');std::ofstream(incoming.physical_path)<<bytes;
      filesystem.metadata_.Upsert(incoming);int fd=open(incoming.physical_path.c_str(),O_RDONLY);assert(fd>=0);
      fill=filesystem.fills_.Acquire(incoming.logical_path,fd,4096);
      assert(fill && fill->Append(0,bytes.data(),bytes.size(),fd));close(fd);
      filesystem.measured_.ReadSample(false,4096,21000);
      filesystem.measured_.ReadSample(true,4096,10500);filesystem.measured_.CopySample(4096,8000);
    }
    void Resident(int domain,const std::string& key,const fs::path& alias={},uint64_t bytes=4096) {
      FileMeta meta=incoming;meta.logical_path="/gpu0/"+key;meta.physical_path=cfg.backends.at("remote").root/"gpu0"/key;
      meta.size_bytes=bytes;std::ofstream(meta.physical_path)<<std::string(bytes,'r');filesystem.metadata_.Upsert(meta);
      LocalReplica replica;replica.logical_path=meta.logical_path;replica.gpu_id=domain;replica.size_bytes=bytes;replica.state="READY";
      replica.physical_path=alias.empty()?cfg.gpus.at(domain).local_root/key:alias;
      std::ofstream(replica.physical_path)<<std::string(bytes,'r');filesystem.metadata_.UpsertLocalReplica(replica);
    }
    void FullDomain(int domain) {Resident(domain,"resident"+std::to_string(domain)+"a");Resident(domain,"resident"+std::to_string(domain)+"b");}
    void Full() {for(size_t gpu=0;gpu<cfg.gpus.size();++gpu)FullDomain(gpu);}
    void Observe(unsigned n) {while(n--)filesystem.measured_.Observe(0,incoming.logical_path,filesystem.MeasuredOptions());}
    bool Reject(int caller=0){return filesystem.PrecheckSharedSubmission(incoming,caller,fill);}
  };
  static void submission_precheck_decisions(const fs::path& root) {
    assert(!Config{}.precheck_shared_submission);
    PrecheckFixture f(root);f.Observe(1);
    assert(!f.Reject()); // Free capacity exploration is preserved.
    f.Full();assert(f.Reject());
    assert(!f.filesystem.PrecheckSharedSubmission(f.incoming,0,{})); // Partial/no capture remains original path.
    auto wrong=f.incoming;wrong.size_bytes=2048;
    assert(!f.filesystem.PrecheckSharedSubmission(wrong,0,f.fill));
    auto partial=f.incoming;partial.logical_path="/gpu0/partial";partial.physical_path=f.cfg.backends.at("remote").root/"gpu0/partial";
    const std::string bytes(4096,'p');std::ofstream(partial.physical_path)<<bytes;
    int fd=open(partial.physical_path.c_str(),O_RDONLY);assert(fd>=0);
    auto unfinished=f.filesystem.fills_.Acquire(partial.logical_path,fd,4096);
    assert(unfinished && !unfinished->Append(0,bytes.data(),2048,fd));
    assert(!f.filesystem.PrecheckSharedSubmission(partial,0,unfinished));
    std::ofstream(partial.physical_path,std::ios::trunc)<<std::string(2048,'z');
    assert(!unfinished->Append(2048,bytes.data()+2048,2048,fd));close(fd);
    assert(!f.filesystem.PrecheckSharedSubmission(partial,0,unfinished)); // Changed source failed capture validation.
    f.filesystem.ScheduleSharedPlacement(f.incoming,0,f.fill);
    {std::lock_guard<std::mutex> lock(f.filesystem.background_mu_);assert(f.filesystem.background_tasks_.empty());}
    assert(f.filesystem.buffered_metrics_["background_submitted"]==0);
    assert(f.filesystem.shared_placement_inflight_.empty());
    // No negative-key cache: the same object can become profitable later.
    f.Observe(7);assert(!f.Reject());
    f.filesystem.config_.precheck_shared_submission=false;assert(!f.Reject());
    f.filesystem.config_.precheck_shared_submission=true;f.filesystem.config_.measured_affinity_gate=true;
    assert(!f.Reject()); // Unsupported location-dependent estimates never use the common bound.
    assert(f.filesystem.buffered_metrics_.count("submission_precheck_us") && f.filesystem.buffered_metric_max_.count("submission_precheck_us_max"));
    auto sieve=PrecheckConfig(root/"sieve");sieve.measured_policy=false;sieve.shared_value_placement=false;sieve.shared_pool_cache=true;
    TokenFS pool(sieve);assert(!pool.SubmissionPrecheckSupported());
  }
  static void submission_precheck_ablations(const fs::path& root) {
    for(bool static_value:{false,true}) {
      PrecheckFixture f(root/(static_value?"static":"hotspot"));f.Full();f.Observe(2);
      f.filesystem.config_.measured_static_reuse_value=static_value;
      // Two sparse observations cover copying, but not Full's incoming noise.
      assert(f.Reject());f.filesystem.config_.measured_joint_admission=false;assert(!f.Reject());
    }
    PrecheckFixture f(root/"caller");f.FullDomain(0);f.Observe(1);
    assert(!f.Reject()); // A permitted noncaller still has headroom.
    f.filesystem.config_.shared_caller_only=true;
    assert(f.Reject(0) && !f.Reject(1) && !f.Reject(99));
  }
  static void submission_precheck_busy(const fs::path& root) {
    PrecheckFixture f(root);f.Full();f.Observe(1);
    auto returns_without_waiting=[&](std::mutex& mutex) {
      std::unique_lock<std::mutex> held(mutex);
      auto result=std::async(std::launch::async,[&]{return f.Reject();});
      assert(result.wait_for(std::chrono::seconds(3))==std::future_status::ready);
      assert(!result.get());
    };
    returns_without_waiting(f.filesystem.layout_mu_);
    returns_without_waiting(f.filesystem.metadata_.mu_);
    assert(f.Reject());
    assert(f.filesystem.buffered_metrics_["submission_precheck_layout_busy"]==1);
    assert(f.filesystem.buffered_metrics_["submission_precheck_metadata_fallback"]==1);
  }
  static void submission_precheck_metadata(const fs::path& root) {
    PrecheckFixture f(root/"malformed",1);f.Full();f.Observe(1);TelemetryProbe probe(f.cfg.metadata_db);
    assert(f.Reject());
    probe.Exec("UPDATE local_replicas SET size_bytes=-1 WHERE logical_path='/gpu0/resident0a';");assert(!f.Reject());
    probe.Exec("UPDATE local_replicas SET size_bytes=4096,gpu_id=99 WHERE logical_path='/gpu0/resident0a';");assert(!f.Reject());
    probe.Exec("UPDATE local_replicas SET gpu_id=0,physical_path='/outside/cache' WHERE logical_path='/gpu0/resident0a';");assert(!f.Reject());
    // A prefix string is not component containment (local0-else is outside).
    auto outside=f.cfg.gpus[0].local_root.string()+"-else/file";
    sqlite3_stmt* stmt=nullptr;assert(sqlite3_prepare_v2(probe.db,"UPDATE local_replicas SET physical_path=? WHERE logical_path='/gpu0/resident0a'",-1,&stmt,nullptr)==SQLITE_OK);
    sqlite3_bind_text(stmt,1,outside.c_str(),-1,SQLITE_TRANSIENT);assert(sqlite3_step(stmt)==SQLITE_DONE);sqlite3_finalize(stmt);assert(!f.Reject());
    PrecheckFixture duplicate(root/"duplicate",1);const auto physical=duplicate.cfg.gpus[0].local_root/"same";
    duplicate.Resident(0,"a",physical);duplicate.Resident(0,"b",physical);duplicate.Observe(1);
    assert(!duplicate.Reject()); // One 4 KiB path leaves 4 KiB headroom, not zero.
    TelemetryProbe dup_probe(duplicate.cfg.metadata_db);
    dup_probe.Exec("UPDATE local_replicas SET size_bytes=8192 WHERE logical_path='/gpu0/b';");
    assert(!duplicate.Reject()); // Conflicting duplicate metadata is unknown.
  }
  static void submission_precheck_startup(const fs::path& root) {
    auto disabled=[&](Config cfg){TokenFS filesystem(cfg);filesystem.Init();assert(!filesystem.submission_precheck_ready_);};
    auto cfg=PrecheckConfig(root/"same-root");cfg.gpus[1].local_root=cfg.gpus[0].local_root;disabled(cfg);
    cfg=PrecheckConfig(root/"nested");cfg.gpus[1].local_root=cfg.gpus[0].local_root/"nested";disabled(cfg);
    cfg=PrecheckConfig(root/"nonempty");fs::create_directories(cfg.gpus[0].local_root);std::ofstream(cfg.gpus[0].local_root/"old")<<'x';disabled(cfg);
    cfg=PrecheckConfig(root/"duplicate-domain");cfg.gpus[1].gpu_id=0;disabled(cfg);
    cfg=PrecheckConfig(root/"orphan-ready");
    {MetadataStore store(cfg.metadata_db);store.Open();LocalReplica orphan;
      orphan.logical_path="/gpu0/later";orphan.gpu_id=0;orphan.physical_path=cfg.gpus[0].local_root/"absent";
      orphan.size_bytes=8192;orphan.state="READY";store.UpsertLocalReplica(orphan);}
    TokenFS filesystem(cfg);filesystem.Init();assert(!filesystem.submission_precheck_ready_);
    FileMeta later;later.logical_path="/gpu0/later";later.gpu_id=0;later.tier="remote";later.state="COMMITTED";
    filesystem.metadata_.Upsert(later);assert(!filesystem.submission_precheck_ready_);
  }
  static int PrecheckIndexCount(MetadataStore& store) {
    auto lease=store.CachedStatement("SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND name IN ('idx_files_shared_precheck_local','idx_replicas_shared_precheck_ready');");
    assert(sqlite3_step(lease.get())==SQLITE_ROW);return sqlite3_column_int(lease.get(),0);
  }
  using ResidentRow=std::tuple<int,std::string,uint64_t>;
  static std::vector<ResidentRow> ResidentRows(MetadataStore& store) {
    std::vector<MetadataStore::ReadyResidentBytes> found;assert(store.TryReadyResidentBytes(found));
    std::vector<ResidentRow> rows;for(const auto& r:found)rows.emplace_back(r.location,r.physical.string(),r.bytes);
    std::sort(rows.begin(),rows.end());return rows;
  }
  static void indexed_precheck_query(const fs::path& root) {
    MetadataStore plain(root/"plain.db"),indexed(root/"indexed.db");plain.Open();indexed.Open();
    assert(indexed.CreateSharedPrecheckIndexes() && indexed.CreateSharedPrecheckIndexes());
    for(auto* store:{&plain,&indexed}) {
      // Most canonical rows are remote; the resident query must not scan them.
      store->Exec("WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM n WHERE x<4096) INSERT INTO files(logical_path,gpu_id,tier,backend_id,physical_path,size_bytes,state,created_at,updated_at) SELECT '/gpu0/remote-'||x,0,'remote','remote','/remote/'||x,4096,'COMMITTED',1,1 FROM n;");
      auto file=[&](const char* key,const char* tier,const char* state) {
        FileMeta m;m.logical_path=std::string("/gpu0/")+key;m.gpu_id=0;m.tier=tier;m.backend_id="remote";
        m.physical_path=fs::path("/cache")/key;m.size_bytes=4096;m.state=state;store->Upsert(m);
      };
      file("a","local","COMMITTED");file("b","remote","COMMITTED");file("d","local","COPYING");
      for(const char* key:{"a","b","c","d"}) {
        LocalReplica r;r.logical_path=std::string("/gpu0/")+key;r.gpu_id=0;r.physical_path=fs::path("/cache")/key;
        r.size_bytes=4096;r.state="READY";store->UpsertLocalReplica(r);
      }
    }
    auto equal=[&](size_t count) {auto a=ResidentRows(plain),b=ResidentRows(indexed);assert(a==b && a.size()==count);};
    equal(3); // a appears twice, b once; orphan c and noncommitted d are excluded.
    auto rows=ResidentRows(indexed);assert(std::count(rows.begin(),rows.end(),ResidentRow{0,"/cache/a",4096})==2);
    std::string plan;const auto explain=std::string("EXPLAIN QUERY PLAN ")+MetadataStore::kReadyResidentBytesSql;
    {auto st=indexed.CachedStatement(explain.c_str());
      int rc;while((rc=sqlite3_step(st.get()))==SQLITE_ROW)plan+=MetadataStore::ColumnText(st.get(),3)+"\n";
      assert(rc==SQLITE_DONE);}
    assert(plan.find("idx_files_shared_precheck_local")!=std::string::npos);
    assert(plan.find("idx_replicas_shared_precheck_ready")!=std::string::npos);
    auto scans=[](MetadataStore& store) {
      auto st=store.CachedStatement(MetadataStore::kReadyResidentBytesSql);
      sqlite3_stmt_status(st.get(),SQLITE_STMTSTATUS_FULLSCAN_STEP,1);
      int rc;while((rc=sqlite3_step(st.get()))==SQLITE_ROW){}assert(rc==SQLITE_DONE);
      return sqlite3_stmt_status(st.get(),SQLITE_STMTSTATUS_FULLSCAN_STEP,0);
    };
    const auto plain_scans=scans(plain),indexed_scans=scans(indexed);
    assert(plain_scans>=4096 && indexed_scans<64);
    std::cout<<"indexed precheck fullscan steps: "<<plain_scans<<" -> "<<indexed_scans<<"\n"<<plan;
    auto mutate=[&](const char* sql,size_t count){plain.Exec(sql);indexed.Exec(sql);equal(count);};
    mutate("UPDATE files SET state='DELETING' WHERE logical_path='/gpu0/a';",1);
    mutate("UPDATE files SET tier='remote',state='COMMITTED' WHERE logical_path='/gpu0/a';",2);
    mutate("UPDATE local_replicas SET state='CREATING' WHERE logical_path='/gpu0/b';",1);
    mutate("UPDATE local_replicas SET state='READY' WHERE logical_path='/gpu0/b';",2);
    mutate("INSERT INTO files(logical_path,gpu_id,tier,backend_id,physical_path,size_bytes,state,created_at,updated_at) VALUES('/gpu0/c',0,'remote','remote','/remote/c',4096,'COMMITTED',1,1);",3);
    mutate("UPDATE files SET state='COMMITTED' WHERE logical_path='/gpu0/d';",5);
    mutate("DELETE FROM local_replicas WHERE logical_path='/gpu0/c';",4);
  }
  static void indexed_precheck_eligibility(const fs::path& root) {
    assert(!Config{}.indexed_shared_precheck);
    for(int mode=0;mode<9;++mode) {
      auto cfg=PrecheckConfig(root/std::to_string(mode));cfg.indexed_shared_precheck=true;
      if(mode==1)cfg.measured_static_reuse_value=true;
      if(mode==2)cfg.shared_caller_only=true;
      if(mode==3)cfg.measured_joint_admission=false;
      if(mode==4)cfg.indexed_shared_precheck=false;
      if(mode==5)cfg.precheck_shared_submission=false;
      if(mode==6) {cfg.measured_policy=false;cfg.shared_value_placement=false;cfg.shared_pool_cache=true;
        cfg.adaptive_reuse_control=false;cfg.compact_measured_planning=false;cfg.measured_burst_reuse=false;}
      if(mode==7) {fs::create_directories(cfg.gpus[0].local_root);std::ofstream(cfg.gpus[0].local_root/"old")<<'x';}
      if(mode==8) {MetadataStore old(cfg.metadata_db);old.Open();LocalReplica r;r.logical_path="/gpu0/orphan";
        r.gpu_id=0;r.physical_path=cfg.gpus[0].local_root/"absent";r.state="READY";old.UpsertLocalReplica(r);}
      TokenFS filesystem(cfg);filesystem.Init();const bool enabled=mode<4;
      assert(filesystem.submission_precheck_ready_==(mode<5));
      assert(PrecheckIndexCount(filesystem.metadata_)==(enabled?2:0));
      filesystem.FlushBufferedMetrics();TelemetryProbe probe(cfg.metadata_db);
      assert(probe.Metric("submission_precheck_index_enabled")==uint64_t(enabled));
      assert(probe.Metric("submission_precheck_index_fallback")==0);
    }
    // Disabling a flag is not a schema migration: old indexes and rows survive.
    auto cfg=PrecheckConfig(root/"restart");cfg.indexed_shared_precheck=true;
    {TokenFS filesystem(cfg);filesystem.Init();assert(PrecheckIndexCount(filesystem.metadata_)==2);
      FileMeta m;m.logical_path="/gpu0/keep";m.gpu_id=0;m.tier="remote";m.state="COMMITTED";m.size_bytes=17;
      filesystem.metadata_.Upsert(m);}
    cfg.indexed_shared_precheck=false;cfg.precheck_shared_submission=false;
    TokenFS restarted(cfg);restarted.Init();assert(!restarted.submission_precheck_ready_);
    assert(PrecheckIndexCount(restarted.metadata_)==2 && restarted.metadata_.Get("/gpu0/keep")->size_bytes==17);
  }
  static void indexed_precheck_setup_failure(const fs::path& root) {
    for(int mode=0;mode<3;++mode) {
      auto cfg=PrecheckConfig(root/std::to_string(mode));cfg.indexed_shared_precheck=true;
      {MetadataStore old(cfg.metadata_db);old.Open();
        if(mode==0)old.Exec("CREATE TABLE idx_replicas_shared_precheck_ready(value TEXT);");
        if(mode==1)old.Exec("CREATE INDEX idx_files_shared_precheck_local ON files(logical_path);");
        if(mode==2) {
          assert(old.CreateSharedPrecheckIndexes());
          old.Exec("DROP INDEX idx_replicas_shared_precheck_ready;");
          old.Exec("CREATE INDEX idx_replicas_shared_precheck_ready ON local_replicas(physical_path);");
        }
      }
      TokenFS filesystem(cfg);filesystem.Init();assert(filesystem.submission_precheck_ready_);
      assert(sqlite3_get_autocommit(filesystem.metadata_.db_));
      assert(PrecheckIndexCount(filesystem.metadata_)==mode); // New first index rolls back; old schema is kept.
      filesystem.FlushBufferedMetrics();TelemetryProbe probe(cfg.metadata_db);
      assert(probe.Metric("submission_precheck_index_enabled")==0 && probe.Metric("submission_precheck_index_fallback")==1);
      if(mode==0)probe.Exec("INSERT INTO idx_replicas_shared_precheck_ready VALUES('preserved');");
      FileMeta m;m.logical_path="/gpu0/fallback";m.gpu_id=0;m.tier="local";m.state="COMMITTED";
      m.physical_path=cfg.gpus[0].local_root/"fallback";m.size_bytes=4096;filesystem.metadata_.Upsert(m);
      assert(ResidentRows(filesystem.metadata_).size()==1); // Original query and later transactions still work.
    }
    // A real authorizer fault can deny both a DDL and rollback. Such an
    // unrecoverable transaction must escape InitializeSubmissionPrecheck.
    auto cfg=PrecheckConfig(root/"rollback-denied");cfg.indexed_shared_precheck=true;
    TokenFS filesystem(cfg);filesystem.Init();
    filesystem.metadata_.Exec("DROP INDEX idx_files_shared_precheck_local;");
    filesystem.metadata_.Exec("DROP INDEX idx_replicas_shared_precheck_ready;");
    assert(sqlite3_set_authorizer(filesystem.metadata_.db_,[](void*,int action,const char* one,const char*,const char*,const char*) {
      if(action==SQLITE_CREATE_INDEX && one && std::string(one)=="idx_replicas_shared_precheck_ready")return SQLITE_DENY;
      if(action==SQLITE_TRANSACTION && one && std::string(one)=="ROLLBACK")return SQLITE_DENY;
      return SQLITE_OK;
    },nullptr)==SQLITE_OK);
    bool failed=false;try{filesystem.InitializeSubmissionPrecheck();}catch(const std::runtime_error&){failed=true;}
    assert(failed && !sqlite3_get_autocommit(filesystem.metadata_.db_));
    assert(sqlite3_set_authorizer(filesystem.metadata_.db_,nullptr,nullptr)==SQLITE_OK);
    filesystem.metadata_.Exec("ROLLBACK;");assert(PrecheckIndexCount(filesystem.metadata_)==0);
  }
  static void ram_first_routing(const fs::path& root,bool enabled,bool lean) {
    Config cfg;cfg.mount_point=root/"mnt";cfg.metadata_db=root/"state.db";
    cfg.foreground_read_fill=true;cfg.request_read_costs=true;cfg.coalesce_pending_reads=true;
    cfg.retain_read_fill=true;cfg.capture_local_reads=true;cfg.ram_first_routing=enabled;
    cfg.read_fill_buffer_bytes=4096;cfg.readonly_canonical=true;cfg.peer_cache_reads=true;
    cfg.shared_pool_cache=true;cfg.checksum="fnv1a64";cfg.affinity_placement=false;
    cfg.lean_read_accounting=lean;cfg.measured_track_affinity=true;
    cfg.read_through_cache=true;cfg.read_through_min_reads=1000;cfg.local_eviction_policy="sieve";
    cfg.gpus.push_back({0,"/gpu0",root/"local",8192,"remote"});
    cfg.gpus.push_back({1,"/gpu1",root/"peer",8192,"remote"});
    cfg.backends.emplace("remote",BackendConfig{"remote","directory",root/"remote"});
    TokenFS filesystem(cfg);filesystem.Init();
    const auto source=root/"remote/gpu0/k",peer=root/"peer/k";
    const std::string payload(4096,'r');std::ofstream(source)<<payload;std::ofstream(peer)<<payload;
    FileMeta meta;meta.logical_path="/gpu0/k";meta.gpu_id=0;meta.tier="remote";meta.backend_id="remote";
    meta.physical_path=source;meta.has_remote_copy=true;meta.size_bytes=payload.size();meta.state="COMMITTED";
    filesystem.metadata_.Upsert(meta);
    LocalReplica replica;replica.logical_path=meta.logical_path;replica.gpu_id=1;
    replica.physical_path=peer;replica.size_bytes=payload.size();replica.state="READY";
    replica.last_access_at=7;replica.created_at=7;filesystem.metadata_.UpsertLocalReplica(replica);
    filesystem.sieve_.Ready(1,meta.logical_path);
    filesystem.sieve_.Ready(1,"/gpu0/cold-peer");
    int source_fd=open(source.c_str(),O_RDONLY);assert(source_fd>=0);
    auto fill=filesystem.fills_.Acquire(meta.logical_path,source_fd,payload.size());
    assert(fill && fill->Append(0,payload.data(),payload.size(),source_fd));close(source_fd);
    filesystem.fills_.Retain(fill);fill.reset();
    auto read=[&](const char* expected_tier,char expected) {
      fuse_file_info fi{};fi.flags=O_RDONLY;char bytes[4096];
      assert(filesystem.Open(meta.logical_path.c_str(),&fi)==0);
      assert(filesystem.FindHandle(&fi)->tier==expected_tier);
      assert(filesystem.Read(meta.logical_path.c_str(),bytes,sizeof(bytes),0,&fi)==4096);
      assert(std::string(bytes,sizeof(bytes))==std::string(4096,expected));
      assert(filesystem.Release(meta.logical_path.c_str(),&fi)==0);
    };
    read("inflight",'r');read("inflight",'r');
    // Upper-tier service must preserve the same SIEVE visited bit as the
    // legacy route, without fabricating a peer data read or disk timestamp.
    assert(filesystem.sieve_.Victim(1,{meta.logical_path,"/gpu0/cold-peer"})=="/gpu0/cold-peer");
    assert(filesystem.metadata_.Get(meta.logical_path)->read_count==2);
    assert(filesystem.measured_.Frequency(0,meta.logical_path)==2);
    const auto touched=filesystem.metadata_.GetLocalReplica(meta.logical_path,1)->last_access_at;
    assert(enabled?touched==7:touched!=7);
    sqlite3* db=nullptr;assert(sqlite3_open(cfg.metadata_db.c_str(),&db)==SQLITE_OK);
    auto metric=[&](const char* name){sqlite3_stmt* st=nullptr;
      assert(sqlite3_prepare_v2(db,"SELECT value FROM metrics WHERE name=?",-1,&st,nullptr)==SQLITE_OK);
      sqlite3_bind_text(st,1,name,-1,SQLITE_TRANSIENT);const int rc=sqlite3_step(st);
      const uint64_t n=rc==SQLITE_ROW?sqlite3_column_int64(st,0):0;sqlite3_finalize(st);return n;};
    assert(metric("read_open_count")==2 && metric("inflight_read_open_count")==2);
    assert(metric("peer_cache_hit")==uint64_t(enabled?0:2));
    assert(metric("cross_gpu_local_replica_hit")==0);
    assert(metric("replica_touch_batched")==uint64_t(!enabled && lean?2:0));
    assert(metric("ram_first_routing_hit")==uint64_t(enabled?2:0));
    assert(metric("sieve_ram_logical_hit")==uint64_t(enabled?2:0));
    // A changed canonical identity must invalidate the old RAM capture, then
    // use the ordinary validated disk path. The peer is updated by the fixture.
    std::ofstream(root/"replacement")<<std::string(4096,'s');fs::rename(root/"replacement",source);
    std::ofstream(peer,std::ios::trunc)<<std::string(4096,'s');read("local",'s');
    assert(filesystem.metadata_.Get(meta.logical_path)->read_count==3);
    assert(filesystem.measured_.Frequency(0,meta.logical_path)==3);
    assert(metric("peer_cache_hit")==uint64_t(enabled?1:3));
    assert(metric("retained_capture_hit")==2 && metric("local_read_open_count")==1);
    assert(filesystem.fills_.PeakBytes()<=4096);
    fuse_file_info writable{};writable.flags=O_RDWR;
    assert(filesystem.Open(meta.logical_path.c_str(),&writable)==-EROFS);
    assert(filesystem.metadata_.Get(meta.logical_path)->read_count==3);
    sqlite3_close(db);
    auto invalid=cfg;invalid.ram_first_routing=true;invalid.retain_read_fill=false;bool rejected=false;
    try{TokenFS bad(invalid);bad.Init();}catch(const std::runtime_error&){rejected=true;}assert(rejected);
    invalid=cfg;invalid.private_cache_domains=true;rejected=false;
    try{TokenFS bad(invalid);bad.Init();}catch(const std::runtime_error&){rejected=true;}assert(rejected);
  }
  static void sieve_ram_permissions(const fs::path& root) {
    Config cfg;cfg.mount_point=root/"mnt";cfg.metadata_db=root/"state.db";
    cfg.readonly_canonical=true;cfg.peer_cache_reads=true;cfg.local_eviction_policy="sieve";
    for(int gpu=0;gpu<3;++gpu)cfg.gpus.push_back({gpu,"/gpu"+std::to_string(gpu),root/("local"+std::to_string(gpu)),8192,"remote"});
    cfg.backends.emplace("remote",BackendConfig{"remote","directory",root/"remote"});
    TokenFS filesystem(cfg);filesystem.Init();
    auto resident=[&](int domain,const std::string& key,const std::string& state="READY",bool indexed=true) {
      LocalReplica replica;replica.logical_path=key;replica.gpu_id=domain;replica.state=state;
      replica.physical_path=root/("local"+std::to_string(domain))/fs::path(key).filename();
      replica.size_bytes=1;replica.created_at=7;replica.last_access_at=7;
      fs::create_directories(replica.physical_path.parent_path());std::ofstream(replica.physical_path)<<'x';
      filesystem.metadata_.UpsertLocalReplica(replica);
      if(indexed)filesystem.sieve_.Ready(domain,key);
      filesystem.sieve_.Ready(domain,key+"-cold");
    };
    auto victim=[&](int domain,const std::string& key){return filesystem.sieve_.Victim(domain,{key,key+"-cold"});};
    resident(1,"/gpu0/peer");
    assert(filesystem.HitSieveLogicalResident("/gpu0/peer",0,0,false));
    assert(victim(1,"/gpu0/peer")=="/gpu0/peer-cold");
    resident(1,"/gpu0/no-peer");filesystem.config_.peer_cache_reads=false;
    assert(!filesystem.HitSieveLogicalResident("/gpu0/no-peer",0,0,false));
    assert(victim(1,"/gpu0/no-peer")=="/gpu0/no-peer");filesystem.config_.peer_cache_reads=true;
    resident(1,"/gpu0/private");filesystem.config_.private_cache_domains=true;
    assert(!filesystem.HitSieveLogicalResident("/gpu0/private",0,0,false));
    assert(victim(1,"/gpu0/private")=="/gpu0/private");
    filesystem.sieve_.Ready(0,"/gpu0/owner-private");filesystem.sieve_.Ready(0,"/gpu0/owner-private-cold");
    assert(!filesystem.HitSieveLogicalResident("/gpu0/owner-private",0,2,true));
    assert(victim(0,"/gpu0/owner-private")=="/gpu0/owner-private");
    resident(2,"/gpu0/caller-private");
    assert(filesystem.HitSieveLogicalResident("/gpu0/caller-private",0,2,false));
    assert(victim(2,"/gpu0/caller-private")=="/gpu0/caller-private-cold");
    filesystem.config_.private_cache_domains=false;
    resident(2,"/gpu0/priority");filesystem.sieve_.Ready(0,"/gpu0/priority");filesystem.sieve_.Ready(0,"/gpu0/priority-cold");
    assert(filesystem.HitSieveLogicalResident("/gpu0/priority",0,2,true));
    assert(victim(2,"/gpu0/priority")=="/gpu0/priority-cold");
    assert(victim(0,"/gpu0/priority")=="/gpu0/priority");
    resident(1,"/gpu0/not-ready","CREATING");
    assert(!filesystem.HitSieveLogicalResident("/gpu0/not-ready",0,0,false));
    assert(victim(1,"/gpu0/not-ready")=="/gpu0/not-ready");
    resident(1,"/gpu0/not-published","READY",false);
    assert(!filesystem.HitSieveLogicalResident("/gpu0/not-published",0,0,false));
    resident(9,"/gpu0/unknown");
    assert(!filesystem.HitSieveLogicalResident("/gpu0/unknown",0,0,false));
    assert(victim(9,"/gpu0/unknown")=="/gpu0/unknown");
    assert(!filesystem.HitSieveLogicalResident("/gpu0/peer",0,9,false));
  }
  static void aligned_tail_reads(const fs::path& root,bool enabled) {
    Config cfg;cfg.mount_point=root/"mnt";cfg.metadata_db=root/"state.db";
    cfg.readonly_canonical=true;cfg.backend_direct_io=true;cfg.reuse_direct_read_tail=enabled;
    cfg.request_read_costs=true;
    cfg.gpus.push_back({0,"/gpu0",root/"local",8192,"remote"});
    cfg.backends.emplace("remote",BackendConfig{"remote","directory",root/"remote"});
    TokenFS filesystem(cfg);filesystem.Init();
    std::string payload(8192,'\0');for(size_t i=0;i<payload.size();++i)payload[i]=char(i%251);
    std::ofstream(root/"remote/gpu0/k",std::ios::binary).write(payload.data(),payload.size());
    fuse_file_info fi{};fi.flags=O_RDONLY;assert(filesystem.Open("/gpu0/k",&fi)==0);
    char bytes[4096];size_t offset=0;
    for(size_t amount:{4048u,48u,4048u,48u,4096u}) {
      const int n=filesystem.Read("/gpu0/k",bytes,amount,offset,&fi);
      assert(n>=0 && size_t(n)==std::min(amount,payload.size()-offset));
      assert(std::string(bytes,size_t(n))==payload.substr(offset,size_t(n)));offset+=size_t(n);
    }
    assert(filesystem.Release("/gpu0/k",&fi)==0 && filesystem.direct_read_tail_handles_==0);
    sqlite3* db=nullptr;assert(sqlite3_open(cfg.metadata_db.c_str(),&db)==SQLITE_OK);
    auto metric=[&](const char* name){sqlite3_stmt* st=nullptr;
      assert(sqlite3_prepare_v2(db,"SELECT value FROM metrics WHERE name=?",-1,&st,nullptr)==SQLITE_OK);
      sqlite3_bind_text(st,1,name,-1,SQLITE_TRANSIENT);const int rc=sqlite3_step(st);
      const uint64_t n=rc==SQLITE_ROW?sqlite3_column_int64(st,0):0;sqlite3_finalize(st);return n;};
    assert(metric("read_bytes")==8192 && metric("read_ops")==5);
    assert(metric("request_cost_remote_samples")==1 && metric("request_cost_remote_bytes")==8192);
    assert(metric("direct_backend_pread_ops")==uint64_t(enabled?3:5));
    assert(metric("direct_backend_pread_bytes")==uint64_t(enabled?8192:16384));
    assert(metric("direct_read_tail_hits")==uint64_t(enabled?2:0));
    assert(metric("direct_read_tail_bytes")==uint64_t(enabled?96:0));
    assert(metric("direct_read_tail_buffer_bytes_peak")==uint64_t(enabled?4096:0));
    assert(metric("read_release_count")==1);
    assert(filesystem.Release("/gpu0/k",&fi)==0 && metric("read_release_count")==1);
    sqlite3_close(db);
  }
  static void background_metric_fence(const fs::path& root,bool batched) {
    Config cfg;cfg.mount_point=root/"mnt";cfg.metadata_db=root/"state.db";
    cfg.batch_background_metrics=batched;
    TokenFS filesystem(cfg);filesystem.Init();
    sqlite3* db=nullptr;assert(sqlite3_open(cfg.metadata_db.c_str(),&db)==SQLITE_OK);
    auto metric=[&](const char* name){
      sqlite3_stmt* stmt=nullptr;assert(sqlite3_prepare_v2(db,"SELECT value FROM metrics WHERE name=?",-1,&stmt,nullptr)==SQLITE_OK);
      sqlite3_bind_text(stmt,1,name,-1,SQLITE_TRANSIENT);const int rc=sqlite3_step(stmt);
      uint64_t value=rc==SQLITE_ROW?sqlite3_column_int64(stmt,0):0;sqlite3_finalize(stmt);return value;
    };
    for(int pass=1;pass<=3;++pass) {
      assert(filesystem.SubmitBackground([&]{filesystem.AddBackgroundMetric("fence_value",7);}));
      const auto limit=std::chrono::steady_clock::now()+std::chrono::seconds(3);
      while(metric("background_completed")<uint64_t(pass)) {
        assert(std::chrono::steady_clock::now()<limit);std::this_thread::yield();
      }
      // A durable completion must never get ahead of its batched counters.
      assert(metric("fence_value")==uint64_t(pass*7));
    }
    assert(metric("background_error_count")==0);sqlite3_close(db);
  }
  static void telemetry_retry_and_release_lock(const fs::path& root) {
    Config cfg;cfg.mount_point=root/"mnt";cfg.metadata_db=root/"state.db";
    cfg.batch_background_metrics=true;cfg.batch_policy_events=true;
    cfg.request_read_costs=true;cfg.readonly_canonical=true;
    cfg.gpus.push_back({0,"/gpu0",root/"local",8192,"remote"});
    cfg.backends.emplace("remote",BackendConfig{"remote","directory",root/"remote"});
    TokenFS filesystem(cfg);filesystem.Init();
    sqlite3* db=nullptr;assert(sqlite3_open(cfg.metadata_db.c_str(),&db)==SQLITE_OK);
    auto exec=[&](const char* sql){assert(sqlite3_exec(db,sql,nullptr,nullptr,nullptr)==SQLITE_OK);};
    auto events=[&]{std::vector<std::string> out;sqlite3_stmt* st=nullptr;
      assert(sqlite3_prepare_v2(db,"SELECT action FROM policy_events ORDER BY seq",-1,&st,nullptr)==SQLITE_OK);
      while(sqlite3_step(st)==SQLITE_ROW)out.emplace_back(reinterpret_cast<const char*>(sqlite3_column_text(st,0)));
      sqlite3_finalize(st);return out;};
    exec("CREATE TRIGGER reject_event BEFORE INSERT ON policy_events WHEN NEW.action='reject' BEGIN SELECT RAISE(ABORT,'injected'); END;");
    filesystem.AddBufferedMetric("retry_delta",7);filesystem.SetBufferedMetricMax("retry_peak",9);
    filesystem.RecordPolicyEvent("first","/gpu0/k",0,4096,"test",-3.5);
    filesystem.RecordPolicyEvent("reject","/gpu0/k",0,4096,"test");
    bool failed=false;try{filesystem.FlushBufferedMetrics(1);}catch(const std::runtime_error&){failed=true;}
    assert(failed && events().empty());
    assert(filesystem.buffered_metrics_.at("retry_delta")==7);
    assert(filesystem.buffered_metric_max_.at("retry_peak")==9);
    assert(filesystem.buffered_metrics_["background_completed"]==0);
    filesystem.RecordPolicyEvent("newer","/gpu0/k",0,4096,"test");
    exec("DROP TRIGGER reject_event;");filesystem.FlushBufferedMetrics();filesystem.FlushBufferedMetrics();
    assert((events()==std::vector<std::string>{"first","reject","newer"}));
    // Completion is durable only after the event batch, for the real worker.
    assert(filesystem.SubmitBackground([&]{filesystem.RecordPolicyEvent("background","/gpu0/k",0,0,"test");}));
    const auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(3);
    while(true) {
      sqlite3_stmt* st=nullptr;assert(sqlite3_prepare_v2(db,"SELECT value FROM metrics WHERE name='background_completed'",-1,&st,nullptr)==SQLITE_OK);
      const bool done=sqlite3_step(st)==SQLITE_ROW && sqlite3_column_int64(st,0)==1;sqlite3_finalize(st);
      if(done)break;assert(std::chrono::steady_clock::now()<deadline);std::this_thread::yield();
    }
    assert(events().back()=="background");
    std::ofstream(root/"remote/gpu0/k")<<std::string(4096,'x');
    fuse_file_info fi{};fi.flags=O_RDONLY;char bytes[2048];
    assert(filesystem.Open("/gpu0/k",&fi)==0);
    assert(filesystem.Read("/gpu0/k",bytes,sizeof(bytes),0,&fi)==2048);
    // Hold the telemetry fence. A partial read accounts its sample in Release;
    // after that marker, the handle table must become available even though
    // Release is still waiting for this fence. The old implementation fails.
    std::unique_lock<std::mutex> fence(filesystem.flush_metrics_mu_);
    auto released=std::async(std::launch::async,[&]{return filesystem.Release("/gpu0/k",&fi);});
    const auto until=std::chrono::steady_clock::now()+std::chrono::seconds(3);
    bool accounted=false;
    while(!accounted) {
      {std::lock_guard<std::mutex> lock(filesystem.buffered_metrics_mu_);accounted=filesystem.buffered_metrics_["request_cost_remote_samples"]==1;}
      assert(std::chrono::steady_clock::now()<until);std::this_thread::yield();
    }
    while(!filesystem.handles_mu_.try_lock()) {assert(std::chrono::steady_clock::now()<until);std::this_thread::yield();}
    assert(filesystem.handles_.empty());filesystem.handles_mu_.unlock();
    assert(released.wait_for(std::chrono::milliseconds(0))==std::future_status::timeout);
    fence.unlock();assert(released.get()==0);sqlite3_close(db);
  }
  static void inflight_reads(const fs::path& root,bool enabled,bool retained=false) {
    Config cfg;cfg.mount_point=root/"mnt";cfg.metadata_db=root/"state.db";
    cfg.foreground_read_fill=true;cfg.request_read_costs=true;cfg.coalesce_pending_reads=enabled;cfg.retain_read_fill=retained;cfg.capture_local_reads=retained;cfg.read_fill_buffer_bytes=4096;cfg.batch_background_metrics=true;
    cfg.readonly_canonical=true;cfg.peer_cache_reads=true;cfg.shared_pool_cache=true;cfg.checksum="fnv1a64";
    cfg.backend_direct_io=true;cfg.affinity_placement=false;cfg.lean_read_accounting=true;
    cfg.read_through_cache=true;cfg.read_through_min_reads=1;cfg.local_eviction_policy="sieve";
    cfg.gpus.push_back({0,"/gpu0",root/"local",8192,"remote"});
    cfg.backends.emplace("remote",BackendConfig{"remote","directory",root/"remote"});
    TokenFS filesystem(cfg);filesystem.Init();
    std::ofstream(root/"remote/gpu0/k")<<std::string(4096,'z');
    // Deterministically put placement behind a barrier, without sleeps or
    // changing the production state machine. The next open must stay correct
    // before READY, after READY, and while its own memory pin remains live.
    std::promise<void> started,proceed;auto started_f=started.get_future();
    auto proceed_f=proceed.get_future().share();
    assert(filesystem.SubmitBackground([&]{started.set_value();proceed_f.wait();}));started_f.wait();
    fuse_file_info a{},b{},c{};a.flags=b.flags=c.flags=O_RDONLY;char bytes[4096]{};
    assert(filesystem.Open("/gpu0/k",&a)==0);
    assert(filesystem.Read("/gpu0/k",bytes,4096,0,&a)==4096);
    assert(filesystem.Release("/gpu0/k",&a)==0);
    assert(filesystem.metadata_.Get("/gpu0/k")->tier=="remote");
    assert(filesystem.Open("/gpu0/k",&b)==0);
    assert(filesystem.FindHandle(&b)->tier==(enabled?"inflight":"remote"));
    assert(filesystem.Read("/gpu0/k",bytes,2048,0,&b)==2048);
    assert(filesystem.Read("/gpu0/k",bytes+2048,2048,2048,&b)==2048);
    assert(std::string(bytes,4096)==std::string(4096,'z'));
    assert(filesystem.Read("/gpu0/k",bytes,4096,4096,&b)==0);
    assert(filesystem.metadata_.Get("/gpu0/k")->tier=="remote");
    proceed.set_value();std::promise<void> drained;auto drained_f=drained.get_future();
    assert(filesystem.SubmitBackground([&]{drained.set_value();}));drained_f.wait();
    assert(filesystem.metadata_.Get("/gpu0/k")->tier=="local");
    assert(filesystem.Open("/gpu0/k",&c)==0 && filesystem.FindHandle(&c)->tier==(retained?"inflight":"local"));
    assert(filesystem.Read("/gpu0/k",bytes,4096,0,&c)==4096);
    assert(filesystem.Release("/gpu0/k",&c)==0);
    if(enabled)assert(filesystem.fills_.UsedBytes()==4096);
    assert(filesystem.Release("/gpu0/k",&b)==0 && filesystem.fills_.UsedBytes()==(retained?4096:0));
    sqlite3* conn=nullptr;assert(sqlite3_open(cfg.metadata_db.c_str(),&conn)==SQLITE_OK);
    sqlite3_stmt* stmt=nullptr;assert(sqlite3_prepare_v2(conn,"SELECT name,value FROM metrics",-1,&stmt,nullptr)==SQLITE_OK);
    std::map<std::string,uint64_t> m;
    while(sqlite3_step(stmt)==SQLITE_ROW)m[reinterpret_cast<const char*>(sqlite3_column_text(stmt,0))]=sqlite3_column_int64(stmt,1);
    sqlite3_finalize(stmt);sqlite3_close(conn);
    assert(m["read_bytes"]==12288 && m["read_local_bytes"]==(retained?0:4096));
    assert(m["read_remote_bytes"]==(enabled?4096:8192) && m["read_inflight_bytes"]==(enabled?(retained?8192:4096):0));
    assert(m["request_cost_inflight_samples"]==(enabled?(retained?2:1):0));
    if(retained) {
      std::ofstream(root/"remote/gpu0/pressure")<<std::string(4096,'p');
      int pressure=open((root/"remote/gpu0/pressure").c_str(),O_RDONLY);
      auto pin=filesystem.fills_.Acquire("pressure",pressure,4096);assert(pin);pin.reset();close(pressure);
      fuse_file_info local{},ram{};local.flags=ram.flags=O_RDONLY;
      assert(filesystem.Open("/gpu0/k",&local)==0 && filesystem.FindHandle(&local)->tier=="local");
      assert(filesystem.Read("/gpu0/k",bytes,4096,0,&local)==4096);
      assert(filesystem.Release("/gpu0/k",&local)==0);
      assert(filesystem.Open("/gpu0/k",&ram)==0 && filesystem.FindHandle(&ram)->tier=="inflight");
      assert(filesystem.Read("/gpu0/k",bytes,4096,0,&ram)==4096 && std::string(bytes,4096)==std::string(4096,'z'));
      assert(filesystem.Release("/gpu0/k",&ram)==0);
      assert(filesystem.shared_placement_inflight_.empty());
    }
    auto invalid=cfg;invalid.shared_caller_only=true;bool rejected=false;
    try{TokenFS bad(invalid);bad.Init();}catch(const std::runtime_error&){rejected=true;}assert(rejected);
    invalid=cfg;invalid.foreground_read_fill=false;invalid.coalesce_pending_reads=true;rejected=false;
    try{TokenFS bad(invalid);bad.Init();}catch(const std::runtime_error&){rejected=true;}assert(rejected);
  }
  static void retained_rejected(const fs::path& root) {
    Config cfg;cfg.mount_point=root/"mnt";cfg.metadata_db=root/"state.db";
    cfg.foreground_read_fill=true;cfg.request_read_costs=true;cfg.coalesce_pending_reads=true;cfg.retain_read_fill=true;
    cfg.readonly_canonical=true;cfg.peer_cache_reads=true;cfg.shared_pool_cache=true;cfg.checksum="fnv1a64";
    cfg.backend_direct_io=true;cfg.affinity_placement=false;cfg.lean_read_accounting=true;
    cfg.read_through_cache=true;cfg.read_through_min_reads=1000;cfg.local_eviction_policy="sieve";
    cfg.gpus.push_back({0,"/gpu0",root/"local",8192,"remote"});
    cfg.backends.emplace("remote",BackendConfig{"remote","directory",root/"remote"});
    TokenFS filesystem(cfg);filesystem.Init();std::ofstream(root/"remote/gpu0/k")<<std::string(4096,'q');
    for(int i=0;i<3;++i) {
      fuse_file_info fi{};fi.flags=O_RDONLY;char bytes[4096]{};
      assert(filesystem.Open("/gpu0/k",&fi)==0);
      assert(filesystem.FindHandle(&fi)->tier==(i?"inflight":"remote"));
      assert(filesystem.Read("/gpu0/k",bytes,4096,0,&fi)==4096 && std::string(bytes,4096)==std::string(4096,'q'));
      assert(filesystem.Release("/gpu0/k",&fi)==0);
      assert(filesystem.metadata_.Get("/gpu0/k")->tier=="remote");
      assert(filesystem.shared_placement_inflight_.empty());
    }
    assert(filesystem.fills_.UsedBytes()==4096);
  }
  static void foreground_fill(const fs::path& root,int threshold,bool adaptive=false,bool incremental=false) {
    Config cfg;cfg.mount_point=root/"mnt";cfg.metadata_db=root/"state.db";
    cfg.incremental_copy_cost=incremental;cfg.batch_background_metrics=true;
    cfg.foreground_read_fill=true;cfg.request_read_costs=true;cfg.readonly_canonical=true;cfg.peer_cache_reads=true;
    cfg.shared_pool_cache=!adaptive;cfg.shared_value_placement=adaptive;cfg.checksum="fnv1a64";
    cfg.backend_direct_io=true;cfg.affinity_placement=false;cfg.lean_read_accounting=true;
    cfg.speculative_copy_may_evict=true;cfg.local_eviction_policy=adaptive?"value_aware":"sieve";
    cfg.read_through_cache=!adaptive;cfg.read_through_min_reads=threshold;
    cfg.measured_policy=adaptive;cfg.measured_causal_window=adaptive;cfg.compact_measured_planning=adaptive;
    cfg.measured_burst_reuse=adaptive;cfg.adaptive_reuse_control=adaptive;
    cfg.gpus.push_back({0,"/gpu0",root/"local",8192,"remote"});
    cfg.gpus.push_back({1,"/gpu1",root/"peer",8192,"remote"});
    cfg.backends.emplace("remote",BackendConfig{"remote","directory",root/"remote"});
    TokenFS filesystem(cfg);filesystem.Init();
    if(adaptive){filesystem.measured_.ReadSample(false,4096,1000000);filesystem.measured_.ReadSample(true,4096,1);filesystem.measured_.CopySample(4096,10);}
    auto drain=[&]{std::promise<void> done;auto ready=done.get_future();assert(filesystem.SubmitBackground([&]{done.set_value();}));ready.wait();};
    for(const std::string key:{"full","partial","reordered","oversize"}) {
      const size_t size=key=="oversize"?12288:4096;
      std::ofstream(root/"remote/gpu0"/key)<<std::string(size,'k');
      for(int pass=0;pass<threshold;++pass) {
        const auto path="/gpu0/"+key;fuse_file_info fi{};fi.flags=O_RDONLY;
        assert(filesystem.Open(path.c_str(),&fi)==0);
        char bytes[12288];
        if(key=="partial")assert(filesystem.Read(path.c_str(),bytes,1024,0,&fi)==1024);
        else if(key=="reordered")assert(filesystem.Read(path.c_str(),bytes,2048,2048,&fi)==2048);
        else {
          assert(filesystem.Read(path.c_str(),bytes,size/2,0,&fi)==int(size/2));
          assert(filesystem.metadata_.Get(path)->tier=="remote"); // No partial READY.
          assert(filesystem.Read(path.c_str(),bytes,size/2,size/2,&fi)==int(size/2));
        }
        assert(filesystem.Release(path.c_str(),&fi)==0);drain();
        auto meta=*filesystem.metadata_.Get(path);
        auto peer=filesystem.ReadablePeer(path,-1);
        if(pass+1<threshold || key=="oversize")assert(meta.tier=="remote" && !peer);
        else {assert(meta.tier=="local" || peer);assert(filesystem.ChecksumFile(meta.tier=="local"?meta.physical_path:peer->physical_path)==filesystem.ChecksumFile(root/"remote/gpu0"/key));}
        assert(filesystem.fills_.UsedBytes()==0);
      }
    }
    // Both destination types use the same verified capture, including peer READY.
    auto source=root/"remote/gpu0/peerfill";std::ofstream(source)<<std::string(4096,'p');
    int fd=open(source.c_str(),O_RDONLY);auto fill=filesystem.fills_.Acquire("/gpu0/peerfill",fd,4096);
    assert(fill && fill->Append(0,std::string(4096,'p').data(),4096,fd));close(fd);
    FileMeta meta;meta.logical_path="/gpu0/peerfill";meta.gpu_id=0;meta.tier="remote";
    meta.physical_path=source;meta.has_remote_copy=true;meta.size_bytes=4096;meta.state="COMMITTED";
    filesystem.metadata_.Upsert(meta);
    filesystem.CreateCrossGpuReplica(cfg.gpus[1],cfg.gpus[0],"peerfill",meta,fill);
    auto peer=filesystem.metadata_.GetLocalReplica(meta.logical_path,1);assert(peer && peer->state=="READY");
    assert(filesystem.ChecksumFile(peer->physical_path)==filesystem.ChecksumFile(source));
    auto tmp=root/"manual-copy";std::error_code ec;
    assert(filesystem.CopyOrFill(source,tmp,4096,fill,ec) && !ec);
    std::ofstream(tmp,std::ios::binary|std::ios::trunc)<<"corruption";
    assert(filesystem.ChecksumFile(tmp)!=std::optional<std::string>(fill->Checksum()));
    std::ofstream(root/"replacement")<<std::string(4096,'q');fs::rename(root/"replacement",source);
    ec.clear();assert(!filesystem.CopyOrFill(source,tmp,4096,fill,ec) && !ec);
    assert(filesystem.ChecksumFile(tmp)==filesystem.ChecksumFile(source));
    if(adaptive) {
      filesystem.FlushBufferedMetrics();
      sqlite3* conn=nullptr;assert(sqlite3_open(cfg.metadata_db.c_str(),&conn)==SQLITE_OK);
      sqlite3_stmt* stmt=nullptr;assert(sqlite3_prepare_v2(conn,"SELECT name,value FROM metrics WHERE name LIKE 'copy_cost_%'",-1,&stmt,nullptr)==SQLITE_OK);
      std::map<std::string,uint64_t> costs;
      while(sqlite3_step(stmt)==SQLITE_ROW)costs[reinterpret_cast<const char*>(sqlite3_column_text(stmt,0))]=sqlite3_column_int64(stmt,1);
      sqlite3_finalize(stmt);sqlite3_close(conn);
      assert(costs["copy_cost_samples"]>0 && costs["copy_cost_remaining_us"]>0);
      assert(costs["copy_cost_full_us"]==costs["copy_cost_remaining_us"]+costs["copy_cost_planning_us"]+costs["copy_cost_capture_us"]);
      assert(costs["copy_cost_charged_us"]==costs[incremental?"copy_cost_remaining_us":"copy_cost_full_us"]);
    }
    auto invalid=cfg;invalid.readonly_canonical=false;bool rejected=false;
    try {TokenFS bad(invalid);bad.Init();}catch(const std::runtime_error&){rejected=true;}assert(rejected);
  }
  static void shared_placement(const fs::path& root,bool compact=false,bool adaptive=false,bool caller_only=false) {
    Config cfg;cfg.mount_point=root/"mnt";cfg.metadata_db=root/"state.db";
    cfg.readonly_canonical=true;cfg.peer_cache_reads=true;cfg.shared_value_placement=true;
    cfg.measured_policy=true;cfg.measured_causal_window=true;cfg.compact_measured_planning=compact;cfg.measured_cost=false;cfg.checksum="fnv1a64";
    cfg.speculative_copy_may_evict=true;
    cfg.adaptive_reuse_control=adaptive;cfg.measured_burst_reuse=adaptive;cfg.measured_cost=adaptive;
    cfg.shared_caller_only=caller_only;
    for(int id=0;id<3;++id)cfg.gpus.push_back({id,"/gpu"+std::to_string(id),root/("local"+std::to_string(id)),1024,"remote"});
    cfg.backends.emplace("remote",BackendConfig{"remote","directory",root/"remote"});
    TokenFS filesystem(cfg);filesystem.Init();
    if(adaptive){filesystem.measured_.ReadSample(false,1024,1000000);filesystem.measured_.ReadSample(true,1024,1);filesystem.measured_.CopySample(1024,20);}
    for(const auto& key:{"hot","incoming"}) {
      auto remote=root/"remote/gpu0"/key;std::ofstream(remote)<<std::string(1024,key[0]);
      FileMeta meta;meta.logical_path=std::string("/gpu0/")+key;meta.gpu_id=0;
      meta.tier="remote";meta.physical_path=remote;meta.backend_id="remote";
      meta.size_bytes=1024;meta.has_remote_copy=true;meta.state="COMMITTED";filesystem.metadata_.Upsert(meta);
    }
    for(int i=0;i<16;++i)filesystem.measured_.Observe(0,"/gpu0/hot",filesystem.MeasuredOptions(),true);
    filesystem.PlaceShared("/gpu0/hot",0);
    assert(filesystem.metadata_.Get("/gpu0/hot")->tier=="local");
    for(int i=0;i<4;++i)filesystem.measured_.Observe(0,"/gpu0/incoming",filesystem.MeasuredOptions(),false);
    filesystem.PlaceShared("/gpu0/incoming",0); // Caller is full: use free peer capacity.
    auto replica=filesystem.metadata_.GetLocalReplica("/gpu0/incoming",1);
    if(caller_only) {
      assert(!replica && !filesystem.metadata_.GetLocalReplica("/gpu0/incoming",2));
      assert(filesystem.metadata_.Get("/gpu0/incoming")->tier=="remote");
      assert(filesystem.metadata_.Get("/gpu0/hot")->tier=="local");
      return;
    }
    assert(replica && replica->state=="READY");
    assert(filesystem.metadata_.Get("/gpu0/hot")->tier=="local");
    assert(filesystem.MarginalCoverage(*filesystem.metadata_.Get("/gpu0/incoming"),1)==1);
    auto copy=*replica;copy.gpu_id=2;copy.physical_path=root/"local2/incoming";
    fs::copy_file(replica->physical_path,copy.physical_path);filesystem.metadata_.UpsertLocalReplica(copy);
    assert(filesystem.MarginalCoverage(*filesystem.metadata_.Get("/gpu0/incoming"),1)==0);
    if(compact) {
      const auto snap=filesystem.SnapshotMeasuredResidents("");
      for(int location:{1,2}) {
        const auto& items=snap.at(location);
        auto item=std::find_if(items.begin(),items.end(),[](const auto& i){return i.key=="/gpu0/incoming";});
        assert(item!=items.end() && item->coverage==0);
      }
    }
    fs::remove(copy.physical_path);filesystem.metadata_.RemoveLocalReplica(copy.logical_path,2);
    filesystem.PlaceShared("/gpu0/incoming",2); // Execution-time coverage prevents duplication.
    assert(!filesystem.metadata_.GetLocalReplica("/gpu0/incoming",2));
    assert(filesystem.MarginalCoverage(*filesystem.metadata_.Get("/gpu0/incoming"),1)==1);
  }
  static void burst_first_read(const fs::path& root) {
    Config cfg;cfg.mount_point=root/"mnt";cfg.metadata_db=root/"state.db";
    cfg.readonly_canonical=true;cfg.peer_cache_reads=true;cfg.shared_value_placement=true;
    cfg.measured_policy=true;cfg.measured_causal_window=true;cfg.compact_measured_planning=true;
    cfg.measured_burst_reuse=true;cfg.checksum="fnv1a64";cfg.speculative_copy_may_evict=true;
    cfg.gpus.push_back({0,"/gpu0",root/"local",1024,"remote"});
    cfg.backends.emplace("remote",BackendConfig{"remote","directory",root/"remote"});
    TokenFS filesystem(cfg);filesystem.Init();
    for(int k=0;k<10;++k)for(int j=0;j<4;++j)filesystem.measured_.Observe(0,"learn"+std::to_string(k),filesystem.MeasuredOptions());
    auto remote=root/"remote/gpu0/new";std::ofstream(remote)<<std::string(1024,'b');
    FileMeta meta;meta.logical_path="/gpu0/new";meta.gpu_id=0;meta.tier="remote";
    meta.backend_id="remote";meta.physical_path=remote;meta.size_bytes=1024;meta.has_remote_copy=true;meta.state="COMMITTED";
    filesystem.metadata_.Upsert(meta);
    filesystem.measured_.Observe(0,meta.logical_path,filesystem.MeasuredOptions());
    filesystem.PlaceShared(meta.logical_path,0);
    assert(filesystem.metadata_.Get(meta.logical_path)->tier=="local");
    assert(fs::file_size(root/"local/new")==1024 && fs::file_size(remote)==1024);
    auto invalid=cfg;invalid.measured_cost=false;bool rejected=false;
    try {TokenFS bad(invalid);bad.Init();}catch(const std::runtime_error&){rejected=true;}
    assert(rejected);
  }
  static void compact_plan_invariants(const fs::path& root) {
    Config cfg;cfg.mount_point=root/"mnt";cfg.metadata_db=root/"state.db";
    cfg.readonly_canonical=true;cfg.measured_policy=true;cfg.measured_causal_window=true;
    cfg.measured_cost=false;cfg.compact_measured_planning=true;cfg.lean_read_accounting=true;
    cfg.affinity_placement=false;cfg.speculative_copy_may_evict=true;
    cfg.gpus.push_back({0,"/gpu0",root/"local",200,"remote"});
    cfg.backends.emplace("remote",BackendConfig{"remote","directory",root/"remote"});
    TokenFS filesystem(cfg);filesystem.Init();
    for(const auto& key:{"a","b","new"}) {
      const auto bytes=std::string(key)=="new"?200:100;
      auto remote=root/"remote/gpu0"/key;std::ofstream(remote)<<std::string(bytes,key[0]);
      FileMeta meta;meta.logical_path=std::string("/gpu0/")+key;meta.gpu_id=0;
      meta.tier=std::string(key)=="new"?"remote":"local";meta.backend_id=meta.tier;
      meta.physical_path=meta.tier=="local"?root/"local"/key:remote;
      if(meta.tier=="local")fs::copy_file(remote,meta.physical_path);
      meta.size_bytes=bytes;meta.has_remote_copy=true;filesystem.metadata_.Upsert(meta);
      for(int i=0;i<(std::string(key)=="new"?10:2);++i) {
        filesystem.measured_.Observe(0,meta.logical_path,filesystem.MeasuredOptions(),true);
        filesystem.metadata_.IncrementReadCount(meta.logical_path,0,70,55,2,10,3,4,2,3,false);
      }
    }
    auto incoming=*filesystem.metadata_.Get("/gpu0/new");
    const auto compact=filesystem.MeasuredPlan(cfg.gpus[0],incoming);
    filesystem.config_.compact_measured_planning=false;
    const auto reference=filesystem.MeasuredPlan(cfg.gpus[0],incoming);
    assert(compact.allowed && compact.victims.size()==2 && compact.victims==reference.victims);
    assert(compact.displaced_us==reference.displaced_us && compact.incoming_us==reference.incoming_us);
    filesystem.config_.compact_measured_planning=true;
    Handle pin;pin.logical_path="/gpu0/a";
    const auto id=filesystem.StoreHandle(pin);
    assert(!filesystem.MeasuredPlan(cfg.gpus[0],incoming).allowed);
    fuse_file_info fi{};fi.fh=id;filesystem.Release("/gpu0/a",&fi);
    assert(filesystem.EnsureLocalCapacity(cfg.gpus[0],200,"/gpu0/new"));
    assert(TokenFS::DirectoryBytes(root/"local")==0);
    assert(filesystem.metadata_.Get("/gpu0/a")->tier=="remote");
    assert(filesystem.metadata_.Get("/gpu0/b")->tier=="remote");
    assert(fs::file_size(root/"remote/gpu0/a")==100 && fs::file_size(root/"remote/gpu0/b")==100);
    // A persisted replica touch belongs to the same read-count transaction.
    LocalReplica replica;replica.logical_path="/gpu0/a";replica.gpu_id=1;
    replica.physical_path=root/"unconfigured";replica.last_access_at=0;
    filesystem.metadata_.UpsertLocalReplica(replica);
    const auto previous=filesystem.metadata_.Get("/gpu0/a")->read_count;
    assert(filesystem.metadata_.IncrementReadCount("/gpu0/a",1,70,55,2,10,3,4,2,3,false,1)==previous+1);
    assert(filesystem.metadata_.GetLocalReplica("/gpu0/a",1)->last_access_at>0);
    // Stale paths and unconfigured locations cannot contribute shared coverage.
    assert(filesystem.SnapshotMeasuredResidents("").empty());
    auto invalid=cfg;invalid.readonly_canonical=false;
    bool rejected=false;try {TokenFS bad(invalid);bad.Init();}catch(const std::runtime_error&){rejected=true;}
    assert(rejected);
    invalid=cfg;invalid.affinity_placement=true;rejected=false;
    try {TokenFS bad(invalid);bad.Init();}catch(const std::runtime_error&){rejected=true;}
    assert(rejected);
  }
  static void stale_advisory_plan(const fs::path& root,bool joint=true) {
    Config cfg;cfg.mount_point=root/"mnt";cfg.metadata_db=root/"state.db";
    cfg.readonly_canonical=true;cfg.peer_cache_reads=true;cfg.shared_value_placement=true;
    cfg.measured_policy=true;cfg.measured_causal_window=true;cfg.compact_measured_planning=true;
    cfg.measured_burst_reuse=true;cfg.adaptive_reuse_control=true;cfg.speculative_copy_may_evict=true;
    cfg.measured_joint_admission=joint;
    cfg.gpus.push_back({0,"/gpu0",root/"local",100,"remote"});
    cfg.backends.emplace("remote",BackendConfig{"remote","directory",root/"remote"});
    TokenFS filesystem(cfg);filesystem.Init();
    auto remote=root/"remote/gpu0/new";std::ofstream(remote)<<std::string(100,'x');
    FileMeta meta;meta.logical_path="/gpu0/new";meta.gpu_id=0;meta.tier="remote";meta.backend_id="remote";
    meta.physical_path=remote;meta.size_bytes=100;meta.has_remote_copy=true;meta.state="COMMITTED";filesystem.metadata_.Upsert(meta);
    filesystem.measured_.Observe(0,meta.logical_path,filesystem.MeasuredOptions());
    auto plan=filesystem.MeasuredPlan(cfg.gpus[0],meta);
    assert(plan.allowed && plan.explore_headroom);
    // New untracked bytes arrive between advisory selection and execution.
    std::ofstream(root/"local/unknown")<<std::string(100,'z');
    assert(!filesystem.EnsureLocalCapacity(cfg.gpus[0],100,meta.logical_path));
    assert(fs::file_size(root/"local/unknown")==100 && fs::file_size(remote)==100);
    auto invalid=cfg;invalid.compact_measured_planning=false;bool rejected=false;
    try {TokenFS bad(invalid);bad.Init();}catch(const std::runtime_error&){rejected=true;}
    assert(rejected);
  }
  static void readable_peer(const fs::path& root) {
    Config cfg; cfg.mount_point=root/"mnt";cfg.metadata_db=root/"peer.db";
    cfg.readonly_canonical=true;cfg.peer_cache_reads=true;
    cfg.gpus.push_back({0,"/gpu0",root/"local0",2048,"remote"});
    cfg.gpus.push_back({1,"/gpu1",root/"local1",2048,"remote"});
    cfg.backends.emplace("remote",BackendConfig{"remote","directory",root/"remote"});
    TokenFS filesystem(cfg);filesystem.Init();
    LocalReplica replica;replica.logical_path="/gpu0/a";replica.gpu_id=1;
    replica.physical_path=root/"local1"/"a";replica.size_bytes=4;
    replica.state="COPYING";std::ofstream(replica.physical_path)<<"data";
    filesystem.metadata_.UpsertLocalReplica(replica);
    assert(!filesystem.ReadablePeer("/gpu0/a",0));
    replica.state="READY";filesystem.metadata_.UpsertLocalReplica(replica);
    assert(filesystem.ReadablePeer("/gpu0/a",0));
    assert(!filesystem.ReadablePeer("/gpu0/a",1));
    int fd=open(filesystem.ReadablePeer("/gpu0/a",0)->physical_path.c_str(),O_RDONLY);
    assert(fd>=0);fs::remove(replica.physical_path);
    assert(!filesystem.ReadablePeer("/gpu0/a",0));
    char bytes[4];assert(pread(fd,bytes,4,0)==4 && std::string(bytes,4)=="data");close(fd);
    cfg.private_cache_domains=true;
    bool rejected=false;try {TokenFS invalid(cfg);invalid.Init();} catch(const std::runtime_error&) {rejected=true;}
    assert(rejected);
    cfg.private_cache_domains=false;cfg.readonly_canonical=false;
    rejected=false;try {TokenFS invalid(cfg);invalid.Init();} catch(const std::runtime_error&) {rejected=true;}
    assert(rejected);
  }
  static void sieve_verified_residents(const fs::path& root) {
    Config cfg; cfg.mount_point=root/"mnt";cfg.metadata_db=root/"sieve.db";
    cfg.local_eviction_policy="sieve";cfg.checksum="fnv1a64";cfg.readonly_canonical=true;cfg.speculative_copy_may_evict=true;
    cfg.gpus.push_back({0,"/gpu0",root/"local0",2048,"remote"});
    cfg.gpus.push_back({1,"/gpu1",root/"local1",2048,"remote"});
    cfg.backends.emplace("remote",BackendConfig{"remote","directory",root/"remote"});
    TokenFS filesystem(cfg);filesystem.Init();
    for(const auto& key:{"a","b","c"}) {
      auto remote=root/"remote"/"gpu0"/key;
      std::ofstream(remote)<<std::string(1024,key[0]);
      FileMeta meta;meta.logical_path=std::string("/gpu0/")+key;meta.gpu_id=0;
      meta.tier="remote";meta.physical_path=remote;meta.backend_id="remote";
      meta.size_bytes=1024;meta.has_remote_copy=true;meta.state="COMMITTED";
      filesystem.metadata_.Upsert(meta);
      if(std::string(key)=="c")filesystem.sieve_.Hit(0,"/gpu0/a");
      assert(filesystem.PromoteToLocal(cfg.gpus[0],key,meta,"promote")==0);
      filesystem.CreateCrossGpuReplica(cfg.gpus[1],cfg.gpus[0],key,meta);
    }
    assert(filesystem.metadata_.Get("/gpu0/a")->tier=="local");
    assert(filesystem.metadata_.Get("/gpu0/b")->tier=="remote");
    assert(filesystem.metadata_.Get("/gpu0/c")->tier=="local");
    assert(!filesystem.metadata_.GetLocalReplica("/gpu0/a",1));
    assert(filesystem.metadata_.GetLocalReplica("/gpu0/b",1));
    assert(filesystem.metadata_.GetLocalReplica("/gpu0/c",1));
    assert(TokenFS::DirectoryBytes(root/"local0")==2048 && TokenFS::DirectoryBytes(root/"local1")==2048);
    for(const auto& key:{"a","b","c"})assert(fs::file_size(root/"remote"/"gpu0"/key)==1024);
  }
  static void signed_eviction_audit_score() {
    EvictionCandidate candidate;
    candidate.meta.size_bytes=4*1024*1024;
    candidate.meta.read_count=5;
    candidate.meta.recompute_cost=10;
    candidate.meta.remote_access_cost=10;
    candidate.meta.producer_gpu=0;candidate.meta.gpu_id=0;
    candidate.last_access_at=123;
    const auto decision_score=TokenFS::ValueAwareEvictionScore(candidate,0);
    assert(decision_score<0);
    assert(TokenFS::EvictionAuditScore("value_aware",candidate,0)==static_cast<double>(decision_score));
    assert(TokenFS::EvictionAuditScore("lru",candidate,0)==123.0);
    assert(TokenFS::EvictionAuditScore("lfu",candidate,0)==5.0);
  }
  static void lookup_during_eviction(const fs::path& root) {
    Config cfg; cfg.mount_point=root/"mnt";cfg.metadata_db=root/"lookup.db";
    cfg.gpus.push_back({0,"/gpu0",root/"local",4096,"remote"});
    cfg.backends.emplace("remote",BackendConfig{"remote","directory",root/"remote"});
    TokenFS filesystem(cfg);filesystem.Init();
    const auto local=root/"local"/"k";
    const auto remote=root/"remote"/"gpu0"/"k";
    std::ofstream(local)<<"payload";std::ofstream(remote)<<"payload";
    FileMeta meta;meta.logical_path="/gpu0/k";meta.gpu_id=0;meta.tier="local";
    meta.physical_path=local;meta.has_remote_copy=true;meta.state="COMMITTED";
    filesystem.metadata_.Upsert(meta);
    std::unique_lock<std::mutex> eviction(filesystem.layout_mu_);
    fs::remove(local);  // Deterministically hold the unlink -> metadata window open.
    std::promise<void> entered;
    auto lookup=std::async(std::launch::async,[&]{
      entered.set_value();struct stat attributes{};
      return filesystem.GetAttr("/gpu0/k",&attributes,nullptr);
    });
    entered.get_future().wait();
    assert(lookup.wait_for(std::chrono::milliseconds(100))==std::future_status::timeout);
    meta.tier="remote";meta.physical_path=remote;filesystem.metadata_.Upsert(meta);
    eviction.unlock();
    assert(lookup.wait_for(std::chrono::seconds(2))==std::future_status::ready);
    assert(lookup.get()==0);
  }
};
}

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
  std::cout<<"PASS: real TokenFS/MetadataStore 80 indexed precheck, 79 precheck, 78 telemetry tests, and legacy fence/release checks (unmounted macOS veneer)\n";
}
