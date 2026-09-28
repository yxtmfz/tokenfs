#define FUSE_USE_VERSION 35

#include <fuse3/fuse.h>
#include <sqlite3.h>
#include <yaml-cpp/yaml.h>
#include "measured_policy.h"
#include "sieve_policy.h"
#include "request_trace.h"
#include "read_fill.h"
#include "request_read_cost.h"

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
  bool adaptive_reuse_control = false;
  bool profile_control_path = false;
  std::string request_trace_path;
  bool foreground_read_fill = false;
  bool request_read_costs = false;
  uint64_t read_fill_buffer_bytes = 4*1024*1024;
  bool compact_measured_planning = false;
  bool lean_read_accounting = false;
  bool private_cache_domains = false;
  bool peer_cache_reads = false;
  bool shared_value_placement = false;
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
  std::shared_ptr<RequestReadCost> read_cost;
};

class MetadataStore {
 public:
  explicit MetadataStore(const fs::path& db_path) : db_path_(db_path) {}

  ~MetadataStore() {
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
    sqlite3_stmt* stmt = nullptr;
    Prepare(sql, &stmt);
    sqlite3_bind_text(stmt, 1, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    int rc = sqlite3_step(stmt);
    if (rc == SQLITE_DONE) {
      sqlite3_finalize(stmt);
      return std::nullopt;
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
    sqlite3_finalize(stmt);
    return meta;
  }

  void Upsert(const FileMeta& meta) {
    std::lock_guard<std::mutex> lock(mu_);
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
                              uint64_t max_local_replicas, bool legacy_affinity=true, int replica_gpu=-1) {
    std::lock_guard<std::mutex> lock(mu_);
    const auto now = UnixNow();
    const auto event_now = UnixNowMillis();
    Exec("BEGIN IMMEDIATE;");
    try {
    sqlite3_stmt* stmt = nullptr;
    Prepare("UPDATE files SET read_count=COALESCE(read_count,0)+1,"
            "last_access_at=? WHERE logical_path=?;",
            &stmt);
    sqlite3_bind_int64(stmt, 1, now);
    sqlite3_bind_text(stmt, 2, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    StepDone(stmt);

    Prepare("INSERT INTO gpu_access(logical_path,gpu_id,read_count,last_access_at,access_order) "
            "VALUES(?,?,1,?,?) "
            "ON CONFLICT(logical_path,gpu_id) DO UPDATE SET "
            "read_count=read_count+1,last_access_at=excluded.last_access_at,access_order=excluded.access_order;",
            &stmt);
    sqlite3_bind_text(stmt, 1, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int(stmt, 2, gpu_id);
    sqlite3_bind_int64(stmt, 3, now);
    sqlite3_bind_int64(stmt, 4, ++access_sequence_);
    StepDone(stmt);

    if(replica_gpu>=0) {
      Prepare("UPDATE local_replicas SET last_access_at=? WHERE logical_path=? AND gpu_id=?;",&stmt);
      sqlite3_bind_int64(stmt,1,now);
      sqlite3_bind_text(stmt,2,logical_path.c_str(),-1,SQLITE_TRANSIENT);
      sqlite3_bind_int(stmt,3,replica_gpu);StepDone(stmt);
    }
    if(legacy_affinity) {
    Prepare("INSERT INTO gpu_access_events(logical_path,gpu_id,access_at) "
            "VALUES(?,?,?);",
            &stmt);
    sqlite3_bind_text(stmt, 1, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int(stmt, 2, gpu_id);
    sqlite3_bind_int64(stmt, 3, event_now);
    StepDone(stmt);

    Prepare("DELETE FROM gpu_access_events WHERE logical_path=? AND access_at<?;",
            &stmt);
    sqlite3_bind_text(stmt, 1, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int64(
        stmt, 2,
        event_now - 1000 * static_cast<sqlite3_int64>(std::max<uint64_t>(long_window_sec, short_window_sec)));
    StepDone(stmt);

    }
    Prepare("UPDATE files SET share_count=("
            "SELECT COUNT(*) FROM gpu_access WHERE logical_path=?) "
            "WHERE logical_path=?;",
            &stmt);
    sqlite3_bind_text(stmt, 1, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 2, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    StepDone(stmt);

    if(legacy_affinity)UpdateAffinityLocked(logical_path, dominant_threshold_x100,
                         shared_threshold_x100, short_window_sec,
                         long_window_sec, trend_min_reads,
                         hot_read_threshold, warm_read_threshold,
                         max_local_replicas);

    Prepare("SELECT COALESCE(read_count,0) FROM files WHERE logical_path=?;", &stmt);
    sqlite3_bind_text(stmt, 1, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    int rc = sqlite3_step(stmt);
    if (rc != SQLITE_ROW) {
      std::string err = rc == SQLITE_DONE ? "missing file metadata" : sqlite3_errmsg(db_);
      sqlite3_finalize(stmt);
      throw std::runtime_error(err);
    }
    uint64_t count = static_cast<uint64_t>(sqlite3_column_int64(stmt, 0));
    sqlite3_finalize(stmt);
    Exec("COMMIT;");
    return count;
    } catch (...) { Exec("ROLLBACK;"); throw; }
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
                        const std::unordered_map<std::string, uint64_t>& maxima) {
    std::lock_guard<std::mutex> lock(mu_);
    Exec("BEGIN IMMEDIATE;");
    try {
      for (const auto& [name, value] : deltas) {
        sqlite3_stmt* stmt = nullptr;
        Prepare("INSERT INTO metrics(name,value) VALUES(?,?) ON CONFLICT(name) DO UPDATE SET value=value+excluded.value;", &stmt);
        sqlite3_bind_text(stmt, 1, name.c_str(), -1, SQLITE_TRANSIENT);
        sqlite3_bind_int64(stmt, 2, value); StepDone(stmt);
      }
      for (const auto& [name, value] : maxima) {
        sqlite3_stmt* stmt = nullptr;
        Prepare("INSERT INTO metrics(name,value) VALUES(?,?) ON CONFLICT(name) DO UPDATE SET value=MAX(value,excluded.value);", &stmt);
        sqlite3_bind_text(stmt, 1, name.c_str(), -1, SQLITE_TRANSIENT);
        sqlite3_bind_int64(stmt, 2, value); StepDone(stmt);
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
    sqlite3_stmt* stmt = nullptr;
    Prepare("SELECT logical_path,gpu_id,physical_path,size_bytes,"
            "cache_generation,created_at,last_access_at,state "
            "FROM local_replicas WHERE logical_path=? AND gpu_id=?;",
            &stmt);
    sqlite3_bind_text(stmt, 1, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int(stmt, 2, gpu_id);
    int rc = sqlite3_step(stmt);
    if (rc == SQLITE_DONE) {
      sqlite3_finalize(stmt);
      return std::nullopt;
    }
    if (rc != SQLITE_ROW) {
      std::string err = sqlite3_errmsg(db_);
      sqlite3_finalize(stmt);
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
    sqlite3_finalize(stmt);
    return replica;
  }

  std::vector<LocalReplica> LocalReplicas(const std::string& logical_path) {
    std::lock_guard<std::mutex> lock(mu_);
    sqlite3_stmt* stmt = nullptr;
    Prepare("SELECT logical_path,gpu_id,physical_path,size_bytes,"
            "cache_generation,created_at,last_access_at,state "
            "FROM local_replicas WHERE logical_path=? "
            "ORDER BY last_access_at ASC,created_at ASC;",
            &stmt);
    sqlite3_bind_text(stmt, 1, logical_path.c_str(), -1, SQLITE_TRANSIENT);
    std::vector<LocalReplica> out;
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
    sqlite3_finalize(stmt);
    return out;
  }

  void UpsertLocalReplica(const LocalReplica& replica) {
    std::lock_guard<std::mutex> lock(mu_);
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

  uint64_t access_sequence_ = 0;
  fs::path db_path_;
  sqlite3* db_ = nullptr;
  std::mutex mu_;
};

class TokenFS {
  friend struct TokenFSTestAccess;
 public:
  explicit TokenFS(Config config)
      : config_(std::move(config)), trace_(config_.request_trace_path), fills_(config_.read_fill_buffer_bytes), metadata_(config_.metadata_db) {}

  void Init() {
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
    if(config_.adaptive_reuse_control && (!config_.measured_burst_reuse || !config_.compact_measured_planning || !config_.measured_joint_admission))
      throw std::runtime_error("adaptive reuse requires compact burst-aware joint control");
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
    RecoverIncompleteFiles();
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
        try { task(); }
        catch (const std::exception& e) {
          std::cerr << "background task failed: " << e.what() << std::endl;
          metadata_.AddMetric("background_error_count", 1);
        }
        metadata_.AddMetric("background_completed", 1);
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
      metadata_.AddMetric("background_queue_rejected", 1);
      return false;
    }
    metadata_.AddMetric("background_submitted", 1);
    background_tasks_.push_back(std::move(task));
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
      metadata_.Upsert(meta);
    }
    const bool writable = IsWritable(fi->flags);
    const int caller_gpu_id = DetectCallerGpuId(gpu->gpu_id);
    bool borrowed_peer = false;
    int resident_gpu_id = gpu->gpu_id;
    // Update policy state on every logical read, including local fast hits.
    if (!writable) {
      auto record_read=[&](int replica_gpu) {
        return metadata_.IncrementReadCount(path, caller_gpu_id,
          config_.affinity_dominant_threshold_x100, config_.affinity_shared_threshold_x100,
          config_.affinity_short_window_sec,
          config_.trend_prediction ? config_.affinity_long_window_sec : config_.affinity_short_window_sec,
          config_.affinity_trend_min_reads, config_.affinity_hot_read_threshold,
          config_.affinity_warm_read_threshold, config_.max_local_replicas_per_file,!config_.lean_read_accounting,replica_gpu);
      };
      int touched_replica=-1;
      if(!config_.lean_read_accounting) {
        record_read(-1);meta=*metadata_.Get(path);
      }
      // Optional isolated access-domain topology: another domain's canonical
      // local copy is not addressable. Every compared policy uses this routing.
      if(config_.private_cache_domains && caller_gpu_id!=gpu->gpu_id) {
        if(meta.tier=="local")AddBufferedMetric("private_domain_owner_copy_bypassed",1);
        meta.tier="remote";meta.backend_id=gpu->remote_backend;
        meta.physical_path=RemotePath(*gpu,rel);
        AddBufferedMetric("private_domain_read_count",1);
      }
      if (caller_gpu_id != gpu->gpu_id) {
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
      if (config_.peer_cache_reads && meta.tier != "local") {
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
      bool affinity_reset=false;
      if((config_.measured_policy || config_.measured_track_affinity || (config_.private_cache_domains && config_.read_through_cache && config_.read_through_min_reads>1)) && measured_.Observe(caller_gpu_id,path,MeasuredOptions(),meta.tier=="local",&affinity_reset))
        AddBufferedMetric("measured_shift_resets",1);
      if(affinity_reset)AddBufferedMetric("measured_affinity_context_resets",1);
      AddBufferedMetric("read_open_count", 1);
      AddBufferedMetric(meta.tier == "local" ? "local_read_open_count" : "remote_read_open_count", 1);
    }
    int fd = open(meta.physical_path.c_str(), fi->flags | ((!writable && config_.backend_direct_io) ? O_DIRECT : 0));
    if (fd < 0) {
      return -errno;
    }
    if (writable) {
      meta.state = "CREATING";
      metadata_.Upsert(meta);
    }
    Handle handle;
    handle.fd = fd;
    handle.logical_path = path;
    handle.gpu_id = gpu->gpu_id;
    handle.caller_gpu_id = caller_gpu_id;
    handle.tier = meta.tier;
    handle.backend_id = meta.backend_id;
    handle.physical_path = meta.physical_path;
    handle.flags = fi->flags;
    handle.writable = writable;
    handle.state = meta.state;
    if(config_.request_read_costs && !writable)handle.read_cost=std::make_shared<RequestReadCost>(meta.size_bytes);
    if(config_.foreground_read_fill && !writable && meta.tier=="remote") {
      handle.read_fill=fills_.Acquire(path,fd,meta.size_bytes);
      AddBufferedMetric(handle.read_fill?"read_fill_capture_started":"read_fill_capture_unavailable",1);
      SetBufferedMetricMax("read_fill_buffer_peak_bytes",fills_.PeakBytes());
    }
    const bool deferred_fill=bool(handle.read_fill);
    fi->fh = StoreHandle(std::move(handle));
    fi->direct_io = config_.fuse_direct_io;
    if(diagnostic.Enabled()){diagnostic.e.handle=fi->fh;diagnostic.e.caller=caller_gpu_id;diagnostic.e.tier=meta.tier;}
    layout_lock.unlock();
    // Pin the selected source before future placement work; this miss remains a miss.
    if (!writable && (config_.shared_value_placement || config_.shared_pool_cache)) {
      if (meta.tier != "local" && !deferred_fill) ScheduleSharedPlacement(*metadata_.Get(path), caller_gpu_id);
    } else if (!writable && !borrowed_peer) {
      FileMeta canonical = *metadata_.Get(path);
      MaybeManageCrossGpuReplica(canonical, caller_gpu_id);
      if (canonical.tier == "remote" && ShouldPromoteOnRead(canonical, canonical.read_count, caller_gpu_id)) {
        if (config_.async_promote_on_read) SchedulePromoteToLocal(*gpu, rel, path, "promote", true);
        else PromoteToLocal(*gpu, rel, canonical, "promote");
      }
      if (caller_gpu_id == gpu->gpu_id) MaybeSchedulePrefetch(*gpu, rel);
    }
    AddBufferedMetric(meta.tier == "local" ? "open_local" : "open_remote", 1);
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
    if (config_.backend_direct_io) {
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
    AddBufferedMetric(handle->tier == "local" ? "read_local_ops"
                                               : "read_remote_ops",
                      1);
    AddBufferedMetric(handle->tier == "local" ? "read_local_bytes"
                                               : "read_remote_bytes",
                      static_cast<uint64_t>(n));
    const uint64_t latency_us = ElapsedMicros(start);
    RecordLatency("read", handle->tier, latency_us);
    if (n > 0) {
      if(!config_.request_read_costs && (config_.measured_policy || config_.measured_track_affinity)) measured_.ReadSample(handle->tier=="local",static_cast<uint64_t>(n),latency_us);
      MaybeAdaptivePromote(*handle, latency_us);
    }
    if(handle->read_cost)AccountRequestReadCost(*handle,n>0?handle->read_cost->Add(offset,n,latency_us):handle->read_cost->Finish());
    if(handle->read_fill) {
      const auto capture_start=ReadFillPool::NowNs();
      const bool complete=handle->read_fill->Append(offset,buf,static_cast<size_t>(n),handle->fd);
      AddBufferedMetric("read_fill_capture_us",(ReadFillPool::NowNs()-capture_start+999)/1000);
      if(complete) {
        AddBufferedMetric("read_fill_capture_complete",1);
        AddBufferedMetric("read_fill_capture_bytes",handle->read_fill->Data().size());
        if(auto meta=metadata_.Get(handle->logical_path))
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
      FlushBufferedMetrics();
      return 0;
    }
    bool should_dedup = false;
    if(diagnostic.Enabled()){diagnostic.e.wait_ns=RequestTrace::Now()-diagnostic.e.start_ns;diagnostic.e.handle=fi->fh;diagnostic.e.path=it->second.logical_path;diagnostic.e.caller=it->second.caller_gpu_id;diagnostic.e.tier=it->second.tier;}
    if (it->second.fd >= 0) {
      if (it->second.writable) {
        int rc = CommitHandle(it->second);
        if (rc != 0) {
          close(it->second.fd);
          handles_.erase(it);
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
    handles_.erase(it);
    if(fallback) {
      lock.unlock();
      AddBufferedMetric("read_fill_partial_fallback",1);
      if(auto meta=metadata_.Get(fallback_path))ScheduleSharedPlacement(*meta,fallback_caller);
    }
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
      metadata_.AddMetric("affinity_caller_env_unreadable", 1);
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
          metadata_.AddMetric("affinity_cross_gpu_caller_count", 1);
        }
        return *parsed;
      }
      metadata_.AddMetric("affinity_caller_env_invalid", 1);
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
            config_.measured_track_affinity,config_.measured_affinity_gate,config_.measured_joint_admission,static_cast<size_t>(config_.measured_affinity_window),config_.measured_affinity_recent_demand,config_.measured_affinity_handover_epoch,config_.shared_value_placement,config_.measured_causal_window,config_.measured_burst_reuse,config_.adaptive_reuse_control};
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
    if(config_.measured_causal_window) {
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
    if(plan.uncertainty_us>0)AddBufferedMetric("measured_uncertainty_plans",1);
    if(plan.burst_remaining>0)AddBufferedMetric("measured_burst_forecast_plans",1);
    if(plan.survival_adjusted_items) {
      AddBufferedMetric("measured_survival_discounted_plans",1);
      AddBufferedMetric("measured_survival_discounted_items",plan.survival_adjusted_items);
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
                           const fs::path* existing_file = nullptr) {
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
      std::ostringstream detail;
      detail << plan.reason << ";incoming=" << plan.incoming_us
             << ";displaced=" << plan.displaced_us << ";copy=" << plan.copy_us
             << ";frequency=" << plan.incoming_count << ";calibrated=" << plan.costs_calibrated
             << ";affinity_count=" << plan.affinity_incoming_count
             << ";affinity_adjusted_items=" << plan.affinity_adjusted_items
             << ";burst_remaining=" << plan.burst_remaining << ";uncertainty=" << plan.uncertainty_us
             << ";explore=" << plan.explore_headroom;
      metadata_.RecordPolicyEvent("ADMIT",protected_logical_path,gpu.gpu_id,required_size,
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
            metadata_.AddMetric("evict_count", 1);
            metadata_.AddMetric("cross_gpu_replica_delete_count", 1);
          }
        } else rc = EvictLocalFile(gpu, candidate.meta);
        if (rc) { metadata_.AddMetric("evict_error_count", 1); return false; }
        sieve_.Removed(gpu.gpu_id, key);
        metadata_.AddMetric("evict_policy_sieve", 1);
        metadata_.RecordPolicyEvent("EVICT", key, gpu.gpu_id, bytes, "sieve", 0);
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
      metadata_.AddMetric("evict_policy_measured",1);
    } else if(config_.measured_policy) {
      std::vector<tokenfs_policy::Item> items;
      for(const auto& c:candidates)items.push_back({c.meta.logical_path,c.meta.size_bytes,c.last_access_at,MarginalCoverage(c.meta,gpu.gpu_id)});
      const auto ranked=measured_.Ranked(gpu.gpu_id,std::move(items),MeasuredOptions());
      std::unordered_map<std::string,size_t> order;
      for(size_t i=0;i<ranked.size();++i)order[ranked[i].key]=i;
      std::sort(candidates.begin(),candidates.end(),[&](const auto& a,const auto& b){return order.at(a.meta.logical_path)<order.at(b.meta.logical_path);});
      metadata_.AddMetric("evict_policy_measured",1);
    } else if (policy == "lru") {
      metadata_.AddMetric("evict_policy_lru", 1);
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
      metadata_.AddMetric("evict_policy_lfu", 1);
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
      metadata_.AddMetric("evict_policy_value_aware", 1);
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
        metadata_.AddMetric("evict_skip_open", 1);
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
          metadata_.AddMetric("evict_count", 1);
          metadata_.AddMetric("cross_gpu_replica_delete_count", 1);
        }
      } else rc = EvictLocalFile(gpu, candidate.meta);
      if (rc != 0) {
        metadata_.AddMetric("evict_error_count", 1);
        continue;
      }
      metadata_.RecordPolicyEvent("EVICT", candidate.meta.logical_path, gpu.gpu_id, candidate_size,
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
        std::stable_sort(locations.begin(),locations.end(),[caller](const auto& a,const auto& b){return (a.gpu_id==caller)>(b.gpu_id==caller);});
        std::optional<PlanningSnapshot> snapshot;
        if(config_.compact_measured_planning)snapshot=SnapshotMeasuredResidents(path);
        std::unordered_map<int,uint64_t> usage;
        if(config_.adaptive_reuse_control) {
          for(const auto& gpu:locations)usage[gpu.gpu_id]=DirectoryBytes(gpu.local_root);
          // This is an advisory snapshot only. Final admission rechecks live
          // quota, pins and values under the layout lock before any eviction.
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
          <<";victim_loss="<<chosen.displaced_us<<";copy="<<chosen.copy_us<<";burst_remaining="<<chosen.burst_remaining<<";uncertainty="<<chosen.uncertainty_us<<";explore="<<chosen.explore_headroom;
        metadata_.RecordPolicyEvent("SHARED_PLACE",path,destination->gpu_id,incoming.size_bytes,detail.str(),best);
        AddBufferedMetric("shared_placement_selected",1);
        if(chosen.explore_headroom)AddBufferedMetric("shared_free_exploration_selected",1);
        if(chosen.burst_remaining>0 && chosen.affinity_incoming_count<2)AddBufferedMetric("shared_burst_first_read_selected",1);
        if(destination->gpu_id!=caller)AddBufferedMetric("shared_placement_relocated",1);
      }
    }
    if(config_.profile_control_path)RecordLatency("shared_plan","background",ElapsedMicros(plan_start));
    // Existing copy/commit path rechecks quota and benefit using current evidence.
    if(destination->gpu_id==owner->gpu_id)PromoteToLocal(*destination,rel,incoming,"promote",true,fill);
    else CreateCrossGpuReplica(*destination,*owner,rel,incoming,fill);
  }

  void ScheduleSharedPlacement(const FileMeta& meta, int caller,std::shared_ptr<ReadFillPool::Buffer> fill={}) {
    if(meta.state!="COMMITTED" || !meta.has_remote_copy)return;
    if(config_.shared_value_placement && !measured_.HasReuseEvidence(caller,meta.logical_path,MeasuredOptions()))return;
    if(config_.shared_pool_cache && meta.read_count<config_.read_through_min_reads)return;
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

  void AccountRequestReadCost(const Handle& handle,const std::optional<RequestReadCost::Sample>& sample) {
    if(!sample)return;
    const auto tier=handle.tier=="local"?"local":"remote";
    AddBufferedMetric(std::string("request_cost_")+tier+"_samples",1);
    AddBufferedMetric(std::string("request_cost_")+tier+"_bytes",sample->bytes);
    AddBufferedMetric(std::string("request_cost_")+tier+"_us",sample->micros);
    if(config_.measured_policy || config_.measured_track_affinity)
      measured_.ReadSample(handle.tier=="local",sample->bytes,sample->micros);
  }

  void CreateCrossGpuReplica(const GpuConfig& caller_gpu,
                             const GpuConfig& owner_gpu, const fs::path& rel,
                             FileMeta meta,std::shared_ptr<ReadFillPool::Buffer> fill={}) {
    fs::path source = RemotePath(owner_gpu, rel);
    if (!fs::exists(source)) {
      source = meta.physical_path;
    }
    if (!fs::exists(source)) {
      metadata_.AddMetric("cross_gpu_replica_skip_missing_source", 1);
      return;
    }
    std::lock_guard<std::mutex> copy_lock(copy_mu_);
    const auto copy_start=Clock::now();
    const uint64_t size = FileSizeNoThrow(source);
    fs::path local = CrossGpuReplicaPath(caller_gpu, owner_gpu, rel);
    if (!config_.speculative_copy_may_evict &&
        !HasLocalCapacity(caller_gpu, size,
                          fs::exists(local) ? &local : nullptr)) {
      metadata_.AddMetric("cross_gpu_replica_skip_no_headroom", 1);
      return;
    }
    if (!EnsureLocalCapacity(caller_gpu, size, meta.logical_path,
                             fs::exists(local) ? &local : nullptr)) {
      metadata_.AddMetric("cross_gpu_replica_skip_no_space", 1);
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
      metadata_.AddMetric("cross_gpu_replica_error_count", 1);
      return;
    }
    if (config_.durable_local_cache) {
      int fd = open(tmp.c_str(), O_RDONLY);
      if (fd >= 0) {
        fsync(fd);
        close(fd);
      }
    } else {
      metadata_.AddMetric("local_cache_fsync_skipped", 1);
      metadata_.AddMetric("local_cache_fsync_skipped_bytes", size);
    }
    if (config_.checksum != "none") {
      const auto verify_start=diagnostic.Enabled()?RequestTrace::Now():0;
      auto source_hash = reused?std::optional<std::string>(fill->Checksum()):ChecksumFile(source);
      auto copy_hash = ChecksumFile(tmp);
      if(diagnostic.Enabled())diagnostic.e.verify_ns=RequestTrace::Now()-verify_start;
      if (!source_hash || !copy_hash || *source_hash != *copy_hash ||
          (reused && !fill->Matches(source.string(),size))) {
        fs::remove(tmp, ec);
        metadata_.AddMetric("copy_checksum_error_count", 1);
        return;
      }
    }
    fs::rename(tmp, local, ec);
    if (ec) {
      fs::remove(tmp, ec);
      metadata_.AddMetric("cross_gpu_replica_error_count", 1);
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
    metadata_.UpsertLocalReplica(replica);
    metadata_.RecordReplicaPromotion(meta.logical_path);
    metadata_.RecordPolicyEvent("REPLICATE_READY", meta.logical_path, caller_gpu.gpu_id, size, "cross_gpu");
    if(reused)RecordReadFillCommit(size,fill);
    if(config_.measured_policy) measured_.CopySample(size,ElapsedMicros(copy_start)+(reused?fill->CaptureUs():0));
    metadata_.AddMetric("cross_gpu_replica_create_count", 1);
    metadata_.AddMetric("cross_gpu_replica_create_bytes", size);
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
    std::lock_guard<std::mutex> copy_lock(copy_mu_);
    const auto copy_start=Clock::now();
    if (auto current = metadata_.Get(meta.logical_path); current && current->tier == "local") return 0;
    const uint64_t size = FileSizeNoThrow(meta.physical_path);
    fs::path local = gpu.local_root / rel;
    const fs::path source = meta.physical_path;
    if (!allow_eviction &&
        !HasLocalCapacity(gpu, size, fs::exists(local) ? &local : nullptr)) {
      metadata_.AddMetric(metric_prefix + "_skip_no_headroom", 1);
      return 0;
    }
    if (!EnsureLocalCapacity(gpu, size, meta.logical_path,
                             fs::exists(local) ? &local : nullptr)) {
      metadata_.AddMetric(metric_prefix + "_skip_no_space", 1);
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

    metadata_.AddMetric("migration_to_local_begin", 1);
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
      metadata_.AddMetric("local_cache_fsync_skipped", 1);
      metadata_.AddMetric("local_cache_fsync_skipped_bytes", size);
    }

    if (config_.checksum != "none") {
      const auto verify_start=diagnostic.Enabled()?RequestTrace::Now():0;
      auto source_hash = reused?std::optional<std::string>(fill->Checksum()):ChecksumFile(source);
      auto copy_hash = ChecksumFile(tmp);
      if(diagnostic.Enabled())diagnostic.e.verify_ns=RequestTrace::Now()-verify_start;
      if (!source_hash || !copy_hash || *source_hash != *copy_hash ||
          (reused && !fill->Matches(source.string(),size))) {
        fs::remove(tmp, ec);
        metadata_.AddMetric("copy_checksum_error_count", 1);
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
    metadata_.RecordPolicyEvent("PROMOTE_READY", meta.logical_path, gpu.gpu_id, size, metric_prefix);
    if(reused)RecordReadFillCommit(size,fill);
    if(config_.measured_policy) {
      const auto elapsed=ElapsedMicros(copy_start)+(reused?fill->CaptureUs():0);
      measured_.CopySample(size,elapsed);
      AddBufferedMetric("measured_verified_copy_us",elapsed);
      SetBufferedMetricMax("measured_history_entries_max",measured_.Entries());
    }
    metadata_.AddMetric("migration_to_local_commit", 1);
    metadata_.AddMetric("local_cache_create_count", 1);
    metadata_.AddMetric(metric_prefix + "_count", 1);
    metadata_.AddMetric(metric_prefix + "_bytes", size);
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
      metadata_.AddMetric("local_cache_delete_count", 1);
      metadata_.AddMetric("local_cache_delete_bytes", size);
      metadata_.AddMetric("evict_count", 1);
      metadata_.AddMetric("evict_bytes", size);
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
    metadata_.AddMetric("migration_to_remote_begin", 1);

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
    metadata_.AddMetric("migration_to_remote_commit", 1);
    metadata_.AddMetric("evict_count", 1);
    metadata_.AddMetric("evict_bytes", size);
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
    handles_.emplace(id, std::move(handle));
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

  void FlushBufferedMetrics() {
    std::unordered_map<std::string, uint64_t> pending;
    std::unordered_map<std::string, uint64_t> pending_max;
    {
      std::lock_guard<std::mutex> lock(buffered_metrics_mu_);
      if (buffered_metrics_.empty() && buffered_metric_max_.empty()) {
        return;
      }
      pending.swap(buffered_metrics_);
      pending_max.swap(buffered_metric_max_);
    }
    metadata_.ApplyMetricBatch(pending, pending_max);
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
    metadata_.AddMetric("qos_background_ops", 1);
    metadata_.AddMetric("qos_background_bytes", bytes);
    metadata_.AddMetric("qos_background_" + activity + "_ops", 1);
    metadata_.AddMetric("qos_background_" + activity + "_bytes", bytes);

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
    metadata_.AddMetric("qos_delay_us_total", static_cast<uint64_t>(delay_us));
    metadata_.AddMetric("qos_delay_ops", 1);
    metadata_.AddMetric("qos_background_delay_ops", 1);
    metadata_.AddMetric("qos_background_delay_us_total",
                        static_cast<uint64_t>(delay_us));
    metadata_.AddMetric("qos_gpu" + std::to_string(gpu_id) +
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
  std::mutex prefetch_mu_;
  std::set<std::string> prefetch_inflight_;
  std::mutex promote_mu_;
  std::set<std::string> promote_inflight_;
  std::mutex cross_gpu_replica_mu_;
  std::set<std::string> cross_gpu_replica_inflight_;
  std::mutex shared_placement_mu_;
  std::set<std::string> shared_placement_inflight_;
  std::mutex buffered_metrics_mu_;
  std::unordered_map<std::string, uint64_t> buffered_metrics_;
  std::unordered_map<std::string, uint64_t> buffered_metric_max_;
  std::mutex qos_mu_;
  std::unordered_map<std::string, Clock::time_point> qos_next_;
};

TokenFS* g_fs = nullptr;

int OpGetAttr(const char* path, struct stat* stbuf, fuse_file_info* fi) {
  return g_fs->GetAttr(path, stbuf, fi);
}

int OpReadDir(const char* path, void* buf, fuse_fill_dir_t filler, off_t offset,
              fuse_file_info* fi, enum fuse_readdir_flags flags) {
  return g_fs->ReadDir(path, buf, filler, offset, fi, flags);
}

int OpMkDir(const char* path, mode_t mode) { return g_fs->MkDir(path, mode); }
int OpRmDir(const char* path) { return g_fs->RmDir(path); }
int OpCreate(const char* path, mode_t mode, fuse_file_info* fi) {
  return g_fs->Create(path, mode, fi);
}
int OpOpen(const char* path, fuse_file_info* fi) { return g_fs->Open(path, fi); }
int OpRead(const char* path, char* buf, size_t size, off_t offset,
           fuse_file_info* fi) {
  return g_fs->Read(path, buf, size, offset, fi);
}
int OpWrite(const char* path, const char* buf, size_t size, off_t offset,
            fuse_file_info* fi) {
  return g_fs->Write(path, buf, size, offset, fi);
}
int OpRelease(const char* path, fuse_file_info* fi) {
  return g_fs->Release(path, fi);
}
int OpFsync(const char* path, int datasync, fuse_file_info* fi) {
  return g_fs->Fsync(path, datasync, fi);
}
int OpFallocate(const char* path, int mode, off_t offset, off_t length,
                fuse_file_info* fi) {
  return g_fs->Fallocate(path, mode, offset, length, fi);
}
int OpTruncate(const char* path, off_t size, fuse_file_info* fi) {
  return g_fs->Truncate(path, size, fi);
}
int OpUnlink(const char* path) { return g_fs->Unlink(path); }
int OpRename(const char* from, const char* to, unsigned int flags) {
  return g_fs->Rename(from, to, flags);
}

uint64_t GiBToBytes(uint64_t gib) { return gib * 1024ULL * 1024ULL * 1024ULL; }
uint64_t MiBToBytes(uint64_t mib) { return mib * 1024ULL * 1024ULL; }

Config LoadConfig(const fs::path& path) {
  YAML::Node root = YAML::LoadFile(path.string());
  Config config;
  if(root["policy"] && root["policy"]["shared_value_placement"]) config.shared_value_placement=root["policy"]["shared_value_placement"].as<bool>();
  if(root["policy"] && root["policy"]["shared_pool_cache"]) config.shared_pool_cache=root["policy"]["shared_pool_cache"].as<bool>();
  if(root["policy"] && root["policy"]["peer_cache_reads"]) config.peer_cache_reads=root["policy"]["peer_cache_reads"].as<bool>();
  if(root["policy"] && root["policy"]["private_cache_domains"]) config.private_cache_domains=root["policy"]["private_cache_domains"].as<bool>();
  if(root["policy"] && root["policy"]["measured_track_affinity"]) config.measured_track_affinity=root["policy"]["measured_track_affinity"].as<bool>();
  if(root["policy"] && root["policy"]["measured_affinity_gate"]) config.measured_affinity_gate=root["policy"]["measured_affinity_gate"].as<bool>();
  if(root["policy"] && root["policy"]["measured_affinity_recent_demand"]) config.measured_affinity_recent_demand=root["policy"]["measured_affinity_recent_demand"].as<bool>();
  if(root["policy"] && root["policy"]["measured_affinity_handover_epoch"]) config.measured_affinity_handover_epoch=root["policy"]["measured_affinity_handover_epoch"].as<bool>();
  if(config.measured_affinity_recent_demand && config.measured_affinity_gate && !config.measured_track_affinity)
    throw std::runtime_error("recent affinity demand requires affinity tracking");
  if(root["policy"] && root["policy"]["measured_joint_admission"]) config.measured_joint_admission=root["policy"]["measured_joint_admission"].as<bool>();
  if(root["policy"] && root["policy"]["measured_affinity_window"]) config.measured_affinity_window=root["policy"]["measured_affinity_window"].as<uint64_t>();
  if(root["policy"] && root["policy"]["lean_read_accounting"]) config.lean_read_accounting=root["policy"]["lean_read_accounting"].as<bool>();
  if(root["policy"] && root["policy"]["adaptive_reuse_control"]) config.adaptive_reuse_control=root["policy"]["adaptive_reuse_control"].as<bool>();
  if(root["policy"] && root["policy"]["profile_control_path"]) config.profile_control_path=root["policy"]["profile_control_path"].as<bool>();
  if(root["policy"] && root["policy"]["request_trace_path"]) config.request_trace_path=root["policy"]["request_trace_path"].as<std::string>();
  if(root["policy"] && root["policy"]["foreground_read_fill"]) config.foreground_read_fill=root["policy"]["foreground_read_fill"].as<bool>();
  if(root["policy"] && root["policy"]["request_read_costs"]) config.request_read_costs=root["policy"]["request_read_costs"].as<bool>();
  if(root["policy"] && root["policy"]["read_fill_buffer_bytes"]) config.read_fill_buffer_bytes=root["policy"]["read_fill_buffer_bytes"].as<uint64_t>();
  if(root["policy"] && root["policy"]["measured_burst_reuse"]) config.measured_burst_reuse=root["policy"]["measured_burst_reuse"].as<bool>();
  if(root["policy"] && root["policy"]["compact_measured_planning"]) config.compact_measured_planning=root["policy"]["compact_measured_planning"].as<bool>();
  if(root["policy"] && root["policy"]["measured_causal_window"]) config.measured_causal_window=root["policy"]["measured_causal_window"].as<bool>();
  if(root["policy"] && root["policy"]["measured_shift_reset"]) config.measured_shift_reset=root["policy"]["measured_shift_reset"].as<bool>();
  if(root["policy"] && root["policy"]["measured_shift_window"]) config.measured_shift_window=root["policy"]["measured_shift_window"].as<uint64_t>();
  if(root["policy"] && root["policy"]["measured_frequency_admission"]) config.measured_frequency_admission=root["policy"]["measured_frequency_admission"].as<bool>();
  if(root["policy"] && root["policy"]["measured_policy"]) config.measured_policy=root["policy"]["measured_policy"].as<bool>();
  if(root["policy"] && root["policy"]["measured_aging"]) config.measured_aging=root["policy"]["measured_aging"].as<bool>();
  if(root["policy"] && root["policy"]["measured_admission"]) config.measured_admission=root["policy"]["measured_admission"].as<bool>();
  if(root["policy"] && root["policy"]["measured_cost"]) config.measured_cost=root["policy"]["measured_cost"].as<bool>();
  if(root["policy"] && root["policy"]["measured_value_victim"]) config.measured_value_victim=root["policy"]["measured_value_victim"].as<bool>();
  if(root["policy"] && root["policy"]["measured_size_aware"]) config.measured_size_aware=root["policy"]["measured_size_aware"].as<bool>();
  if(root["policy"] && root["policy"]["measured_window"]) config.measured_window=root["policy"]["measured_window"].as<uint64_t>();
  if (root["policy"] && root["policy"]["affinity_placement"]) config.affinity_placement = root["policy"]["affinity_placement"].as<bool>();
  if (root["policy"] && root["policy"]["gain_admission"]) config.gain_admission = root["policy"]["gain_admission"].as<bool>();
  if (root["policy"] && root["policy"]["trend_prediction"]) config.trend_prediction = root["policy"]["trend_prediction"].as<bool>();
  if (root["policy"] && root["policy"]["fuse_direct_io"]) config.fuse_direct_io = root["policy"]["fuse_direct_io"].as<bool>();
  if (root["policy"] && root["policy"]["readonly_canonical"]) config.readonly_canonical = root["policy"]["readonly_canonical"].as<bool>();
  if (root["policy"] && root["policy"]["backend_direct_io"]) config.backend_direct_io = root["policy"]["backend_direct_io"].as<bool>();
  config.mount_point =
      root["filesystem"]["mount_point"].as<std::string>("/mnt/tokenfs");
  config.metadata_db = root["filesystem"]["metadata_db"].as<std::string>(
      "/var/lib/tokenfs/metadata/tokenfs.db");
  config.temp_suffix =
      root["filesystem"]["temp_suffix"].as<std::string>(".tokenfs_tmp");
  if (root["policy"] && root["policy"]["checksum"]) {
    config.checksum = root["policy"]["checksum"].as<std::string>("none");
  }
  if (root["policy"] && root["policy"]["local_eviction_policy"]) {
    config.local_eviction_policy =
        root["policy"]["local_eviction_policy"].as<std::string>("value_aware");
  }
  if (root["policy"] && root["policy"]["placement_policy"]) {
    config.placement_policy =
        root["policy"]["placement_policy"].as<std::string>("value_aware");
  }
  if (root["policy"] && root["policy"]["default_recompute_cost"]) {
    config.default_recompute_cost =
        root["policy"]["default_recompute_cost"].as<uint64_t>(10);
  }
  if (root["policy"] && root["policy"]["default_remote_access_cost"]) {
    config.default_remote_access_cost =
        root["policy"]["default_remote_access_cost"].as<uint64_t>(10);
  }
  if (root["policy"] && root["policy"]["value_promote_threshold"]) {
    config.value_promote_threshold =
        root["policy"]["value_promote_threshold"].as<uint64_t>(100);
  }
  if (root["policy"] && root["policy"]["adaptive_migration"]) {
    config.adaptive_migration =
        root["policy"]["adaptive_migration"].as<bool>(false);
  }
  if (root["policy"] && root["policy"]["adaptive_remote_promote_us"]) {
    config.adaptive_remote_promote_us =
        root["policy"]["adaptive_remote_promote_us"].as<uint64_t>(10000);
  }
  if (root["policy"] && root["policy"]["qos_read_iops_per_gpu"]) {
    config.qos_read_iops_per_gpu =
        root["policy"]["qos_read_iops_per_gpu"].as<uint64_t>(0);
  }
  if (root["policy"] && root["policy"]["qos_write_iops_per_gpu"]) {
    config.qos_write_iops_per_gpu =
        root["policy"]["qos_write_iops_per_gpu"].as<uint64_t>(0);
  }
  if (root["policy"] && root["policy"]["qos_background_iops_per_gpu"]) {
    config.qos_background_iops_per_gpu =
        root["policy"]["qos_background_iops_per_gpu"].as<uint64_t>(0);
  }
  if (root["policy"] && root["policy"]["qos_background_mib_per_sec_per_gpu"]) {
    config.qos_background_mib_per_sec_per_gpu =
        root["policy"]["qos_background_mib_per_sec_per_gpu"].as<uint64_t>(0);
  }
  if (root["policy"] && root["policy"]["affinity_dominant_threshold_x100"]) {
    config.affinity_dominant_threshold_x100 =
        root["policy"]["affinity_dominant_threshold_x100"].as<uint64_t>(70);
  }
  if (root["policy"] && root["policy"]["affinity_shared_threshold_x100"]) {
    config.affinity_shared_threshold_x100 =
        root["policy"]["affinity_shared_threshold_x100"].as<uint64_t>(55);
  }
  if (root["policy"] && root["policy"]["affinity_short_window_sec"]) {
    config.affinity_short_window_sec =
        root["policy"]["affinity_short_window_sec"].as<uint64_t>(300);
  }
  if (root["policy"] && root["policy"]["affinity_long_window_sec"]) {
    config.affinity_long_window_sec =
        root["policy"]["affinity_long_window_sec"].as<uint64_t>(3600);
  }
  if (root["policy"] && root["policy"]["affinity_trend_min_reads"]) {
    config.affinity_trend_min_reads =
        root["policy"]["affinity_trend_min_reads"].as<uint64_t>(3);
  }
  if (root["policy"] && root["policy"]["affinity_hot_read_threshold"]) {
    config.affinity_hot_read_threshold =
        root["policy"]["affinity_hot_read_threshold"].as<uint64_t>(4);
  }
  if (root["policy"] && root["policy"]["affinity_warm_read_threshold"]) {
    config.affinity_warm_read_threshold =
        root["policy"]["affinity_warm_read_threshold"].as<uint64_t>(2);
  }
  if (root["policy"] && root["policy"]["max_local_replicas_per_file"]) {
    config.max_local_replicas_per_file =
        root["policy"]["max_local_replicas_per_file"].as<uint64_t>(2);
  }
  if (root["policy"] && root["policy"]["affinity_replica_cooldown_sec"]) {
    config.affinity_replica_cooldown_sec =
        root["policy"]["affinity_replica_cooldown_sec"].as<uint64_t>(30);
  }
  if (root["policy"] && root["policy"]["affinity_replica_min_residency_sec"]) {
    config.affinity_replica_min_residency_sec =
        root["policy"]["affinity_replica_min_residency_sec"].as<uint64_t>(120);
  }
  if (root["policy"] && root["policy"]["cross_gpu_local_cache"]) {
    config.cross_gpu_local_cache =
        root["policy"]["cross_gpu_local_cache"].as<bool>(false);
  }
  if (root["policy"] && root["policy"]["physical_dedup"]) {
    config.physical_dedup = root["policy"]["physical_dedup"].as<bool>(false);
  }
  if (root["policy"] && root["policy"]["promote_on_read"]) {
    config.promote_on_read = root["policy"]["promote_on_read"].as<bool>(false);
  }
  if (root["policy"] && root["policy"]["async_promote_on_read"]) {
    config.async_promote_on_read =
        root["policy"]["async_promote_on_read"].as<bool>(false);
  }
  if (root["policy"] && root["policy"]["read_through_cache"]) {
    config.read_through_cache =
        root["policy"]["read_through_cache"].as<bool>(false);
  }
  if (root["policy"] && root["policy"]["read_through_min_reads"]) {
    config.read_through_min_reads =
        root["policy"]["read_through_min_reads"].as<uint64_t>(2);
  }
  if (root["policy"] && root["policy"]["promote_read_threshold"]) {
    config.promote_read_threshold =
        root["policy"]["promote_read_threshold"].as<uint64_t>(2);
  }
  if (root["policy"] && root["policy"]["migration_min_reuse_reads"]) {
    config.migration_min_reuse_reads =
        root["policy"]["migration_min_reuse_reads"].as<uint64_t>(6);
  }
  if (root["policy"] && root["policy"]["migration_min_benefit_x100"]) {
    config.migration_min_benefit_x100 =
        root["policy"]["migration_min_benefit_x100"].as<uint64_t>(150);
  }
  if (root["policy"] && root["policy"]["migration_copy_cost_per_mib"]) {
    config.migration_copy_cost_per_mib =
        root["policy"]["migration_copy_cost_per_mib"].as<uint64_t>(8);
  }
  if (root["policy"] && root["policy"]["durable_local_cache"]) {
    config.durable_local_cache =
        root["policy"]["durable_local_cache"].as<bool>(false);
  }
  if (root["policy"] && root["policy"]["fast_local_cache_hit"]) {
    config.fast_local_cache_hit =
        root["policy"]["fast_local_cache_hit"].as<bool>(true);
  }
  if (root["policy"] && root["policy"]["speculative_copy_may_evict"]) {
    config.speculative_copy_may_evict =
        root["policy"]["speculative_copy_may_evict"].as<bool>(false);
  }
  if (root["policy"] && root["policy"]["prefetch_on_read"]) {
    config.prefetch_on_read = root["policy"]["prefetch_on_read"].as<bool>(false);
  }
  if (root["policy"] && root["policy"]["async_cross_gpu_replica"]) {
    config.async_cross_gpu_replica =
        root["policy"]["async_cross_gpu_replica"].as<bool>(false);
  }

  for (const auto& item : root["backends"]) {
    BackendConfig backend;
    backend.id = item["id"].as<std::string>();
    backend.type = item["type"].as<std::string>("directory");
    backend.root = item["root"].as<std::string>();
    config.backends.emplace(backend.id, backend);
  }

  for (const auto& item : root["gpus"]) {
    GpuConfig gpu;
    gpu.gpu_id = item["gpu_id"].as<int>();
    gpu.logical_root = item["logical_root"].as<std::string>();
    gpu.local_root = item["local_root"].as<std::string>();
    if (item["local_quota_mib"]) {
      gpu.local_quota_bytes = MiBToBytes(item["local_quota_mib"].as<uint64_t>());
    } else {
      gpu.local_quota_bytes = GiBToBytes(item["local_quota_gib"].as<uint64_t>());
    }
    gpu.remote_backend = item["remote_backend"].as<std::string>();
    config.gpus.push_back(std::move(gpu));
  }
  return config;
}

std::vector<char*> BuildFuseArgv(const std::vector<std::string>& args,
                                 std::vector<std::string>& storage) {
  std::vector<char*> argv;
  storage = args;
  argv.reserve(storage.size());
  for (auto& arg : storage) {
    argv.push_back(arg.data());
  }
  return argv;
}

}  // namespace

int main(int argc, char* argv[]) {
  fs::path config_path = "config/tokenfs.dev.yaml";
  std::vector<std::string> fuse_args;
  fuse_args.emplace_back(argv[0]);

  for (int i = 1; i < argc; ++i) {
    std::string arg = argv[i];
    if (arg == "--config" && i + 1 < argc) {
      config_path = argv[++i];
    } else {
      fuse_args.push_back(arg);
    }
  }

  try {
    Config config = LoadConfig(config_path);
    if (fuse_args.size() == 1) {
      fuse_args.push_back(config.mount_point.string());
    }
    auto fs = std::make_unique<TokenFS>(std::move(config));
    fs->Init();
    g_fs = fs.get();

    fuse_operations ops{};
    ops.getattr = OpGetAttr;
    ops.readdir = OpReadDir;
    ops.mkdir = OpMkDir;
    ops.rmdir = OpRmDir;
    ops.create = OpCreate;
    ops.open = OpOpen;
    ops.read = OpRead;
    ops.write = OpWrite;
    ops.release = OpRelease;
    ops.fsync = OpFsync;
    ops.fallocate = OpFallocate;
    ops.truncate = OpTruncate;
    ops.unlink = OpUnlink;
    ops.rename = OpRename;

    std::vector<std::string> argv_storage;
    auto fuse_argv = BuildFuseArgv(fuse_args, argv_storage);
    return fuse_main(static_cast<int>(fuse_argv.size()), fuse_argv.data(), &ops,
                     nullptr);
  } catch (const std::exception& ex) {
    std::cerr << "tokenfs: " << ex.what() << "\n";
    return 1;
  }
}
